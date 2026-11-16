from __future__ import annotations

from ..costs import CostModel
from ..models import Solution, SweepState


def greedy_order(states: list[SweepState], model: CostModel) -> list[SweepState]:
    """Nearest-neighbor over one fixed directed service state per cell."""
    remaining = list(states)
    order = []
    last = None
    while remaining:
        chosen = min(remaining, key=lambda s: (model.edge(last, s.id), s.cell_id))
        order.append(chosen)
        remaining.remove(chosen)
        last = chosen.id
    return order


def solve_tsp(model: CostModel, improve: bool = True, max_rounds: int = 30) -> Solution:
    """Greedy then directed-safe segment-reversal local search.

    Directed costs require evaluating ALL affected edges. The symmetric
    four-edge 2-opt delta would be incorrect here. States stay fixed.
    """
    if max_rounds < 0:
        raise ValueError("max_rounds must be nonnegative")
    states = greedy_order([c[0] for c in model.clusters], model)
    cost = model.evaluate(states)
    history = [cost]
    if improve:
        for _ in range(max_rounds):
            best_states, best_cost = states, cost
            for i in range(len(states) - 1):
                for j in range(i + 1, len(states)):
                    candidate = states[:i] + list(reversed(states[i:j + 1])) + states[j + 1:]
                    value = model.evaluate(candidate)
                    if value < best_cost - 1e-9:
                        best_states, best_cost = candidate, value
            if best_cost >= cost - 1e-9:
                break
            states, cost = best_states, best_cost
            history.append(cost)
    return Solution("tsp-2opt" if improve else "tsp-greedy", states, cost, history)
