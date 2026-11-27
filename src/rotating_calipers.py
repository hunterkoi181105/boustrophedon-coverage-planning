
from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient


def minimum_width_direction(
    polygon: Polygon,
) -> tuple[float, float]:
    """
    Find the minimum-width sweep direction using
    rotating calipers.

    Returns
    -------
    angle_deg : float
        Lane orientation in degrees, in [0, 180).
    width : float
        Minimum perpendicular width.

    Complexity
    ----------
    Convex hull: O(n log n) using a standard hull algorithm.
    Rotating calipers: O(h), where h is the hull size.
    """

    hull = polygon.convex_hull

    if hull.geom_type != "Polygon" or hull.area <= 0:
        raise ValueError("Expected a positive-area convex hull.")

    # Ensure counterclockwise vertex order.
    hull = orient(hull, sign=1.0)

    # Remove the repeated closing vertex.
    points = list(hull.exterior.coords)[:-1]
    h = len(points)

    def height(i: int, j: int) -> float:
        """Cross product: edge i against vertex j."""
        ax, ay = points[i]
        bx, by = points[(i + 1) % h]
        px, py = points[j % h]

        return (
            (bx - ax) * (py - ay)
            - (by - ay) * (px - ax)
        )

    # Find the first antipodal vertex.
    j = max(range(h), key=lambda q: height(0, q))

    # The antipodal pointer traverses at most one full cycle.
    limit = j + h

    best_width = math.inf
    best_angle = 0.0

    for i in range(h):
        # Advance the supporting vertex while distance increases.
        while (
            j < limit
            and height(i, j + 1) > height(i, j)
        ):
            j += 1

        ax, ay = points[i]
        bx, by = points[(i + 1) % h]

        dx = bx - ax
        dy = by - ay

        edge_length = math.hypot(dx, dy)

        width = height(i, j) / edge_length

        if width < best_width:
            best_width = width

            best_angle = (
                math.degrees(math.atan2(dy, dx)) % 180.0
            )

    return best_angle, best_width
