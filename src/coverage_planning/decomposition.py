"""Polygonal BCD using the incremental floor-and-ceiling sweep."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from heapq import merge

from shapely.errors import GEOSException
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .geometry import event_coordinates, polygon_parts, to_local, to_world, tolerance
from .models import Cell, Decomposition, Point2D


def decompose(region: Polygon, angle_deg: float = 90.0) -> Decomposition:
    """Build cells incrementally at boundary events, following Choset and Pignon."""
    if (
        not isinstance(region, Polygon) or region.is_empty or not region.is_valid
        or not math.isfinite(region.area) or region.area <= 0
    ):
        raise ValueError("Expected one valid, connected, positive-area Polygon.")
    if not math.isfinite(angle_deg):
        raise ValueError("Decomposition angle must be finite.")
    try:
        return _sweep(region, angle_deg)
    except GEOSException as exc:
        raise ValueError("Decomposition geometry failed; rescale or clean the map.") from exc


@dataclass(frozen=True)
class _Edge:
    left: Point2D
    right: Point2D

    def height(self, x: float) -> float:
        if x == self.left[0]:
            return self.left[1]
        if x == self.right[0]:
            return self.right[1]
        t = (x - self.left[0]) / (self.right[0] - self.left[0])
        return self.left[1] + t * (self.right[1] - self.left[1])

    def right_order(self, x: float) -> tuple[float, float]:
        slope = (self.right[1] - self.left[1]) / (self.right[0] - self.left[0])
        return self.height(x), slope


_Section = tuple[_Edge, _Edge]


@dataclass
class _OpenCell:
    id: int
    section: _Section
    floor: list[Point2D]
    ceiling: list[Point2D]
    opening: list[Point2D]

    def continue_at(self, x: float, section: _Section) -> None:
        for chain, old, new in zip((self.floor, self.ceiling), self.section, section):
            if old != new:
                point = (x, old.height(x))
                chain.append(point)
                next_point = (x, new.height(x))
                if next_point != point:
                    chain.append(next_point)
        self.section = section

    def close_at(self, x: float, closing: list[Point2D]) -> Polygon:
        floor, ceiling = self.section
        self.floor.append((x, floor.height(x)))
        self.ceiling.append((x, ceiling.height(x)))
        roof = self.ceiling[::-1]
        start = int(self.floor[-1] == roof[0])
        end = len(roof) - int(self.floor[0] == roof[-1])
        return Polygon(self.floor + closing + roof[start:end] + self.opening[::-1])


def _section_links(
    left: list[_Section], right: list[_Section], x: float,
) -> tuple[list[list[int]], list[list[int]]]:
    """Match ordered free-space intervals across gates of positive length."""
    left_bounds = [(floor.height(x), ceiling.height(x)) for floor, ceiling in left]
    right_bounds = [(floor.height(x), ceiling.height(x)) for floor, ceiling in right]
    outgoing: list[list[int]] = [[] for _ in left]
    incoming: list[list[int]] = [[] for _ in right]
    i = j = 0
    while i < len(left_bounds) and j < len(right_bounds):
        low_left, high_left = left_bounds[i]
        low_right, high_right = right_bounds[j]
        if max(low_left, low_right) < min(high_left, high_right):
            outgoing[i].append(j)
            incoming[j].append(i)
        if high_left <= high_right:
            i += 1
        if high_right <= high_left:
            j += 1
    return outgoing, incoming


def _gate_vertices(x: float, section: _Section, neighbors: list[_Section]) -> list[Point2D]:
    # Identical gate subdivisions keep adjacent cells joined after rotation.
    low, high = (edge.height(x) for edge in section)
    heights = (edge.height(x) for neighbor in neighbors for edge in neighbor)
    return [(x, y) for y in dict.fromkeys(heights) if low < y < high]


def _event(x: float, outgoing: list[list[int]], incoming: list[list[int]]) -> dict:
    return {
        "local_x": x,
        "components_before": len(outgoing),
        "components_after": len(incoming),
        "splits": sum(len(links) > 1 for links in outgoing),
        "merges": sum(len(parents) > 1 for parents in incoming),
        "births": sum(not parents for parents in incoming),
        "deaths": sum(not links for links in outgoing),
    }


def _sweep(region: Polygon, angle_deg: float) -> Decomposition:
    local = to_local(region, angle_deg)
    if not local.is_valid or not math.isfinite(local.area) or local.area <= 0:
        raise ValueError("Decomposition rotation lost valid geometry.")

    starts: dict[float, list[_Edge]] = defaultdict(list)
    for ring in [local.exterior, *local.interiors]:
        points = list(ring.coords)
        for a, b in zip(points, points[1:]):
            left, right = sorted((a, b))
            starts.setdefault(right[0], [])
            if left[0] < right[0]:
                starts[left[0]].append(_Edge(left, right))

    active: list[_Edge] = []
    previous: list[_OpenCell] = []
    adjacency: dict[int, set[int]] = {}
    events: list[dict] = []
    cells: list[Cell] = []
    for x, entering in sorted(starts.items()):
        # Continuing edges keep their order. Outgoing slopes break ties at vertices
        # so ordering needs no sample point between neighboring events.
        def right_order(edge: _Edge) -> tuple[float, float]:
            return edge.right_order(x)

        continuing = (edge for edge in active if edge.right[0] > x)
        active = list(merge(continuing, sorted(entering, key=right_order), key=right_order))
        sections = list(zip(active[::2], active[1::2], strict=True))
        previous_sections = [cell.section for cell in previous]
        outgoing, incoming = _section_links(previous_sections, sections, x)
        current = []
        kept = set()
        for section, parents in zip(sections, incoming):
            if len(parents) == 1 and len(outgoing[parents[0]]) == 1:
                i = parents[0]
                cell = previous[i]
                cell.continue_at(x, section)
                kept.add(i)
            else:
                floor, ceiling = section
                opening = _gate_vertices(x, section, [previous_sections[i] for i in parents])
                cell = _OpenCell(
                    len(adjacency), section, [(x, floor.height(x))], [(x, ceiling.height(x))], opening,
                )
                adjacency[cell.id] = {previous[i].id for i in parents}
                for parent_id in adjacency[cell.id]:
                    adjacency[parent_id].add(cell.id)
            current.append(cell)
        for i, cell in enumerate(previous):
            if i not in kept:
                closing = _gate_vertices(x, cell.section, [sections[j] for j in outgoing[i]])
                polygon = to_world(cell.close_at(x, closing), angle_deg)
                if not polygon.is_valid or not math.isfinite(polygon.area) or polygon.area <= 0:
                    raise ValueError("Decomposition produced a numerically degenerate cell.")
                cells.append(Cell(cell.id, polygon))
        events.append(_event(x, outgoing, incoming))
        previous = current

    _validate_partition(region, cells)
    return Decomposition(sorted(cells, key=lambda cell: cell.id), adjacency, events, angle_deg)


def decompose_slabs(region: Polygon, angle_deg: float = 90.0) -> Decomposition:
    """Decompose by polygon clipping for comparisons against the default sweep."""
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
        events.append(_event(left, links, incoming))
        previous, previous_ids = current, current_ids

    events.append(_event(xs[-1], [[] for _ in previous], []))
    cells = []
    for cell_id, parts in sorted(pieces.items()):
        merged = unary_union(parts)
        if merged.geom_type != "Polygon" or merged.interiors:
            raise ValueError("Numerically degenerate cell; rescale or clean the input map.")
        cells.append(Cell(cell_id, to_world(merged, angle_deg)))
    _validate_partition(region, cells)
    return Decomposition(cells, dict(adjacency), events, angle_deg)


def _validate_partition(region: Polygon, cells: list[Cell]) -> None:
    if not cells:
        raise ValueError("Decomposition produced no cells.")
    union = unary_union([c.polygon for c in cells])
    error = union.symmetric_difference(region).area
    overlap = sum(c.polygon.area for c in cells) - union.area
    if error > max(region.area, 1) * 1e-7 or overlap > max(region.area, 1) * 1e-7:
        raise ValueError("Decomposition failed area/overlap validation.")
