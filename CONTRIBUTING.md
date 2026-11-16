# Contributing

Create a short-lived branch, explain the modeling change, and include a regression
test plus a small reproducible input map. Run `python -m pytest` before opening a
pull request. Keep geometry, state construction, route optimization, and metrics
separate so comparisons remain interpretable.

Never claim a planner improves performance from one hand-picked example. Record
seeds, candidate angles, swath, boundary policy, start/end conventions, cost weights,
and preprocessing/solver times. Retain failure cases. Do not copy third-party code
without its required license and attribution.
