"""Matched answer heads with either fixed integration or learned local messages."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from adiona.geometric.contracts import Advice, RELATIONS, Task
from adiona.geometric.model import GeometricReasoner


def tensorize(tasks: list[Task], architecture: str) -> dict[str, torch.Tensor]:
    """Construct topology without accessing labels. Learned batches never solve a graph."""
    if architecture not in ("fixed", "learned") or not 1 <= len(tasks) <= 512:
        raise ValueError("invalid architecture or batch size")
    count, nodes, edges = len(tasks), max(len(t.entities) for t in tasks), max(len(t.facts) for t in tasks)
    incidence = torch.zeros(count, edges, nodes)
    source = torch.zeros(count, edges, dtype=torch.long)
    target = torch.zeros_like(source)
    relations = torch.zeros_like(source)
    edge_mask, node_mask = torch.zeros(count, edges), torch.zeros(count, nodes)
    anchors = torch.zeros(count, nodes)
    anchor_index = torch.zeros(count, nodes, dtype=torch.long)
    query = torch.zeros(count, 2, dtype=torch.long)
    connected = torch.zeros(count, dtype=torch.bool)
    for b, task in enumerate(tasks):
        index = {name: i for i, name in enumerate(task.entities)}
        parent = list(range(len(index)))

        def root(i):
            while i != parent[i]:
                i = parent[i]
            return i

        for e, fact in enumerate(task.facts):
            u, v = index[fact.subject], index[fact.object]
            source[b, e], target[b, e] = v, u
            incidence[b, e, u] += 1
            incidence[b, e, v] -= 1
            relations[b, e] = RELATIONS.index(fact.relation)
            edge_mask[b, e] = 1
            a, c = root(u), root(v)
            parent[max(a, c)] = min(a, c)
        qa, qb = (index[name] for name in task.query)
        query[b] = torch.tensor((qa, qb))
        connected[b] = root(qa) == root(qb)
        roots = {root(i) for i in range(len(index))}
        selected = {r: (qb if r == root(qb) else r) for r in roots}
        for i in range(nodes):
            if i < len(index):
                anchor_index[b, i] = selected[root(i)]
                anchors[b, i] = i == selected[root(i)]
                node_mask[b, i] = 1
            else:
                anchors[b, i] = 1
    batch = {"incidence": incidence, "source": source, "target": target,
             "relations": relations, "edge_mask": edge_mask, "node_mask": node_mask,
             "anchors": anchors, "anchor_index": anchor_index, "query": query, "connected": connected}
    if architecture == "fixed":
        laplacian = incidence.transpose(1, 2) @ incidence + torch.diag_embed(anchors)
        batch["integration"] = torch.linalg.solve(laplacian, incidence.transpose(1, 2))
    return batch


class AblationModel(GeometricReasoner):
    def __init__(self, architecture: str, dimension: int = 16, rounds: int = 16):
        if architecture not in ("fixed", "learned"):
            raise ValueError("architecture must be fixed or learned")
        if architecture == "learned" and (type(rounds) is not int or not 1 <= rounds <= 32):
            raise ValueError("message rounds must be in 1..32")
        super().__init__(dimension)
        self.architecture = architecture
        self.rounds = rounds if architecture == "learned" else 0
        if architecture == "learned":
            self.message = nn.Sequential(nn.Linear(3 * dimension + 2, 2 * dimension),
                                         nn.Tanh(), nn.Linear(2 * dimension, dimension))
            self.update = nn.GRUCell(dimension, dimension)
            self.geometry_projection = nn.Linear(dimension, dimension, bias=False)

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        r = self.relations(batch["relations"]) * batch["edge_mask"].unsqueeze(-1)
        if self.architecture == "fixed":
            z = batch["integration"] @ r
        else:
            # Bidirectional local messages. The sign records traversal direction;
            # the update never receives oracle coordinates or an integration matrix.
            src = torch.cat((batch["source"], batch["target"]), dim=1)
            dst = torch.cat((batch["target"], batch["source"]), dim=1)
            mask = torch.cat((batch["edge_mask"], batch["edge_mask"]), dim=1).unsqueeze(-1)
            edge = torch.cat((r, -r), dim=1)
            src_index = src.unsqueeze(-1).expand(-1, -1, self.dimension)
            dst_index = dst.unsqueeze(-1).expand(-1, -1, self.dimension)
            src_anchor = batch["anchors"].gather(1, src).unsqueeze(-1)
            dst_anchor = batch["anchors"].gather(1, dst).unsqueeze(-1)
            z = r.new_zeros(len(r), batch["node_mask"].shape[1], self.dimension)
            degree = z.new_zeros(len(r), z.shape[1], 1).scatter_add_(1, dst.unsqueeze(-1), mask)
            active = (batch["node_mask"] * (1 - batch["anchors"])).unsqueeze(-1)
            for _ in range(self.rounds):
                inputs = torch.cat((z.gather(1, src_index), z.gather(1, dst_index), edge,
                                    src_anchor, dst_anchor), dim=-1)
                messages = self.message(inputs) * mask
                aggregated = torch.zeros_like(z).scatter_add_(1, dst_index, messages) / degree.clamp_min(1)
                z = self.update(aggregated.reshape(-1, self.dimension),
                                z.reshape(-1, self.dimension)).reshape_as(z) * active
            # GRU states are bounded; a learned projection permits unbounded
            # coordinate scale without supplying an analytic graph solution.
            z = self.geometry_projection(z)
        row = torch.arange(len(z), device=z.device)
        delta = z[row, batch["query"][:, 0]] - z[row, batch["query"][:, 1]]
        xy = self.readout(delta)
        signed = xy * (F.softplus(self.log_slope) + 1)
        middle = (F.softplus(self.zero_bias) + .25).expand_as(signed)
        axis = F.log_softmax(torch.stack((-signed, middle, signed), dim=-1), dim=-1)
        logits = (axis[:, 1, :, None] + axis[:, 0, None, :]).reshape(-1, 9)
        residual = (batch["incidence"] @ z - r).square().sum((1, 2))
        energy = r.square().sum((1, 2)).clamp_min(1e-8)
        return {"logits": logits, "latent": z, "xy": xy,
                "relative_residual": (residual / energy).clamp_min(0).sqrt()}

    def weight_payload(self) -> dict:
        return {"architecture": self.architecture, "dimension": self.dimension, "rounds": self.rounds,
                "state": {k: v.detach().cpu().tolist() for k, v in self.state_dict().items()}}


def save_model(model: AblationModel, path: str | Path, metadata: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"version": "adiona-geometric-model-v2", "model": model.weight_payload(),
             "model_digest": model.fingerprint, "metadata": metadata}
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_model(path: str | Path) -> tuple[AblationModel, dict]:
    with Path(path).open("rb") as handle:
        raw = handle.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("checkpoint exceeds 2 MB limit")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate checkpoint key")
            out[key] = value
        return out

    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite checkpoint")))
    if not isinstance(value, dict) or set(value) != {"version", "model", "model_digest", "metadata"}:
        raise ValueError("invalid checkpoint fields")
    if value["version"] != "adiona-geometric-model-v2" or not isinstance(value["metadata"], dict):
        raise ValueError("invalid checkpoint version or metadata")
    spec = value["model"]
    if not isinstance(spec, dict) or set(spec) != {"architecture", "dimension", "rounds", "state"}:
        raise ValueError("invalid model fields")
    if spec["architecture"] == "fixed" and (type(spec["rounds"]) is not int or spec["rounds"] != 0):
        raise ValueError("fixed model must record zero learned message rounds")
    model = AblationModel(spec["architecture"], spec["dimension"], spec["rounds"])
    if not isinstance(spec["state"], dict) or set(spec["state"]) != set(model.state_dict()):
        raise ValueError("invalid tensor names")
    state = {}
    for key, expected in model.state_dict().items():
        tensor = torch.tensor(spec["state"][key], dtype=expected.dtype)
        if tensor.shape != expected.shape or not torch.isfinite(tensor).all():
            raise ValueError("invalid tensor shape or value")
        state[key] = tensor
    model.load_state_dict(state, strict=True)
    if model.fingerprint != value["model_digest"]:
        raise ValueError("model digest mismatch")
    model.eval()
    return model, value["metadata"]


@torch.no_grad()
def predict(model: AblationModel, tasks: list[Task], min_confidence: float = .6) -> list[Advice]:
    if not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1:
        raise ValueError("invalid confidence threshold")
    batch = tensorize(tasks, model.architecture)
    out = model(batch)
    if any(not torch.isfinite(v).all() for v in out.values()):
        raise ValueError("nonfinite model output")
    confidence, labels = out["logits"].exp().max(-1)
    result = []
    fingerprint = model.fingerprint
    for i, task in enumerate(tasks):
        c = float(confidence[i])
        status = "disconnected" if not batch["connected"][i] else "uncertain" if c < min_confidence else "ok"
        # Residual is retained as a diagnostic, NOT a v2 rejection threshold or
        # unsatisfiability verdict: message states need not encode literal edges.
        result.append(Advice.build({"version": "adiona-geometric-advice-v1", "admissible_use": "proposal_only",
            "task_digest": task.digest, "model_digest": fingerprint, "status": status,
            "label": RELATIONS[int(labels[i])] if status == "ok" else None,
            "confidence_ppm": round(c * 1_000_000) if status != "disconnected" else 0,
            "residual_ppm": round(min(float(out["relative_residual"][i]), 1) * 1_000_000)}))
    return result
