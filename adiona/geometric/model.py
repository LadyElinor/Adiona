"""Trainable relation geometry with a fixed differentiable graph integration layer."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import Advice, RELATIONS, Task


def tensorize(tasks: list[Task]) -> dict[str, torch.Tensor]:
    """Topology only. No oracle, relation displacement table, or labels are used."""
    if not tasks or len(tasks) > 512:
        raise ValueError("batch size must be between 1 and 512")
    n, e, b = max(len(t.entities) for t in tasks), max(len(t.facts) for t in tasks), len(tasks)
    incidence = torch.zeros(b, e, n)
    relations = torch.zeros(b, e, dtype=torch.long)
    edge_mask, node_mask = torch.zeros(b, e), torch.zeros(b, n)
    anchors = torch.zeros(b, n)
    query = torch.zeros(b, 2, dtype=torch.long)
    connected = torch.zeros(b, dtype=torch.bool)
    for k, task in enumerate(tasks):
        index = {name: i for i, name in enumerate(task.entities)}
        parent = list(range(len(index)))

        def root(i):
            while parent[i] != i:
                i = parent[i]
            return i

        for j, fact in enumerate(task.facts):
            u, v = index[fact.subject], index[fact.object]
            incidence[k, j, u] += 1
            incidence[k, j, v] -= 1
            relations[k, j] = RELATIONS.index(fact.relation)
            edge_mask[k, j] = 1
            ru, rv = root(u), root(v)
            parent[max(ru, rv)] = min(ru, rv)
        node_mask[k, :len(index)] = 1
        # Fix one origin in every component, including padded singleton nodes.
        for i in range(n):
            if i >= len(index) or root(i) == i:
                anchors[k, i] = 1
        query[k] = torch.tensor([index[x] for x in task.query])
        connected[k] = root(index[task.query[0]]) == root(index[task.query[1]])
    laplacian = incidence.transpose(1, 2) @ incidence + torch.diag_embed(anchors)
    # This operator is topology-derived and does not carry semantic labels.
    integration = torch.linalg.solve(laplacian, incidence.transpose(1, 2))
    return {"incidence": incidence, "integration": integration, "relations": relations,
            "edge_mask": edge_mask, "node_mask": node_mask, "query": query, "connected": connected}


class GeometricReasoner(nn.Module):
    """180 learned parameters at dimension 16; the graph solver is an explicit prior."""
    def __init__(self, dimension: int = 16):
        super().__init__()
        if type(dimension) is not int or not 2 <= dimension <= 64:
            raise ValueError("dimension must be an integer from 2 to 64")
        self.dimension = dimension
        self.relations = nn.Embedding(len(RELATIONS), dimension)
        nn.init.normal_(self.relations.weight, std=.15)
        self.readout = nn.Linear(dimension, 2, bias=False)
        self.log_slope = nn.Parameter(torch.ones(2))
        self.zero_bias = nn.Parameter(torch.ones(2))

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        r = self.relations(batch["relations"]) * batch["edge_mask"].unsqueeze(-1)
        z = batch["integration"] @ r
        index = torch.arange(len(z), device=z.device)
        delta = z[index, batch["query"][:, 0]] - z[index, batch["query"][:, 1]]
        xy = self.readout(delta)
        signed = xy * (F.softplus(self.log_slope) + 1)
        middle = (F.softplus(self.zero_bias) + .25).expand_as(signed)
        axis_logits = torch.stack((-signed, middle, signed), dim=-1)
        # Joint class probabilities factor over horizontal and vertical signs.
        logp = F.log_softmax(axis_logits, dim=-1)
        logits = (logp[:, 1, :, None] + logp[:, 0, None, :]).reshape(-1, 9)
        residual = (batch["incidence"] @ z - r).square().sum((1, 2))
        energy = r.square().sum((1, 2)).clamp_min(1e-8)
        return {"logits": logits, "latent": z, "xy": xy,
                "relative_residual": (residual / energy).clamp_min(0).sqrt()}

    def weight_payload(self) -> dict:
        return {"dimension": self.dimension,
                "state": {key: value.detach().cpu().tolist() for key, value in self.state_dict().items()}}

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.weight_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode()).hexdigest()


def geometry_loss(latent: torch.Tensor, coordinates: torch.Tensor, node_mask: torch.Tensor) -> torch.Tensor:
    """Full anchored Gram supervision, with scale normalization by target energy."""
    mask = node_mask[:, :, None] * node_mask[:, None, :]
    predicted, target = latent @ latent.transpose(1, 2), coordinates @ coordinates.transpose(1, 2)
    numerator = ((predicted - target).square() * mask).sum((1, 2))
    denominator = (target.square() * mask).sum((1, 2)).clamp_min(1)
    return (numerator / denominator).mean()


def save_model(model: GeometricReasoner, path: str | Path, metadata: dict) -> None:
    value = {"version": "adiona-geometric-model-v1", "model": model.weight_payload(),
             "model_digest": model.fingerprint, "metadata": metadata}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_model(path: str | Path) -> tuple[GeometricReasoner, dict]:
    """JSON tensor weights only; never unpickle a downloaded model."""
    path = Path(path)
    with path.open("rb") as handle:
        raw = handle.read(512_001)
    if len(raw) > 512_000:
        raise ValueError("checkpoint exceeds 512 KB limit")

    def pairs(items):
        out = {}
        for key, val in items:
            if key in out:
                raise ValueError("duplicate checkpoint key")
            out[key] = val
        return out

    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite checkpoint")))
    if not isinstance(value, dict) or set(value) != {"version", "model", "model_digest", "metadata"}:
        raise ValueError("invalid checkpoint fields")
    if value["version"] != "adiona-geometric-model-v1" or not isinstance(value["metadata"], dict):
        raise ValueError("invalid checkpoint version or metadata")
    spec = value["model"]
    if not isinstance(spec, dict) or set(spec) != {"dimension", "state"}:
        raise ValueError("invalid model specification")
    model = GeometricReasoner(spec["dimension"])
    expected = model.state_dict()
    if not isinstance(spec["state"], dict) or set(spec["state"]) != set(expected):
        raise ValueError("unexpected checkpoint tensor names")
    state = {}
    for key, target in expected.items():
        tensor = torch.tensor(spec["state"][key], dtype=target.dtype)
        if tensor.shape != target.shape or not torch.isfinite(tensor).all():
            raise ValueError("invalid tensor shape or value")
        state[key] = tensor
    model.load_state_dict(state, strict=True)
    if model.fingerprint != value["model_digest"]:
        raise ValueError("checkpoint model digest mismatch")
    model.eval()
    return model, value["metadata"]


@torch.no_grad()
def predict(model: GeometricReasoner, tasks: list[Task], *, min_confidence: float = .6,
            max_residual: float = .15) -> list[Advice]:
    if (not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1
            or not math.isfinite(max_residual) or not 0 <= max_residual <= 1):
        raise ValueError("thresholds must be finite probabilities")
    batch = tensorize(tasks)
    output = model(batch)
    if any(not torch.isfinite(v).all() for v in output.values()):
        raise ValueError("nonfinite model output")
    confidence, labels = output["logits"].exp().max(-1)
    fingerprint = model.fingerprint
    result = []
    for i, task in enumerate(tasks):
        conf, residual = float(confidence[i]), float(output["relative_residual"][i])
        status = ("disconnected" if not batch["connected"][i] else
                  "inconsistent" if residual > max_residual else
                  "uncertain" if conf < min_confidence else "ok")
        result.append(Advice.build({"version": "adiona-geometric-advice-v1", "admissible_use": "proposal_only",
            "task_digest": task.digest, "model_digest": fingerprint, "status": status,
            "label": RELATIONS[int(labels[i])] if status == "ok" else None,
            "confidence_ppm": round(conf * 1_000_000) if status not in ("disconnected", "inconsistent") else 0,
            "residual_ppm": round(min(residual, 1) * 1_000_000)}))
    return result
