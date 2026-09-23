"""Synthetic task generators and an exact oracle used ONLY for training/evaluation."""
from __future__ import annotations

from collections import deque
from dataclasses import replace
import random

from .contracts import Fact, RELATIONS, Task

VECTORS = {name: (i % 3 - 1, i // 3 - 1) for i, name in enumerate(RELATIONS)}
INVERSE = {name: RELATIONS[8 - i] for i, name in enumerate(RELATIONS)}
PRIMITIVES = RELATIONS  # Include the zero displacement, not just compass directions.
HELD_OUT_PAIRS = (("N", "E"), ("S", "W"))


def relation_of(x: int, y: int) -> str:
    sx, sy = (x > 0) - (x < 0), (y > 0) - (y < 0)
    return RELATIONS[(sy + 1) * 3 + sx + 1]


def oracle(task: Task) -> tuple[str | None, list[tuple[int, int]], str]:
    """Integer constraints, with separate disconnected and inconsistent states."""
    adj = {e: [] for e in task.entities}
    for f in task.facts:
        x, y = VECTORS[f.relation]
        adj[f.object].append((f.subject, x, y))
        adj[f.subject].append((f.object, -x, -y))
    positions, components = {}, {}
    for root in task.entities:
        if root in positions:
            continue
        positions[root], components[root] = (0, 0), root
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for other, dx, dy in adj[node]:
                p = (positions[node][0] + dx, positions[node][1] + dy)
                if other in positions:
                    if positions[other] != p:
                        return None, [], "inconsistent"
                else:
                    positions[other], components[other] = p, root
                    queue.append(other)
    a, b = task.query
    coords = [positions[e] for e in task.entities]
    if components[a] != components[b]:
        return None, coords, "disconnected"
    return relation_of(positions[a][0] - positions[b][0], positions[a][1] - positions[b][1]), coords, "ok"


def _names(rng: random.Random, n: int) -> list[str]:
    return [f"entity_{i}" for i in rng.sample(range(10_000_000), n)]


def _present(rng: random.Random, names: list[str], facts: list[Fact], query: tuple[str, str]) -> Task:
    # Names, node order, premise order, and orientation are all nuisance variables.
    facts = [Fact(f.object, INVERSE[f.relation], f.subject) if rng.random() < .5 else f for f in facts]
    rng.shuffle(names)
    rng.shuffle(facts)
    return Task(tuple(names), tuple(facts), query)


def chain(rng: random.Random, depth: int, *, held_out: bool = False, distractors: int = 2) -> Task:
    if not 1 <= depth <= 24 or not 0 <= distractors <= 6:
        raise ValueError("unsupported generator bounds")
    while True:
        steps = [rng.choice(PRIMITIVES) for _ in range(depth)]
        has_heldout = any(pair in HELD_OUT_PAIRS for pair in zip(steps, steps[1:]))
        if has_heldout == held_out:
            break
        if held_out and depth < 2:
            raise ValueError("held-out compositions require depth >= 2")
    names = _names(rng, depth + 1 + distractors)
    facts = [Fact(names[i + 1], step, names[i]) for i, step in enumerate(steps)]
    # Branches off path nodes do not change the endpoint displacement.
    for i in range(distractors):
        facts.append(Fact(names[depth + 1 + i], rng.choice(PRIMITIVES), rng.choice(names[:depth + 1])))
    query = (names[depth], names[0])
    if rng.random() < .5:
        query = query[::-1]
    return _present(rng, names, facts, query)


def tree(rng: random.Random, n: int = 14) -> Task:
    names = _names(rng, n)
    facts = [Fact(names[i], rng.choice(PRIMITIVES), names[rng.randrange(i)]) for i in range(1, n)]
    return _present(rng, names, facts, tuple(rng.sample(names, 2)))


def grid(rng: random.Random, side: int = 4) -> Task:
    names = _names(rng, side * side)
    facts = []
    for y in range(side):
        for x in range(side):
            i = y * side + x
            if x:
                facts.append(Fact(names[i], "E", names[i - 1]))
            if y:
                facts.append(Fact(names[i], "N", names[i - side]))
    return _present(rng, names, facts, tuple(rng.sample(names, 2)))


def counterfactual(task: Task, rng: random.Random) -> Task:
    """Change exactly one decisive relation, retaining a consistent new answer."""
    original, _, status = oracle(task)
    if status != "ok":
        raise ValueError("counterfactual requires a consistent connected query")
    indexes = list(range(len(task.facts)))
    rng.shuffle(indexes)
    relations = list(RELATIONS)
    for i in indexes:
        rng.shuffle(relations)
        for relation in relations:
            if relation == task.facts[i].relation:
                continue
            facts = list(task.facts)
            facts[i] = replace(facts[i], relation=relation)
            candidate = replace(task, facts=tuple(facts))
            answer, _, new_status = oracle(candidate)
            if new_status == "ok" and answer != original:
                return candidate
    raise ValueError("no one-edge answer-changing consistent perturbation exists")


def rename_and_reorder(task: Task, rng: random.Random) -> Task:
    names = _names(rng, len(task.entities))
    mapping = dict(zip(task.entities, names))
    facts = [Fact(mapping[f.subject], f.relation, mapping[f.object]) for f in task.facts]
    rng.shuffle(names)
    rng.shuffle(facts)
    return Task(tuple(names), tuple(facts), (mapping[task.query[0]], mapping[task.query[1]]))


def training_pool(seed: int = 1729, per_depth: int = 128) -> list[Task]:
    rng = random.Random(seed)
    tasks = []
    for depth in range(1, 5):
        for _ in range(per_depth):
            task = chain(rng, depth)
            tasks.append(task)
            # The counterfactual can introduce a held-out ordered composition.
            # Do not use it in the pool; evaluation creates pairs separately.
    return tasks


def evaluation_sets(count: int = 128, seed: int = 8675309) -> dict[str, list[Task]]:
    rng = random.Random(seed)
    return {
        "iid": [chain(rng, rng.randint(1, 4)) for _ in range(count)],
        "composition_holdout": [chain(rng, rng.randint(2, 4), held_out=True) for _ in range(count)],
        "depth_ood": [chain(rng, rng.randint(6, 12)) for _ in range(count)],
        "tree_family": [tree(rng) for _ in range(count)],
        "cyclic_grid": [grid(rng) for _ in range(count)],
    }
