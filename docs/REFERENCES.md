# Primary references and provenance

## Foundations used in this project

1. Howie Choset and Philippe Pignon, **Coverage Path Planning: The Boustrophedon
   Cellular Decomposition**. User-supplied source: `choset_howie_1997_5.pdf`.
   Sections 3-5 describe connectivity events, cell boundaries, adjacency, and
   graph traversal. The original method's DFS-like coverage walk is not this
   repository's GTSP optimizer. The paper is not bundled in this repository.

2. Rik Bahnemann, Nicholas Lawrance, Jen Jen Chung, Michael Pantic, Roland Siegwart,
   and Juan Nieto, **Revisiting Boustrophedon Coverage Path Planning as a Generalized
   Traveling Salesman Problem** (2019).
   https://arxiv.org/abs/1907.09224
   Relevant ideas: four sweep permutations per sweepable angle, obstacle-aware
   transitions, and equality GTSP with one sweep state per cell.
   This starter does not reproduce the paper's optimization implementation,
   motion/time model, or reported performance figures.

3. ETH Zurich Autonomous Systems Lab reference implementation:
   https://github.com/ethz-asl/polygon_coverage_planning
   Reference only. No source files are copied into this starter. Check the
   upstream license before incorporating upstream code into any derivative.

## Implementation and platform documentation

4. Shapely user manual:
   https://shapely.readthedocs.io/en/stable/manual.html
   Polygon intersections, buffering, rotations, and geometric predicates.

5. GitHub CLI repository creation:
   https://cli.github.com/manual/gh_repo_create

6. GitHub Actions: building and testing Python:
   https://docs.github.com/en/actions/tutorials/build-and-test-code/python

## What is new in this starter

The event-slab representation, Python module structure, bounded exact oracle,
layered-DP/local-order-search heuristic, tests, and command-line interfaces are
newly written for this project. They are educational design choices, not claims
that the original paper used these precise algorithms or data structures.
