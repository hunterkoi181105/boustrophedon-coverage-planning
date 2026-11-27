import csv
import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from coverage_planning.benchmark import main as benchmark_main
from coverage_planning.datasets import ac300, main as datasets_main, synthetic

from .conftest import ROOT


def test_benchmark_each_run_has_metrics_and_files(tmp_path):
    folder = tmp_path / "maps"
    folder.mkdir()
    (folder / "rectangle.json").write_text(
        (ROOT / "examples/rectangle.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    output = tmp_path / "metrics.csv"
    assert benchmark_main([
        "--maps", str(folder), "--algorithms", "tsp-greedy", "gtsp",
        "--seeds", "0", "1", "--robot-speed", "2", "--out", str(output),
    ]) == 0
    with output.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert all(row["status"] == "ok" for row in rows)
    assert all(float(row["coverage_ratio"]) == pytest.approx(1.0) for row in rows)
    assert all("total_length" in row for row in rows)
    assert all(float(row["total_length"]) == pytest.approx(
        float(row["service_length"]) + float(row["transit_length"])
    ) for row in rows)
    assert all(float(row["planning_seconds"]) >= 0 for row in rows)
    assert all(float(row["estimated_mission_seconds"]) == pytest.approx(
        float(row["total_length"]) / 2
    ) for row in rows)
    assert all(json.loads(row["selected_sweep_angles_deg"]) for row in rows)
    assert all(Path(row["run_directory"], "metrics.json").is_file() for row in rows)
    with output.with_name("metrics_summary.csv").open(newline="", encoding="utf-8") as f:
        summary = list(csv.DictReader(f))
    assert len(summary) == 2
    assert all(int(row["runs"]) == 2 for row in summary)
    assert all(float(row["success_rate"]) == 1 for row in summary)


def test_benchmark_preserves_failures_and_nested_names(tmp_path):
    maps = tmp_path / "maps"
    (maps / "nested").mkdir(parents=True)
    (maps / "nested" / "invalid.json").write_text("not JSON", encoding="utf-8")
    (maps / "nested" / "rectangle.json").write_text(
        (ROOT / "examples/rectangle.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    out = tmp_path / "runs.csv"
    assert benchmark_main([
        "--maps", str(maps), "--algorithms", "tsp-2opt", "--seeds", "7",
        "--no-save-runs", "--out", str(out),
    ]) == 0
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["map"] == "nested/invalid"
    assert rows[0]["status"] == "failed"
    assert "JSONDecodeError" in rows[0]["error"]
    assert rows[1]["map"] == "nested/rectangle"
    assert rows[1]["status"] == "ok"
    assert benchmark_main([
        "--maps", str(maps), "--algorithms", "tsp-2opt", "--seeds", "7",
        "--strict", "--no-save-runs", "--out", str(out),
    ]) == 1


def test_fixed_seed_synthetic_geometry(tmp_path):
    left = tmp_path / "a"
    right = tmp_path / "b"
    assert synthetic(left, count=7, seed=2026, swath=3.0) == 7
    assert synthetic(right, count=7, seed=2026, swath=3.0) == 7
    for i in range(7):
        name = f"synthetic_{i:03d}.json"
        assert (left / name).read_bytes() == (right / name).read_bytes()
        data = json.loads((left / name).read_text(encoding="utf-8"))
        assert len(data["holes"]) == i % 6
        assert Polygon(data["boundary"], data["holes"]).is_valid


def test_ac300_converter_parses_blank_line_separated_holes(tmp_path):
    source = tmp_path / "source" / "AC300" / "AC1_0000"
    source.mkdir(parents=True)
    (source / "outer_polygon").write_text("0 0\n100 0\n100 100\n0 100\n")
    (source / "holes").write_text("30 30\n40 30\n40 40\n30 40\n")
    destination = tmp_path / "converted"
    assert ac300(source.parent, destination, 1, [1], 3.0) == 1
    result = json.loads((destination / "AC1_0000.json").read_text(encoding="utf-8"))
    assert result["swath"] == 3.0
    assert result["start"] == [1.0, 1.0]
    assert len(result["holes"]) == 1
    assert Polygon(result["boundary"], result["holes"]).area == pytest.approx(9900)


def test_datasets_cli_synthetic(tmp_path):
    assert datasets_main([
        "synthetic", "--count", "2", "--seed", "19", "--out", str(tmp_path),
    ]) == 0
    assert len(list(tmp_path.glob("*.json"))) == 2
