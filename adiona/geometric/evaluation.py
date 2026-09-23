"""Report accuracy, coverage, paired correctness, and declared holdout limits."""
from __future__ import annotations

from dataclasses import replace
import math
import random
import time

import torch

from .contracts import Fact, RELATIONS, Task
from .data import counterfactual, evaluation_sets, oracle, rename_and_reorder
from .model import GeometricReasoner, predict, tensorize


@torch.no_grad()
def raw_labels(model: GeometricReasoner, tasks: list[Task]) -> list[str]:
    labels = []
    for start in range(0, len(tasks), 128):
        out = model(tensorize(tasks[start:start + 128]))
        labels.extend(RELATIONS[i] for i in out["logits"].argmax(-1).tolist())
    return labels


def _advice(model, tasks, min_confidence, max_residual):
    return [a.body() for start in range(0, len(tasks), 128)
            for a in predict(model, tasks[start:start + 128], min_confidence=min_confidence,
                             max_residual=max_residual)]


def _fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate(model: GeometricReasoner, *, count: int = 128, seed: int = 8675309,
             min_confidence: float = .6, max_residual: float = .15) -> dict:
    if type(count) is not int or not 1 <= count <= 10_000:
        raise ValueError("count must be in 1..10000")
    if not all(math.isfinite(x) and 0 <= x <= 1 for x in (min_confidence, max_residual)):
        raise ValueError("evaluation thresholds must be in [0,1]")
    torch.set_num_threads(1)
    started = time.perf_counter()
    datasets = evaluation_sets(count, seed)
    rng = random.Random(seed + 1)
    results = {}
    for name, tasks in datasets.items():
        expected = [oracle(t)[0] for t in tasks]
        predictions = raw_labels(model, tasks)
        advice = _advice(model, tasks, min_confidence, max_residual)
        accepted = sum(a["status"] == "ok" for a in advice)
        accepted_correct = sum(a["status"] == "ok" and a["label"] == y for a, y in zip(advice, expected))
        row = {"count": len(tasks), "correct": sum(p == y for p, y in zip(predictions, expected)),
               "accepted": accepted, "accepted_correct": accepted_correct,
               "coverage": _fraction(accepted, len(tasks)),
               "selective_accuracy": _fraction(accepted_correct, accepted),
               "accuracy_including_abstentions": _fraction(accepted_correct, len(tasks))}
        row["raw_accuracy"] = row["correct"] / len(tasks)
        renamed = [rename_and_reorder(t, rng) for t in tasks]
        renamed_predictions = raw_labels(model, renamed)
        row["rename_reorder_consistency"] = sum(a == b for a, b in zip(predictions, renamed_predictions)) / len(tasks)
        if name != "cyclic_grid":
            pairs, originals, pair_expected, original_expected = [], [], [], []
            for task, pred, y in zip(tasks, predictions, expected):
                try:
                    changed = counterfactual(task, rng)
                except ValueError:
                    continue
                pairs.append(changed)
                originals.append(pred)
                original_expected.append(y)
                pair_expected.append(oracle(changed)[0])
            changed_predictions = raw_labels(model, pairs) if pairs else []
            both = sum(a == y and b == z for a, b, y, z in
                       zip(originals, changed_predictions, original_expected, pair_expected))
            row.update({"eligible_pairs": len(pairs), "ineligible_for_one_edge_flip": len(tasks) - len(pairs),
                "both_correct": both, "paired_accuracy": _fraction(both, len(pairs)),
                "counterfactual_accuracy": _fraction(sum(a == b for a, b in zip(changed_predictions, pair_expected)), len(pairs)),
                "answer_change_rate": _fraction(sum(a != b for a, b in zip(originals, changed_predictions)), len(pairs))})
        results[name] = row
    # Explicit negative controls, checked using model diagnostics rather than the oracle at inference.
    negative = [Task(("A", "B", "C"), (Fact("A", "E", "B"),), ("A", "C")),
                Task(("A", "B"), (Fact("A", "E", "B"), Fact("A", "W", "B")), ("A", "B"))]
    controls = _advice(model, negative, min_confidence, max_residual)
    return {"version": "adiona-geometric-evaluation-v1", "model_digest": model.fingerprint,
        "scope": "exploratory synthetic evaluation; not an AGI or Sophontic replication claim",
        "eval_seed": seed, "samples_per_family": count, "min_confidence": min_confidence,
        "max_relative_residual": max_residual, "seconds": time.perf_counter() - started,
        "families": results, "negative_controls": {
            "disconnected_status": controls[0]["status"], "contradictory_status": controls[1]["status"]},
        "limitations": ["IID draws may repeat training semantics under new entity names.",
            "Composition holdout excludes two ordered generator step pairs, not their algebraic equivalents.",
            "Depth and tree/grid generator families are absent from training; all share unit-grid semantics.",
            "Paired correctness is conditional on existence of a one-edge answer-changing perturbation.",
            "Softmax confidence is uncalibrated; residual-based inconsistency detection is heuristic.",
            "Fixed graph integration and sign decoding provide substantial inductive structure.",
            "Geometry supervision consumes oracle coordinates beyond the task-only answer labels.",
            "Equal examples and steps do not establish equal compute or energy.",
            "One seed's examples are not independent training replications."]}
