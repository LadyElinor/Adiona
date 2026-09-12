"""Zero-dependency local demonstration. No provider calls or external actions."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile
import time
from .canonical import Rejected
from .identity import demo_identities
from .kernel import Kernel


def demo() -> dict:
    keys, c = demo_identities()
    with tempfile.TemporaryDirectory(prefix="adiona-") as directory:
        kernel = Kernel(str(Path(directory) / "sandbox.sqlite3"), keys)
        kernel.add_grant(c["root"], {"id": "welcome-home", "subject": "worker", "parent": None,
                         "keys": ["message", "status", "counter"], "expires_at": int(time.time()) + 3600, "max_uses": 10})

        def evaluate(action):
            refs = [kernel.snapshot()["state_digest"]]
            assessments = [kernel.assess(c[who], action, facet, "PASS", evidence_refs=refs,
                                         reason="scripted local fixture judgment, not validated ethical assessment")
                           for who, facet in (("norms", "duties"), ("norms", "rights"), ("evidence", "warrant"))]
            decision = kernel.decide(c["decider"], action, assessments, alternatives=["do not change the sandbox"])
            return kernel.authorize(c["authorizer"], action, decision, "welcome-home")

        first = kernel.propose(c["worker"], [{"key": "status", "value": "away"}])
        cap = evaluate(first)
        outward = kernel.commit(c["executor"], first, cap)
        try:
            kernel.commit(c["executor"], first, cap)
            replay = "ERROR: accepted"
        except Rejected:
            replay = "DENIED"
        returning = kernel.propose(c["worker"], [{"key": "status", "value": "home"},
                                   {"key": "message", "value": "Welcome home."}], recovery_of=outward["event_hash"])
        try:
            kernel.commit(c["executor"], returning, cap)
            old_approval = "ERROR: accepted"
        except Rejected:
            old_approval = "DENIED"
        returned = kernel.commit(c["executor"], returning, evaluate(returning))
        head = kernel.verify_history(expected_head=returned["event_hash"])
        return {"project": "Adiona", "message": "Welcome home.", "profile": "scripted sandbox demonstration",
                "revision": kernel.snapshot()["revision"], "state": kernel.snapshot()["state"],
                "replayed_capability": replay, "old_approval_for_recovery": old_approval,
                "history_verified_against_retained_head": head == returned["event_hash"],
                "production_cleared": False, "external_side_effects_allowed": False,
                "models_evaluated": 0, "cognitive_independence_demonstrated": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Adiona. Welcome home.")
    parser.add_argument("command", choices=["demo", "status", "deployment-check"])
    command = parser.parse_args().command
    if command == "demo":
        print(json.dumps(demo(), indent=2))
        return 0
    print(json.dumps({"project": "Adiona", "version": "0.1.0", "profile": "sandbox-only research seed",
                      "production_cleared": False, "external_side_effects_allowed": False,
                      "root_governance": "fixture, not independently administered",
                      "substantive_ethics_validated": False, "models_evaluated": 0}, indent=2))
    return 2 if command == "deployment-check" else 0


if __name__ == "__main__":
    raise SystemExit(main())
