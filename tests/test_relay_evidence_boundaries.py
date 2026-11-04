"""Synthetic representation controls, not evidence about real-world identities.

The oracle is used as a diagnostic fixture, never as learned-model performance.
"""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from adiona import Kernel, Rejected
from adiona.geometric.adapter import propose_advice
from adiona.geometric.contracts import Advice, Fact, Task
from adiona.geometric.data import oracle
from adiona.identity import demo_identities


class RelayEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        # Similar display names in separate collections are not shared IDs.
        self.separate = Task(
            ("left_Alex", "left_B", "right_Alex", "right_C"),
            (Fact("left_B", "E", "left_Alex"),
             Fact("right_Alex", "N", "right_C")),
            ("left_B", "right_C"),
        )

    def test_distinct_collection_ids_do_not_create_a_path(self):
        label, _, status = oracle(self.separate)
        self.assertEqual((label, status), (None, "disconnected"))

    def test_lossy_identity_merge_can_manufacture_an_answer(self):
        # Intentionally unsafe transformation: this contrast documents a risk,
        # not an identity-resolution feature or an approved ingestion method.
        merged = Task(
            ("Alex", "left_B", "right_C"),
            (Fact("left_B", "E", "Alex"), Fact("Alex", "N", "right_C")),
            self.separate.query,
        )
        self.assertEqual(oracle(self.separate)[2], "disconnected")
        self.assertEqual((oracle(merged)[0], oracle(merged)[2]), ("NE", "ok"))
        self.assertNotEqual(self.separate.digest, merged.digest)

    def test_category_membership_is_not_a_spatial_constraint(self):
        with self.assertRaises(Rejected):
            replace(self.separate, facts=(Fact("left_Alex", "MEMBER_OF", "right_Alex"),))

    def test_identifier_case_is_not_silently_normalized(self):
        task = Task(("Alex", "alex", "B"), (Fact("Alex", "E", "B"),), ("alex", "B"))
        self.assertEqual(oracle(task)[2], "disconnected")

    def test_whitespace_in_identifiers_is_rejected_not_trimmed(self):
        for identifier in (" Alex", "Alex ", "Alex\t", "Alex\n"):
            with self.subTest(identifier=identifier), self.assertRaises(Rejected):
                Task((identifier, "B"), (Fact(identifier, "E", "B"),), (identifier, "B"))

    def test_inverse_restatement_does_not_supply_a_new_constraint(self):
        original = Task(("A", "B"), (Fact("A", "E", "B"),), ("A", "B"))
        restated = replace(original, facts=original.facts + (Fact("B", "W", "A"),))
        self.assertEqual(oracle(original), oracle(restated))
        self.assertNotEqual(original.digest, restated.digest)
        # Exact duplicate rejection is not source-independence verification.
        with self.assertRaises(Rejected):
            replace(original, facts=original.facts * 2)

    def test_removing_bridge_invalidates_old_advice(self):
        connected = replace(self.separate, facts=self.separate.facts +
                            (Fact("left_Alex", "O", "right_Alex"),))
        self.assertEqual(oracle(connected)[2], "ok")
        self.assertEqual(oracle(self.separate)[2], "disconnected")
        advice = Advice.build({
            "version": "adiona-geometric-advice-v1", "admissible_use": "proposal_only",
            "task_digest": connected.digest, "model_digest": "a" * 64,
            "status": "ok", "label": "NE", "confidence_ppm": 1_000_000,
            "residual_ppm": 0,
        })
        with tempfile.TemporaryDirectory() as directory:
            keys, credentials = demo_identities()
            kernel = Kernel(str(Path(directory) / "test.sqlite3"), keys, clock=lambda: 1000)
            before = kernel.snapshot()
            with self.assertRaises(Rejected):
                propose_advice(kernel, credentials["worker"], self.separate, advice)
            self.assertEqual(kernel.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
