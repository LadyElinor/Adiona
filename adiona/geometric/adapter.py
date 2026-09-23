"""Translate advice into an inert sandbox proposal, never an assessment or grant."""
from __future__ import annotations

from adiona.canonical import Rejected
from adiona.contracts import Action
from adiona.identity import Credential
from adiona.kernel import Kernel
from .contracts import Advice, Task


def propose_advice(kernel: Kernel, worker: Credential, task: Task, advice: Advice) -> Action:
    # Revalidate even when callers construct objects outside the normal loader.
    value = Advice(advice.payload).body()
    if value["task_digest"] != task.digest:
        raise Rejected("advice is bound to a different task")
    if value["status"] != "ok":
        raise Rejected("abstained advice cannot propose an answer")
    # Fixed existing sandbox key; no model-selected action, target, or credential.
    # The kernel independently binds current world, policy, origin, and epoch.
    return kernel.propose(worker, [{"key": "message", "value": {
        "kind": "geometric_reasoning_advice", "task": task.body(), "advice": value,
        "notice": "Uncalibrated research prediction; requires separate assessment and authorization."
    }}])
