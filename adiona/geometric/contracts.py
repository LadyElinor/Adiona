"""Bounded spatial task and advisory output contracts; no authority is granted."""
from __future__ import annotations

from dataclasses import dataclass
import re

from adiona.canonical import Rejected, canonical, digest, exact, loads, sha

# Row-major ordering of the nine answer classes. Semantics live in data.py;
# the neural forward pass never looks up the displacement of a relation.
RELATIONS = ("SW", "S", "SE", "W", "O", "E", "NW", "N", "NE")
MAX_ENTITIES = 32
MAX_FACTS = 128


@dataclass(frozen=True)
class Fact:
    subject: str
    relation: str
    object: str


@dataclass(frozen=True)
class Task:
    """Each fact means position(subject) - position(object) = one grid step."""
    entities: tuple[str, ...]
    facts: tuple[Fact, ...]
    query: tuple[str, str]

    def __post_init__(self) -> None:
        if type(self.entities) is not tuple or not 2 <= len(self.entities) <= MAX_ENTITIES:
            raise Rejected("task requires 2 to 32 entities")
        if any(type(e) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", e) is None
               for e in self.entities) or len(set(self.entities)) != len(self.entities):
            raise Rejected("unique bounded entity identifiers required")
        if type(self.facts) is not tuple or not 1 <= len(self.facts) <= MAX_FACTS:
            raise Rejected("task requires 1 to 128 facts")
        for f in self.facts:
            if (type(f) is not Fact or f.subject not in self.entities or f.object not in self.entities
                    or f.relation not in RELATIONS):
                raise Rejected("invalid fact or unknown entity/relation")
        if len(set(self.facts)) != len(self.facts):
            raise Rejected("duplicate facts are unsupported")
        if (type(self.query) is not tuple or len(self.query) != 2
                or any(e not in self.entities for e in self.query)):
            raise Rejected("query requires two declared entities")

    def body(self) -> dict:
        return {"version": "adiona-geometric-task-v1", "entities": list(self.entities),
                "facts": [{"subject": f.subject, "relation": f.relation, "object": f.object}
                          for f in self.facts], "query": list(self.query)}

    @property
    def digest(self) -> str:
        return digest(self.body())

    @classmethod
    def from_dict(cls, value: dict) -> Task:
        exact(value, {"version", "entities", "facts", "query"})
        if value["version"] != "adiona-geometric-task-v1":
            raise Rejected("unsupported geometric task version")
        if any(type(value[k]) is not list for k in ("entities", "facts", "query")):
            raise Rejected("task entities, facts, and query must be arrays")
        facts = []
        for f in value["facts"]:
            exact(f, {"subject", "relation", "object"})
            if any(type(v) is not str for v in f.values()):
                raise Rejected("fact fields must be strings")
            facts.append(Fact(f["subject"], f["relation"], f["object"]))
        return cls(tuple(value["entities"]), tuple(facts), tuple(value["query"]))

    @classmethod
    def from_json(cls, value: str) -> Task:
        return cls.from_dict(loads(value))


@dataclass(frozen=True)
class Advice:
    """Canonical immutable prediction. Integer diagnostics fit Adiona's JSON contract."""
    payload: str

    def __post_init__(self) -> None:
        a = loads(self.payload)
        exact(a, {"version", "admissible_use", "task_digest", "model_digest", "status",
                  "label", "confidence_ppm", "residual_ppm"})
        if a["version"] != "adiona-geometric-advice-v1" or a["admissible_use"] != "proposal_only":
            raise Rejected("unsupported advisory contract")
        sha(a["task_digest"])
        sha(a["model_digest"])
        if a["status"] not in ("ok", "uncertain", "disconnected", "inconsistent"):
            raise Rejected("invalid advisory status")
        if a["status"] == "ok":
            if type(a["label"]) is not str or a["label"] not in RELATIONS:
                raise Rejected("an accepted prediction requires a relation label")
        elif a["label"] is not None:
            raise Rejected("abstention must not include an answer")
        for key in ("confidence_ppm", "residual_ppm"):
            if type(a[key]) is not int or not 0 <= a[key] <= 1_000_000:
                raise Rejected("bounded integer diagnostic required")
        if a["status"] in ("disconnected", "inconsistent") and a["confidence_ppm"] != 0:
            raise Rejected("unsupported input cannot carry answer confidence")
        if canonical(a) != self.payload:
            raise Rejected("noncanonical advice")

    def body(self) -> dict:
        return loads(self.payload)

    @classmethod
    def build(cls, value: dict) -> Advice:
        return cls(canonical(value))
