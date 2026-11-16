from __future__ import annotations

import math
from functools import lru_cache

from .geometry import clean_path, headings, path_length, turn_angle
from .models import Point2D, SweepState
from .transitions import VisibilityRouter


class CostModel:
    """Additive directed cost of service paths and obstacle-aware connectors.

    Cost = length + turn_weight * absolute heading change in radians.
    Connectors are shortest in Euclidean LENGTH, then scored for turning;
    they are not globally turn-optimal paths. Turns in place are permitted.
    """

    def __init__(
        self,
        clusters: list[list[SweepState]],
        router: VisibilityRouter,
        start: Point2D,
        closed: bool = True,
        turn_weight: float = 0.0,
        start_heading_deg: float | None = None,
    ):
        if not math.isfinite(turn_weight) or turn_weight < 0:
            raise ValueError("turn_weight must be finite and nonnegative")
        if start_heading_deg is not None and not math.isfinite(start_heading_deg):
            raise ValueError("start heading must be finite")
        self.clusters = clusters
        self.by_id = {s.id: s for cluster in clusters for s in cluster}
        if len(self.by_id) != sum(len(c) for c in clusters):
            raise ValueError("State IDs must be globally unique.")
        if not clusters or any(not c for c in clusters):
            raise ValueError("Every cell needs at least one sweep state.")
        self.router = router
        self.start = start
        self.closed = closed
        self.turn_weight = turn_weight
        self.start_heading = None if start_heading_deg is None else math.radians(start_heading_deg)
        self._headings = {s.id: headings(s.path) for s in self.by_id.values()}
        self._service = {
            s.id: path_length(s.path) + turn_weight * turn_angle(s.path)
            for s in self.by_id.values()
        }
        router.path(start, start)  # Validate depot before starting any solver.

    def service(self, state: SweepState) -> float:
        return self._service[state.id]

    @lru_cache(maxsize=200_000)
    def edge(self, source_id: int | None, target_id: int | None) -> float:
        if source_id is None and target_id is None:
            return 0.0
        if target_id is None and not self.closed:
            return 0.0
        source = self.by_id.get(source_id)
        target = self.by_id.get(target_id)
        a = self.start if source is None else source.exit
        b = self.start if target is None else target.entry
        before = self.start_heading if source is None else self._headings[source.id][-1]
        after = None if target is None else self._headings[target.id][0]
        connector = self.router.path(a, b)
        return path_length(connector) + self.turn_weight * turn_angle(connector, before, after)

    def evaluate(self, states: list[SweepState]) -> float:
        if not states:
            return 0.0
        total = self.edge(None, states[0].id)
        for i, state in enumerate(states):
            total += self.service(state)
            if i:
                total += self.edge(states[i - 1].id, state.id)
        return total + self.edge(states[-1].id, None)

    def connectors(self, states: list[SweepState]):
        if not states:
            return []
        routes = [self.router.path(self.start, states[0].entry)]
        routes += [self.router.path(a.exit, b.entry) for a, b in zip(states, states[1:])]
        if self.closed:
            routes.append(self.router.path(states[-1].exit, self.start))
        return routes

    def trajectory(self, states: list[SweepState]):
        if not states:
            return (self.start,)
        parts = self.connectors(states)
        result = []
        for i, state in enumerate(states):
            result.extend(parts[i])
            result.extend(state.path)
        if self.closed:
            result.extend(parts[-1])
        return clean_path(result)
