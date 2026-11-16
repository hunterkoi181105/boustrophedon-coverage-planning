from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .pipeline import Config, plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reproducible planner comparison on JSON maps")
    parser.add_argument("--maps", default="examples")
    parser.add_argument("--algorithms", nargs="+", default=["tsp-greedy", "tsp-2opt", "gtsp"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--boundary-pass", action="store_true")
    parser.add_argument("--out", default="results/benchmark.csv")
    args = parser.parse_args(argv)
    paths = sorted(Path(args.maps).glob("*.json"))
    if not paths:
        parser.exit(2, "No JSON maps found.\n")
    rows = []
    for path in paths:
        for algorithm in args.algorithms:
            for seed in args.seeds:
                # Fresh model/router each run: no cross-solver warm-cache advantage.
                run = plan(path, Config(algorithm=algorithm, seed=seed, boundary_pass=args.boundary_pass))
                m = run.metrics
                row = {"map": path.stem, **{k: v for k, v in m.items() if not isinstance(v, (list, tuple))}}
                rows.append(row)
                print(f"{path.stem:24} {algorithm:12} seed={seed} length={m['total_length']:.3f} coverage={m['coverage_ratio']:.3%}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
