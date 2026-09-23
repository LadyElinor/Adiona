"""Optional PyTorch research tests, separate from the dependency-free kernel suite."""
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import torch

from adiona.geometric.contracts import Fact, RELATIONS, Task
from adiona.geometric.data import chain, counterfactual, grid, oracle, rename_and_reorder, VECTORS
from adiona.geometric.evaluation import raw_labels
from adiona.geometric.model import GeometricReasoner, geometry_loss, load_model, predict, save_model, tensorize

ROOT = Path(__file__).resolve().parents[1]


def reference_model():
    """Hand-set diagnostic fixture, never presented as a trained checkpoint."""
    model = GeometricReasoner(2)
    with torch.no_grad():
        model.relations.weight.copy_(torch.tensor([VECTORS[r] for r in RELATIONS], dtype=torch.float))
        model.readout.weight.copy_(torch.eye(2))
        model.log_slope.fill_(10)
        model.zero_bias.fill_(4)
    return model


class GeometryTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(1)
        self.task = Task(("A", "B", "C"), (Fact("A", "E", "B"), Fact("B", "N", "C")), ("A", "C"))

    def test_two_step_reasoning_and_query_inverse(self):
        model = reference_model()
        self.assertEqual(raw_labels(model, [self.task, replace(self.task, query=("C", "A"))]), ["NE", "SW"])

    def test_diagonal_and_zero_relations(self):
        tasks = [Task(("A", "B"), (Fact("A", r, "B"),), ("A", "B")) for r in RELATIONS]
        self.assertEqual(raw_labels(reference_model(), tasks), list(RELATIONS))

    def test_model_does_not_call_oracle(self):
        with patch("adiona.geometric.data.oracle", side_effect=AssertionError("oracle used at inference")):
            self.assertEqual(predict(reference_model(), [self.task])[0].body()["label"], "NE")

    def test_node_names_and_order_do_not_change_forward(self):
        model = GeometricReasoner()
        rng = random.Random(17)
        renamed = rename_and_reorder(self.task, rng)
        a, b = (model(tensorize([t]))["logits"] for t in (self.task, renamed))
        torch.testing.assert_close(a, b, atol=1e-5, rtol=1e-5)

    def test_disconnected_abstains_even_with_zero_confidence_threshold(self):
        task = Task(("A", "B", "C"), (Fact("A", "E", "B"),), ("A", "C"))
        result = predict(reference_model(), [task], min_confidence=0)[0].body()
        self.assertEqual((result["status"], result["label"]), ("disconnected", None))

    def test_contradictory_cycle_abstains(self):
        task = Task(("A", "B"), (Fact("A", "E", "B"), Fact("A", "W", "B")), ("A", "B"))
        result = predict(reference_model(), [task])[0].body()
        self.assertEqual((result["status"], result["confidence_ppm"]), ("inconsistent", 0))

    def test_consistent_cycles_and_disconnected_irrelevant_component(self):
        task = grid(random.Random(3))
        model = reference_model()
        result = predict(model, [task])[0].body()
        self.assertEqual(result["label"], oracle(task)[0])
        extra = replace(self.task, entities=self.task.entities + ("D", "E"),
                        facts=self.task.facts + (Fact("D", "W", "E"),))
        self.assertEqual(predict(model, [extra])[0].body()["label"], "NE")

    def test_mixed_sizes_padding_does_not_change_predictions(self):
        long = chain(random.Random(5), 12)
        model = reference_model()
        self.assertEqual(raw_labels(model, [self.task, long]),
                         raw_labels(model, [self.task]) + raw_labels(model, [long]))

    def test_counterfactual_changes_exactly_one_fact_and_answer(self):
        changed = counterfactual(self.task, random.Random(6))
        self.assertEqual(sum(a != b for a, b in zip(self.task.facts, changed.facts)), 1)
        self.assertNotEqual(oracle(self.task)[0], oracle(changed)[0])
        self.assertEqual(raw_labels(reference_model(), [changed])[0], oracle(changed)[0])

    def test_geometric_objective_has_nonzero_finite_embedding_gradient(self):
        model = GeometricReasoner()
        batch = tensorize([self.task])
        output = model(batch)
        coords = torch.tensor([oracle(self.task)[1]], dtype=torch.float)
        loss = geometry_loss(output["latent"], coords, batch["node_mask"])
        loss.backward()
        grad = model.relations.weight.grad
        self.assertTrue(torch.isfinite(grad).all())
        self.assertGreater(float(grad.abs().sum()), 0)

    def test_geometry_gradient_agrees_with_finite_difference(self):
        batch = tensorize([self.task])
        integration = batch["integration"].double()
        coords = torch.tensor([oracle(self.task)[1]], dtype=torch.double)
        embeddings = torch.randn(1, 2, 3, dtype=torch.double, requires_grad=True)
        self.assertTrue(torch.autograd.gradcheck(
            lambda x: geometry_loss(integration @ x, coords, batch["node_mask"].double()), (embeddings,)))

    def test_gram_loss_rotation_invariant_but_detects_collapsed_geometry(self):
        coords = torch.tensor([oracle(self.task)[1]], dtype=torch.float)
        mask = tensorize([self.task])["node_mask"]
        rotation = torch.tensor([[0., -1.], [1., 0.]])
        self.assertLess(float(geometry_loss(coords @ rotation, coords, mask)), 1e-8)
        self.assertGreater(float(geometry_loss(torch.zeros_like(coords), coords, mask)), .9)

    def test_checkpoint_roundtrip_and_tamper_rejection(self):
        model = reference_model()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            save_model(model, path, {"fixture": True})
            restored, metadata = load_model(path)
            self.assertEqual(restored.fingerprint, model.fingerprint)
            self.assertTrue(metadata["fixture"])
            value = json.loads(path.read_text())
            value["model"]["state"]["log_slope"][0] += 1
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_model(path)

    def test_checkpoint_rejects_nonfinite_duplicate_and_oversized_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for raw in ('{"x":NaN}', '{"x":1,"x":2}', " " * 512_001):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    load_model(path)

    def test_untrained_model_is_not_secretly_exact_solver(self):
        tasks = [chain(random.Random(i), 3) for i in range(40)]
        got = raw_labels(GeometricReasoner(), tasks)
        self.assertLess(sum(p == oracle(t)[0] for p, t in zip(got, tasks)), 30)

    def test_shipped_checkpoint_predicts_demo_without_training(self):
        model, metadata = load_model(ROOT / "models/geometric/agrm-seed7.json")
        self.assertEqual(predict(model, [self.task])[0].body()["label"], "NE")
        self.assertGreater(metadata["steps"], 0)

    def test_invalid_threshold_and_dimension_rejected(self):
        with self.assertRaises(ValueError):
            GeometricReasoner(True)
        with self.assertRaises(ValueError):
            predict(reference_model(), [self.task], min_confidence=float("nan"))
        with self.assertRaises(ValueError):
            predict(reference_model(), [self.task], max_residual=-1)


if __name__ == "__main__":
    unittest.main()
