import unittest
from adiona import Rejected
from adiona.recovery import ExternalState as S, advance
from adiona.telemetry import challenge_elasticity, dissent_survival


class RecoveryTests(unittest.TestCase):
    def test_timeout_is_unknown_not_rollback(self):
        self.assertEqual(advance(advance(S.PREPARED, "dispatch"), "timeout"), S.UNKNOWN_EXTERNAL_STATE)

    def test_unknown_outcome_cannot_blindly_retry(self):
        for event in ("retry", "dispatch", "rollback", "release_nonce"):
            with self.subTest(event=event), self.assertRaises(Rejected):
                advance(S.UNKNOWN_EXTERNAL_STATE, event)

    def test_observation_does_not_reauthorize(self):
        observed = advance(S.UNKNOWN_EXTERNAL_STATE, "confirmed_noncommit")
        self.assertEqual(observed, S.OBSERVED_NOT_COMMITTED)
        with self.assertRaises(Rejected):
            advance(observed, "dispatch")

    def test_observed_commit_is_terminal(self):
        state = advance(S.UNKNOWN_EXTERNAL_STATE, "confirmed_commit")
        with self.assertRaises(Rejected):
            advance(state, "dispatch")


class TelemetryTests(unittest.TestCase):
    def test_separate_material_and_irrelevant_metrics(self):
        result = challenge_elasticity([
            {"kind": "material", "before": "ALLOW", "after": "DENY"},
            {"kind": "material", "before": "ALLOW", "after": "ALLOW"},
            {"kind": "irrelevant", "before": "DENY", "after": "DENY"},
        ])
        self.assertEqual(result["material_sensitivity"], 0.5)
        self.assertEqual(result["irrelevant_stability"], 1.0)
        self.assertEqual(result["material_pairs"], 2)
        self.assertNotIn("authority", result)

    def test_empty_challenge_data_not_perfect_score(self):
        result = challenge_elasticity([])
        self.assertIsNone(result["material_sensitivity"])
        self.assertIsNone(result["irrelevant_stability"])

    def test_dissent_omissions_visible(self):
        result = dissent_survival(["a", "b", "c"], ["a", "c", "invented"])
        self.assertEqual(result["missing_ids"], ["b"])
        self.assertEqual(result["survival_fraction"], 2 / 3)

    def test_no_dissent_is_not_proof_of_health(self):
        self.assertIsNone(dissent_survival([], [])["survival_fraction"])

    def test_invalid_challenge_kind_rejected(self):
        with self.assertRaises(Rejected):
            challenge_elasticity([{"kind": "unknown", "before": "ALLOW", "after": "DENY"}])
