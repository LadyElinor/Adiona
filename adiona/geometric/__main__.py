"""Local train, evaluate, infer, and inert-proposal demonstration commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from adiona.canonical import Rejected
from .contracts import Fact, Task


def demo_task() -> Task:
    return Task(("A", "B", "C"), (Fact("A", "E", "B"), Fact("B", "N", "C")), ("A", "C"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Adiona Geometric Reasoner: synthetic research prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    train_parser = commands.add_parser("train", help="train a fresh CPU model")
    train_parser.add_argument("--output", type=Path, required=True)
    train_parser.add_argument("--seed", type=int, default=7)
    train_parser.add_argument("--steps", type=int, default=1200)
    train_parser.add_argument("--dimension", type=int, default=16)
    train_parser.add_argument("--geometry-weight", type=float, default=.2)
    train_parser.add_argument("--no-curriculum", action="store_true")
    for command in ("evaluate", "infer", "demo"):
        sub = commands.add_parser(command)
        sub.add_argument("--model", type=Path, required=True)
        sub.add_argument("--min-confidence", type=float, default=.6)
        sub.add_argument("--max-residual", type=float, default=.15)
        if command == "evaluate":
            sub.add_argument("--count", type=int, default=128)
            sub.add_argument("--seed", type=int, default=8675309)
            sub.add_argument("--output", type=Path)
        elif command == "infer":
            sub.add_argument("--task", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        from .model import load_model, predict
        if args.command == "train":
            from .training import train_to_file
            result = train_to_file(args.output, seed=args.seed, steps=args.steps, dimension=args.dimension,
                                   geometry_weight=args.geometry_weight, curriculum=not args.no_curriculum)
        else:
            model, metadata = load_model(args.model)
            thresholds = {"min_confidence": args.min_confidence, "max_residual": args.max_residual}
            if args.command == "evaluate":
                from .evaluation import evaluate
                result = evaluate(model, count=args.count, seed=args.seed, **thresholds)
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            elif args.command == "infer":
                with args.task.open("r", encoding="utf-8") as handle:
                    task = Task.from_json(handle.read(262145))
                result = predict(model, [task], **thresholds)[0].body()
            else:
                from adiona.identity import demo_identities
                from adiona.kernel import Kernel
                from .adapter import propose_advice
                task = demo_task()
                advice = predict(model, [task], **thresholds)[0]
                keys, credentials = demo_identities()
                with tempfile.TemporaryDirectory(prefix="adiona-geometric-") as tmp:
                    kernel = Kernel(str(Path(tmp) / "sandbox.sqlite3"), keys)
                    before = kernel.snapshot()
                    action = propose_advice(kernel, credentials["worker"], task, advice)
                    decision = kernel.decide(credentials["decider"], action, [])
                    denied = False
                    try:
                        kernel.commit(credentials["executor"], action, "ALLOW")
                    except Rejected:
                        denied = True
                    result = {"task": task.body(), "advice": advice.body(), "proposal_digest": action.digest,
                        "decision_without_assessments": decision.body()["decision"],
                        "execution_without_capability_rejected": denied,
                        "world_unchanged": kernel.snapshot() == before,
                        "production_cleared": False, "assessments_generated_by_model": 0}
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except ModuleNotFoundError as exc:
        if exc.name in ("torch", "numpy"):
            print("Install the optional research runtime: python -m pip install -e '.[geometric]'", file=sys.stderr)
            return 2
        raise
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        print(f"Geometric reasoning error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
