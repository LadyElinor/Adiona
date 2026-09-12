"""Sandbox-only transactional enforcement reference.

The database, clock, policy loader and keyring are trusted-host dependencies.
This module does not isolate an untrusted process or implement moral judgment.
There are no network, shell, messaging or production execution adapters.
"""
from __future__ import annotations

from contextlib import contextmanager
import secrets
import sqlite3
import time
from typing import Any, Callable, Iterator, Sequence

from .canonical import Rejected, canonical, digest, exact, loads, natural, sha, text
from .contracts import Action, FACET_ROLES, default_policy, validate_grant, validate_policy
from .identity import Credential, Envelope, Keyring


class Kernel:
    def __init__(self, path: str, keyring: Keyring, *, initial: dict[str, Any] | None = None,
                 policy: dict[str, Any] | None = None, clock: Callable[[], float] = time.time):
        if path == ":memory:":
            raise Rejected("use a private temporary file; operations use separate database connections")
        self.path, self.keys, self.clock = path, keyring, clock
        p = default_policy() if policy is None else loads(canonical(policy))
        validate_policy(p)
        state = initial if initial is not None else {"counter": 0, "message": "Welcome home.", "status": "ready", "protected": "unchanged"}
        if type(state) is not dict:
            raise Rejected("world state must be an object")
        canonical(state)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), policy TEXT NOT NULL, epoch INTEGER NOT NULL, halted INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS grants (id TEXT PRIMARY KEY, body TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, uses INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS capabilities (nonce TEXT PRIMARY KEY, envelope TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS decisions (warrant_digest TEXT PRIMARY KEY, envelope TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals (action_digest TEXT PRIMARY KEY, envelope TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, envelope TEXT NOT NULL, event_hash TEXT UNIQUE NOT NULL);
            """)
        with self._transaction() as db:
            has_world = db.execute("SELECT 1 FROM world").fetchone() is not None
            has_control = db.execute("SELECT 1 FROM control").fetchone() is not None
            if has_world != has_control:
                raise Rejected("inconsistent store initialization")
            if not has_world:
                db.execute("INSERT INTO world VALUES (1,0,?)", (canonical(state),))
                db.execute("INSERT INTO control VALUES (1,?,0,0)", (canonical(p),))
            else:
                # Reopening does not overwrite the existing world or its policy.
                validate_policy(loads(db.execute("SELECT policy FROM control WHERE id=1").fetchone()[0]))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self, *, write: bool = True) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def _now(self) -> int:
        value = int(self.clock())
        natural(value)
        return value

    @staticmethod
    def _snapshot(db: sqlite3.Connection) -> dict[str, Any]:
        w = db.execute("SELECT revision,document FROM world WHERE id=1").fetchone()
        c = db.execute("SELECT policy,epoch,halted FROM control WHERE id=1").fetchone()
        state, policy = loads(w["document"]), loads(c["policy"])
        return {"revision": w["revision"], "state": state, "state_digest": digest(state), "policy": policy,
                "policy_digest": digest(policy), "authority_epoch": c["epoch"], "halted": bool(c["halted"])}

    def snapshot(self) -> dict[str, Any]:
        with self._transaction(write=False) as db:
            return self._snapshot(db)

    def _event(self, db: sqlite3.Connection, credential: Credential, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        prior = db.execute("SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (prior["seq"] + 1, prior["event_hash"]) if prior else (1, "GENESIS")
        envelope = self.keys.sign(credential, purpose, {"sequence": seq, "previous": previous, "record": body})
        event_hash = digest(envelope.to_dict())
        db.execute("INSERT INTO events VALUES (?,?,?)", (seq, canonical(envelope.to_dict()), event_hash))
        return {"event_hash": event_hash, "envelope": envelope.to_dict()}

    def _chain(self, db: sqlite3.Connection, grant_id: str, *, now: int) -> list[dict[str, Any]]:
        chain, seen = [], set()
        current: str | None = grant_id
        while current is not None:
            if current in seen or len(seen) >= 32:
                raise Rejected("cyclic or overlong grant ancestry")
            seen.add(current)
            row = db.execute("SELECT body,revoked,uses FROM grants WHERE id=?", (current,)).fetchone()
            if row is None:
                raise Rejected("missing grant ancestor")
            grant = loads(row["body"])
            validate_grant(grant)
            if row["revoked"] or now >= grant["expires_at"] or row["uses"] >= grant["max_uses"]:
                raise Rejected("grant or ancestor revoked, expired or exhausted")
            if chain:
                child = chain[-1]
                if (not set(child["keys"]) <= set(grant["keys"]) or child["expires_at"] > grant["expires_at"]
                        or child["max_uses"] > grant["max_uses"]):
                    raise Rejected("delegation exceeds ancestor")
            chain.append(grant)
            current = grant["parent"]
        return chain

    def add_grant(self, root: Credential, grant: dict[str, Any]) -> None:
        self.keys.authenticate(root, "root")
        g = loads(canonical(grant))
        validate_grant(g)
        if self.keys.principal(g["subject"]).role != "worker":
            raise Rejected("sandbox grants target registered workers")
        with self._transaction() as db:
            s, now = self._snapshot(db), self._now()
            if not set(g["keys"]) <= set(s["policy"]["allowed_keys"]) or g["expires_at"] <= now:
                raise Rejected("grant outside current policy or already expired")
            if g["parent"] is not None:
                parent = self._chain(db, g["parent"], now=now)[0]
                if (not set(g["keys"]) <= set(parent["keys"]) or g["expires_at"] > parent["expires_at"]
                        or g["max_uses"] > parent["max_uses"]):
                    raise Rejected("delegation broadens scope, lifetime or budget")
            if db.execute("SELECT 1 FROM grants WHERE id=?", (g["id"],)).fetchone():
                raise Rejected("grant identifiers cannot be reused")
            db.execute("INSERT INTO grants(id,body) VALUES (?,?)", (g["id"], canonical(g)))
            db.execute("UPDATE control SET epoch=epoch+1 WHERE id=1")
            self._event(db, root, "root_receipt", {"operation": "ADD_GRANT", "grant_digest": digest(g), "at": now})

    def revoke(self, root: Credential, grant_id: str) -> None:
        self.keys.authenticate(root, "root")
        with self._transaction() as db:
            if not db.execute("SELECT 1 FROM grants WHERE id=?", (grant_id,)).fetchone():
                raise Rejected("unknown grant")
            db.execute("UPDATE grants SET revoked=1 WHERE id=?", (grant_id,))
            db.execute("UPDATE control SET epoch=epoch+1 WHERE id=1")
            self._event(db, root, "root_receipt", {"operation": "REVOKE", "grant_id": grant_id, "at": self._now()})

    def set_halt(self, root: Credential, halted: bool) -> None:
        self.keys.authenticate(root, "root")
        if type(halted) is not bool:
            raise Rejected("halt must be boolean")
        with self._transaction() as db:
            db.execute("UPDATE control SET halted=?,epoch=epoch+1 WHERE id=1", (int(halted),))
            self._event(db, root, "root_receipt", {"operation": "HALT" if halted else "RESUME", "at": self._now()})

    def change_policy(self, root: Credential, policy: dict[str, Any]) -> None:
        self.keys.authenticate(root, "root")
        p = loads(canonical(policy))
        validate_policy(p)
        with self._transaction() as db:
            if p["version"] == self._snapshot(db)["policy"]["version"]:
                raise Rejected("policy changes require a new explicit version")
            db.execute("UPDATE control SET policy=?,epoch=epoch+1 WHERE id=1", (canonical(p),))
            self._event(db, root, "root_receipt", {"operation": "CHANGE_POLICY", "policy_digest": digest(p), "at": self._now()})

    def propose(self, worker: Credential, edits: list[dict[str, Any]], *, beneficiary: str | None = None,
                intent_id: str | None = None, recovery_of: str | None = None) -> Action:
        self.keys.authenticate(worker, "worker")
        recipient = beneficiary or worker.principal
        self.keys.principal(recipient)
        s = self.snapshot()
        action = Action.build({"version": "adiona-action-v1", "actor": worker.principal, "beneficiary": recipient,
                             "intent_id": intent_id or secrets.token_hex(16), "kind": "RECOVERY_PATCH" if recovery_of else "PATCH",
                             "target": "sandbox://world", "edits": edits, "expected_revision": s["revision"],
                             "state_digest": s["state_digest"], "policy_digest": s["policy_digest"],
                             "authority_epoch": s["authority_epoch"], "recovery_of": recovery_of})
        origin = self.keys.sign(worker, "proposal", action.body())
        with self._transaction() as db:
            db.execute("INSERT OR IGNORE INTO proposals VALUES (?,?)", (action.digest, canonical(origin.to_dict())))
        return action

    def assess(self, assessor: Credential, action: Action, facet: str, verdict: str, *, evidence_refs: list[str],
               reason: str, assumptions: list[str] | None = None, uncertainty: list[str] | None = None) -> Envelope:
        """Record a qualified assessment. This function does not perform moral reasoning."""
        role = FACET_ROLES.get(facet)
        if role is None or verdict not in ("PASS", "FAIL", "UNKNOWN"):
            raise Rejected("invalid facet or verdict")
        self.keys.authenticate(assessor, role)
        text(reason)
        for ref in evidence_refs:
            sha(ref)
        s, now = self.snapshot(), self._now()
        return self.keys.sign(assessor, "assessment", {
            "facet": facet, "verdict": verdict, "action_digest": action.digest,
            "policy_digest": s["policy_digest"], "evidence_refs": evidence_refs, "reason": reason,
            "issued_at": now, "expires_at": now + s["policy"]["assessment_ttl_seconds"],
            "qualification": {"A": assumptions or [], "D": "sandbox", "M": "explicit assessor judgment",
                              "U": uncertainty or [], "J": "local sandbox policy only"}})

    def _preflight(self, db: sqlite3.Connection, action: Action, s: dict[str, Any]) -> None:
        a = Action(action.payload).body()
        row = db.execute("SELECT envelope FROM proposals WHERE action_digest=?", (action.digest,)).fetchone()
        if row is None:
            raise Rejected("action was not registered by an authenticated proposer")
        origin = Envelope.from_dict(loads(row["envelope"]))
        if self.keys.verify(origin, "proposal", "worker") != a or origin.principal != a["actor"]:
            raise Rejected("proposal origin mismatch")
        if self.keys.principal(a["actor"]).role != "worker":
            raise Rejected("action actor is not a worker")
        self.keys.principal(a["beneficiary"])
        if s["halted"]:
            raise Rejected("legitimate halt is active")
        for field, expected in (("expected_revision", s["revision"]), ("state_digest", s["state_digest"]),
                                ("policy_digest", s["policy_digest"]), ("authority_epoch", s["authority_epoch"])):
            if a[field] != expected:
                raise Rejected(f"stale or substituted {field}")
        p = s["policy"]
        if len(a["edits"]) > p["max_edits"] or s["revision"] >= p["max_commits"]:
            raise Rejected("edit or cumulative commit budget exhausted")
        for edit in a["edits"]:
            if edit["key"] in p["protected_keys"] or edit["key"] not in p["allowed_keys"]:
                raise Rejected("protected or unapproved key")
            if edit["key"] not in s["state"]:
                raise Rejected("patch targets a missing state key")
        if a["recovery_of"]:
            row = db.execute("SELECT envelope FROM events WHERE event_hash=?", (a["recovery_of"],)).fetchone()
            if row is None:
                raise Rejected("recovery must reference an existing execution receipt")
            prior = Envelope.from_dict(loads(row["envelope"]))
            self.keys.verify(prior, "execution_receipt", "executor")

    def _evaluate(self, db: sqlite3.Connection, action: Action, assessments: Sequence[Envelope],
                  s: dict[str, Any], now: int) -> tuple[str, list[str], int]:
        self._preflight(db, action, s)
        a, p = action.body(), s["policy"]
        seen: dict[str, dict[str, Any]] = {}
        expiry = now + p["assessment_ttl_seconds"]
        for envelope in assessments:
            if not isinstance(envelope, Envelope):
                raise Rejected("a producer name is not assessment evidence")
            facet = envelope.body().get("facet")
            role = FACET_ROLES.get(facet)
            if role is None:
                raise Rejected("unknown assessment facet")
            b = self.keys.verify(envelope, "assessment", role)
            exact(b, {"facet", "verdict", "action_digest", "policy_digest", "evidence_refs", "reason",
                      "issued_at", "expires_at", "qualification"})
            if facet in seen:
                raise Rejected("duplicate assessment facet")
            self.keys.distinct(envelope.principal, a["actor"], a["beneficiary"])
            if b["action_digest"] != action.digest or b["policy_digest"] != s["policy_digest"]:
                raise Rejected("assessment subject or policy mismatch")
            natural(b["issued_at"])
            natural(b["expires_at"])
            if not b["issued_at"] <= now < b["expires_at"] or b["expires_at"] - b["issued_at"] > p["assessment_ttl_seconds"]:
                raise Rejected("assessment is stale, future dated or overlong")
            text(b["reason"])
            if b["verdict"] not in ("PASS", "FAIL", "UNKNOWN") or type(b["evidence_refs"]) is not list:
                raise Rejected("malformed assessment")
            for ref in b["evidence_refs"]:
                sha(ref)
            q = b["qualification"]
            exact(q, {"A", "D", "M", "U", "J"})
            if q["D"] != "sandbox" or q["J"] != "local sandbox policy only":
                raise Rejected("assessment outside its demonstrated domain or jurisdiction")
            text(q["M"])
            for field in ("A", "U"):
                if type(q[field]) is not list or not all(type(v) is str for v in q[field]):
                    raise Rejected("qualification assumptions and uncertainty must remain explicit lists")
            seen[facet] = b
            expiry = min(expiry, b["expires_at"])
        if any(b["verdict"] == "FAIL" for b in seen.values()):
            return "DENY", ["an applicable signed assessment failed"], expiry
        required = p["required_facets"]
        if any(f not in seen or seen[f]["verdict"] != "PASS" or not seen[f]["evidence_refs"] for f in required):
            return "REQUIRE_EVIDENCE", ["missing, uncertain or unsupported required assessment"], expiry
        if any(b["verdict"] == "UNKNOWN" or not b["evidence_refs"] for b in seen.values()):
            return "REQUIRE_EVIDENCE", ["supplied assessment remains uncertain or unsupported"], expiry
        if p["human_required"] and "human_review" not in seen:
            return "CONFIRM_HUMAN", ["fresh authenticated human review is required"], expiry
        return "ALLOW", ["encoded sandbox gates passed; semantic judgment remains assessor-dependent"], expiry

    def decide(self, decider: Credential, action: Action, assessments: Sequence[Envelope], *,
               alternatives: list[str] | None = None, dissent: list[str] | None = None,
               predictions: list[str] | None = None, review_triggers: list[str] | None = None) -> Envelope:
        self.keys.authenticate(decider, "decider")
        a = action.body()
        for values in (alternatives or [], dissent or [], predictions or [], review_triggers or []):
            if type(values) is not list or not all(type(item) is str for item in values):
                raise Rejected("decision memory fields must be lists of strings")
        self.keys.distinct(decider.principal, a["actor"], a["beneficiary"], *(e.principal for e in assessments if isinstance(e, Envelope)))
        with self._transaction() as db:
            s, now = self._snapshot(db), self._now()
            try:
                result, reasons, expires = self._evaluate(db, action, assessments, s, now)
            except Rejected as exc:
                result, reasons, expires = "DENY", [str(exc)], now
            # A denied record need not preserve malformed input as accepted evidence.
            accepted = [e.to_dict() for e in assessments if isinstance(e, Envelope)]
            warrant = self.keys.sign(decider, "decision_warrant", {
                "action_digest": action.digest, "policy_digest": s["policy_digest"], "decision": result,
                "reasons": reasons, "assessments": accepted, "alternatives": alternatives or [], "dissent": dissent or [],
                "affected_parties": sorted({a["actor"], a["beneficiary"]}), "predictions": predictions or [],
                "review_triggers": review_triggers or ["policy_change", "authority_change", "evidence_expiry", "world_change"],
                "issued_at": now, "expires_at": expires, "scope": "local sandbox only"})
            db.execute("INSERT OR IGNORE INTO decisions VALUES (?,?)", (digest(warrant.to_dict()), canonical(warrant.to_dict())))
            self._event(db, decider, "decision_receipt", {"decision_digest": digest(warrant.to_dict()),
                        "action_digest": action.digest, "decision": result, "at": now})
            return warrant

    def _check_decision(self, db: sqlite3.Connection, action: Action, warrant: Envelope,
                        s: dict[str, Any], now: int) -> dict[str, Any]:
        b = self.keys.verify(warrant, "decision_warrant", "decider")
        row = db.execute("SELECT envelope FROM decisions WHERE warrant_digest=?", (digest(warrant.to_dict()),)).fetchone()
        if row is None or row["envelope"] != canonical(warrant.to_dict()):
            raise Rejected("decision warrant was not registered through the decision gate")
        exact(b, {"action_digest", "policy_digest", "decision", "reasons", "assessments", "alternatives",
                  "dissent", "affected_parties", "predictions", "review_triggers", "issued_at", "expires_at", "scope"})
        a = action.body()
        self.keys.distinct(warrant.principal, a["actor"], a["beneficiary"])
        natural(b["issued_at"])
        natural(b["expires_at"])
        if (b["action_digest"] != action.digest or b["policy_digest"] != s["policy_digest"]
                or b["decision"] != "ALLOW" or not b["issued_at"] <= now < b["expires_at"]
                or b["scope"] != "local sandbox only"):
            raise Rejected("no current action-bound ALLOW decision warrant")
        assessments = [Envelope.from_dict(item) for item in b["assessments"]]
        self.keys.distinct(warrant.principal, *(item.principal for item in assessments))
        result, _, _ = self._evaluate(db, action, assessments, s, now)
        if result != "ALLOW":
            raise Rejected("a prior decision does not bypass current evidence gates")
        return b

    def authorize(self, authorizer: Credential, action: Action, warrant: Envelope, grant_id: str) -> Envelope:
        self.keys.authenticate(authorizer, "authorizer")
        a = action.body()
        self.keys.distinct(authorizer.principal, a["actor"], a["beneficiary"], warrant.principal)
        with self._transaction() as db:
            s, now = self._snapshot(db), self._now()
            decision = self._check_decision(db, action, warrant, s, now)
            self.keys.distinct(authorizer.principal, *(item["principal"] for item in decision["assessments"]))
            chain = self._chain(db, grant_id, now=now)
            if chain[0]["subject"] != a["actor"] or not {e["key"] for e in a["edits"]} <= set(chain[0]["keys"]):
                raise Rejected("grant subject or scope mismatch")
            nonce = secrets.token_hex(32)
            expires = min(now + s["policy"]["capability_ttl_seconds"], decision["expires_at"], *(g["expires_at"] for g in chain))
            capability = self.keys.sign(authorizer, "execution_capability", {
                "nonce": nonce, "action_digest": action.digest, "policy_digest": s["policy_digest"],
                "authority_epoch": s["authority_epoch"], "grant_id": grant_id, "warrant": warrant.to_dict(),
                "issued_at": now, "expires_at": expires})
            db.execute("INSERT INTO capabilities(nonce,envelope) VALUES (?,?)", (nonce, canonical(capability.to_dict())))
            self._event(db, authorizer, "authorization_receipt", {"action_digest": action.digest,
                        "capability_digest": digest(capability.to_dict()), "decision_digest": digest(warrant.to_dict()), "at": now})
            return capability

    def commit(self, executor: Credential, action: Action, capability: Envelope) -> dict[str, Any]:
        self.keys.authenticate(executor, "executor")  # Before any transaction or mutation.
        token = self.keys.verify(capability, "execution_capability", "authorizer")
        exact(token, {"nonce", "action_digest", "policy_digest", "authority_epoch", "grant_id", "warrant", "issued_at", "expires_at"})
        a = action.body()
        warrant = Envelope.from_dict(token["warrant"])
        self.keys.distinct(executor.principal, a["actor"], a["beneficiary"], capability.principal, warrant.principal)
        with self._transaction() as db:
            s, now = self._snapshot(db), self._now()
            row = db.execute("SELECT envelope,consumed FROM capabilities WHERE nonce=?", (token["nonce"],)).fetchone()
            if row is None or row["consumed"] or row["envelope"] != canonical(capability.to_dict()):
                raise Rejected("unknown, altered or already consumed capability")
            natural(token["issued_at"])
            natural(token["expires_at"])
            if (not token["issued_at"] <= now < token["expires_at"] or token["action_digest"] != action.digest
                    or token["policy_digest"] != s["policy_digest"] or token["authority_epoch"] != s["authority_epoch"]):
                raise Rejected("expired or mismatched exact-action capability")
            decision = self._check_decision(db, action, warrant, s, now)
            self.keys.distinct(executor.principal, *(item["principal"] for item in decision["assessments"]))
            chain = self._chain(db, token["grant_id"], now=now)
            if chain[0]["subject"] != a["actor"] or not {e["key"] for e in a["edits"]} <= set(chain[0]["keys"]):
                raise Rejected("live grant no longer covers action")
            staged = loads(canonical(s["state"]))
            for edit in a["edits"]:
                staged[edit["key"]] = edit["value"]
            # State, consumption, ancestor budgets, and the receipt share ONE transaction.
            db.execute("UPDATE world SET revision=revision+1,document=? WHERE id=1", (canonical(staged),))
            db.execute("UPDATE capabilities SET consumed=1 WHERE nonce=?", (token["nonce"],))
            for grant in chain:
                db.execute("UPDATE grants SET uses=uses+1 WHERE id=?", (grant["id"],))
            return self._event(db, executor, "execution_receipt", {
                "status": "COMMITTED", "action_digest": action.digest, "capability_digest": digest(capability.to_dict()),
                "decision_digest": digest(warrant.to_dict()), "state_before": s["state_digest"], "state_after": digest(staged),
                "revision_before": s["revision"], "revision_after": s["revision"] + 1,
                "recovery_of": a["recovery_of"], "at": now})

    def verify_history(self, *, expected_head: str | None = None) -> str:
        roles = {"root_receipt": "root", "decision_receipt": "decider", "authorization_receipt": "authorizer", "execution_receipt": "executor"}
        with self._transaction(write=False) as db:
            previous, sequence = "GENESIS", 0
            for row in db.execute("SELECT seq,envelope,event_hash FROM events ORDER BY seq"):
                envelope = Envelope.from_dict(loads(row["envelope"]))
                role = roles.get(envelope.purpose)
                if role is None:
                    raise Rejected("unknown receipt purpose")
                b = self.keys.verify(envelope, envelope.purpose, role)
                sequence += 1
                if b["sequence"] != sequence or row["seq"] != sequence or b["previous"] != previous:
                    raise Rejected("receipt ordering or chain mismatch")
                if digest(envelope.to_dict()) != row["event_hash"]:
                    raise Rejected("receipt digest mismatch")
                previous = row["event_hash"]
            if expected_head is not None and previous != expected_head:
                raise Rejected("history differs from independently retained head")
            return previous
