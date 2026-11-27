import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from coverage_planning.decomposition import decompose
from coverage_planning.geometry import is_monotone, load_map

from .conftest import ROOT


@pytest.mark.parametrize("name", ["rectangle", "one_obstacle", "two_obstacles", "concave_u"])
@pytest.mark.parametrize("angle", [0, 30, 90])
def test_partition_and_monotonicity(name, angle):
    region, _ = load_map(ROOT / f"examples/{name}.json")
    result = decompose(region, angle)
    combined = unary_union([c.polygon for c in result.cells])
    assert combined.symmetric_difference(region).area < 1e-6
    assert abs(sum(c.polygon.area for c in result.cells) - region.area) < 1e-6
    assert all(is_monotone(c.polygon, angle) for c in result.cells)
    for u, neighbors in result.adjacency.items():
        assert u not in neighbors
        assert all(u in result.adjacency[v] for v in neighbors)


def test_rectangle_is_one_cell():
    assert len(decompose(box(0, 0, 10, 6)).cells) == 1


def test_rectangular_hole_is_four_cells(one_obstacle):
    result = decompose(one_obstacle)
    assert len(result.cells) == 4
    assert sum(len(n) for n in result.adjacency.values()) == 8


def test_rotated_neighbors_share_positive_length_gates(one_obstacle):
    result = decompose(one_obstacle, 17)
    assert sum(len(neighbors) for neighbors in result.adjacency.values()) == 8
    for cell in result.cells:
        for neighbor_id in result.adjacency[cell.id]:
            neighbor = result.cells[neighbor_id]
            assert cell.polygon.boundary.intersection(neighbor.polygon.boundary).length > 0


def test_middle_events_do_not_create_cells():
    # Lots of vertices, but all vertical sections remain connected.
    poly = Polygon([(0, 0), (4, 0), (8, 0), (8, 5), (6, 6), (4, 5), (2, 7), (0, 5)])
    assert len(decompose(poly).cells) == 1


def test_simultaneous_split_merge_not_missed():
    poly = Polygon([(0, 0), (14, 0), (14, 12), (0, 12)], holes=[
        [(2, 2), (6, 2), (6, 4), (2, 4)],
        [(6, 7), (10, 7), (10, 9), (6, 9)],
    ])
    result = decompose(poly)
    event = next(e for e in result.events if abs(e["local_x"] - 6) < 1e-9)
    assert event["components_before"] == event["components_after"]
    assert event["splits"] == event["merges"] == 1


def test_concave_hole():
    poly = Polygon([(0, 0), (16, 0), (16, 14), (0, 14)], holes=[
        [(3, 3), (11, 3), (11, 5), (6, 5), (6, 9), (11, 9), (11, 11), (3, 11)],
    ])
    result = decompose(poly)
    assert unary_union([c.polygon for c in result.cells]).symmetric_difference(poly).area < 1e-8
    assert all(is_monotone(c.polygon, 90) for c in result.cells)


def test_u_shape_is_x_but_not_y_monotone():
    poly, _ = load_map(ROOT / "examples/concave_u.json")
    assert is_monotone(poly, 90)
    assert not is_monotone(poly, 0)
    assert len(decompose(poly, 90).cells) == 1
    assert len(decompose(poly, 0).cells) == 3


def test_invalid_polygon_rejected():
    with pytest.raises(ValueError):
        decompose(Polygon([(0, 0), (1, 1), (0, 1), (1, 0)]))
