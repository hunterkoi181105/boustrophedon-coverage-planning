import pytest
from shapely.geometry import LineString, box

from coverage_planning.geometry import load_map
from coverage_planning.models import Cell
from coverage_planning.sweeps import generate_states

from .conftest import ROOT


def test_four_states_per_orientation():
    states = generate_states(Cell(0, box(0, 0, 10, 6)), 2, (90,))
    assert len(states) == 4
    assert {s.first_turn for s in states} == {"left", "right"}
    assert len({s.entry for s in states}) == 4


@pytest.mark.parametrize("side", ["left", "right"])
def test_turn_filter(side):
    cell = Cell(0, box(0, 0, 10, 6))
    states = generate_states(cell, 2, (90,), first_turn=side)
    assert len(states) == 2
    assert all(s.first_turn == side for s in states)
    for s in states:
        assert cell.polygon.buffer(1e-8).covers(LineString(s.path))


def test_first_turn_cross_product():
    for s in generate_states(Cell(0, box(0, 0, 10, 6)), 2, (90, 0)):
        a, b = s.lanes[0]
        c, d = s.lanes[1]
        first = (b[0] - a[0], b[1] - a[1])
        advance = ((c[0] + d[0] - a[0] - b[0]) / 2, (c[1] + d[1] - a[1] - b[1]) / 2)
        cross = first[0] * advance[1] - first[1] * advance[0]
        assert s.first_turn == ("left" if cross > 0 else "right")


def test_single_lane_has_no_turn():
    states = generate_states(Cell(0, box(0, 0, 1, 8)), 2, (90,), first_turn="left")
    assert len(states) == 2
    assert all(s.first_turn == "none" for s in states)


def test_invalid_orientation_is_skipped():
    poly, _ = load_map(ROOT / "examples/concave_u.json")
    states = generate_states(Cell(0, poly), 2, (90, 0))
    assert {s.angle_deg for s in states} == {90}
    with pytest.raises(ValueError, match="no valid states"):
        generate_states(Cell(0, poly), 2, (0,))


@pytest.mark.parametrize("spacing", [0, -1, float("nan"), float("inf")])
def test_invalid_spacing(spacing):
    with pytest.raises(ValueError):
        generate_states(Cell(0, box(0, 0, 10, 6)), spacing)
