"""BCD via event slabs and one-to-one component continuation.

This deliberately readable implementation is NOT an O(n log n) balanced-tree
sweep. It clips the polygon at all vertex projections, then merges across
noncritical events. No uniform raster discretization is used.
"""
from __future__ import annotations

import math
from collections import defaultdict

from shapely.errors import GEOSException
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .geometry import event_coordinates, is_monotone, polygon_parts, to_local, to_world
from .models import Cell, Decomposition


def decompose(region: Polygon, angle_deg: float = 90.0) -> Decomposition:
    if (
        not isinstance(region, Polygon) or region.is_empty or not region.is_valid
        or not math.isfinite(region.area) or region.area <= 0
    ):
        raise ValueError("Expected one valid, connected, positive-area Polygon.")
    if not math.isfinite(angle_deg):
        raise ValueError("Decomposition angle must be finite.")
    try:
        return _decompose(region, angle_deg)
    except GEOSException as exc:
        raise ValueError(
            "Numerically degenerate decomposition: geometry operation failed; "
            "rescale or clean the input map."
        ) from exc


def _decompose(region: Polygon, angle_deg: float) -> Decomposition:
    local = to_local(region, angle_deg)
    if local.is_empty or not local.is_valid or not math.isfinite(local.area) or local.area <= 0:
        raise ValueError("Numerically degenerate decomposition: rotation lost valid geometry.")
    xs = event_coordinates(local)
    if len(xs) < 2:
        raise ValueError("Numerically degenerate decomposition: no positive-width event strips.")
    _, ymin, _, ymax = local.bounds
    pad = max(ymax - ymin, 1)
    pieces: dict[int, list[Polygon]] = defaultdict(list)
    adjacency: dict[int, set[int]] = defaultdict(set)
    events: list[dict] = []
    previous: list[Polygon] = []
    previous_ids: list[int] = []
    next_id = 0

    for left, right in zip(xs, xs[1:]):
        if not left < right:
            raise ValueError("Numerically degenerate decomposition: unordered event coordinates.")
        clipped = local.intersection(box(left, ymin - pad, right, ymax + pad))
        current = sorted(polygon_parts(clipped), key=lambda p: p.centroid.y)
        if not current or any(
            not p.is_valid or not math.isfinite(p.area) or p.area <= 0 for p in current
        ):
            raise ValueError("Numerically degenerate decomposition: event strip lost positive area.")
        # Positive-length shared gates, not just touching at a point.
        links = [
            [j for j, q in enumerate(current) if p.intersection(q).length > 0]
            for p in previous
        ]
        incoming = [
            [i for i, js in enumerate(links) if j in js] for j in range(len(current))
        ]
        current_ids = []
        for j, poly in enumerate(current):
            parents = incoming[j]
            if len(parents) == 1 and len(links[parents[0]]) == 1:
                cell_id = previous_ids[parents[0]]  # MIDDLE: retain the cell.
            else:
                cell_id = next_id
                next_id += 1
            current_ids.append(cell_id)
            pieces[cell_id].append(poly)
            adjacency[cell_id]  # Include isolated cells.
            for i in parents:
                old = previous_ids[i]
                if old != cell_id:
                    adjacency[old].add(cell_id)
                    adjacency[cell_id].add(old)
        events.append({
            "local_x": left,
            "components_before": len(previous),
            "components_after": len(current),
            "splits": sum(len(js) > 1 for js in links),
            "merges": sum(len(parents) > 1 for parents in incoming),
            "births": sum(not parents for parents in incoming),
            "deaths": sum(not js for js in links),
        })
        previous, previous_ids = current, current_ids

    events.append({
        "local_x": xs[-1], "components_before": len(previous), "components_after": 0,
        "splits": 0, "merges": 0, "births": 0, "deaths": len(previous),
    })
    cells = []
    for cell_id, parts in sorted(pieces.items()):
        merged = unary_union(parts)
        # Check topology in the construction frame before round-trip rotation.
        if merged.geom_type != "Polygon" or not is_monotone(merged, 90.0):
            raise ValueError("Numerically degenerate decomposition: cell is invalid or nonmonotone.")
        world = to_world(merged, angle_deg)
        if not is_monotone(world, angle_deg):
            raise ValueError("Numerically degenerate decomposition: rotated cell is nonmonotone.")
        cells.append(Cell(cell_id, world))
    if not cells:
        raise ValueError("Numerically degenerate decomposition: positive-area input produced no cells.")
    union = unary_union([c.polygon for c in cells])
    error = union.symmetric_difference(region).area
    overlap = math.fsum(c.polygon.area for c in cells) - union.area
    # A fixed absolute floor can accept losing an entire small input polygon.
    # Ratios retain a relative allowance without underflowing area * tolerance.
    if (
        not math.isfinite(error) or not math.isfinite(overlap)
        or error / region.area > 1e-7 or overlap / region.area > 1e-7
    ):
        raise ValueError("Numerically degenerate decomposition: area/overlap validation failed.")
    return Decomposition(cells, dict(adjacency), events, angle_deg)
