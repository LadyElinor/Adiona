"""Pre-freeze engineering control, separate from the research experiment."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import torch
from torch.nn import functional as F
from adiona.geometric.contracts import Fact, RELATIONS, Task
from adiona.geometric_v2.model import AblationModel, tensorize


def main():
    torch.set_num_threads(1)
    torch.manual_seed(6719)
    tasks = [Task(("A", "B"), (Fact("A", r, "B"),), ("A", "B")) for r in RELATIONS]
    batch = tensorize(tasks, "learned")
    model = AblationModel("learned", 16, 16)
    optimizer = torch.optim.Adam(model.parameters(), lr=.01)
    labels = torch.arange(9)
    history = []
    start = time.perf_counter()
    for step in range(200):
        out = model(batch)
        loss = F.nll_loss(out["logits"], labels)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 10, error_if_nonfinite=True)
        optimizer.step()
        if (step + 1) % 50 == 0:
            history.append({"step": step + 1, "loss": float(loss.detach())})
    with torch.no_grad():
        accuracy = float((model(batch)["logits"].argmax(-1) == labels).float().mean())
    report = {"scope": "engineering capacity control only; no held-out generalization claim",
              "seed": 6719, "tasks": 9, "steps": 200, "learning_rate": .01,
              "architecture": "learned", "geometry_weight": 0, "history": history,
              "training_accuracy": accuracy, "seconds": time.perf_counter() - start,
              "parameters": sum(p.numel() for p in model.parameters()), "passed": accuracy == 1.0,
              "final_evaluation_accessed": False, "attempt": 1}
    print(json.dumps(report, indent=2))
    destination = ROOT / "reports/geometric_v2/engineering-control.json"
    if destination.exists():
        raise ValueError("preserve the original control; choose another explicit artifact for a new attempt")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
