# Algorithms and modeling decisions

## 1. Scope

Input: one valid planar polygon P with holes, a start depot, coverage width w,
maximum lane spacing d <= w, candidate lane angles, and optional turn costs.
Output: cells, directed service states, a cell order, obstacle-aware connectors,
a continuous piecewise-linear trajectory, and measured metrics.

The vehicle is a point in the supplied free-space polygon. Boundary motion and
in-place heading changes are allowed. A swath is a sensor/tool footprint, not
collision clearance. The input must already represent admissible center positions
when using a configuration-space interpretation.

## 2. Boustrophedon decomposition

The default `decompose()` follows the incremental floor-and-ceiling construction
of Choset and Pignon. It rotates the polygon into the sweep frame and processes
the sorted boundary events, handling vertices with the same X together. The
active boundary edges define the ordered free-space intervals on each side of
an event.

An interval continues the same cell when it has a mutual one-to-one match across
a gate of positive length. At IN (split) and OUT (merge) events, the sweep closes
the affected cells, opens new cells, and records their adjacency. Floor and ceiling
changes extend the current cell's boundary chains. The sweep forms a polygon from
those chains when the cell closes, then rotates it back and validates the partition.

The original polygon-clipping implementation is available as `decompose_slabs()`
for comparisons.

IMPORTANT: compare the local component correspondence, not just the total number
of slice components. A split and a merge can happen at the same X coordinate,
leaving the total unchanged. A regression test covers this case.

An adjacency edge records a shared geometric gate. It is not the same graph as
the GTSP state graph: a GTSP transition may pass through other cells without
servicing them. Every cell must still have exactly one selected service state.

## 3. Sweep generation and initial turn

A candidate state is a directed, complete service polyline for a cell. For each
requested angle, sample the open intervals between projected boundary events to
check monotonicity. A nonmonotone orientation is skipped. Supporting it would
require another decomposition, not a straight jump over disconnected intervals.

Place N = ceil(cell_width / d) centered lanes, with a uniform separation of
cell_width / N. Generate increasing/decreasing lane order and positive/negative
first lane travel: four permutations, deduplicated for one-lane cases. Connect
consecutive lanes inside the cell using the visibility router rather than assuming
a straight connector lies inside a concave cell.

The first-turn side is sign(cross(first_lane_heading, lane_progression)). A positive
sign means left; a negative sign means right. A single lane has no reversal.
This is the nominal U-turn side, not an explicit circular turn or the first
small corner in a detour. The `first_turn` filter applies to every cell.

A boundary pass, when requested, walks the whole cell perimeter from the last
lane endpoint and returns to that endpoint. This is optional because it changes
the service cost and adds overlap.

## 4. Directed objective

For a sequence of selected states s_1, ..., s_m:

    J = C(depot, s_1)
        + sum_i I(s_i)
        + sum_i C(s_i, s_(i+1))
        + C(s_m, depot)                  [closed routes only]

I(s) is the internal service length plus lambda times its absolute heading change.
C(a,b) is the connector length plus lambda times its internal bends and the
source-exit / target-entry heading changes. The optional initial heading contributes
to the first connector's cost. The final returned heading is unconstrained.

lambda has units of map-length per radian. With lambda=0, J is total path length.
There is no energy model, speed profile, acceleration model, or yaw-rate constraint.

A connector is a Euclidean shortest path in the point-robot polygon, then scored
for its turns. With nonzero lambda it need not be the minimum-cost connector over
all alternative geometric routes. The exact oracle is exact only for this fixed
state/connector cost model.

## 5. TSP baseline

Freeze one canonical state per cell: the first admissible state generated under
the shared angle/turn configuration. This is an order-only, generally asymmetric
service-state TSP baseline, not a centroid-distance TSP.

Build an initial sequence by nearest-neighbor connector cost. Try reversing each
contiguous subsequence; accept the best strict improvement and repeat subject to
a round budget. Evaluate the complete directed cost after a reversal. Do not use
the symmetric four-edge 2-opt shortcut: reversed internal edges change cost too.
The selected cell service paths are not reversed by this order move.

## 6. GTSP heuristic

Each cell is a cluster of candidate states. Exactly one state must be selected
from every cluster. For a fixed cell order, a layered dynamic program gives the
best choices under the supplied pairwise costs:

    D_i(s) = I(s) + min_t [D_(i-1)(t) + C(t,s)]

Include the depot cost at initialization and terminal return cost when closing.
Then search cell orders with segment-reversal moves, re-running the state DP for
each candidate order. Add seeded random starts to reduce dependence on one order.
The TSP order is always included, so GTSP cannot have a larger objective than that
specific TSP baseline under identical inputs. This does not establish global
optimality or imply a shorter route if a different objective is being optimized.

The exact solver stores the best cost indexed by `(visited_cell_mask, last_state)`.
It is limited to 8 cells by default and used for regression checks and tiny-instance
comparisons. It solves the finite candidate GTSP, not continuous global CCPP.

## 7. Metrics

- Total length = service length + inter-cell/depot transit length.
- Absolute turning = sum of heading changes in radians along the whole polyline,
  including an optional initial heading change.
- Vertex turns = polyline bends exceeding 1 degree; excludes initial heading setup.
- Lane reversals = sum over cells of max(number_of_lanes - 1, 0).
- Coverage = area(union of buffered service segments intersected with P) / area(P).
- Overlap excess = (sum of individually clipped segment footprint areas minus
  their union area) / area(P). It includes overlap at segment joins, can exceed 1,
  and is NOT simply the fraction covered at least twice.
- Preprocessing and solver times are separate. Metrics and rendering are excluded.

Coverage swaths are clipped geometrically; occlusion and sensing physics are not
modeled. Transit has the sensor off. Use the same sensor policy for all comparisons.

## 8. Complexity: distinguish this code from the ideal sweep

Let n be boundary vertices, m cells, and k the largest number of states per cell.

| Stage | Complexity/qualification |
|---|---|
| Event sorting | O(n log n) |
| Incremental BCD | O(n log n + sum of active edge counts across events), before geometry validation |
| Slab BCD baseline | O(n) full polygon/slab intersections plus component joins and polygon unions |
| Full visibility graph | O(n^2) visibility tests; naive each-test cost can depend on n |
| Dijkstra | O(E log V) per uncached query, plus endpoint-visibility construction |
| Greedy order | O(m^2) cached cost lookups |
| TSP 2-opt | O(m^3) per full pass using full-route scoring |
| Fixed-order state DP | O(m k^2) |
| GTSP order pass | O(m^3 k^2), before previously unseen transition construction |
| Exact subset DP | O(2^m m^2 k^2) time; O(2^m m k) memory |

The Shapely/GEOS geometric operations have their own costs. Report measured
preprocessing separately; do not label the whole pipeline O(n log n).

## Limitations

This is a tested educational starter, not a universal robust geometry library.

* Floating-point geometry is used, with scale-relative tolerance. Extremely narrow
  features, nearly coincident events, and zero-width passages need extra care.
* The model excludes finite robot radius, turning radius, dynamics, altitude,
  energy, wind, uncertainty, and sensing occlusion.
* Basic finite zig-zag sampling can leave boundary gaps. Measured coverage must be
  reported, and 100% should not be asserted from decomposition alone.
* Candidate angles are discrete; different decompositions are not jointly optimized.
* GTSP is heuristic except for the bounded tiny-instance oracle. No approximation
  factor is claimed. Noon-Bean, ILP, GA, LNS, and ACO are not implemented.
* Only small deterministic example maps are included. They are smoke benchmarks,
  not a statistically meaningful reproduction of published experiments.

See REFERENCES.md for the distinction between the published methods and this code.
