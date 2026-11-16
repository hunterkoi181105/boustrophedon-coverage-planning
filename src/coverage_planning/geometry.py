from __future__ import annotations

import json
import math
from pathlib import Path

from shapely.affinity import rotate
from shapely.geometry import LineString, Polygon
from shapely.validation import explain_validity

from .models import Point2D


def tolerance(poly: Polygon) -> float:
    x0, y0, x1, y1 = poly.bounds
    return max(x1 - x0, y1 - y0, 1.0) * 1e-9


def to_local(geom, angle_deg: float):
    """Rotate so lanes at angle_deg from world +X become vertical."""
    return rotate(geom, 90.0 - angle_deg, origin=(0, 0))


def to_world(geom, angle_deg: float):
    return rotate(geom, angle_deg - 90.0, origin=(0, 0))


def polygon_parts(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in polygon_parts(g)]
    return []


def line_parts(geom) -> list[LineString]:
    if geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in line_parts(g)]
    return []


def vertices(poly: Polygon) -> list[Point2D]:
    rings = [poly.exterior, *poly.interiors]
    return list(dict.fromkeys((float(x), float(y)) for r in rings for x, y in list(r.coords)[:-1]))


def event_coordinates(poly: Polygon) -> list[float]:
    """Group numerically coincident event positions, including vertical edges."""
    eps = tolerance(poly)
    result: list[float] = []
    for x in sorted(p[0] for p in vertices(poly)):
        if not result or x - result[-1] > eps:
            result.append(x)
    # Include the exact maximum even if it was grouped with a nearby event.
    result[-1] = poly.bounds[2]
    return result


def load_map(path: str | Path) -> tuple[Polygon, dict]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    poly = Polygon(data["boundary"], data.get("holes", []))
    if poly.is_empty or poly.area <= 0 or not poly.is_valid:
        raise ValueError(f"Map must be a valid positive-area polygon: {explain_validity(poly)}")
    if any(not math.isfinite(v) for p in vertices(poly) for v in p):
        raise ValueError("Coordinates must be finite planar numbers.")
    return poly, data


def clean_path(points) -> tuple[Point2D, ...]:
    result: list[Point2D] = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if not result or math.dist(result[-1], p) > 1e-10:
            result.append(p)
    return tuple(result)


def path_length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def headings(points) -> list[float]:
    return [
        math.atan2(b[1] - a[1], b[0] - a[0])
        for a, b in zip(points, points[1:])
        if math.dist(a, b) > 1e-10
    ]


def angle_difference(a: float, b: float) -> float:
    return abs(math.atan2(math.sin(b - a), math.cos(b - a)))


def turn_angle(points, before: float | None = None, after: float | None = None) -> float:
    hs = headings(points)
    if before is not None:
        hs.insert(0, before)
    if after is not None:
        hs.append(after)
    return sum(angle_difference(a, b) for a, b in zip(hs, hs[1:]))


def is_monotone(poly: Polygon, angle_deg: float) -> bool:
    """Check one connected vertical section in every open event slab.

    For polygonal boundaries topology is constant between consecutive vertex
    projections. Event-line degeneracies use the neighboring open slabs.
    """
    local = to_local(poly, angle_deg)
    if local.interiors:
        return False
    xs = event_coordinates(local)
    _, ymin, _, ymax = local.bounds
    pad = max(ymax - ymin, 1)
    for a, b in zip(xs, xs[1:]):
        cut = LineString([((a + b) / 2, ymin - pad), ((a + b) / 2, ymax + pad)])
        lines = [s for s in line_parts(local.intersection(cut)) if s.length > tolerance(local)]
        if len(lines) != 1:
            return False
    return True
