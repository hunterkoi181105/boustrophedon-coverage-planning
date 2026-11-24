from __future__ import annotations

import argparse
import json

from .pipeline import Config, plan, save_run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BCD coverage planning: TSP and sweep-state GTSP")
    parser.add_argument("map", help="JSON file with boundary, holes, and optional start/swath")
    parser.add_argument("--algorithm", choices=["tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact", "aco"], default="gtsp")
    parser.add_argument("--decomposition-angle", type=float, default=90.0, help="Slice orientation from +X, degrees")
    parser.add_argument("--angles", nargs="+", type=float, help="Candidate lane orientations; invalid angles per cell are skipped")
    parser.add_argument("--swath", type=float, help="Sensor/tool coverage width, NOT robot diameter")
    parser.add_argument("--spacing", type=float, help="Maximum lane separation; defaults to swath")
    parser.add_argument("--first-turn", choices=["any", "left", "right"], default="any", help="Filter nominal first lane reversal in EACH multi-lane cell")
    parser.add_argument("--boundary-pass", action="store_true", help="Add one perimeter pass per cell")
    parser.add_argument("--open", action="store_true", help="Do not return to the start depot")
    parser.add_argument("--start", nargs=2, type=float, metavar=("X", "Y"))
    parser.add_argument("--start-heading", type=float, help="Initial vehicle heading, degrees from +X; used by turn-weight")
    parser.add_argument("--turn-weight", type=float, default=0.0, help="Objective units per radian of heading change")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--restarts", type=int, default=2)
    parser.add_argument("--aco-ants", type=int, default=Config.aco_ants)
    parser.add_argument("--aco-iterations", type=int, default=Config.aco_iterations)
    parser.add_argument("--out", default="results/demo")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args(argv)
    config = Config(
        algorithm=args.algorithm, decomposition_angle=args.decomposition_angle,
        angles=None if args.angles is None else tuple(args.angles),
        swath=args.swath, spacing=args.spacing, first_turn=args.first_turn,
        boundary_pass=args.boundary_pass, closed=not args.open,
        start=None if args.start is None else tuple(args.start),
        start_heading=args.start_heading, turn_weight=args.turn_weight,
        seed=args.seed, restarts=args.restarts,
        aco_ants=args.aco_ants, aco_iterations=args.aco_iterations,
    )
    try:
        run = plan(args.map, config)
        save_run(run, args.out, make_plot=not args.no_plot)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Planning failed: {exc}\n")
    print(json.dumps(run.metrics, indent=2))
    print(f"Outputs written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
