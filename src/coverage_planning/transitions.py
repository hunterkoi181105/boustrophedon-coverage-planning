"""Obstacle-aware Euclidean shortest paths for a point robot."""
from __future__ import annotations

import heapq
import math
from functools import lru_cache

from shapely.geometry import LineString, Point, Polygon

from .geometry import tolerance, vertices
from .models import Point2D


class VisibilityRouter:
    """Full visibility graph of boundary vertices, searched with Dijkstra.

    Boundary travel is allowed. An epsilon buffer is used for floating-point
    predicates; this is not a physical robot-clearance model.
    """

    def __init__(self, region: Polygon):
        self.region = region
        self.eps = tolerance(region)
        self.safe = region.buffer(self.eps)
        self.nodes = vertices(region)
        self.graph: list[list[tuple[int, float]]] = [[] for _ in self.nodes]
        for i, a in enumerate(self.nodes):
            for j in range(i):
                b = self.nodes[j]
                if self.visible(a, b):
                    length = math.dist(a, b)
                    self.graph[i].append((j, length))
                    self.graph[j].append((i, length))

    def visible(self, a: Point2D, b: Point2D) -> bool:
        if a == b:
            return self.safe.covers(Point(a))
        return self.safe.covers(LineString([a, b]))

    @lru_cache(maxsize=100_000)
    def path(self, start: Point2D, end: Point2D) -> tuple[Point2D, ...]:
        if not self.safe.covers(Point(start)) or not self.safe.covers(Point(end)):
            raise ValueError("Route endpoint lies outside free space.")
        if start == end:
            return (start,)
        if self.visible(start, end):
            return (start, end)
        nodes = self.nodes + [start, end]
        graph = [list(edges) for edges in self.graph] + [[], []]
        source, target = len(nodes) - 2, len(nodes) - 1
        for i in [source, target]:
            for j in range(i):
                if self.visible(nodes[i], nodes[j]):
                    d = math.dist(nodes[i], nodes[j])
                    graph[i].append((j, d))
                    graph[j].append((i, d))
        distances = [math.inf] * len(nodes)
        parent = [-1] * len(nodes)
        distances[source] = 0.0
        queue = [(0.0, source)]
        while queue:
            cost, u = heapq.heappop(queue)
            if cost > distances[u]:
                continue
            if u == target:
                indices = []
                while u != -1:
                    indices.append(u)
                    u = parent[u]
                return tuple(nodes[k] for k in reversed(indices))
            for v, weight in graph[u]:
                candidate = cost + weight
                if candidate < distances[v] - 1e-12:
                    distances[v] = candidate
                    parent[v] = u
                    heapq.heappush(queue, (candidate, v))
        raise ValueError("No path connects the endpoints within free space.")
