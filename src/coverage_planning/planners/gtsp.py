from __future__ import annotations

import random

from ..costs import CostModel
from ..models import Solution, SweepState
from .tsp import solve_tsp


def optimize_states(order: list[int], model: CostModel) -> tuple[list[SweepState], float]:
    """Exact layered DP for state choice conditional on a FIXED cell order."""
    by_cell = {c[0].cell_id: c for c in model.clusters}
    if not order:
        return [], 0.0
    previous = by_cell[order[0]]
    costs = {s.id: model.edge(None, s.id) + model.service(s) for s in previous}
    parents: list[dict[int, int]] = []
    for cell_id in order[1:]:
        current = by_cell[cell_id]
        next_costs = {}
        parent = {}
        for state in current:
            best = min(previous, key=lambda p: costs[p.id] + model.edge(p.id, state.id))
            next_costs[state.id] = costs[best.id] + model.edge(best.id, state.id) + model.service(state)
            parent[state.id] = best.id
        parents.append(parent)
        costs, previous = next_costs, current
    last = min(previous, key=lambda s: costs[s.id] + model.edge(s.id, None))
    value = costs[last.id] + model.edge(last.id, None)
    ids = [last.id]
    for parent in reversed(parents):
        ids.append(parent[ids[-1]])
    return [model.by_id[i] for i in reversed(ids)], value


def solve_gtsp(
    model: CostModel, seed: int = 0, restarts: int = 2, max_rounds: int = 20,
) -> Solution:
    """Joint state/order heuristic, NOT a globally exact GTSP solver.

    Include the TSP order as the first seed, guaranteeing the final objective
    is no worse than that baseline under the identical states and cost model.
    """
    if restarts < 0 or max_rounds < 0:
        raise ValueError("Search budgets must be nonnegative")
    baseline = solve_tsp(model)
    base_order = [s.cell_id for s in baseline.states]
    rng = random.Random(seed)
    orders = [base_order]
    for _ in range(restarts):
        order = list(base_order)
        rng.shuffle(order)
        orders.append(order)
    best_states, best_value = optimize_states(base_order, model)
    history = [baseline.objective, best_value]
    for order in orders:
        states, value = optimize_states(order, model)
        for _ in range(max_rounds):
            candidate_order, candidate_states, candidate_value = order, states, value
            for i in range(len(order) - 1):
                for j in range(i + 1, len(order)):
                    changed = order[:i] + list(reversed(order[i:j + 1])) + order[j + 1:]
                    s, c = optimize_states(changed, model)
                    if c < candidate_value - 1e-9:
                        candidate_order, candidate_states, candidate_value = changed, s, c
            if candidate_value >= value - 1e-9:
                break
            order, states, value = candidate_order, candidate_states, candidate_value
        if value < best_value - 1e-9:
            best_states, best_value = states, value
            history.append(value)
    return Solution("gtsp", best_states, best_value, history)
