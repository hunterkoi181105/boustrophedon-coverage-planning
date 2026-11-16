from __future__ import annotations

import math

from shapely.geometry import LineString, Point
from shapely.ops import substring

from .geometry import (
    clean_path,
    is_monotone,
    line_parts,
    to_local,
    to_world,
    tolerance,
)
from .models import Cell, SweepState
from .transitions import VisibilityRouter


def _boundary_loop(poly, start):
    """Walk the cell boundary once, beginning and ending at a lane endpoint."""
    ring = LineString(poly.exterior.coords)
    t = ring.project(Point(start))
    first = substring(ring, t, ring.length)
    second = substring(ring, 0, t)
    return clean_path([start, *list(first.coords), *list(second.coords), start])


def generate_states(
    cell: Cell,
    spacing: float,
    angles: tuple[float, ...] = (90.0, 0.0),
    first_turn: str = "any",
    boundary_pass: bool = False,
    id_offset: int = 0,
) -> list[SweepState]:
    """Generate four start/order permutations for each sweepable angle.

    Angle is the undirected lane orientation measured CCW from world +X.
    The lane order and first pass determine the nominal initial U-turn side.
    Single-lane cells have no U-turn and remain admissible under either filter.
    """
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("spacing must be a finite positive number")
    if first_turn not in {"any", "left", "right"}:
        raise ValueError("first_turn must be any, left, or right")
    unique_angles = list(dict.fromkeys(float(a) % 180 for a in angles))
    if not unique_angles or not all(math.isfinite(a) for a in unique_angles):
        raise ValueError("Provide at least one finite sweep angle.")
    result = []
    seen_paths = set()
    for angle in unique_angles:
        if not is_monotone(cell.polygon, angle):
            continue  # Never silently apply a non-sweepable orientation.
        local = to_local(cell.polygon, angle)
        router = VisibilityRouter(local)
        x0, y0, x1, y1 = local.bounds
        count = max(1, math.ceil((x1 - x0) / spacing))
        actual_spacing = (x1 - x0) / count
        lanes = []
        pad = max(y1 - y0, 1)
        for i in range(count):
            x = x0 + (i + 0.5) * actual_spacing
            cut = LineString([(x, y0 - pad), (x, y1 + pad)])
            segments = [s for s in line_parts(local.intersection(cut)) if s.length > tolerance(local)]
            if len(segments) != 1:
                raise ValueError("Expected exactly one nondegenerate lane in a monotone cell.")
            points = sorted(segments[0].coords, key=lambda p: p[1])
            lanes.append((tuple(points[0]), tuple(points[-1])))
        for increasing in (True, False):
            ordered = lanes if increasing else list(reversed(lanes))
            for start_up in (True, False):
                # cross(first heading, lane-progression vector) gives the side.
                side = "right" if increasing == start_up else "left"
                if count == 1:
                    side = "none"
                if first_turn != "any" and side not in {first_turn, "none"}:
                    continue
                route = []
                directed_lanes = []
                for i, (bottom, top) in enumerate(ordered):
                    up = start_up if i % 2 == 0 else not start_up
                    entry, exit_ = (bottom, top) if up else (top, bottom)
                    if route:
                        route.extend(router.path(route[-1], entry)[1:])
                    else:
                        route.append(entry)
                    route.append(exit_)
                    directed_lanes.append((entry, exit_))
                if boundary_pass:
                    route.extend(_boundary_loop(local, route[-1])[1:])
                world = clean_path(to_world(LineString(route), angle).coords)
                key = tuple((round(x, 9), round(y, 9)) for x, y in world)
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                world_lanes = tuple(
                    tuple(to_world(LineString([a, b]), angle).coords) for a, b in directed_lanes
                )
                if not cell.polygon.buffer(tolerance(cell.polygon) * 5).covers(LineString(world)):
                    raise ValueError("Generated service path escaped its cell.")
                result.append(SweepState(
                    id=id_offset + len(result),
                    cell_id=cell.id,
                    angle_deg=angle,
                    lane_order="increasing" if increasing else "decreasing",
                    first_pass="positive" if start_up else "negative",
                    first_turn=side,
                    path=world,
                    lanes=world_lanes,
                ))
    if not result:
        raise ValueError(f"Cell {cell.id} has no valid states at the requested angles.")
    return result
