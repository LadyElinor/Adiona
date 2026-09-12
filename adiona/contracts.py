"""Typed proposals, policy contracts, and explicit warrant bridges."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .canonical import Rejected, canonical, digest, exact, loads, natural, sha, text

FACET_ROLES = {"duties": "normative", "rights": "normative", "warrant": "epistemic", "human_review": "human"}
BRIDGES = [["recommendation", "decision_warrant"], ["decision_warrant", "execution_authorization"]]


@dataclass(frozen=True)
class Action:
    """Canonical text prevents mutable aliases after an action is approved."""
    payload: str

    def __post_init__(self) -> None:
        a = loads(self.payload)
        exact(a, {"version", "actor", "beneficiary", "intent_id", "kind", "target", "edits",
                  "expected_revision", "state_digest", "policy_digest", "authority_epoch", "recovery_of"})
        if a["version"] != "adiona-action-v1":
            raise Rejected("unsupported action contract")
        for key in ("actor", "beneficiary", "intent_id", "kind", "target"):
            text(a[key])
        for key in ("expected_revision", "authority_epoch"):
            natural(a[key])
        for key in ("state_digest", "policy_digest"):
            sha(a[key])
        if a["kind"] not in ("PATCH", "RECOVERY_PATCH") or a["target"] != "sandbox://world":
            raise Rejected("only the local sandbox patch adapter exists")
        if a["kind"] == "RECOVERY_PATCH":
            sha(a["recovery_of"])
        elif a["recovery_of"] is not None:
            raise Rejected("ordinary patch cannot assert recovery lineage")
        if type(a["edits"]) is not list or not 1 <= len(a["edits"]) <= 64:
            raise Rejected("bounded nonempty edit list required")
        seen = set()
        for edit in a["edits"]:
            exact(edit, {"key", "value"})
            if type(edit["key"]) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", edit["key"]) is None:
                raise Rejected("flat unambiguous state key required; paths are unsupported")
            if edit["key"] in seen:
                raise Rejected("duplicate edit key")
            seen.add(edit["key"])
        if canonical(a) != self.payload:
            raise Rejected("noncanonical action")

    @classmethod
    def build(cls, value: dict[str, Any]) -> Action:
        return cls(canonical(value))

    def body(self) -> dict[str, Any]:
        return loads(self.payload)

    @property
    def digest(self) -> str:
        return digest(self.body())


def validate_policy(p: dict[str, Any]) -> None:
    exact(p, {"version", "domain", "required_facets", "allowed_keys", "protected_keys", "max_edits",
              "max_commits", "assessment_ttl_seconds", "capability_ttl_seconds", "human_required", "bridges"})
    text(p["version"])
    if p["domain"] != "sandbox" or p["bridges"] != BRIDGES:
        raise Rejected("the seed supports only the two declared sandbox warrant bridges")
    if p["required_facets"] != ["duties", "rights", "warrant"]:
        raise Rejected("required assessments cannot be silently weakened")
    if type(p["human_required"]) is not bool:
        raise Rejected("human_required must be boolean")
    for field in ("max_edits", "max_commits", "assessment_ttl_seconds", "capability_ttl_seconds"):
        natural(p[field])
        if p[field] == 0:
            raise Rejected("positive policy bound required")
    for field in ("allowed_keys", "protected_keys"):
        if type(p[field]) is not list or not p[field] or len(set(p[field])) != len(p[field]):
            raise Rejected("nonempty unique key list required")
        for key in p[field]:
            if type(key) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key) is None:
                raise Rejected("invalid policy key")
    if set(p["allowed_keys"]) & set(p["protected_keys"]):
        raise Rejected("policy both allows and protects a key")
    canonical(p)


def default_policy() -> dict[str, Any]:
    return {"version": "adiona-sandbox-0.1", "domain": "sandbox", "required_facets": ["duties", "rights", "warrant"],
            "allowed_keys": ["counter", "message", "status"], "protected_keys": ["protected"],
            "max_edits": 8, "max_commits": 100, "assessment_ttl_seconds": 300,
            "capability_ttl_seconds": 60, "human_required": False, "bridges": loads(canonical(BRIDGES))}


def validate_grant(g: dict[str, Any]) -> None:
    exact(g, {"id", "subject", "parent", "keys", "expires_at", "max_uses"})
    text(g["id"])
    text(g["subject"])
    if g["parent"] is not None:
        text(g["parent"])
    for field in ("expires_at", "max_uses"):
        natural(g[field])
    if g["max_uses"] == 0 or type(g["keys"]) is not list or not g["keys"]:
        raise Rejected("positive scoped grant required")
    for key in g["keys"]:
        text(key)
    if len(set(g["keys"])) != len(g["keys"]):
        raise Rejected("duplicate grant key")
    canonical(g)
