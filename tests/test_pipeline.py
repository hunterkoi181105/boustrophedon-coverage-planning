import json

import pytest

from coverage_planning.cli import main
from coverage_planning.pipeline import Config, plan, save_run

from .conftest import ROOT


def test_serialization(tmp_path):
    run = plan(ROOT / "examples/rectangle.json")
    save_run(run, tmp_path, make_plot=False)
    data = json.loads((tmp_path / "plan.json").read_text())
    assert data["metrics"]["num_cells"] == 1
    assert (tmp_path / "geometry.geojson").exists()


def test_cli(tmp_path):
    assert main([
        str(ROOT / "examples/one_obstacle.json"), "--algorithm", "gtsp",
        "--first-turn", "left", "--out", str(tmp_path), "--no-plot",
    ]) == 0
    data = json.loads((tmp_path / "plan.json").read_text())
    assert set(data["metrics"]["selected_first_turns"]) <= {"left", "none"}


def test_boundary_pass_closes_triangle_gaps(tmp_path):
    path = tmp_path / "triangle.json"
    path.write_text(json.dumps({"boundary": [[0, 0], [20, 0], [0, 12]], "swath": 2}))
    regular = plan(path, Config(angles=(90,)))
    repaired = plan(path, Config(angles=(90,), boundary_pass=True))
    assert repaired.metrics["coverage_ratio"] >= regular.metrics["coverage_ratio"]
    assert repaired.metrics["coverage_ratio"] >= 0.999
    assert repaired.metrics["total_length"] > regular.metrics["total_length"]


def test_invalid_spacing():
    with pytest.raises(ValueError, match="no greater"):
        plan(ROOT / "examples/rectangle.json", Config(swath=1, spacing=2))


def test_aco_cli_single_cell(tmp_path):
    assert main([str(ROOT / "examples/rectangle.json"), "--algorithm", "aco",
                 "--aco-ants", "3", "--aco-iterations", "4", "--turn-weight", "0.5",
                 "--start-heading", "33", "--out", str(tmp_path), "--no-plot"]) == 0
    report = json.loads((tmp_path / "plan.json").read_text())
    assert report["config"]["aco_ants"] == 3
    assert report["config"]["aco_iterations"] == 4
    m = report["metrics"]
    assert m["algorithm"] == "aco"
    assert len(report["states"]) == 1
    assert m["objective"] == pytest.approx(m["total_length"] + 0.5 * m["absolute_turn_angle_rad"])
