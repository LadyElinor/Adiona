"""CPU-reproducible curriculum training and task-only control."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
import random
import time

import torch
from torch.nn import functional as F

from .contracts import RELATIONS
from .data import oracle, training_pool
from .model import GeometricReasoner, geometry_loss, save_model, tensorize


def source_fingerprints() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}


def train(*, seed: int = 7, steps: int = 1200, dimension: int = 16,
          geometry_weight: float = .2, curriculum: bool = True,
          batch_size: int = 64, data_seed: int = 1729,
          learning_rate: float = .02) -> tuple[GeometricReasoner, dict]:
    if type(steps) is not int or not 1 <= steps <= 100_000:
        raise ValueError("steps must be in 1..100000")
    if type(batch_size) is not int or not 1 <= batch_size <= 512:
        raise ValueError("batch size must be in 1..512")
    if not math.isfinite(geometry_weight) or geometry_weight < 0:
        raise ValueError("geometry weight must be finite and nonnegative")
    if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
        raise ValueError("learning rate must be in (0,1]")
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    rng = random.Random(seed)
    started = time.perf_counter()
    tasks = training_pool(data_seed)
    all_batch = tensorize(tasks)
    labels = []
    coordinates = torch.zeros(len(tasks), all_batch["node_mask"].shape[1], 2)
    for i, task in enumerate(tasks):
        answer, coords, status = oracle(task)
        if status != "ok":
            raise ValueError("training generator produced an unsupported task")
        labels.append(RELATIONS.index(answer))
        coordinates[i, :len(coords)] = torch.tensor(coords)
    labels = torch.tensor(labels, dtype=torch.long)
    model = GeometricReasoner(dimension)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    history = []
    examples_seen = facts_seen = 0
    for step in range(steps):
        stage = min(4, 1 + 4 * step // steps) if curriculum else 4
        # training_pool is grouped by depth; the available pool is identical in
        # both objective arms. A no-curriculum run changes only this sampling rule.
        indexes = torch.tensor([rng.randrange(stage * 128) for _ in range(batch_size)])
        batch = {key: value[indexes] for key, value in all_batch.items()}
        output = model(batch)
        task_loss = F.nll_loss(output["logits"], labels[indexes])
        geometric = geometry_loss(output["latent"], coordinates[indexes], batch["node_mask"])
        loss = task_loss + geometry_weight * geometric
        if not torch.isfinite(loss):
            raise RuntimeError("nonfinite training loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10, error_if_nonfinite=True)
        optimizer.step()
        examples_seen += batch_size
        facts_seen += int(batch["edge_mask"].sum())
        if step == 0 or (step + 1) % 100 == 0 or step + 1 == steps:
            history.append({"step": step + 1, "max_depth": stage, "task_loss": float(task_loss.detach()),
                            "geometry_loss": float(geometric.detach()), "loss": float(loss.detach())})
    model.eval()
    metadata = {"scope": "synthetic unit-grid relations; exploratory research",
        "seed": seed, "data_seed": data_seed, "steps": steps, "batch_size": batch_size,
        "learning_rate": learning_rate, "geometry_weight": geometry_weight,
        "curriculum": curriculum, "dimension": dimension,
        "parameters": sum(p.numel() for p in model.parameters()), "training_examples": len(tasks),
        "examples_seen": examples_seen, "facts_seen": facts_seen,
        "training_task_digest": hashlib.sha256("\n".join(t.digest for t in tasks).encode()).hexdigest(),
        "seconds": time.perf_counter() - started, "python": platform.python_version(),
        "torch": str(torch.__version__), "device": "cpu", "threads": 1,
        "source_sha256": source_fingerprints(), "history": history,
        "selection": "fixed final step; no evaluation-driven checkpoint selection",
        "production_cleared": False}
    return model, metadata


def train_to_file(path: str | Path, **kwargs) -> dict:
    model, metadata = train(**kwargs)
    save_model(model, path, metadata)
    return {"checkpoint": str(path), "model_digest": model.fingerprint, **metadata}
