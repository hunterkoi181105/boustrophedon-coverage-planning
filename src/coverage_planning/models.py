from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shapely.geometry import Polygon

Point2D = tuple[float, float]
Turn = Literal["left", "right", "none"]


@dataclass(frozen=True)
class Cell:
    id: int
    polygon: Polygon


@dataclass
class Decomposition:
    cells: list[Cell]
    adjacency: dict[int, set[int]]
    events: list[dict]
    angle_deg: float


@dataclass(frozen=True)
class SweepState:
    """One complete, directed service path through one cell.

    first_turn describes the nominal first lane-reversal side, not a
    dynamically feasible curved maneuver or the first corner of a detour.
    """

    id: int
    cell_id: int
    angle_deg: float
    lane_order: str
    first_pass: str
    first_turn: Turn
    path: tuple[Point2D, ...]
    lanes: tuple[tuple[Point2D, Point2D], ...]

    @property
    def entry(self) -> Point2D:
        return self.path[0]

    @property
    def exit(self) -> Point2D:
        return self.path[-1]


@dataclass
class Solution:
    algorithm: str
    states: list[SweepState]
    objective: float
    accepted_objectives: list[float]
