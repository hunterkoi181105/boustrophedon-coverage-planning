import math

import pytest
from shapely.geometry import LineString

from coverage_planning.geometry import path_length
from coverage_planning.transitions import VisibilityRouter


def test_connector_avoids_hole(one_obstacle):
    router = VisibilityRouter(one_obstacle)
    a, b = (2.0, 8.0), (22.0, 8.0)
    path = router.path(a, b)
    assert len(path) > 2
    assert path_length(path) > math.dist(a, b)
    assert one_obstacle.covers(LineString(path))
    assert path[0] == a and path[-1] == b


def test_direct_and_zero_length(one_obstacle):
    router = VisibilityRouter(one_obstacle)
    assert router.path((1.0, 1.0), (2.0, 2.0)) == ((1.0, 1.0), (2.0, 2.0))
    assert router.path((1.0, 1.0), (1.0, 1.0)) == ((1.0, 1.0),)


def test_outside_endpoint(one_obstacle):
    router = VisibilityRouter(one_obstacle)
    with pytest.raises(ValueError, match="outside"):
        router.path((12.0, 8.0), (1.0, 1.0))
