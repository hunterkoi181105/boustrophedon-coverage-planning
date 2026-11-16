from pathlib import Path

import pytest

from coverage_planning.geometry import load_map

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def one_obstacle():
    return load_map(ROOT / "examples/one_obstacle.json")[0]
