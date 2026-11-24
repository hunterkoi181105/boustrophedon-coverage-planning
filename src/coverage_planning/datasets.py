"""Prepare reproducible synthetic and AC300 polygon-with-holes benchmarks.

Use `python -m coverage_planning.datasets --help` for local and GitHub imports.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from shapely.geometry import Point, Polygon, box


def _write_map(path: Path, data: dict) -> None:
    polygon = Polygon(data["boundary"], data["holes"])
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError(f"Invalid generated polygon: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def synthetic(out: Path, count: int, seed: int, swath: float) -> int:
    """Generate rectangular maps with 0..5 disjoint rectangular holes."""
    if count < 1 or swath <= 0:
        raise ValueError("count and swath must be positive")
    for index in range(count):
        rng = random.Random(seed + index)
        w = float(rng.randint(85, 115))
        h = float(rng.randint(85, 115))
        n_holes = index % 6
        holes = []
        occupied = []
        for _ in range(n_holes):
            for _attempt in range(1000):
                rw = rng.uniform(5, 13)
                rh = rng.uniform(5, 13)
                x = rng.uniform(12, w - 12 - rw)
                y = rng.uniform(12, h - 12 - rh)
                proposal = box(x, y, x + rw, y + rh)
                if all(not proposal.buffer(3).intersects(prev) for prev in occupied):
                    occupied.append(proposal)
                    holes.append([[round(a, 5), round(b, 5)]
                                  for a, b in list(proposal.exterior.coords)[:-1]])
                    break
            else:
                raise ValueError("Could not generate disjoint holes")
        data = {
            "name": f"synthetic_{index:03d}", "units": "metres",
            "boundary": [[0, 0], [w, 0], [w, h], [0, h]],
            "holes": holes, "start": [1, 1], "swath": swath,
            "generation_seed": seed + index,
        }
        _write_map(out / f"synthetic_{index:03d}.json", data)
    return count


def _points(text: str) -> list[list[float]]:
    points = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) != 2:
            raise ValueError("Expected exactly two numeric columns in coordinate file")
        points.append([float(tokens[0]), float(tokens[1])])
    return points


def _read_rings(path: Path) -> list[list[list[float]]]:
    if not path.exists():
        return []
    rings = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        if block:
            ring = _points(block)
            if len(ring) < 3:
                raise ValueError(f"Invalid ring in {path}")
            rings.append(ring)
    return rings


def ac300(source: Path, out: Path, per_hole: int | None, hole_counts: list[int] | None,
          swath: float) -> int:
    """Import matching UNC Charlotte AC300 maps, using one consistent depot."""
    if (per_hole is not None and per_hole < 1) or not math.isfinite(swath) or swath <= 0:
        raise ValueError("per-hole and swath must be positive")
    root = source / "AC300" if (source / "AC300").is_dir() else source
    groups: dict[int, list[Path]] = {}
    for directory in sorted(root.iterdir()):
        match = re.fullmatch(r"AC(\d+)_\d+", directory.name)
        if match and directory.is_dir():
            groups.setdefault(int(match[1]), []).append(directory)
    if not groups:
        raise ValueError(f"No AC300 map directories found in {root}")
    total = 0
    for holes in sorted(groups) if hole_counts is None else hole_counts:
        candidates = groups.get(holes, [])
        if not candidates or (per_hole is not None and len(candidates) < per_hole):
            raise ValueError(f"Need {per_hole} AC{holes} environments, found {len(candidates)}")
        for directory in candidates[:per_hole]:
            outer_rings = _read_rings(directory / "outer_polygon")
            if len(outer_rings) != 1:
                raise ValueError(f"Expected one outer ring at {directory}")
            inner_rings = _read_rings(directory / "holes")
            if len(inner_rings) != holes:
                raise ValueError(
                    f"Expected {holes} holes, found {len(inner_rings)} in {directory}"
                )
            region = Polygon(outer_rings[0], inner_rings)
            if not region.is_valid or region.area <= 0:
                raise ValueError(f"Invalid AC300 geometry: {directory}")
            # A common, unobstructed depot; not a source-provided reference depot.
            depot = (1.0, 1.0)
            if not region.covers(Point(depot)):
                depot = tuple(region.representative_point().coords[0])
            data = {
                "name": directory.name, "units": "metres",
                "boundary": outer_rings[0], "holes": inner_rings,
                "start": list(depot), "swath": swath,
                "dataset": "UNCCharlotte-CS-Robotics/AreaCoverage-dataset AC300",
                "source": f"UNCCharlotte-CS-Robotics/AreaCoverage-dataset/AC300/{directory.name}",
            }
            _write_map(out / f"{directory.name}.json", data)
            total += 1
    return total


def fetch_ac300(out: Path, swath: float) -> int:
    """Check out the AC300 subtree from GitHub, convert all maps, and clean up."""
    url = "https://github.com/UNCCharlotte-CS-Robotics/AreaCoverage-dataset.git"
    with TemporaryDirectory() as tmp:
        repo = Path(tmp) / "dataset"
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                        "--branch", "main", url, str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", "AC300"], check=True)
        return ac300(repo, out, None, None, swath)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build reproducible PWH benchmark maps")
    commands = parser.add_subparsers(dest="mode", required=True)
    gen = commands.add_parser("synthetic", help="Generate fixed-seed maps with 0..5 holes")
    gen.add_argument("--out", default="benchmarks/synthetic")
    gen.add_argument("--count", type=int, default=10)
    gen.add_argument("--seed", type=int, default=2026)
    gen.add_argument("--swath", type=float, default=3.0)
    imp = commands.add_parser("ac300", help="Convert AC300 folders from a local dataset clone")
    imp.add_argument("--source", required=True, help="Path to AreaCoverage-dataset or AC300 folder")
    imp.add_argument("--out", default="benchmarks/ac300")
    imp.add_argument("--per-hole", type=int, default=3)
    imp.add_argument("--holes", nargs="+", type=int, default=[1, 3, 5, 10, 15])
    imp.add_argument("--swath", type=float, default=3.0)
    fetch = commands.add_parser("fetch-ac300", help="Download and convert the full AC300 dataset")
    fetch.add_argument("--out", default="benchmarks/ac300_full")
    fetch.add_argument("--swath", type=float, default=3.0)
    fetch.add_argument("--source", type=Path, help="Use an existing checkout or AC300 folder")
    args = parser.parse_args(argv)
    try:
        if args.mode == "synthetic":
            total = synthetic(Path(args.out), args.count, args.seed, args.swath)
        elif args.mode == "fetch-ac300":
            if args.source is None:
                total = fetch_ac300(Path(args.out), args.swath)
            else:
                total = ac300(args.source, Path(args.out), None, None, args.swath)
        else:
            total = ac300(Path(args.source), Path(args.out), args.per_hole,
                          args.holes, args.swath)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Dataset preparation failed: {exc}\n")
    print(f"Prepared {total} maps in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
