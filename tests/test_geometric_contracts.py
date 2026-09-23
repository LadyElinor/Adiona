"""Standard-library tests of the proposal boundary; no learned accuracy claim."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from adiona import Kernel, Rejected
from adiona.canonical import canonical
from adiona.geometric.adapter import propose_advice
from adiona.geometric.contracts import Advice, Fact, Task
from adiona.identity import demo_identities


class GeometricContractTests(unittest.TestCase):
    def setUp(self):
        self.task = Task(("A", "B", "C"), (Fact("A", "E", "B"), Fact("B", "N", "C")), ("A", "C"))
        self.advice = Advice.build({"version": "adiona-geometric-advice-v1", "admissible_use": "proposal_only",
            "task_digest": self.task.digest, "model_digest": "a" * 64, "status": "ok", "label": "NE",
            "confidence_ppm": 1_000_000, "residual_ppm": 0})
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.keys, self.c = demo_identities()
        self.kernel = Kernel(str(Path(self.temp.name) / "test.sqlite3"), self.keys, clock=lambda: 1000)

    def test_task_roundtrip(self):
        self.assertEqual(self.task, Task.from_json(canonical(self.task.body())))

    def test_unknown_task_fields_rejected(self):
        value = self.task.body()
        value["authority"] = "ALLOW"
        with self.assertRaises(Rejected):
            Task.from_dict(value)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(Rejected):
            Task.from_json('{"version":"a","version":"b"}')

    def test_malformed_task_and_size_limits(self):
        for kwargs in ({"entities": ("A", "A")}, {"query": ("A", "missing")},
                       {"facts": (Fact("A", "NORTHISH", "B"),)}, {"facts": self.task.facts * 2},
                       {"facts": ()}, {"entities": tuple(f"E{i}" for i in range(33))}):
            with self.subTest(kwargs=kwargs), self.assertRaises(Rejected):
                replace(self.task, **kwargs)

    def test_advice_cannot_assert_execution_use(self):
        value = self.advice.body()
        value["admissible_use"] = "execution_permission"
        with self.assertRaises(Rejected):
            Advice.build(value)

    def test_advice_rejects_floats_booleans_and_false_answer_on_abstention(self):
        for key, val in (("confidence_ppm", 1.0), ("confidence_ppm", True),
                         ("confidence_ppm", 1_000_001), ("status", "disconnected")):
            value = self.advice.body()
            value[key] = val
            with self.subTest(key=key, value=val), self.assertRaises(Rejected):
                Advice.build(value)

    def test_full_confidence_proposal_grants_no_authority(self):
        before = self.kernel.snapshot()
        action = propose_advice(self.kernel, self.c["worker"], self.task, self.advice)
        self.assertEqual(self.kernel.snapshot(), before)
        self.assertEqual(action.body()["edits"][0]["key"], "message")
        decision = self.kernel.decide(self.c["decider"], action, [])
        self.assertEqual(decision.body()["decision"], "REQUIRE_EVIDENCE")
        with self.assertRaises(Rejected):
            self.kernel.commit(self.c["executor"], action, self.advice)
        with self.assertRaises(Rejected):
            self.kernel.commit(self.c["executor"], action, "ALLOW")
        self.assertEqual(self.kernel.snapshot(), before)

    def test_advice_must_match_exact_task(self):
        other = replace(self.task, query=("B", "C"))
        with self.assertRaises(Rejected):
            propose_advice(self.kernel, self.c["worker"], other, self.advice)

    def test_abstention_cannot_propose_answer(self):
        value = self.advice.body()
        value.update(status="uncertain", label=None, confidence_ppm=200_000)
        with self.assertRaises(Rejected):
            propose_advice(self.kernel, self.c["worker"], self.task, Advice.build(value))

    def test_wrong_role_cannot_register_proposal(self):
        with self.assertRaises(Rejected):
            propose_advice(self.kernel, self.c["evidence"], self.task, self.advice)

    def test_only_separate_existing_assessments_and_capability_allow_commit(self):
        self.kernel.add_grant(self.c["root"], {"id": "test", "subject": "worker", "parent": None,
            "keys": ["message"], "expires_at": 2000, "max_uses": 1})
        action = propose_advice(self.kernel, self.c["worker"], self.task, self.advice)
        assessments = [self.kernel.assess(self.c[who], action, facet, "PASS",
            evidence_refs=[self.task.digest], reason="explicit fixture judgment, not model-generated approval")
            for who, facet in (("norms", "duties"), ("norms", "rights"), ("evidence", "warrant"))]
        decision = self.kernel.decide(self.c["decider"], action, assessments)
        capability = self.kernel.authorize(self.c["authorizer"], action, decision, "test")
        self.kernel.commit(self.c["executor"], action, capability)
        self.assertEqual(self.kernel.snapshot()["state"]["message"]["advice"], self.advice.body())
        with self.assertRaises(Rejected):
            self.kernel.commit(self.c["executor"], action, capability)


if __name__ == "__main__":
    unittest.main()
