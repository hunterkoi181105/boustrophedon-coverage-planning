"""Regression cases where geometric tolerances must not erase topology."""

import math

import pytest
from shapely.errors import GEOSException
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

import coverage_planning.decomposition as decomposition
from coverage_planning.geometry import event_coordinates, is_monotone


@pytest.fixture
def close_event_c_shape():
    return Polygon([
        (0, 0), (10, 0), (10, 3), (4.000000005, 3),
        (4.000000005, 7), (10, 7), (10, 10), (4, 10), (0, 10),
    ])


def assert_partition(region, result):
    """Use relative area checks so a small missing polygon cannot pass."""
    assert result.cells
    assert all(cell.polygon.is_valid and cell.polygon.area > 0 for cell in result.cells)
    combined = unary_union([cell.polygon for cell in result.cells])
    assert combined.symmetric_difference(region).area <= region.area * 1e-12
    assert sum(cell.polygon.area for cell in result.cells) == pytest.approx(
        region.area, rel=1e-12, abs=0,
    )
    assert all(is_monotone(cell.polygon, 90) for cell in result.cells)


def test_nearby_distinct_events_are_preserved(close_event_c_shape):
    assert event_coordinates(close_event_c_shape) == [0.0, 4.0, 4.000000005, 10.0]


def test_close_event_split_is_not_hidden(close_event_c_shape):
    assert close_event_c_shape.is_valid
    assert not is_monotone(close_event_c_shape, 90)
    result = decomposition.decompose(close_event_c_shape, 90)
    assert len(result.cells) == 3
    assert sum(event["splits"] for event in result.events) == 1
    assert_partition(close_event_c_shape, result)


@pytest.mark.parametrize("width,height", [
    (5e-10, 1.0),
    (1.0, 5e-10),
    (5e-10, 5e-10),
])
def test_positive_small_rectangles_are_not_discarded(width, height):
    region = box(0, 0, width, height)
    assert region.is_valid and region.area > 0
    assert event_coordinates(region) == [0.0, width]
    result = decomposition.decompose(region, 90)
    assert len(result.cells) == 1
    assert_partition(region, result)


def test_short_positive_gate_continues_the_same_cell():
    # The extra top-edge vertex creates two event strips sharing a short gate.
    region = Polygon([(0, 0), (10, 0), (10, 5e-10), (4, 5e-10), (0, 5e-10)])
    result = decomposition.decompose(region, 90)
    assert len(result.cells) == 1
    assert_partition(region, result)


def test_adjacent_float_events_do_not_require_an_interior_sample():
    right = math.nextafter(1.0, math.inf)
    region = box(1.0, 0, right, 1)
    assert event_coordinates(region) == [1.0, right]
    result = decomposition.decompose(region, 90)
    assert len(result.cells) == 1
    assert_partition(region, result)


def test_axis_aligned_one_ulp_backtrack_is_nonmonotone():
    left = 4.0
    right = math.nextafter(left, math.inf)
    # Two sections occur only between adjacent floats: no float midpoint exists.
    region = Polygon([
        (0, 0), (10, 0), (10, 10), (left, 10),
        (left, 6), (right, 6), (right, 4), (0, 4),
    ])
    assert region.is_valid
    assert not is_monotone(region, 90)
    result = decomposition.decompose(region, 90)
    assert len(result.cells) == 3
    assert_partition(region, result)


def test_empty_decomposition_of_positive_area_is_rejected(monkeypatch):
    region = box(0, 0, 1e-4, 1e-4)
    monkeypatch.setattr(decomposition, "polygon_parts", lambda _geometry: [])
    with pytest.raises(ValueError, match="(?i)(numerical|degenera|empty|coverage|area)"):
        decomposition.decompose(region, 90)


def test_partial_loss_of_small_region_is_rejected(monkeypatch):
    region = box(0, 0, 1e-4, 1e-4)
    partial = box(0, 0, 5e-5, 1e-4)
    # Simulate an overlay losing half a region, below the former absolute floor.
    monkeypatch.setattr(decomposition, "polygon_parts", lambda _geometry: [partial])
    with pytest.raises(ValueError, match="(?i)(numerical|degenera|coverage|area)"):
        decomposition.decompose(region, 90)


def test_nonmonotone_output_is_rejected(monkeypatch, close_event_c_shape):
    # Simulate a missed split. Area conservation alone still holds in this case.
    monkeypatch.setattr(decomposition, "event_coordinates", lambda _polygon: [0.0, 10.0])
    with pytest.raises(ValueError, match="(?i)(numerical|degenera|monotone)"):
        decomposition.decompose(close_event_c_shape, 90)


def test_overlay_failure_reports_numerical_degeneracy(monkeypatch):
    def failed_intersection(*_args, **_kwargs):
        raise GEOSException("forced overlay failure")

    monkeypatch.setattr(Polygon, "intersection", failed_intersection)
    with pytest.raises(ValueError, match="(?i)(numerical|degenera)"):
        decomposition.decompose(box(0, 0, 2, 1), 90)
