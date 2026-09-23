"""Frozen four-arm integrator ablation, with separate fit and score stages."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import random
import time
from datetime import datetime, timezone

import torch
from torch.nn import functional as F

from adiona.geometric.contracts import RELATIONS, Task
from adiona.geometric.data import chain, counterfactual, evaluation_sets, oracle, rename_and_reorder, training_pool
from adiona.geometric.model import geometry_loss
from .model import AblationModel, load_model, save_model, tensorize


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def source_hashes() -> dict:
    root = Path(__file__).resolve().parents[2]
    return {str(p.relative_to(root)): sha(p) for directory in (root / "adiona/geometric", root / "adiona/geometric_v2")
            for p in sorted(directory.glob("*.py"))}


def protocol(path: Path) -> tuple[dict, str]:
    value = json.loads(path.read_text())
    if value["version"] != "agrm-integrator-ablation-v2":
        raise ValueError("unsupported protocol")
    return value, sha(path)


def pool_for_size(pool: list[Task], size: int) -> list[Task]:
    if type(size) is not int or size % 4 or not 4 <= size <= 512:
        raise ValueError("size must be a multiple of four in 4..512")
    per = size // 4
    return [task for depth in range(4) for task in pool[depth * 128:depth * 128 + per]]


def targets(tasks: list[Task], batch: dict) -> tuple[torch.Tensor, torch.Tensor]:
    coords = torch.zeros(len(tasks), batch["node_mask"].shape[1], 2)
    labels = []
    for i, task in enumerate(tasks):
        answer, positions, status = oracle(task)
        if status != "ok":
            raise ValueError("training task is not supported")
        labels.append(RELATIONS.index(answer))
        coords[i, :len(positions)] = torch.tensor(positions)
    # Match each architecture's identical query-reference gauge.
    reference = coords.gather(1, batch["anchor_index"].unsqueeze(-1).expand(-1, -1, 2))
    coords = (coords - reference) * batch["node_mask"].unsqueeze(-1)
    return torch.tensor(labels), coords


@torch.no_grad()
def forward_tasks(model: AblationModel, tasks: list[Task]) -> tuple[list[int], list[float]]:
    guesses, confidence = [], []
    for start in range(0, len(tasks), 64):
        out = model(tensorize(tasks[start:start + 64], model.architecture))
        if not torch.isfinite(out["logits"]).all():
            raise RuntimeError("nonfinite evaluation output")
        p, y = out["logits"].exp().max(-1)
        guesses.extend(y.tolist())
        confidence.extend(p.tolist())
    return guesses, confidence


def train_one(config: dict, architecture: str, weight: float, size: int, seed: int,
              tasks: list[Task], dev_tasks: list[Task]) -> tuple[AblationModel, dict]:
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    rng = random.Random(seed)
    started = time.perf_counter()
    batch = tensorize(tasks, architecture)
    labels, coords = targets(tasks, batch)
    model = AblationModel(architecture, config["dimension"], config["message_rounds"])
    initial_digest = model.fingerprint
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    setup_seconds = time.perf_counter() - started
    dev_expected = [RELATIONS.index(oracle(t)[0]) for t in dev_tasks]
    history, train_seconds, dev_seconds = [], 0., 0.
    examples_seen = facts_seen = nodes_seen = 0
    sample_hash = hashlib.sha256()

    def log(step, loss=None, geometric=None):
        nonlocal dev_seconds
        before = time.perf_counter()
        guessed, _ = forward_tasks(model, dev_tasks)
        row = {"step": step, "dev_accuracy": sum(a == b for a, b in zip(guessed, dev_expected)) / len(dev_tasks)}
        if loss is not None:
            row.update(answer_loss=loss, geometry_loss=geometric)
        history.append(row)
        dev_seconds += time.perf_counter() - before

    log(0)
    for step in range(config["steps"]):
        before = time.perf_counter()
        stage = min(4, 1 + 4 * step // config["steps"])
        indexes = [rng.randrange(stage * (size // 4)) for _ in range(config["batch_size"])]
        sample_hash.update(json.dumps(indexes, separators=(",", ":")).encode() + b"\n")
        index = torch.tensor(indexes)
        current = {k: v[index] for k, v in batch.items()}
        out = model(current)
        answer_loss = F.nll_loss(out["logits"], labels[index])
        geometric = geometry_loss(out["latent"], coords[index], current["node_mask"])
        loss = answer_loss + weight * geometric
        if not torch.isfinite(loss):
            raise RuntimeError("nonfinite training loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10, error_if_nonfinite=True)
        optimizer.step()
        examples_seen += len(indexes)
        facts_seen += int(current["edge_mask"].sum())
        nodes_seen += int(current["node_mask"].sum())
        train_seconds += time.perf_counter() - before
        if step + 1 in config["curve_steps"]:
            log(step + 1, float(answer_loss.detach()), float(geometric.detach()))
    model.eval()
    train_guesses, _ = forward_tasks(model, tasks)
    metadata = {"architecture": architecture, "geometry_weight": weight, "training_size": size,
        "seed": seed, "initial_model_digest": initial_digest, "batch_sequence_digest": sample_hash.hexdigest(),
        "training_task_digest": hashlib.sha256("\n".join(t.digest for t in tasks).encode()).hexdigest(),
        "label_histogram": dict(Counter(RELATIONS[int(i)] for i in labels)),
        "parameters": sum(p.numel() for p in model.parameters()),
        "rounds": model.rounds, "steps": config["steps"], "examples_seen": examples_seen,
        "facts_seen": facts_seen, "nodes_seen": nodes_seen, "setup_seconds": setup_seconds,
        "training_seconds": train_seconds, "development_evaluation_seconds": dev_seconds,
        "total_seconds": time.perf_counter() - started,
        "training_accuracy": sum(a == b for a, b in zip(train_guesses, labels.tolist())) / size,
        "history": history, "torch": str(torch.__version__), "python": platform.python_version(),
        "device": "cpu", "threads": 1, "checkpoint_selection": "fixed final step"}
    return model, metadata


def fit(protocol_path: Path, output: Path) -> dict:
    config, protocol_digest = protocol(protocol_path)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty; preserve completed or failed attempts")
    frozen_sources = source_hashes()
    pool = training_pool(config["data_seed"])
    dev_rng = random.Random(config["development_seed"])
    dev = [chain(dev_rng, dev_rng.randint(1, 4)) for _ in range(config["development_count"])]
    write_json(output / "training-pool.json", [t.body() for t in pool])
    write_json(output / "development-tasks.json", [t.body() for t in dev])
    runs = []
    for size in config["training_sizes"]:
        tasks = pool_for_size(pool, size)
        for architecture in config["architectures"]:
            for seed in config["model_seeds"]:
                for weight in config["geometry_weights"]:
                    stem = f"{architecture}-n{size}-s{seed}-g{weight:g}"
                    model, metadata = train_one(config, architecture, weight, size, seed, tasks, dev)
                    metadata.update(protocol_sha256=protocol_digest, source_sha256=frozen_sources)
                    checkpoint = output / "checkpoints" / f"{stem}.json"
                    save_model(model, checkpoint, metadata)
                    row = {"run_id": stem, "checkpoint": str(checkpoint.relative_to(output)),
                           "checkpoint_sha256": sha(checkpoint), "model_digest": model.fingerprint, **metadata}
                    runs.append(row)
                    # Retain every completed run, even if a subsequent run fails.
                    write_json(output / "fit-progress.json", {"completed": len(runs), "runs": runs})
                    print(json.dumps({"stage": "fit", "run_id": stem, "train_accuracy": metadata["training_accuracy"],
                                      "dev_accuracy": metadata["history"][-1]["dev_accuracy"],
                                      "seconds": round(metadata["training_seconds"], 2)}), flush=True)
    manifest = {"protocol_sha256": protocol_digest, "source_sha256": frozen_sources,
                "final_evaluation_accessed": False, "runs": runs,
                "pool_sha256": sha(output / "training-pool.json"),
                "development_sha256": sha(output / "development-tasks.json")}
    write_json(output / "training-manifest.json", manifest)
    return manifest


@torch.no_grad()
def benchmark_latency(model: AblationModel, tasks: list[Task]) -> dict:
    tasks = tasks[:32]
    batch = tensorize(tasks, model.architecture)
    model(batch)
    prep, forward = 0., 0.
    for _ in range(3):
        start = time.perf_counter()
        batch = tensorize(tasks, model.architecture)
        middle = time.perf_counter()
        model(batch)
        end = time.perf_counter()
        prep += middle - start
        forward += end - middle
    return {"batch_size": len(tasks), "repeats": 3,
            "preprocess_ms_per_example": 1000 * prep / (3 * len(tasks)),
            "forward_ms_per_example": 1000 * forward / (3 * len(tasks))}


def score(protocol_path: Path, output: Path) -> dict:
    config, protocol_digest = protocol(protocol_path)
    manifest = json.loads((output / "training-manifest.json").read_text())
    if (output / "score-start.json").exists() or (output / "results.json").exists():
        raise ValueError("scoring already started; preserve the attempt and record any recovery separately")
    if manifest["protocol_sha256"] != protocol_digest or manifest["source_sha256"] != source_hashes():
        raise ValueError("protocol or implementation changed after fitting")
    expected_runs = len(config["training_sizes"]) * len(config["architectures"]) * len(config["model_seeds"]) * len(config["geometry_weights"])
    if len(manifest["runs"]) != expected_runs:
        raise ValueError("not all declared runs were completed")
    expected_keys = {(a, n, s, w) for a in config["architectures"] for n in config["training_sizes"]
                     for s in config["model_seeds"] for w in config["geometry_weights"]}
    actual_keys = {(r["architecture"], r["training_size"], r["seed"], r["geometry_weight"]) for r in manifest["runs"]}
    if actual_keys != expected_keys:
        raise ValueError("run identities differ from the declared factorial design")
    if sha(output / "training-pool.json") != manifest["pool_sha256"] or sha(output / "development-tasks.json") != manifest["development_sha256"]:
        raise ValueError("training or development dataset changed after fitting")
    for row in manifest["runs"]:
        if sha(output / row["checkpoint"]) != row["checkpoint_sha256"]:
            raise ValueError("checkpoint changed before final scoring")
    torch.set_num_threads(1)
    write_json(output / "score-start.json", {"started_at": datetime.now(timezone.utc).isoformat(),
               "protocol_sha256": protocol_digest, "training_manifest_sha256": sha(output / "training-manifest.json")})
    # Final tasks and perturbations are generated ONLY after all models are fixed.
    datasets = evaluation_sets(config["evaluation_count"], config["evaluation_seed"])
    rng = random.Random(config["evaluation_seed"] + 1)
    final = {}
    for family, tasks in datasets.items():
        records = []
        for task in tasks:
            changed = None
            if family != "cyclic_grid":
                try:
                    changed = counterfactual(task, rng)
                except ValueError:
                    pass
            records.append({"task": task.body(), "answer": oracle(task)[0],
                            "renamed": rename_and_reorder(task, rng).body(),
                            "changed": changed.body() if changed else None,
                            "changed_answer": oracle(changed)[0] if changed else None})
        final[family] = records
    write_json(output / "final-tasks.json", final)
    results = []
    for row in manifest["runs"]:
        model, metadata = load_model(output / row["checkpoint"])
        if model.fingerprint != row["model_digest"]:
            raise ValueError("weight fingerprint mismatch")
        family_results, predictions = {}, {}
        for family, records in final.items():
            tasks = [Task.from_dict(r["task"]) for r in records]
            expected = [RELATIONS.index(r["answer"]) for r in records]
            guessed, confidence = forward_tasks(model, tasks)
            renamed = [Task.from_dict(r["renamed"]) for r in records]
            renamed_guesses, _ = forward_tasks(model, renamed)
            eligible = [i for i, r in enumerate(records) if r["changed"] is not None]
            changed = [Task.from_dict(records[i]["changed"]) for i in eligible]
            changed_guesses, _ = forward_tasks(model, changed) if changed else ([], [])
            changed_expected = [RELATIONS.index(records[i]["changed_answer"]) for i in eligible]
            both = sum(guessed[i] == expected[i] and p == y for i, p, y in zip(eligible, changed_guesses, changed_expected))
            accepted = [i for i, c in enumerate(confidence) if c >= config["min_confidence"]]
            correct = sum(a == b for a, b in zip(guessed, expected))
            accepted_correct = sum(guessed[i] == expected[i] for i in accepted)
            family_results[family] = {"count": len(tasks), "correct": correct, "raw_accuracy": correct / len(tasks),
                "accepted": len(accepted), "accepted_correct": accepted_correct,
                "coverage": len(accepted) / len(tasks),
                "selective_accuracy": accepted_correct / len(accepted) if accepted else None,
                "accuracy_including_abstentions": accepted_correct / len(tasks),
                "rename_reorder_consistency": sum(a == b for a, b in zip(guessed, renamed_guesses)) / len(tasks),
                "eligible_pairs": len(eligible), "both_correct": both,
                "paired_accuracy": both / len(eligible) if eligible else None,
                "answer_change_rate": sum(guessed[i] != p for i, p in zip(eligible, changed_guesses)) / len(eligible) if eligible else None}
            predictions[family] = {"labels": guessed, "confidence": confidence, "renamed_labels": renamed_guesses,
                                   "eligible_pair_indexes": eligible, "changed_labels": changed_guesses}
        score_value = sum(family_results[f]["raw_accuracy"] for f in config["primary_families"]) / len(config["primary_families"])
        result = {"run_id": row["run_id"], "architecture": row["architecture"],
                  "geometry_weight": row["geometry_weight"], "training_size": row["training_size"], "seed": row["seed"],
                  "model_digest": model.fingerprint, "primary_score": score_value,
                  "families": family_results, "latency": benchmark_latency(model, datasets["depth_ood"])}
        write_json(output / "predictions" / f'{row["run_id"]}.json', predictions)
        results.append(result)
        print(json.dumps({"stage": "score", "run_id": row["run_id"], "primary_score": score_value}), flush=True)
    complete = {"protocol_sha256": protocol_digest, "training_manifest_sha256": sha(output / "training-manifest.json"),
                "final_tasks_sha256": sha(output / "final-tasks.json"), "runs": results}
    write_json(output / "results.json", complete)
    return complete


def summarize(protocol_path: Path, output: Path) -> dict:
    config, protocol_digest = protocol(protocol_path)
    results = json.loads((output / "results.json").read_text())
    if results["protocol_sha256"] != protocol_digest:
        raise ValueError("protocol mismatch")
    index = {(r["architecture"], r["training_size"], r["seed"], r["geometry_weight"]): r for r in results["runs"]}
    differences, by_size = [], {}
    for seed in config["model_seeds"]:
        difference = sum(index[("learned", n, seed, .2)]["primary_score"] - index[("learned", n, seed, 0.)]["primary_score"]
                         for n in config["training_sizes"]) / len(config["training_sizes"])
        differences.append({"seed": seed, "difference": difference})
    for size in config["training_sizes"]:
        by_size[str(size)] = {architecture: {
            str(weight): sum(index[(architecture, size, seed, weight)]["primary_score"] for seed in config["model_seeds"]) / len(config["model_seeds"])
            for weight in config["geometry_weights"]} for architecture in config["architectures"]}
    mean = sum(r["difference"] for r in differences) / len(differences)
    gate = mean >= config["meaningful_improvement"] and all(r["difference"] > 0 for r in differences)
    summary = {"protocol_sha256": protocol_digest, "primary_mean_difference": mean,
               "paired_seed_differences": differences, "primary_by_size": by_size,
               "gate_passed": gate, "verdict": "RETAIN_FOR_INDEPENDENT_REPLICATION" if gate else "NO_SUPPORT_AT_PRESPECIFIED_THRESHOLD",
               "scope": "conditional on this model family, training budget, data pool, task algebra, and five initialization seeds",
               "not_established": ["equivalence or absence of any geometry benefit", "general intelligence", "compute efficiency",
                                   "benefit attributable to geometry rather than additional coordinate supervision"]}
    write_json(output / "summary.json", summary)
    return summary
