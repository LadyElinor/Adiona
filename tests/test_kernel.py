from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from adiona import Action, Credential, Envelope, Kernel, Keyring, Principal, Rejected, default_policy
from adiona.canonical import canonical, digest
from adiona.identity import demo_identities


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="adiona-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "test.sqlite3")
        self.now = 1800000000
        self.keys, self.c = demo_identities()
        self.k = Kernel(self.path, self.keys, clock=lambda: self.now)
        self.k.add_grant(self.c["root"], self.grant("root-grant"))

    def grant(self, name, *, parent=None, uses=10, keys=None, expires=None):
        return {"id": name, "subject": "worker", "parent": parent,
                "keys": keys or ["counter", "message", "status"],
                "expires_at": expires or self.now + 1000, "max_uses": uses}

    def action(self, value=1, **kwargs):
        return self.k.propose(self.c["worker"], [{"key": "counter", "value": value}], **kwargs)

    def assessments(self, a, *, verdicts=None):
        verdicts = verdicts or {}
        return [self.k.assess(self.c[who], a, facet, verdicts.get(facet, "PASS"),
                             evidence_refs=[self.k.snapshot()["state_digest"]], reason="fixture judgment")
                for who, facet in (("norms", "duties"), ("norms", "rights"), ("evidence", "warrant"))]

    def decision(self, a, assessments=None):
        return self.k.decide(self.c["decider"], a, self.assessments(a) if assessments is None else assessments)

    def capability(self, a, grant="root-grant"):
        return self.k.authorize(self.c["authorizer"], a, self.decision(a), grant)

    def count(self, table):
        # Fixed internal table names in the test harness, never untrusted input.
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def commit(self, a, cap):
        return self.k.commit(self.c["executor"], a, cap)

    def test_propose_has_no_world_or_audit_effect(self):
        before, events = self.k.snapshot(), self.count("events")
        self.action()
        self.assertEqual(before, self.k.snapshot())
        self.assertEqual(events, self.count("events"))

    def test_action_has_no_mutable_aliases(self):
        edits = [{"key": "message", "value": {"nested": ["original"]}}]
        a = self.k.propose(self.c["worker"], edits)
        edits[0]["value"]["nested"].append("injected")
        self.assertEqual(a.body()["edits"][0]["value"], {"nested": ["original"]})
        body = a.body()
        body["edits"][0]["value"]["nested"].append("other")
        self.assertNotEqual(body, a.body())

    def test_happy_path_commits_once(self):
        a = self.action()
        receipt = self.commit(a, self.capability(a))
        self.assertEqual(self.k.snapshot()["state"]["counter"], 1)
        self.assertEqual(self.k.snapshot()["revision"], 1)
        self.assertEqual(self.k.verify_history(expected_head=receipt["event_hash"]), receipt["event_hash"])

    def test_no_capability_no_commit(self):
        a = self.action()
        before = self.k.snapshot()
        with self.assertRaises(Rejected):
            self.commit(a, "ALLOW")
        self.assertEqual(before, self.k.snapshot())

    def test_decision_is_not_execution_permission(self):
        a = self.action()
        with self.assertRaises(Rejected):
            self.commit(a, self.decision(a))
        self.assertEqual(self.k.snapshot()["revision"], 0)

    def test_E1_replanning_invalidates_prior_approval(self):
        a = self.action(1)
        cap = self.capability(a)
        replacement = self.action(2, intent_id=a.body()["intent_id"])
        with self.assertRaises(Rejected):
            self.commit(replacement, cap)
        self.assertEqual(self.k.snapshot()["revision"], 0)

    def test_E2_changed_approved_arguments_rejected(self):
        a = self.action()
        cap = self.capability(a)
        changed = a.body()
        changed["edits"][0]["value"] = 999
        with self.assertRaises(Rejected):
            self.commit(Action.build(changed), cap)

    def test_E3_single_use_capability(self):
        a = self.action()
        cap = self.capability(a)
        self.commit(a, cap)
        with self.assertRaises(Rejected):
            self.commit(a, cap)
        self.assertEqual(self.k.snapshot()["revision"], 1)

    def test_E4_invalid_executor_rejected_before_mutation(self):
        a = self.action()
        cap = self.capability(a)
        before, events = self.k.snapshot(), self.count("events")
        with self.assertRaises(Rejected):
            self.k.commit(self.c["worker"], a, cap)
        self.assertEqual(before, self.k.snapshot())
        self.assertEqual(events, self.count("events"))
        self.commit(a, cap)

    def test_E5_invalid_authorizer_leaves_no_spendable_approval(self):
        a = self.action()
        warrant = self.decision(a)
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["worker"], a, warrant, "root-grant")
        self.assertEqual(self.count("capabilities"), 0)
        self.assertEqual(self.k.snapshot()["revision"], 0)

    def test_E6_mixed_validity_edits_are_atomic(self):
        before = self.k.snapshot()
        a = self.k.propose(self.c["worker"], [{"key": "counter", "value": 99}, {"key": "missing", "value": 1}])
        decision = self.decision(a)
        self.assertEqual(decision.body()["decision"], "DENY")
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, decision, "root-grant")
        self.assertEqual(before, self.k.snapshot())

    def test_M1_bare_human_label_is_not_approval(self):
        a = self.action()
        with self.assertRaises(Rejected):
            self.k.assess("human", a, "human_review", "PASS", evidence_refs=[digest({})], reason="name only")

    def test_M2_bare_evidence_producer_is_not_evidence(self):
        a = self.action()
        decision = self.decision(a, ["independent-producer"])
        self.assertEqual(decision.body()["decision"], "DENY")
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, decision, "root-grant")

    def test_unknown_principal_rejected(self):
        with self.assertRaises(Rejected):
            self.k.propose(Credential("invented", b"x" * 32), [{"key": "counter", "value": 1}])

    def test_forged_known_principal_rejected(self):
        with self.assertRaises(Rejected):
            self.k.propose(Credential("worker", b"x" * 32), [{"key": "counter", "value": 1}])

    def test_tampered_capability_signature_rejected(self):
        a = self.action()
        cap = self.capability(a)
        with self.assertRaises(Rejected):
            self.commit(a, replace(cap, mac="0" * 64))

    def test_capability_payload_substitution_rejected(self):
        a = self.action()
        cap = self.capability(a)
        body = cap.body()
        body["expires_at"] += 10000
        with self.assertRaises(Rejected):
            self.commit(a, replace(cap, payload=canonical(body)))

    def test_issuer_substitution_rejected(self):
        a = self.action()
        cap = self.capability(a)
        with self.assertRaises(Rejected):
            self.commit(a, replace(cap, principal="worker"))

    def test_unregistered_signed_capability_rejected(self):
        a = self.action()
        cap = self.capability(a)
        body = cap.body()
        body["nonce"] = "new-nonce"
        forged = self.keys.sign(self.c["authorizer"], "execution_capability", body)
        with self.assertRaises(Rejected):
            self.commit(a, forged)

    def test_unregistered_decision_cannot_skip_gates(self):
        a = self.action()
        body = self.decision(a).body()
        body["reasons"] = ["unregistered alteration"]
        fresh = self.keys.sign(self.c["decider"], "decision_warrant", body)
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, fresh, "root-grant")

    def test_protected_write_is_denied(self):
        a = self.k.propose(self.c["worker"], [{"key": "protected", "value": "changed"}])
        self.assertEqual(self.decision(a).body()["decision"], "DENY")
        self.assertEqual(self.k.snapshot()["state"]["protected"], "unchanged")

    def test_authorized_request_can_still_fail_duties(self):
        a = self.action()
        decision = self.decision(a, self.assessments(a, verdicts={"duties": "FAIL"}))
        self.assertEqual(decision.body()["decision"], "DENY")
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, decision, "root-grant")

    def test_unknown_duty_requires_evidence(self):
        a = self.action()
        decision = self.decision(a, self.assessments(a, verdicts={"duties": "UNKNOWN"}))
        self.assertEqual(decision.body()["decision"], "REQUIRE_EVIDENCE")

    def test_fail_dominates_unknown(self):
        a = self.action()
        d = self.decision(a, self.assessments(a, verdicts={"duties": "UNKNOWN", "rights": "FAIL"}))
        self.assertEqual(d.body()["decision"], "DENY")

    def test_empty_evidence_refs_do_not_satisfy_warrant(self):
        a = self.action()
        assessments = self.assessments(a)
        assessments[-1] = self.k.assess(self.c["evidence"], a, "warrant", "PASS", evidence_refs=[], reason="no evidence")
        self.assertEqual(self.decision(a, assessments).body()["decision"], "REQUIRE_EVIDENCE")

    def test_missing_facet_requires_evidence(self):
        a = self.action()
        self.assertEqual(self.decision(a, self.assessments(a)[:-1]).body()["decision"], "REQUIRE_EVIDENCE")

    def test_duplicate_assessment_facet_denied(self):
        a = self.action()
        assessments = self.assessments(a)
        self.assertEqual(self.decision(a, assessments + [assessments[0]]).body()["decision"], "DENY")

    def test_assessment_for_other_action_denied(self):
        a, other = self.action(1), self.action(2)
        self.assertEqual(self.decision(a, self.assessments(other)).body()["decision"], "DENY")

    def test_domain_relabeling_denied(self):
        a = self.action()
        assessments = self.assessments(a)
        body = assessments[-1].body()
        body["qualification"]["D"] = "clinical practice"
        assessments[-1] = self.keys.sign(self.c["evidence"], "assessment", body)
        self.assertEqual(self.decision(a, assessments).body()["decision"], "DENY")

    def test_common_trust_domain_is_not_independence(self):
        entries = dict(self.keys._entries)
        entries["norms"] = (Principal("normative", "fixture:worker"), self.c["norms"].secret)
        self.k.keys = Keyring(entries)
        a = self.action()
        self.assertEqual(self.decision(a).body()["decision"], "DENY")

    def test_human_gate_needs_authenticated_fresh_review(self):
        p = default_policy()
        p.update(version="human-policy", human_required=True)
        self.k.change_policy(self.c["root"], p)
        a = self.action()
        assessments = self.assessments(a)
        waiting = self.decision(a, assessments)
        self.assertEqual(waiting.body()["decision"], "CONFIRM_HUMAN")
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, waiting, "root-grant")
        review = self.k.assess(self.c["human"], a, "human_review", "PASS", evidence_refs=[digest({"review": "fixture"})], reason="fixture human review")
        current = self.decision(a, assessments + [review])
        self.assertEqual(current.body()["decision"], "ALLOW")
        self.commit(a, self.k.authorize(self.c["authorizer"], a, current, "root-grant"))

    def test_human_review_does_not_override_failed_duty(self):
        a = self.action()
        review = self.k.assess(self.c["human"], a, "human_review", "PASS", evidence_refs=[digest({})], reason="review")
        decision = self.decision(a, self.assessments(a, verdicts={"duties": "FAIL"}) + [review])
        self.assertEqual(decision.body()["decision"], "DENY")

    def test_denied_retry_does_not_gain_authority(self):
        a = self.action()
        for _ in range(3):
            self.assertEqual(self.decision(a, []).body()["decision"], "REQUIRE_EVIDENCE")
        self.assertEqual(self.count("capabilities"), 0)

    def test_expired_assessment_denied(self):
        a = self.action()
        assessments = self.assessments(a)
        self.now += 301
        self.assertEqual(self.decision(a, assessments).body()["decision"], "DENY")

    def test_future_dated_assessment_denied(self):
        a = self.action()
        self.now += 10
        assessments = self.assessments(a)
        self.now -= 10
        self.assertEqual(self.decision(a, assessments).body()["decision"], "DENY")

    def test_expired_capability_denied(self):
        a = self.action()
        cap = self.capability(a)
        self.now += 60
        with self.assertRaises(Rejected):
            self.commit(a, cap)

    def test_expired_decision_cannot_issue_capability(self):
        a = self.action()
        decision = self.decision(a)
        self.now += 301
        with self.assertRaises(Rejected):
            self.k.authorize(self.c["authorizer"], a, decision, "root-grant")

    def test_stale_world_invalidates_other_capability(self):
        first, second = self.action(1), self.action(2)
        first_cap, second_cap = self.capability(first), self.capability(second)
        self.commit(first, first_cap)
        with self.assertRaises(Rejected):
            self.commit(second, second_cap)
        self.assertEqual(self.k.snapshot()["state"]["counter"], 1)

    def test_policy_change_invalidates_prior_approval(self):
        a = self.action()
        cap = self.capability(a)
        p = default_policy()
        p["version"] = "v-next"
        self.k.change_policy(self.c["root"], p)
        with self.assertRaises(Rejected):
            self.commit(a, cap)

    def test_worker_cannot_change_policy(self):
        p = default_policy()
        p["version"] = "bad"
        with self.assertRaises(Rejected):
            self.k.change_policy(self.c["worker"], p)

    def test_no_implicit_policy_overwrite_on_restart(self):
        a = self.action()
        self.commit(a, self.capability(a))
        p = default_policy()
        p["version"] = "must-not-replace"
        reopened = Kernel(self.path, self.keys, initial={"counter": 500}, policy=p, clock=lambda: self.now)
        self.assertEqual(reopened.snapshot(), self.k.snapshot())
        self.assertEqual(reopened.snapshot()["state"]["counter"], 1)

    def test_root_revocation_invalidates_child(self):
        self.k.add_grant(self.c["root"], self.grant("child", parent="root-grant"))
        a = self.action()
        cap = self.capability(a, "child")
        self.k.revoke(self.c["root"], "root-grant")
        with self.assertRaises(Rejected):
            self.commit(a, cap)
        new = self.action()
        with self.assertRaises(Rejected):
            self.capability(new, "child")

    def test_delegation_cannot_expand_scope(self):
        self.k.add_grant(self.c["root"], self.grant("narrow", keys=["counter"]))
        with self.assertRaises(Rejected):
            self.k.add_grant(self.c["root"], self.grant("expanded", parent="narrow"))

    def test_delegation_cannot_expand_lifetime(self):
        with self.assertRaises(Rejected):
            self.k.add_grant(self.c["root"], self.grant("late", parent="root-grant", expires=self.now + 2000))

    def test_delegation_cannot_expand_budget(self):
        with self.assertRaises(Rejected):
            self.k.add_grant(self.c["root"], self.grant("large", parent="root-grant", uses=11))

    def test_missing_parent_denied(self):
        with self.assertRaises(Rejected):
            self.k.add_grant(self.c["root"], self.grant("orphan", parent="missing"))

    def test_scope_checked_before_authorization(self):
        self.k.add_grant(self.c["root"], self.grant("status-only", keys=["status"]))
        a = self.action()
        with self.assertRaises(Rejected):
            self.capability(a, "status-only")

    def test_grant_identity_cannot_be_reused(self):
        with self.assertRaises(Rejected):
            self.k.add_grant(self.c["root"], self.grant("root-grant"))

    def test_parent_budget_shared_across_children(self):
        self.k.add_grant(self.c["root"], self.grant("one-total", uses=1))
        self.k.add_grant(self.c["root"], self.grant("a", parent="one-total", uses=1))
        self.k.add_grant(self.c["root"], self.grant("b", parent="one-total", uses=1))
        first = self.action(1, intent_id="first-session")
        self.commit(first, self.capability(first, "a"))
        second = self.action(2, intent_id="new-session")
        with self.assertRaises(Rejected):
            self.capability(second, "b")

    def test_global_budget_survives_new_intent(self):
        p = default_policy()
        p.update(version="one-commit", max_commits=1)
        self.k.change_policy(self.c["root"], p)
        a = self.action()
        self.commit(a, self.capability(a))
        self.assertEqual(self.decision(self.action(2, intent_id="new-intent")).body()["decision"], "DENY")

    def test_halt_and_resume_do_not_restore_old_approval(self):
        a = self.action()
        cap = self.capability(a)
        self.k.set_halt(self.c["root"], True)
        with self.assertRaises(Rejected):
            self.commit(a, cap)
        self.k.set_halt(self.c["root"], False)
        with self.assertRaises(Rejected):
            self.commit(a, cap)
        fresh = self.action()
        self.commit(fresh, self.capability(fresh))

    def test_receipt_write_failure_rolls_back_everything(self):
        a = self.action()
        cap = self.capability(a)
        before, count = self.k.snapshot(), self.count("events")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'injected receipt failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.commit(a, cap)
        self.assertEqual(before, self.k.snapshot())
        self.assertEqual(count, self.count("events"))
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT consumed FROM capabilities").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT uses FROM grants WHERE id='root-grant'").fetchone()[0], 0)
            db.execute("DROP TRIGGER fail_receipt")
        self.commit(a, cap)

    def test_competing_commits_consume_capability_once(self):
        a = self.action()
        cap = self.capability(a)

        def attempt(_):
            try:
                self.commit(a, cap)
                return "COMMITTED"
            except Rejected:
                return "REJECTED"
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(16)))
        self.assertEqual(results.count("COMMITTED"), 1)
        self.assertEqual(results.count("REJECTED"), 15)
        self.assertEqual(self.k.snapshot()["revision"], 1)

    def test_history_tampering_detected(self):
        a = self.action()
        self.commit(a, self.capability(a))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE events SET event_hash=? WHERE seq=1", ("0" * 64,))
        with self.assertRaises(Rejected):
            self.k.verify_history()

    def test_truncation_requires_retained_head(self):
        a = self.action()
        receipt = self.commit(a, self.capability(a))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
        # An internally consistent prefix alone cannot prove completeness.
        self.k.verify_history()
        with self.assertRaises(Rejected):
            self.k.verify_history(expected_head=receipt["event_hash"])

    def test_recovery_is_new_action_with_new_authorization(self):
        first = self.action(1)
        cap = self.capability(first)
        outward = self.commit(first, cap)
        recovery = self.action(0, recovery_of=outward["event_hash"])
        with self.assertRaises(Rejected):
            self.commit(recovery, cap)
        returned = self.commit(recovery, self.capability(recovery))
        body = Envelope.from_dict(returned["envelope"]).body()["record"]
        self.assertEqual(body["recovery_of"], outward["event_hash"])
        self.assertEqual(self.k.snapshot()["state"]["counter"], 0)
        self.assertEqual(self.k.snapshot()["revision"], 2)

    def test_recovery_cannot_invent_prior_execution(self):
        a = self.action(0, recovery_of="0" * 64)
        self.assertEqual(self.decision(a).body()["decision"], "DENY")

    def test_decision_retains_alternatives_dissent_and_qualifications(self):
        a = self.action()
        decision = self.k.decide(self.c["decider"], a, self.assessments(a),
                                 alternatives=["wait"], dissent=["dissent-1"])
        self.assertEqual(decision.body()["alternatives"], ["wait"])
        self.assertEqual(decision.body()["dissent"], ["dissent-1"])
        q = decision.body()["assessments"][0]["payload"]
        self.assertIn('"qualification"', q)
        self.assertEqual(self.count("decisions"), 1)

    def test_deny_decisions_remain_reconstructable(self):
        a = self.action()
        self.decision(a, self.assessments(a, verdicts={"rights": "FAIL"}))
        self.assertEqual(self.count("decisions"), 1)
        self.assertEqual(self.count("capabilities"), 0)
        self.k.verify_history()

    def test_manual_action_cannot_impersonate_registered_proposer(self):
        a = self.action()
        body = a.body()
        body["intent_id"] = "unregistered-intent"
        invented = Action.build(body)
        self.assertEqual(self.decision(invented).body()["decision"], "DENY")

    def test_unsafe_paths_rejected_at_parsing_boundary(self):
        for key in ("../protected", "a.b", "/etc/passwd", "a/b", "_private"):
            with self.subTest(key=key), self.assertRaises(Rejected):
                self.k.propose(self.c["worker"], [{"key": key, "value": "bad"}])

    def test_unknown_action_fields_are_rejected(self):
        body = self.action().body()
        body["override"] = True
        with self.assertRaises(Rejected):
            Action.build(body)

    def test_external_target_is_rejected(self):
        body = self.action().body()
        body["target"] = "https://outside.invalid"
        with self.assertRaises(Rejected):
            Action.build(body)

    def test_duplicate_patch_keys_rejected(self):
        with self.assertRaises(Rejected):
            self.k.propose(self.c["worker"], [{"key": "counter", "value": 1}, {"key": "counter", "value": 2}])

    def test_root_actions_require_root_credential(self):
        for operation in (lambda: self.k.add_grant(self.c["worker"], self.grant("bad")),
                          lambda: self.k.revoke(self.c["worker"], "root-grant"),
                          lambda: self.k.set_halt(self.c["worker"], False)):
            with self.assertRaises(Rejected):
                operation()

    def test_prediction_and_reconsideration_memory_preserved(self):
        a = self.action()
        d = self.k.decide(self.c["decider"], a, self.assessments(a),
                          predictions=["counter should equal one"], review_triggers=["counter differs"])
        self.assertEqual(d.body()["predictions"], ["counter should equal one"])
        self.assertEqual(d.body()["review_triggers"], ["counter differs"])
        self.assertEqual(d.body()["affected_parties"], ["worker"])
