import itertools

import pytest
from shapely.geometry import box

from coverage_planning.costs import CostModel
from coverage_planning.geometry import path_length, turn_angle
from coverage_planning.models import Cell
from coverage_planning.pipeline import Config, plan
from coverage_planning.planners import solve_exact, solve_gtsp, solve_tsp
from coverage_planning.planners.gtsp import optimize_states
from coverage_planning.sweeps import generate_states
from coverage_planning.transitions import VisibilityRouter

from .conftest import ROOT


@pytest.fixture
def tiny_model():
    clusters = []
    offset = 0
    for i, x in enumerate([1, 8, 15]):
        states = generate_states(Cell(i, box(x, 2, x + 3, 8)), 2, (90,), id_offset=offset)
        clusters.append(states)
        offset += len(states)
    return CostModel(clusters, VisibilityRouter(box(0, 0, 20, 12)), (1.0, 1.0), turn_weight=0.4)


def test_fixed_order_dp_against_bruteforce(tiny_model):
    states, value = optimize_states([0, 2, 1], tiny_model)
    combinations = itertools.product(tiny_model.clusters[0], tiny_model.clusters[2], tiny_model.clusters[1])
    best = min(tiny_model.evaluate(list(c)) for c in combinations)
    assert value == pytest.approx(best)
    assert value == pytest.approx(tiny_model.evaluate(states))


def test_exact_gtsp_against_bruteforce(tiny_model):
    best = float("inf")
    for order in itertools.permutations(range(3)):
        for choice in itertools.product(*(tiny_model.clusters[i] for i in order)):
            best = min(best, tiny_model.evaluate(list(choice)))
    assert solve_exact(tiny_model).objective == pytest.approx(best)


def test_baseline_heuristic_exact_ordering(tiny_model):
    greedy = solve_tsp(tiny_model, improve=False)
    improved = solve_tsp(tiny_model)
    heuristic = solve_gtsp(tiny_model)
    exact = solve_exact(tiny_model)
    assert exact.objective <= heuristic.objective + 1e-8
    assert heuristic.objective <= improved.objective + 1e-8
    assert improved.objective <= greedy.objective + 1e-8
    for solution in [greedy, improved, heuristic, exact]:
        assert sorted(s.cell_id for s in solution.states) == [0, 1, 2]
        assert solution.objective == pytest.approx(tiny_model.evaluate(solution.states))


def test_turn_cost_additive(tiny_model):
    s = solve_gtsp(tiny_model)
    path = tiny_model.trajectory(s.states)
    actual = path_length(path) + tiny_model.turn_weight * turn_angle(path)
    assert s.objective == pytest.approx(actual)


def test_reproducible_seed(tiny_model):
    a, b = solve_gtsp(tiny_model, seed=42), solve_gtsp(tiny_model, seed=42)
    assert [s.id for s in a.states] == [s.id for s in b.states]
    assert a.objective == b.objective


@pytest.mark.parametrize("closed", [True, False])
@pytest.mark.parametrize("algorithm", ["tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact"])
def test_end_to_end(closed, algorithm):
    run = plan(ROOT / "examples/one_obstacle.json", Config(algorithm=algorithm, closed=closed))
    assert run.metrics["collision_free_within_tolerance"]
    assert run.metrics["num_cells"] == 4
    assert run.metrics["coverage_ratio"] >= 0.999
    assert len(run.solution.states) == len(run.model.clusters)
    if closed:
        path = run.model.trajectory(run.solution.states)
        assert path[0] == path[-1]


def test_exact_guard(tiny_model):
    with pytest.raises(ValueError, match="limited"):
        solve_exact(tiny_model, max_cells=2)


def test_start_heading_additive():
    run = plan(ROOT / "examples/one_obstacle.json", Config(start_heading=33, turn_weight=0.5))
    assert run.metrics["objective"] == pytest.approx(
        run.metrics["total_length"] + 0.5 * run.metrics["absolute_turn_angle_rad"]
    )
