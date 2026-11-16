"""Subset DP oracle for TINY discretized GTSP instances only."""
from __future__ import annotations

import math

from ..costs import CostModel
from ..models import Solution


def solve_exact(model: CostModel, max_cells: int = 8) -> Solution:
    count = len(model.clusters)
    if count > max_cells:
        raise ValueError(f"Exact GTSP is limited to {max_cells} cells; received {count}.")
    full = (1 << count) - 1
    dp: dict[tuple[int, int], float] = {}
    parent: dict[tuple[int, int], tuple[int, int] | None] = {}
    for i, cluster in enumerate(model.clusters):
        for s in cluster:
            key = (1 << i, s.id)
            dp[key] = model.edge(None, s.id) + model.service(s)
            parent[key] = None
    for mask in range(1, full + 1):
        for i, cluster in enumerate(model.clusters):
            if not mask & (1 << i):
                continue
            for state in cluster:
                key = (mask, state.id)
                if key not in dp:
                    continue
                for j, following in enumerate(model.clusters):
                    if mask & (1 << j):
                        continue
                    new_mask = mask | (1 << j)
                    for target in following:
                        new_key = (new_mask, target.id)
                        value = dp[key] + model.edge(state.id, target.id) + model.service(target)
                        if value < dp.get(new_key, math.inf):
                            dp[new_key] = value
                            parent[new_key] = key
    last = min(
        ((full, s.id) for c in model.clusters for s in c),
        key=lambda k: dp[k] + model.edge(k[1], None),
    )
    value = dp[last] + model.edge(last[1], None)
    states = []
    key = last
    while key is not None:
        states.append(model.by_id[key[1]])
        key = parent[key]
    states.reverse()
    return Solution("gtsp-exact", states, value, [value])
