# Local validation record

## Executed in the preparation environment

Python 3.13.5, Shapely 2.1.2, Matplotlib 3.10.8, NumPy 2.3.5,
pytest 9.0.2, pytest-cov 7.0.0, Linux.

- 51 automated tests passed.
- Statement coverage reported by pytest-cov: 85% across the package.
- Editable package installation succeeded using the environment's preinstalled
  build tools and dependencies (`--no-build-isolation --no-deps`).
- The installed `coverage-plan` and `coverage-benchmark` console commands ran.
- 36 small-map benchmark runs completed: 4 maps x 3 planners x 3 seeds.
- 18 additional fixed-seed randomized integration runs passed across 6 two-hole
  maps and 3 decomposition angles (0, 27, and 90 degrees).
- PNG, JSON, and GeoJSON outputs were generated; the example PNG was inspected.
- Tiny exact GTSP matched the heuristic on the one-obstacle example.
- A perimeter-pass run on the two-obstacle example reached measured 100% coverage.

The normal online `pip install -e ".[dev]"` path could not be exercised in this
network-restricted preparation environment. The included dependency specifications
are compatible with the runtime versions above. Optional Ruff was unavailable
and not run; it is not a required CI gate.

No GitHub remote was created or pushed. GitHub Actions has been configured, not
executed remotely. The Python 3.11/3.12 and Windows matrix jobs are unverified here.
A local test suite does not prove robustness for arbitrary polygon inputs.

## Included one-obstacle example

Map: `examples/one_obstacle.json`; 4 cells; 32 candidate states; seed 0; swath and
spacing both 2 map units; closed route from (1,1); zero turn penalty; no perimeter
pass. The map is 24 x 16 with one 6 x 6 rectangular hole.

| Planner | Total path length | Measured coverage |
|---|---:|---:|
| TSP Greedy | 269.222661 | 100% |
| TSP Greedy + 2-opt | 268.788681 | 100% |
| GTSP heuristic | 229.332033 | 100% |
| Exact finite-state GTSP | 229.332033 | 100% |

This is a local smoke example, not evidence of a general improvement percentage.
The agreement with the oracle certifies the objective only for this finite
candidate-state model and this example.

## Boundary-gap example

On `two_obstacles.json`, seed 0, no perimeter pass:

| Planner | Total path length | Measured coverage |
|---|---:|---:|
| TSP Greedy + 2-opt | 388.780110 | 99.365415% |
| GTSP heuristic | 345.687765 | 99.403449% |

With the GTSP perimeter-pass option, the measured coverage becomes 100%, while
length increases to 656.939658 units. Coverage improvement is not free. Do not
compare path lengths without also checking the coverage policy and achieved area.

The full 36-run smoke data are in `benchmark_smoke.csv`. Timings are environment
specific. The demo output files are in `demo/`; they can be regenerated with:

```sh
coverage-plan examples/one_obstacle.json --algorithm gtsp --seed 0 --out docs/demo
```
