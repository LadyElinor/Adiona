"""Derive inspectable tables and figures from the frozen experiment outputs."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adiona.geometric_v2.experiment import source_hashes, sha, write_json
    base = ROOT / "reports/geometric_v2"
    output = base / "experiment"
    config = json.loads((base / "protocol.json").read_text())
    training = json.loads((output / "training-manifest.json").read_text())
    results = json.loads((output / "results.json").read_text())
    summary = json.loads((output / "summary.json").read_text())
    frozen = json.loads((base / "freeze.json").read_text())
    training_index = {r["run_id"]: r for r in training["runs"]}
    results_index = {(r["architecture"], r["training_size"], r["seed"], r["geometry_weight"]): r for r in results["runs"]}
    checks = {
        "source_matches_freeze": source_hashes() == frozen["source_sha256"] == training["source_sha256"],
        "protocol_matches_freeze": sha(base / "protocol.json") == frozen["protocol_sha256"] == training["protocol_sha256"] == results["protocol_sha256"],
        "results_bind_training_manifest": sha(output / "training-manifest.json") == results["training_manifest_sha256"],
        "final_tasks_match_recorded_hash": sha(output / "final-tasks.json") == results["final_tasks_sha256"],
        "all_checkpoint_hashes_match": all(sha(output / r["checkpoint"]) == r["checkpoint_sha256"] for r in training["runs"]),
        "all_recorded_model_digests_match": all(r["model_digest"] == training_index[r["run_id"]]["model_digest"] for r in results["runs"]),
        "sixty_training_and_scored_runs": len(training["runs"]) == len(results["runs"]) == 60,
    }
    paired = []
    for architecture in config["architectures"]:
        for n in config["training_sizes"]:
            for seed in config["model_seeds"]:
                rows = [training_index[results_index[(architecture, n, seed, w)]["run_id"]] for w in config["geometry_weights"]]
                paired.append(all(rows[0][key] == rows[1][key] for key in
                    ("initial_model_digest", "batch_sequence_digest", "training_task_digest", "examples_seen", "facts_seen", "nodes_seen")))
    checks["all_thirty_objective_pairs_matched"] = all(paired)
    # Recompute the primary contrast independently of the summary routine.
    seed_deltas = [statistics.mean(results_index[("learned", n, seed, .2)]["primary_score"] -
                                  results_index[("learned", n, seed, 0.)]["primary_score"]
                                  for n in config["training_sizes"]) for seed in config["model_seeds"]]
    checks["primary_arithmetic_reproduced"] = abs(statistics.mean(seed_deltas) - summary["primary_mean_difference"]) < 1e-12
    checks["decision_gate_reproduced"] = summary["gate_passed"] == (statistics.mean(seed_deltas) >= .05 and min(seed_deltas) > 0)
    raw_checks, secondary_checks = [], []
    from adiona.geometric.contracts import RELATIONS
    final = json.loads((output / "final-tasks.json").read_text())
    for row in results["runs"]:
        predictions = json.loads((output / "predictions" / (row["run_id"] + ".json")).read_text())
        for family, records in final.items():
            expected = [RELATIONS.index(r["answer"]) for r in records]
            saved = predictions[family]
            guessed = saved["labels"]
            measured = row["families"][family]
            raw_checks.append(len(guessed) == len(expected) and sum(a == b for a, b in zip(expected, guessed)) == measured["correct"])
            accepted = [i for i, c in enumerate(saved["confidence"]) if c >= config["min_confidence"]]
            eligible = [i for i, r in enumerate(records) if r["changed"] is not None]
            changed_expected = [RELATIONS.index(records[i]["changed_answer"]) for i in eligible]
            both = sum(guessed[i] == expected[i] and y == p for i, y, p in zip(eligible, changed_expected, saved["changed_labels"]))
            secondary_checks.append(len(accepted) == measured["accepted"] and
                sum(guessed[i] == expected[i] for i in accepted) == measured["accepted_correct"] and
                eligible == saved["eligible_pair_indexes"] and len(eligible) == measured["eligible_pairs"] and
                len(saved["changed_labels"]) == len(eligible) and both == measured["both_correct"] and
                sum(a == b for a, b in zip(guessed, saved["renamed_labels"])) / len(guessed) == measured["rename_reorder_consistency"])
    checks["all_three_hundred_raw_accuracy_counts_reproduced"] = all(raw_checks)
    checks["all_secondary_coverage_pair_and_invariance_counts_reproduced"] = all(secondary_checks)
    write_json(base / "integrity-audit.json", {"checks": checks, "passed": all(checks.values()),
              "scope": "local deterministic audit; hashes are integrity bindings, not independent authentication"})
    if not all(checks.values()):
        raise RuntimeError("experiment integrity check failed")
    flat = []
    for row in results["runs"]:
        train = training_index[row["run_id"]]
        for family, metrics in row["families"].items():
            flat.append({"run_id": row["run_id"], "architecture": row["architecture"],
                "training_size": row["training_size"], "seed": row["seed"], "geometry_weight": row["geometry_weight"],
                "parameters": train["parameters"], "training_seconds": train["training_seconds"],
                "training_accuracy": train["training_accuracy"], "dev_accuracy": train["history"][-1]["dev_accuracy"],
                "primary_score": row["primary_score"], "family": family, **metrics, **row["latency"]})
    with (base / "metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    arm_stats = []
    for architecture in config["architectures"]:
        for weight in config["geometry_weights"]:
            rows = [r for r in results["runs"] if r["architecture"] == architecture and r["geometry_weight"] == weight]
            fitted = [training_index[r["run_id"]] for r in rows]
            arm_stats.append({"architecture": architecture, "geometry_weight": weight, "parameters": fitted[0]["parameters"],
                "mean_primary_score": statistics.mean(r["primary_score"] for r in rows),
                "mean_training_seconds": statistics.mean(r["training_seconds"] for r in fitted),
                "mean_train_accuracy": statistics.mean(r["training_accuracy"] for r in fitted),
                "mean_forward_ms": statistics.mean(r["latency"]["forward_ms_per_example"] for r in rows),
                "mean_preprocess_ms": statistics.mean(r["latency"]["preprocess_ms_per_example"] for r in rows),
                "min_rename_consistency": min(m["rename_reorder_consistency"] for r in rows for m in r["families"].values()),
                "families": {f: {metric: statistics.mean(r["families"][f][metric] for r in rows if r["families"][f][metric] is not None)
                                 for metric in ("raw_accuracy", "coverage", "selective_accuracy", "accuracy_including_abstentions")
                                 if any(r["families"][f][metric] is not None for r in rows)}
                             for f in final}})
    write_json(base / "aggregate-metrics.json", {"arms": arm_stats,
              "total_training_seconds": sum(r["training_seconds"] for r in training["runs"]),
              "all_metric_means": "Equal model weighting, not independent population estimates"})
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    colors = ["#89929d", "#171c24", "#d17732", "#087e8b"]
    arms = [(a, w) for a in config["architectures"] for w in config["geometry_weights"]]
    labels = ["Fixed / answer", "Fixed / + geometry", "Learned / answer", "Learned / + geometry"]
    fig, ax = plt.subplots(figsize=(9, 5.3), layout="constrained")
    for arm, ((architecture, weight), label, color) in enumerate(zip(arms, labels, colors)):
        means, low, high = [], [], []
        for n in config["training_sizes"]:
            values = [100*results_index[(architecture, n, seed, weight)]["primary_score"] for seed in config["model_seeds"]]
            means.append(statistics.mean(values)); low.append(means[-1]-min(values)); high.append(max(values)-means[-1])
        xs = [i + (arm - 1.5)*.19 for i in range(3)]
        ax.bar(xs, means, width=.18, color=color, label=label, yerr=[low, high], capsize=3)
    ax.set(xticks=range(3), xticklabels=config["training_sizes"], ylim=(0, 105),
           xlabel="Training tasks", ylabel="Mean transfer accuracy (%)",
           title="AGRM v2: learned integration exposes an unsaturated comparison")
    ax.legend(loc="lower right", fontsize=9)
    fig.supxlabel("Depth-OOD + tree macro-average. Bars: five seeds; whiskers: observed seed range.", fontsize=9)
    fig.savefig(base / "transfer.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.1), sharey=True, layout="constrained")
    for ax, n in zip(axes, config["training_sizes"]):
        for (architecture, weight), label, color in zip(arms, labels, colors):
            rows = [r for r in training["runs"] if r["architecture"] == architecture and r["geometry_weight"] == weight and r["training_size"] == n]
            steps = [r["step"] for r in rows[0]["history"]]
            values = [100*statistics.mean(r["history"][i]["dev_accuracy"] for r in rows) for i in range(len(steps))]
            ax.plot(steps, values, color=color, marker="o", label=label, linewidth=1.7, markersize=3)
        ax.set(title=f"{n} training tasks", xlabel="Optimizer steps", ylim=(0,105), xticks=[0,150,300,450,600])
    axes[0].set_ylabel("Development accuracy (%)")
    axes[2].legend(fontsize=8, loc="lower right")
    fig.suptitle("Learning curves on 96 development tasks; means over five initialization seeds")
    fig.savefig(base / "learning-curves.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"audit_passed": all(checks.values()), "metric_rows": len(flat), "arms": arm_stats}, indent=2))


if __name__ == "__main__":
    main()
