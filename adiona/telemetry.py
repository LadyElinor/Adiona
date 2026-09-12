"""Descriptive WIA-inspired telemetry. These functions never authorize action.

Material-change sensitivity is not correctness: paired case construction and
independent labels remain necessary. Return denominators, not a single score.
"""
from __future__ import annotations
from typing import Any, Iterable
from .canonical import Rejected, exact, text


def challenge_elasticity(pairs: Iterable[dict[str, str]]) -> dict[str, Any]:
    counts = {"material": 0, "irrelevant": 0}
    successes = {"material": 0, "irrelevant": 0}
    for pair in pairs:
        exact(pair, {"kind", "before", "after"})
        kind = pair["kind"]
        if kind not in counts:
            raise Rejected("challenge must be material or irrelevant")
        text(pair["before"])
        text(pair["after"])
        counts[kind] += 1
        changed = pair["before"] != pair["after"]
        successes[kind] += int(changed if kind == "material" else not changed)
    return {
        "material_pairs": counts["material"], "material_changed": successes["material"],
        "material_sensitivity": successes["material"] / counts["material"] if counts["material"] else None,
        "irrelevant_pairs": counts["irrelevant"], "irrelevant_stable": successes["irrelevant"],
        "irrelevant_stability": successes["irrelevant"] / counts["irrelevant"] if counts["irrelevant"] else None,
        "interpretation": "descriptive signal only; not accuracy, wisdom or execution authority",
    }


def dissent_survival(original_ids: Iterable[str], retained_ids: Iterable[str]) -> dict[str, Any]:
    original, retained = set(original_ids), set(retained_ids)
    if not all(type(item) is str and item for item in original | retained):
        raise Rejected("dissent identifiers must be nonempty strings")
    return {"original": len(original), "retained": len(original & retained),
            "missing_ids": sorted(original - retained),
            "survival_fraction": len(original & retained) / len(original) if original else None,
            "limitation": "identifier survival does not establish dissent quality or freedom to dissent"}
