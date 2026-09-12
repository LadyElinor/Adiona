import unittest
from adiona.canonical import Rejected, canonical, digest, loads
from adiona.contracts import Action, default_policy, validate_policy
from adiona.identity import Credential, Keyring, Principal, demo_identities


class CanonicalTests(unittest.TestCase):
    def test_order_invariant(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(Rejected):
            loads('{"role":"worker","role":"root"}')

    def test_unsupported_values_rejected(self):
        for value in (1.0, float("nan"), float("inf"), (1, 2), {1: "numeric key"}, 2**63, b"bytes"):
            with self.subTest(value=repr(value)), self.assertRaises(Rejected):
                canonical(value)

    def test_utf8_round_trip(self):
        data = {"message": "Welcome home. Καλημέρα."}
        self.assertEqual(loads(canonical(data)), data)

    def test_nesting_limit(self):
        data = []
        for _ in range(34):
            data = [data]
        with self.assertRaises(Rejected):
            canonical(data)

    def test_size_limit(self):
        with self.assertRaises(Rejected):
            canonical({"large": "x" * 262144})

    def test_policy_requires_both_warrant_bridges(self):
        p = default_policy()
        p["bridges"].pop()
        with self.assertRaises(Rejected):
            validate_policy(p)

    def test_policy_cannot_disable_core_assessments(self):
        p = default_policy()
        p["required_facets"] = []
        with self.assertRaises(Rejected):
            validate_policy(p)

    def test_policy_has_no_production_enable_switch(self):
        p = default_policy()
        p["external_side_effects_allowed"] = True
        with self.assertRaises(Rejected):
            validate_policy(p)

    def test_policy_conflicting_allowed_and_protected_key(self):
        p = default_policy()
        p["allowed_keys"].append("protected")
        with self.assertRaises(Rejected):
            validate_policy(p)

    def test_short_authentication_key_rejected(self):
        with self.assertRaises(Rejected):
            Keyring({"root": (Principal("root", "root"), b"short")})

    def test_shared_authentication_key_rejected(self):
        with self.assertRaises(Rejected):
            Keyring({"a": (Principal("worker", "a"), b"x" * 32), "b": (Principal("root", "b"), b"x" * 32)})

    def test_envelope_purpose_separation(self):
        keys, credentials = demo_identities()
        envelope = keys.sign(credentials["worker"], "claim", {"statement": "ALLOW"})
        with self.assertRaises(Rejected):
            keys.verify(envelope, "execution_capability", "authorizer")

    def test_bool_is_not_integer_budget(self):
        p = default_policy()
        p["max_commits"] = True
        with self.assertRaises(Rejected):
            validate_policy(p)
