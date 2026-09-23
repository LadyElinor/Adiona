#!/usr/bin/env python3
"""Reproduce the declared paired-seed experiment without altering shipped evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/geometric")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 19, 41])
    parser.add_argument("--steps", type=int, default=1200)
    parser.add_argument("--count", type=int, default=128)
    parser.add_argument("--no-curriculum", action="store_true")
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("training seeds must be unique")
    from adiona.geometric.training import train
    from adiona.geometric.evaluation import evaluate
    from adiona.geometric.model import save_model
    args.output.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in args.seeds:
        for weight, arm in ((0., "task-only"), (.2, "geometry")):
            model, metadata = train(seed=seed, steps=args.steps, geometry_weight=weight,
                                    curriculum=not args.no_curriculum)
            result = evaluate(model, count=args.count)
            row = {"arm": arm, "training": metadata, "evaluation": result}
            stem = f"seed{seed}-{arm}"
            (args.output / f"{stem}.json").write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            save_model(model, args.output / f"{stem}-model.json", metadata)
            runs.append({"arm": arm, "seed": seed, "training_seconds": metadata["seconds"],
                         "model_digest": model.fingerprint, "families": result["families"]})
            print(json.dumps({"seed": seed, "arm": arm, "raw_accuracy":
                              {name: data["raw_accuracy"] for name, data in result["families"].items()}}), flush=True)
    (args.output / "comparison.json").write_text(json.dumps({
        "design": "paired initialization seeds, fixed final checkpoints, shared data and evaluation seeds",
        "runs": runs, "claims": "exploratory; no calibrated population-effect or compute-efficiency claim"
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
