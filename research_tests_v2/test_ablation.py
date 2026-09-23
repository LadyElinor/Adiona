"""Structural and negative controls for the optional v2 experiment."""
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import torch

from adiona import Kernel, Rejected
from adiona.identity import demo_identities
from adiona.geometric.adapter import propose_advice
from adiona.geometric.contracts import Fact, RELATIONS, Task
from adiona.geometric.data import chain, oracle, rename_and_reorder, training_pool, VECTORS
from adiona.geometric.model import geometry_loss
from adiona.geometric_v2.experiment import pool_for_size, sha, source_hashes, targets, train_one
from adiona.geometric_v2.model import AblationModel, load_model, predict, save_model, tensorize

ROOT = Path(__file__).resolve().parents[1]


def fixture_model():
    model = AblationModel("fixed", 2)
    with torch.no_grad():
        model.relations.weight.copy_(torch.tensor([VECTORS[r] for r in RELATIONS], dtype=torch.float))
        model.readout.weight.copy_(torch.eye(2))
        model.log_slope.fill_(10)
        model.zero_bias.fill_(4)
    return model


class AblationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(19)
        self.task = Task(("A", "B", "C"), (Fact("A", "E", "B"), Fact("B", "N", "C")), ("A", "C"))

    def test_learned_path_cannot_access_graph_solver_or_oracle(self):
        with patch("torch.linalg.solve", side_effect=AssertionError("solver accessed")), \
             patch("adiona.geometric.data.oracle", side_effect=AssertionError("oracle accessed")):
            batch = tensorize([self.task], "learned")
            self.assertNotIn("integration", batch)
            advice = predict(AblationModel("learned"), [self.task], 0)[0]
            self.assertEqual(advice.body()["admissible_use"], "proposal_only")

    def test_fixed_path_recovers_known_displacements(self):
        model = fixture_model()
        tasks = [self.task, replace(self.task, query=("C", "A"))]
        self.assertEqual([a.body()["label"] for a in predict(model, tasks)], ["NE", "SW"])

    def test_query_gauge_and_geometry_targets(self):
        batch = tensorize([self.task], "learned")
        _, coordinates = targets([self.task], batch)
        torch.testing.assert_close(coordinates, torch.tensor([[[1., 1.], [0., 1.], [0., 0.]]]))
        self.assertEqual(batch["anchors"].tolist(), [[0., 0., 1.]])

    def test_renaming_and_order_equivariance(self):
        renamed = rename_and_reorder(self.task, random.Random(49))
        for architecture in ("fixed", "learned"):
            model = AblationModel(architecture)
            outputs = [model(tensorize([t], architecture))["logits"] for t in (self.task, renamed)]
            torch.testing.assert_close(*outputs, atol=2e-5, rtol=2e-5)

    def test_padding_does_not_change_learned_prediction(self):
        model = AblationModel("learned")
        alone = model(tensorize([self.task], "learned"))["logits"]
        together = model(tensorize([self.task, chain(random.Random(4), 12)], "learned"))["logits"][:1]
        torch.testing.assert_close(alone, together, atol=2e-5, rtol=2e-5)

    def test_geometry_gradients_reach_message_update_and_projection(self):
        model = AblationModel("learned")
        batch = tensorize([self.task], "learned")
        _, coordinates = targets([self.task], batch)
        loss = geometry_loss(model(batch)["latent"], coordinates, batch["node_mask"])
        loss.backward()
        for name in ("relations.weight", "message.0.weight", "update.weight_hh", "geometry_projection.weight"):
            grad = dict(model.named_parameters())[name].grad
            self.assertIsNotNone(grad)
            self.assertTrue(torch.isfinite(grad).all())
            self.assertGreater(float(grad.abs().sum()), 0)

    def test_geometry_gradient_matches_finite_difference(self):
        model = AblationModel("learned", 2, 2).double()
        batch = {k: v.double() if v.is_floating_point() else v for k, v in tensorize([self.task], "learned").items()}
        _, coordinates = targets([self.task], batch)
        parameter = model.geometry_projection.weight
        def objective():
            return geometry_loss(model(batch)["latent"], coordinates.double(), batch["node_mask"])
        objective().backward()
        analytic = float(parameter.grad[0, 0])
        with torch.no_grad():
            original = float(parameter[0, 0])
            parameter[0, 0] = original + 1e-5
            plus = float(objective())
            parameter[0, 0] = original - 1e-5
            minus = float(objective())
            parameter[0, 0] = original
        self.assertAlmostEqual(analytic, (plus - minus) / 2e-5, places=7)

    def test_nested_depth_balanced_training_subsets(self):
        pool = training_pool(67123)
        subsets = [pool_for_size(pool, n) for n in (32, 128, 512)]
        self.assertTrue(set(t.digest for t in subsets[0]) <= set(t.digest for t in subsets[1]))
        self.assertTrue(set(t.digest for t in subsets[1]) <= set(t.digest for t in subsets[2]))
        for tasks, n in zip(subsets, (32, 128, 512)):
            self.assertEqual(len(tasks), n)
            for depth in range(4):
                self.assertEqual(tasks[depth*n//4:(depth+1)*n//4], pool[depth*128:depth*128+n//4])

    def test_matched_objectives_share_initialization_and_batches(self):
        pool = pool_for_size(training_pool(8123), 4)
        config = {"dimension": 2, "message_rounds": 2, "learning_rate": .01,
                  "steps": 4, "batch_size": 2, "curve_steps": [4]}
        a, ma = train_one(config, "learned", 0., 4, 5, pool, [self.task])
        b, mb = train_one(config, "learned", .2, 4, 5, pool, [self.task])
        self.assertEqual(ma["initial_model_digest"], mb["initial_model_digest"])
        self.assertEqual(ma["batch_sequence_digest"], mb["batch_sequence_digest"])
        self.assertEqual(ma["training_task_digest"], mb["training_task_digest"])
        self.assertNotEqual(a.fingerprint, b.fingerprint)

    def test_shared_heads_start_identically_across_architectures(self):
        torch.manual_seed(100)
        fixed = AblationModel("fixed")
        torch.manual_seed(100)
        learned = AblationModel("learned")
        for key, value in fixed.state_dict().items():
            torch.testing.assert_close(value, learned.state_dict()[key], rtol=0, atol=0)
        self.assertGreater(sum(p.numel() for p in learned.parameters()), sum(p.numel() for p in fixed.parameters()))

    def test_json_checkpoint_roundtrip_and_tamper_rejection(self):
        model = AblationModel("learned")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.json"
            save_model(model, path, {"test": True})
            restored, metadata = load_model(path)
            self.assertEqual(restored.fingerprint, model.fingerprint)
            self.assertTrue(metadata["test"])
            value = json.loads(path.read_text())
            value["model"]["state"]["relations.weight"][0][0] += 1
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                load_model(path)

    def test_checkpoint_rejects_nonfinite_duplicates_and_oversize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.json"
            for raw in ('{"x":NaN}', '{"x":1,"x":2}', ' ' * 2_000_001):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    load_model(path)

    def test_disconnected_prediction_abstains(self):
        task = replace(self.task, facts=(self.task.facts[0],))
        for architecture in ("fixed", "learned"):
            body = predict(AblationModel(architecture), [task], 0)[0].body()
            self.assertEqual((body["status"], body["label"], body["confidence_ppm"]), ("disconnected", None, 0))

    def test_v2_advice_still_cannot_authorize_execution(self):
        advice = predict(AblationModel("learned"), [self.task], 0)[0]
        keys, credentials = demo_identities()
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(str(Path(directory) / "state.db"), keys, clock=lambda: 1000)
            before = kernel.snapshot()
            action = propose_advice(kernel, credentials["worker"], self.task, advice)
            decision = kernel.decide(credentials["decider"], action, [])
            self.assertEqual(decision.body()["decision"], "REQUIRE_EVIDENCE")
            with self.assertRaises(Rejected):
                kernel.commit(credentials["executor"], action, advice)
            self.assertEqual(kernel.snapshot(), before)

    def test_source_inventory_is_nonempty_and_includes_both_versions(self):
        sources = source_hashes()
        self.assertIn("adiona/geometric/model.py", sources)
        self.assertIn("adiona/geometric_v2/model.py", sources)
        self.assertIn("adiona/geometric_v2/experiment.py", sources)

    def test_v1_files_remain_byte_identical(self):
        manifest = json.loads((ROOT / "reports/geometric_v2/v1-freeze.json").read_text())
        for name, digest in manifest["files"].items():
            self.assertEqual(sha(ROOT / name), digest, name)


if __name__ == "__main__":
    unittest.main()
