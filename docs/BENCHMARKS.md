# Topic 5 experiment set: reproducible per-sample metrics

This is a benchmark *harness*, not published performance results. No statistics
are claimed until the commands are run on the experiment machine.

## 1. Prepare two collections of polygons with holes

Generate 10 fixed-seed synthetic maps. The generator creates rectangles with
0 to 5 disjoint rectangular holes and records each map's generation seed.

```powershell
python -m coverage_planning.datasets synthetic --out benchmarks/synthetic --count 10 --seed 2026 --swath 3
```

To convert the full AC300 collection from GitHub, run this from the project
directory with Git and the project dependencies installed:

```powershell
python -m coverage_planning.datasets fetch-ac300
```

This writes one planner input per map to `benchmarks/ac300_full/<map-id>.json`.
The boundary comes from `outer_polygon`. Each blank-line-separated ring in
`holes` becomes one obstacle. The importer checks the hole count and polygon
validity. The default swath is 3 metres. Use `--swath` to change it or
`--source PATH` to convert a previously downloaded collection offline.

To select 15 ETH-derived AC300 maps (3 each with 1, 3, 5, 10 and 15 holes), first
obtain UNC Charlotte's AreaCoverage-dataset repository separately. Then run:

```powershell
python -m coverage_planning.datasets ac300 --source ..\AreaCoverage-dataset --out benchmarks/ac300 --holes 1 3 5 10 15 --per-hole 3 --swath 3
```

Source: https://github.com/UNCCharlotte-CS-Robotics/AreaCoverage-dataset
and https://github.com/ethz-asl/polygon_coverage_planning . The original ETH
benchmark cost is time-based; do not compare it numerically with our distance
objective. AC300 is ETH-derived, not an independent third collection.

AC300 coordinates are planar metres. The converted depot is (1,1) when in free
space; otherwise it is a representative interior point. This depot is *our*
benchmark convention, not an original dataset start location.

## 2. Run every algorithm on every sample

For an initial smoke run with one seed:

```powershell
coverage-benchmark --maps benchmarks/synthetic --algorithms tsp-greedy tsp-2opt gtsp --seeds 0 --out results/synthetic_smoke.csv
```

For the final experiment, use 1 seed for the deterministic baselines and 30
seeds for randomized GTSP. Use identical swath, start, closed/open setting,
and decomposition/sweep angles for each algorithm:

```powershell
coverage-benchmark --maps benchmarks/synthetic --algorithms tsp-greedy tsp-2opt --seeds 0 --swath 3 --out results/synthetic_baselines.csv
coverage-benchmark --maps benchmarks/synthetic --algorithms gtsp --seed-count 30 --swath 3 --out results/synthetic_gtsp.csv
coverage-benchmark --maps benchmarks/ac300 --algorithms tsp-greedy tsp-2opt --seeds 0 --swath 3 --out results/ac300_baselines.csv
coverage-benchmark --maps benchmarks/ac300 --algorithms gtsp --seed-count 30 --swath 3 --out results/ac300_gtsp.csv
```

The CSV naming is illustrative: `--out X.csv` always produces `X_summary.csv`
and a matching `X_runs/` folder. GTSP uses different fixed random seeds;
it may nevertheless return identical routes for many seeds.

For small maps (up to 8 cells), run the discretized GTSP exact oracle and
compute `100 * (GTSP_heuristic - GTSP_exact) / GTSP_exact` with both objectives
under the same settings:

```powershell
coverage-benchmark --maps examples --algorithms gtsp gtsp-exact --seeds 0 --out results/small_exact.csv
```

Exclude any map exceeding the exact solver's 8-cell guard; failures are
recorded in the CSV rather than silently ignored.

For sweep-angle ablation:

```powershell
coverage-benchmark --maps benchmarks/synthetic --seed-count 30 --angles 90 --out results/vertical_only.csv
coverage-benchmark --maps benchmarks/synthetic --seed-count 30 --angles 90 0 --out results/mixed_angles.csv
```

The output is **not** automatically a controlled test unless all *other*
parameters are identical. Default decomposition orientation is 90 degrees.

## 3. Files written for each sample and run

`results/synthetic.csv`: one row per map, algorithm and seed, including:

- success/failure, error message, map source, holes, vertices and free area;
- total, service and transit length, coverage %, overlap excess %;
- vertex turns, lane reversals, total absolute turn angle;
- preprocessing, solver and planning time, cells and candidate states;
- optional constant-speed estimated mission duration (`--robot-speed 1.5`);
- selected cell order, selected sweep angles and first-turn decisions;
- experiment configuration (spacing, swath, seed, turn penalty, etc.).

`results/synthetic_summary.csv`: per-map/per-algorithm success rate,
median coverage, path length, overlap, turns, runtime, plus path length and
runtime IQR. Quartiles use linear interpolation at rank `(n-1)*p`.

`results/synthetic_runs/<map>/<algorithm>/seed_<n>/metrics.json` and
`plan.json`: full original metric object and selected trajectory/state details.
`geometry.geojson` is also included. Add `--plot-runs` to save a PNG for each
run, but do not enable this for large timing experiments without reason.

Errors are recorded instead of being discarded. CSV rows and the summary are
flushed continuously so interrupted experiments leave partial evidence. Pass
`--strict` in CI to return an error code if any map fails; otherwise inspect the
per-run `status` column and success rate.

## 4. Metric definitions and reporting cautions

Coverage = clipped service-footprint union / free-space area.
Overlap excess = sum of clipped segment footprint areas minus their union,
divided by free-space area. It is **not** the fraction of area covered twice.
Turns count polyline heading changes exceeding 1 degree, including transitions;
lane reversals are `sum(lanes - 1)` and exclude transit.

The planning timing fields exclude rendering and metric computation; they are
not robot mission times. `--robot-speed V` estimates mission time as total
route length / V, assuming constant speed with zero time penalty for turning;
this is a labeled approximation, **not** a physically modeled mission time.
The project has no energy model. State energy as a modeling limitation unless
an explicit energy/turning model is separately implemented.

Use separate maps for hyperparameter tuning and final evaluation. For a report,
add log-log runtime scaling, profiling, parameter sensitivity, an ablation,
small-instance optimality-gap checks with `gtsp-exact` (<=8 cells), and
appropriate statistical comparisons. Record the CPU, OS, Python/Shapely
versions, and peak memory using separate profiling tools.

Avoid copying ETH/UNC algorithm source; cite the upstream dataset and paper.
