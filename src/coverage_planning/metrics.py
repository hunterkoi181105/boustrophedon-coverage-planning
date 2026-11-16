from __future__ import annotations

import math

from shapely.geometry import LineString
from shapely.ops import unary_union

from .costs import CostModel
from .geometry import angle_difference, headings, path_length, turn_angle
from .models import Solution


def evaluate(solution: Solution, model: CostModel, region, swath: float) -> dict:
    if not math.isfinite(swath) or swath <= 0:
        raise ValueError("swath must be finite and positive")
    trajectory = model.trajectory(solution.states)
    # Treat the sensor as active on cell-service paths, inactive on transit.
    # Individual segment footprints deliberately count overlaps at joins too.
    footprints = [
        LineString([a, b]).buffer(swath / 2, quad_segs=16).intersection(region)
        for state in solution.states
        for a, b in zip(state.path, state.path[1:])
        if math.dist(a, b) > 1e-10
    ]
    covered = unary_union(footprints).area
    counted = sum(p.area for p in footprints)
    hs = headings(trajectory)
    valid = region.buffer(model.router.eps * 5).covers(LineString(trajectory))
    service = sum(path_length(s.path) for s in solution.states)
    transit = sum(path_length(p) for p in model.connectors(solution.states))
    return {
        "algorithm": solution.algorithm,
        "objective": solution.objective,
        "total_length": path_length(trajectory),
        "service_length": service,
        "transit_length": transit,
        "absolute_turn_angle_rad": turn_angle(trajectory, before=model.start_heading),
        "vertex_turn_count": sum(
            angle_difference(a, b) > math.radians(1) for a, b in zip(hs, hs[1:])
        ),
        "lane_reversal_count": sum(max(0, len(s.lanes) - 1) for s in solution.states),
        "coverage_ratio": min(1.0, covered / region.area),
        "uncovered_area": max(0.0, region.area - covered),
        "overlap_excess_ratio": max(0.0, counted - covered) / region.area,
        "collision_free_within_tolerance": bool(valid),
        "num_cells": len(model.clusters),
        "num_candidate_states": sum(len(c) for c in model.clusters),
        "selected_cell_order": [s.cell_id for s in solution.states],
        "selected_first_turns": [s.first_turn for s in solution.states],
    }
