"""BCD via event slabs and one-to-one component continuation.

This deliberately readable implementation is NOT an O(n log n) balanced-tree
sweep. It clips the polygon at all vertex projections, then merges across
noncritical events. No uniform raster discretization is used.
"""
from __future__ import annotations

from collections import defaultdict

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .geometry import event_coordinates, polygon_parts, to_local, to_world, tolerance
from .models import Cell, Decomposition


def decompose(region: Polygon, angle_deg: float = 90.0) -> Decomposition:
    if region.is_empty or not region.is_valid or region.area <= 0:
        raise ValueError("Expected one valid, connected, positive-area Polygon.")
    local = to_local(region, angle_deg)
    eps = tolerance(local)
    xs = event_coordinates(local)
    _, ymin, _, ymax = local.bounds
    pad = max(ymax - ymin, 1)
    pieces: dict[int, list[Polygon]] = defaultdict(list)
    adjacency: dict[int, set[int]] = defaultdict(set)
    events: list[dict] = []
    previous: list[Polygon] = []
    previous_ids: list[int] = []
    next_id = 0

    for left, right in zip(xs, xs[1:]):
        if right - left <= eps:
            continue
        clipped = local.intersection(box(left, ymin - pad, right, ymax + pad))
        current = sorted(
            [p for p in polygon_parts(clipped) if p.area > eps * eps],
            key=lambda p: p.centroid.y,
        )
        # Positive-length shared gates, not just touching at a point.
        links = [
            [j for j, q in enumerate(current) if p.intersection(q).length > eps]
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
        if merged.geom_type != "Polygon" or merged.interiors:
            raise ValueError("Numerically degenerate cell; rescale or clean the input map.")
        cells.append(Cell(cell_id, to_world(merged, angle_deg)))
    union = unary_union([c.polygon for c in cells])
    error = union.symmetric_difference(region).area
    overlap = sum(c.polygon.area for c in cells) - union.area
    if error > max(region.area, 1) * 1e-7 or overlap > max(region.area, 1) * 1e-7:
        raise ValueError("Decomposition failed area/overlap validation.")
    return Decomposition(cells, dict(adjacency), events, angle_deg)
