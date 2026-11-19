import hashlib
import itertools
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SNAPSHOT = ROOT / "route_rl_research/20261103/source_snapshot"
sys.path.insert(0, str(SNAPSHOT))
sys.path.insert(0, str(HERE))

from lrphsd.evaluator import evaluate
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from station_split_dp import WorkBudget, solve_station


def make_instance(target_count=3, **overrides):
    station = Node(0, 0.0, 0.0, 0.0, 0.0)
    points = ((100.0, 0.0), (200.0, 0.0), (-200.0, 0.0),
              (0.0, 250.0), (0.0, -250.0), (300.0, 100.0),
              (-300.0, -100.0), (150.0, 150.0), (-150.0, -150.0),
              (350.0, 0.0), (0.0, 350.0), (-350.0, 0.0),
              (0.0, -350.0))
    targets = tuple(
        Node(i + 1, x, y, 0.01, 1.0)
        for i, (x, y) in enumerate(points[:target_count])
    )
    parameters = {
        "speed": 100.0,
        "flight_energy": 0.1,
        "small_battery": 0.8,
        "large_battery": 1.0,
        "small_radius": 500.0,
        "large_radius": 500.0,
        "small_duration": 480.0,
        "large_duration": 600.0,
        "time_cost": 0.5,
    }
    parameters.update(overrides)
    raw = "|".join(map(str, (station,) + targets)).encode()
    return Instance("station_dp_fixture", targets, (station,), hashlib.sha256(raw).hexdigest(),
                    Parameters(**parameters))


def _partitions(items):
    items = tuple(items)
    if not items:
        yield ()
        return

    def visit(index, blocks):
        if index == len(items):
            yield tuple(tuple(block) for block in blocks)
            return
        item = items[index]
        for block_idx in range(len(blocks)):
            blocks[block_idx].append(item)
            yield from visit(index + 1, blocks)
            blocks[block_idx].pop()
        blocks.append([item])
        yield from visit(index + 1, blocks)
        blocks.pop()

    yield from visit(0, [])


def _route_sets(target_ids):
    if not target_ids:
        yield []
        return
    for partition in _partitions(target_ids):
        trip_orders = [list(itertools.permutations(block)) for block in partition]
        for ordered_trips in itertools.product(*trip_orders):
            for trip_order in itertools.permutations(ordered_trips):
                yield [list(trip) for trip in trip_order]


def brute_force_station_cost(instance, station_type, target_ids):
    ids = tuple(sorted(target_ids))
    best = float("inf")
    for ld_mask in range(1 << len(ids)):
        if station_type == 1 and ld_mask:
            continue
        ld_ids = tuple(ids[i] for i in range(len(ids)) if ld_mask & (1 << i))
        sd_ids = tuple(nid for nid in ids if nid not in set(ld_ids))
        ld_routes = _route_sets(ld_ids) if station_type == 2 else ([[]] if not ld_ids else [])
        sd_routes = _route_sets(sd_ids)
        for route0, route1 in itertools.product(ld_routes, sd_routes):
            solution = empty_solution(instance, [station_type])
            solution["routes"][0] = [route0, route1]
            audit = evaluate(instance, solution)
            if audit["feasible"]:
                best = min(best, audit["operating_minutes"])
    return best


class StationSplitDPTests(unittest.TestCase):
    def setUp(self):
        self.budget = lambda: WorkBudget(deadline=float("inf"))

    def test_dabs_matches_exhaustive_partition_and_route_enumeration(self):
        ins = make_instance(3)
        ids = ins.target_ids
        result = solve_station(ins, 0, 2, ids, self.budget())
        self.assertEqual(result.status, "COMPLETE_REFERENCE", result.detail)
        audit_solution = empty_solution(ins, [2])
        audit_solution["routes"][0] = result.routes
        audit = evaluate(ins, audit_solution)
        self.assertTrue(audit["feasible"], audit["issues"])
        brute = brute_force_station_cost(ins, 2, ids)
        self.assertAlmostEqual(audit["operating_minutes"], brute, delta=1e-8)
        self.assertAlmostEqual(result.operating_minutes_dp, brute, delta=1e-8)

    def test_sabs_matches_exhaustive_and_reconstructs_multiple_trips(self):
        ins = make_instance(3, small_battery=0.5, small_duration=30.0)
        result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
        self.assertEqual(result.status, "COMPLETE_REFERENCE", result.detail)
        self.assertGreater(len(result.routes[1]), 1)
        solution = empty_solution(ins, [1])
        solution["routes"][0] = result.routes
        audit = evaluate(ins, solution)
        self.assertTrue(audit["feasible"], audit["issues"])
        brute = brute_force_station_cost(ins, 1, ins.target_ids)
        self.assertAlmostEqual(audit["operating_minutes"], brute, delta=1e-8)

    def test_dabs_small_slot_uses_dabs_radius_and_duty(self):
        ins = make_instance(1, small_radius=50.0, small_duration=1.0,
                            large_radius=500.0, large_duration=20.0)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "COMPLETE_REFERENCE", result.detail)
        self.assertEqual(result.slot_target_ids["0"], [])
        self.assertEqual(result.slot_target_ids["1"], [ins.target_ids[0]])
        solution = empty_solution(ins, [2])
        solution["routes"][0] = result.routes
        self.assertTrue(evaluate(ins, solution)["feasible"])

    def test_empty_physical_slot_is_preserved(self):
        ins = make_instance(1)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "COMPLETE_REFERENCE")
        self.assertTrue(any(not trips for trips in result.routes))

    def test_station_size_cutoff_is_predeclared_and_kept_unresolved(self):
        ins = make_instance(13)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_SIZE_LIMIT")
        self.assertIsNone(result.routes)

    def test_infeasible_station_pool_is_not_called_an_optimum(self):
        ins = make_instance(1, small_battery=0.1, large_battery=0.1)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_NO_FEASIBLE_PARTITION")
        self.assertIsNone(result.routes)

    def test_work_budget_marks_unresolved(self):
        ins = make_instance(3)
        budget = WorkBudget(deadline=float("inf"), max_transitions=0)
        result = solve_station(ins, 0, 2, ins.target_ids, budget)
        self.assertEqual(result.status, "UNRESOLVED_BOUND")


if __name__ == "__main__":
    unittest.main(verbosity=2)
