"""Explicitly optional research CLI; the dependency-free kernel does not import it."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AGRM v2 integrator ablation")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fit", "score", "summarize"):
        sub = commands.add_parser(name)
        sub.add_argument("--protocol", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
    sub = commands.add_parser("infer")
    sub.add_argument("--model", type=Path, required=True)
    sub.add_argument("--task", type=Path, required=True)
    sub.add_argument("--min-confidence", type=float, default=.6)
    args = parser.parse_args()
    try:
        from . import experiment
        from .model import load_model, predict
    except ModuleNotFoundError as error:
        if error.name == "torch":
            parser.error("optional PyTorch dependency missing; install the project's geometric extra")
        raise
    if args.command == "infer":
        from adiona.geometric.contracts import Task
        task = Task.from_json(args.task.read_text())
        model, _ = load_model(args.model)
        print(json.dumps(predict(model, [task], args.min_confidence)[0].body(), sort_keys=True))
    else:
        result = getattr(experiment, args.command)(args.protocol, args.output)
        if args.command == "summarize":
            print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
