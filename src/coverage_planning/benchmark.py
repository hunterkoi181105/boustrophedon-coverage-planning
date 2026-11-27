"""Run reproducible per-instance benchmarks and retain every run's metrics."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from .geometry import load_map
from .pipeline import Config, plan, save_run

ALGORITHMS = ("tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact")
METRIC_COLUMNS = (
    "objective", "total_length", "service_length", "transit_length",
    "coverage_ratio", "uncovered_area", "overlap_excess_ratio",
    "vertex_turn_count", "lane_reversal_count", "absolute_turn_angle_rad",
    "preprocessing_seconds", "solver_seconds", "planning_seconds",
    "collision_free_within_tolerance", "num_cells", "num_candidate_states",
)
COLUMNS = (
    "map", "source_file", "algorithm", "seed", "status", "error", "run_directory",
    "holes", "vertices", "free_area", "swath", "spacing", "decomposition_angle_deg",
    "candidate_angles_deg", "turn_weight", "robot_speed_m_per_s", "restarts", "closed", "boundary_pass",
    *METRIC_COLUMNS, "coverage_percent", "overlap_excess_percent",
    "estimated_mission_seconds",
    "selected_cell_order", "selected_sweep_angles_deg", "selected_first_turns",
)
SUMMARY_COLUMNS = (
    "map", "algorithm", "runs", "successful_runs", "success_rate",
    "total_length_median", "total_length_iqr", "coverage_percent_median",
    "transit_length_median", "vertex_turn_count_median", "lane_reversal_count_median",
    "overlap_excess_percent_median", "planning_seconds_median", "planning_seconds_iqr",
    "estimated_mission_seconds_median",
)


def _quartile(values: list[float], proportion: float) -> float:
    """Linear interpolation at (n - 1) * proportion for reproducible IQR."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * proportion
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _stat(rows: list[dict], field: str, *, iqr: bool = False) -> float | str:
    values = [float(row[field]) for row in rows if row.get(field) not in (None, "")]
    if not values:
        return ""
    if iqr:
        return _quartile(values, 0.75) - _quartile(values, 0.25)
    return statistics.median(values)


def _write_summary(rows: list[dict], path: Path) -> None:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["map"], row["algorithm"])].append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for (name, algorithm), group in sorted(groups.items()):
            passed = [row for row in group if row["status"] == "ok"]
            writer.writerow({
                "map": name, "algorithm": algorithm, "runs": len(group),
                "successful_runs": len(passed), "success_rate": len(passed) / len(group),
                "total_length_median": _stat(passed, "total_length"),
                "total_length_iqr": _stat(passed, "total_length", iqr=True),
                "coverage_percent_median": _stat(passed, "coverage_percent"),
                "transit_length_median": _stat(passed, "transit_length"),
                "vertex_turn_count_median": _stat(passed, "vertex_turn_count"),
                "lane_reversal_count_median": _stat(passed, "lane_reversal_count"),
                "overlap_excess_percent_median": _stat(passed, "overlap_excess_percent"),
                "planning_seconds_median": _stat(passed, "planning_seconds"),
                "planning_seconds_iqr": _stat(passed, "planning_seconds", iqr=True),
                "estimated_mission_seconds_median": _stat(passed, "estimated_mission_seconds"),
            })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Per-run metrics for BCD + TSP/GTSP benchmarks")
    parser.add_argument("--maps", default="examples", help="Directory of JSON maps (searched recursively)")
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHMS,
                        default=["tsp-greedy", "tsp-2opt", "gtsp"])
    seed_choice = parser.add_mutually_exclusive_group()
    seed_choice.add_argument("--seeds", nargs="+", type=int, help="Explicit fixed seed values")
    seed_choice.add_argument("--seed-count", type=int, help="Use seeds 0..N-1 (30 for randomized GTSP)")
    parser.add_argument("--decomposition-angle", type=float, default=90.0)
    parser.add_argument("--angles", nargs="+", type=float, default=None)
    parser.add_argument("--swath", type=float, default=None)
    parser.add_argument("--spacing", type=float, default=None)
    parser.add_argument("--turn-weight", type=float, default=0.0)
    parser.add_argument("--robot-speed", type=float, default=None,
                        help="Optional constant speed (m/s) for estimated mission duration")
    parser.add_argument("--restarts", type=int, default=2)
    parser.add_argument("--start", nargs=2, type=float, default=None)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--boundary-pass", action="store_true")
    parser.add_argument("--out", default="results/benchmark.csv")
    parser.add_argument("--runs-dir", help="Where per-run plan.json and metrics.json are written")
    parser.add_argument("--no-save-runs", action="store_true", help="Only write CSV files")
    parser.add_argument("--plot-runs", action="store_true", help="Also save per-run trajectory.png")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if any run fails")
    args = parser.parse_args(argv)
    if args.seed_count is not None and args.seed_count < 1:
        parser.error("--seed-count must be positive")
    if args.restarts < 0:
        parser.error("--restarts must be nonnegative")
    if args.robot_speed is not None and (
        not math.isfinite(args.robot_speed) or args.robot_speed <= 0
    ):
        parser.error("--robot-speed must be a finite positive number")
    if not math.isfinite(args.decomposition_angle):
        parser.error("--decomposition-angle must be finite")
    if args.plot_runs and args.no_save_runs:
        parser.error("--plot-runs is incompatible with --no-save-runs")
    seeds = args.seeds if args.seeds is not None else list(range(args.seed_count or 3))
    maps_dir = Path(args.maps)
    paths = sorted(maps_dir.rglob("*.json"))
    if not paths:
        parser.error(f"No JSON maps found in {maps_dir}")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = output.with_name(output.stem + "_summary.csv")
    runs_dir = Path(args.runs_dir) if args.runs_dir else output.with_name(output.stem + "_runs")
    rows: list[dict] = []
    failures = 0
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for path in paths:
            name = path.relative_to(maps_dir).with_suffix("").as_posix()
            for algorithm in args.algorithms:
                for seed in seeds:
                    directory = runs_dir / name / algorithm / f"seed_{seed}"
                    row: dict = {
                        "map": name, "source_file": str(path), "algorithm": algorithm,
                        "seed": seed, "status": "ok", "error": "", "run_directory": "",
                        "decomposition_angle_deg": args.decomposition_angle,
                        "candidate_angles_deg": json.dumps(args.angles if args.angles is not None
                                                           else [args.decomposition_angle, 0.0]),
                        "turn_weight": args.turn_weight, "robot_speed_m_per_s": args.robot_speed,
                        "restarts": args.restarts,
                        "closed": not args.open, "boundary_pass": args.boundary_pass,
                    }
                    try:
                        region, data = load_map(path)
                        row.update({
                            "holes": len(region.interiors),
                            "vertices": len(region.exterior.coords) - 1 + sum(
                                len(ring.coords) - 1 for ring in region.interiors
                            ),
                            "free_area": region.area,
                        })
                        config = Config(
                            algorithm=algorithm, seed=seed, boundary_pass=args.boundary_pass,
                            decomposition_angle=args.decomposition_angle,
                            angles=tuple(args.angles) if args.angles is not None else None,
                            swath=args.swath, spacing=args.spacing, turn_weight=args.turn_weight,
                            restarts=args.restarts, closed=not args.open,
                            start=tuple(args.start) if args.start is not None else None,
                        )
                        # Fresh planner, costs, and router per trial: no cross-trial cache.
                        run = plan(path, config)
                        metrics = run.metrics
                        row.update({k: metrics.get(k, "") for k in METRIC_COLUMNS})
                        row.update({
                            "swath": metrics["swath"], "spacing": metrics["spacing"],
                            "coverage_percent": metrics["coverage_ratio"] * 100,
                            "estimated_mission_seconds": (
                                metrics["total_length"] / args.robot_speed
                                if args.robot_speed is not None else ""
                            ),
                            "overlap_excess_percent": metrics["overlap_excess_ratio"] * 100,
                            "selected_cell_order": json.dumps(metrics["selected_cell_order"]),
                            "selected_first_turns": json.dumps(metrics["selected_first_turns"]),
                            "selected_sweep_angles_deg": json.dumps(
                                [s.angle_deg for s in run.solution.states]
                            ),
                        })
                        if not args.no_save_runs:
                            save_run(run, directory, make_plot=args.plot_runs)
                            row["run_directory"] = str(directory)
                        print(f"OK   {name:24} {algorithm:12} seed={seed:<3} "
                              f"length={metrics['total_length']:.3f} "
                              f"coverage={metrics['coverage_ratio']:.1%} "
                              f"turns={metrics['vertex_turn_count']} "
                              f"time={metrics['planning_seconds']:.3f}s", flush=True)
                    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
                        failures += 1
                        row["status"] = "failed"
                        row["error"] = f"{type(exc).__name__}: {exc}"
                        print(f"FAIL {name:24} {algorithm:12} seed={seed:<3} {row['error']}",
                              file=sys.stderr, flush=True)
                    writer.writerow(row)
                    handle.flush()  # Partial results survive interrupted benchmark jobs.
                    rows.append(row)
                    _write_summary(rows, summary)
    print(f"Per-run metrics: {output}\nPer-map summaries: {summary}")
    print(f"Completed {len(rows) - failures}/{len(rows)} runs successfully.")
    return 1 if failures and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
