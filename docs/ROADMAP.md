# Course project roadmap

## Milestone 1: Understand and validate decomposition

Read the Choset-Pignon event definitions. Run the rectangle, U-shaped boundary, and
one-obstacle examples. Add tests for multiple holes and simultaneous events.
Deliverable: cells, adjacency, event trace, conservation tests, and pseudocode.

The current event-slab implementation prioritizes readability. Implementing a
balanced sweep status structure is a separate optimization milestone, not a
complexity property this starter already claims.

## Milestone 2: Establish the baseline

Keep one deterministic sweep per cell and compare nearest-neighbor with 2-opt.
Explain why costs are directed and why full route scoring is used.
Deliverable: route plots, length/transit/turn counts, and runtime decomposition.

## Milestone 3: Direction-aware GTSP

Inspect the four permutations for a rectangle. Verify entry/exit and first-turn
signs by hand. Compare fixed state versus state-optimized fixed order versus
joint state/order search. The current GTSP module supports the latter two.
Deliverable: ablation results showing what each modeling choice changes.

## Milestone 4: Meaningful benchmarks

Add a fixed-seed valid polygon-with-holes generator, varied vertex counts, hole
counts, narrow passages, and rotations. Reject invalid generated geometries.
Use enough maps and independent restarts to report distributions, not one demo.
Benchmark preprocessing separately from solver time and report coverage alongside
length. Comparing paths that leave different uncovered areas needs care.

Run exact subset DP only on tiny cases to measure the heuristic's gap against the
finite-state optimum. Do not describe this as a lower bound for the unrestricted
continuous coverage problem.

## Milestone 5: Choose ONE substantial extension

Possible extensions: Noon-Bean plus an ATSP solver; an ILP oracle; LNS/GA/ACO;
optimized decomposition angle; boundary-gap repair; finite-radius configuration
spaces; or dynamically feasible turn trajectories. Keep experimental baselines
unchanged so the effect of the chosen extension can be isolated.

## Report outline

Problem definition and assumptions; geometric decomposition; state model;
objective; baseline and proposed algorithms; correctness invariants; complexity;
experimental setup; results and failure cases; limitations; conclusions.

A working starter is not a finished course submission. Understand, extend, and
justify the algorithms and report your own experiments and sources.
