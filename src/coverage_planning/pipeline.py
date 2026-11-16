from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from shapely.geometry import LineString, mapping

from .costs import CostModel
from .decomposition import decompose
from .geometry import load_map
from .metrics import evaluate
from .planners import solve_exact, solve_gtsp, solve_tsp
from .sweeps import generate_states
from .transitions import VisibilityRouter


@dataclass
class Config:
    algorithm: str = "gtsp"
    decomposition_angle: float = 90.0
    angles: tuple[float, ...] | None = None
    swath: float | None = None
    spacing: float | None = None
    first_turn: str = "any"
    boundary_pass: bool = False
    closed: bool = True
    start: tuple[float, float] | None = None
    start_heading: float | None = None
    turn_weight: float = 0.0
    seed: int = 0
    restarts: int = 2


@dataclass
class Run:
    region: object
    decomposition: object
    model: CostModel
    solution: object
    metrics: dict
    config: Config
    map_data: dict


def plan(map_path: str | Path, config: Config | None = None) -> Run:
    config = config or Config()
    if not math.isfinite(config.decomposition_angle):
        raise ValueError("decomposition_angle must be finite")
    started = time.perf_counter()
    region, data = load_map(map_path)
    swath = float(config.swath if config.swath is not None else data.get("swath", 1.0))
    spacing = float(config.spacing if config.spacing is not None else swath)
    if not math.isfinite(swath) or swath <= 0:
        raise ValueError("swath must be finite and positive")
    if not math.isfinite(spacing) or spacing <= 0 or spacing > swath:
        raise ValueError("spacing must be positive and no greater than swath")
    angles = config.angles if config.angles is not None else (config.decomposition_angle, 0.0)
    decomposition = decompose(region, config.decomposition_angle)
    clusters = []
    offset = 0
    for cell in decomposition.cells:
        cluster = generate_states(
            cell, spacing, tuple(angles), config.first_turn, config.boundary_pass, offset,
        )
        clusters.append(cluster)
        offset += len(cluster)
    default_start = tuple(region.representative_point().coords[0])
    start = tuple(config.start if config.start is not None else data.get("start", default_start))
    router = VisibilityRouter(region)
    model = CostModel(
        clusters, router, start, config.closed, config.turn_weight, config.start_heading,
    )
    preprocessed = time.perf_counter()
    if config.algorithm == "tsp-greedy":
        solution = solve_tsp(model, improve=False)
    elif config.algorithm == "tsp-2opt":
        solution = solve_tsp(model)
    elif config.algorithm == "gtsp":
        solution = solve_gtsp(model, seed=config.seed, restarts=config.restarts)
    elif config.algorithm == "gtsp-exact":
        solution = solve_exact(model)
    else:
        raise ValueError(f"Unknown algorithm: {config.algorithm}")
    solved = time.perf_counter()
    metrics = evaluate(solution, model, region, swath)
    metrics.update({
        "preprocessing_seconds": preprocessed - started,
        "solver_seconds": solved - preprocessed,
        "planning_seconds": solved - started,
        "swath": swath,
        "spacing": spacing,
        "start": start,
        "closed": config.closed,
        "boundary_pass": config.boundary_pass,
        "seed": config.seed,
    })
    if not metrics["collision_free_within_tolerance"]:
        raise ValueError("Final path failed collision validation.")
    return Run(region, decomposition, model, solution, metrics, config, data)


def save_run(run: Run, output: str | Path, make_plot: bool = True) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "config": asdict(run.config),
        "metrics": run.metrics,
        "states": [asdict(s) for s in run.solution.states],
        "trajectory": run.model.trajectory(run.solution.states),
        "accepted_objectives": run.solution.accepted_objectives,
        "decomposition_events": run.decomposition.events,
        "cell_adjacency": {str(k): sorted(v) for k, v in run.decomposition.adjacency.items()},
    }
    (output / "plan.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(run.metrics, indent=2), encoding="utf-8")
    features = [{
        "type": "Feature", "geometry": mapping(run.region), "properties": {"kind": "region"},
    }]
    features += [{
        "type": "Feature", "geometry": mapping(c.polygon),
        "properties": {"kind": "cell", "cell_id": c.id},
    } for c in run.decomposition.cells]
    features.append({
        "type": "Feature",
        "geometry": mapping(LineString(run.model.trajectory(run.solution.states))),
        "properties": {"kind": "trajectory", "algorithm": run.solution.algorithm},
    })
    # Coordinates are LOCAL PLANAR, not geographic longitude/latitude.
    (output / "geometry.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        encoding="utf-8",
    )
    if make_plot:
        from .visualization import plot_run
        plot_run(run, output / "trajectory.png")
