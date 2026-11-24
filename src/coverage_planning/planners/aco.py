"""Ant colony search over cell orders with exact fixed-order sweep selection."""
from __future__ import annotations

import random
from functools import cache

from ..costs import CostModel
from ..models import Solution
from .gtsp import optimize_states
from .tsp import solve_tsp


def solve_aco(
    model: CostModel, *, seed: int = 0, ants: int = 12, iterations: int = 20,
) -> Solution:
    if type(ants) is not int or ants < 1:
        raise ValueError("ants must be a positive integer")
    if type(iterations) is not int or iterations < 0:
        raise ValueError("iterations must be a nonnegative integer")

    initial_order = [s.cell_id for s in solve_tsp(model).states]
    best_states, best_cost = optimize_states(initial_order, model)
    history = [best_cost]
    if iterations == 0 or len(initial_order) == 1:
        return Solution("aco", best_states, best_cost, history)

    rng = random.Random(seed)
    clusters = {group[0].cell_id: group for group in model.clusters}
    trails = {(i, j): 1.0 for i in [None, *clusters] for j in clusters if i != j}

    @cache
    def estimate(source: int | None, target: int) -> float:
        if source is None:
            cost = min(model.edge(None, b.id) for b in clusters[target])
        else:
            cost = min(model.edge(a.id, b.id) for a in clusters[source] for b in clusters[target])
        return max(model.router.eps, cost)

    def sample_order() -> tuple[int, ...]:
        remaining = list(clusters)
        order = []
        source = None
        while len(remaining) > 1:
            costs = [estimate(source, target) for target in remaining]
            scale = min(costs)
            weights = [trails[source, target] * (scale / cost)
                       for target, cost in zip(remaining, costs)]
            target = rng.choices(remaining, weights=weights, k=1)[0]
            order.append(target)
            remaining.remove(target)
            source = target
        return (*order, remaining[0])

    for _ in range(iterations):
        # Keep first-occurrence order for reproducible tie breaking.
        orders = dict.fromkeys(sample_order() for _ in range(ants))
        winner = ()
        winner_cost = float("inf")
        for order in orders:
            states, cost = optimize_states(list(order), model)
            if cost < winner_cost:
                winner, winner_cost = order, cost
            if cost < best_cost - 1e-9:
                best_states, best_cost = states, cost
                history.append(cost)

        for arc in trails:
            # A lower bound maintains exploration even after long runs.
            trails[arc] = max(1e-6, 0.8 * trails[arc])
        for arc in zip((None, *winner), winner):
            trails[arc] += 1.0

    return Solution("aco", best_states, best_cost, history)
