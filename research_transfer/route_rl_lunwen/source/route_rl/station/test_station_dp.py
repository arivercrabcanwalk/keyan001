"""Synthetic-only engineering checks, not quality or IEEE-optimality evidence."""
import copy
import hashlib
import itertools
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SNAPSHOT = ROOT / "route_rl_research/20261103/source_snapshot"
sys.path.insert(0, str(SNAPSHOT))
sys.path.insert(0, str(HERE))

from lrphsd.evaluator import evaluate
from lrphsd.problem import Instance, Node, Parameters, empty_solution
import station_split_dp as dp_module
from station_split_dp import WorkBudget, solve_station


def make_instance(target_count=3, points=None, energies=None, services=None, **overrides):
    station = Node(0, 0.0, 0.0, 0.0, 0.0)
    default_points = ((100.0, 0.0), (200.0, 0.0), (-200.0, 0.0),
                      (0.0, 250.0), (0.0, -250.0), (300.0, 100.0),
                      (-300.0, -100.0), (150.0, 150.0), (-150.0, -150.0),
                      (350.0, 0.0), (0.0, 350.0), (-350.0, 0.0),
                      (0.0, -350.0))
    points = tuple(default_points if points is None else points)[:target_count]
    if len(points) != target_count:
        raise ValueError("fixture target_count does not match supplied points")
    energies = [0.01] * target_count if energies is None else list(energies)
    services = [1.0] * target_count if services is None else list(services)
    targets = tuple(Node(i + 1, x, y, energies[i], services[i])
                    for i, (x, y) in enumerate(points))
    parameters = {"speed": 100.0, "flight_energy": 0.1,
                  "small_battery": 0.8, "large_battery": 1.0,
                  "small_radius": 500.0, "large_radius": 500.0,
                  "small_duration": 480.0, "large_duration": 600.0,
                  "time_cost": 0.5}
    parameters.update(overrides)
    raw = repr(((station,) + targets, parameters)).encode()
    return Instance("station_dp_fixture", targets, (station,), hashlib.sha256(raw).hexdigest(),
                    Parameters(**parameters))


def _partitions(items):
    """Enumerate unordered nonempty set partitions independently of DP."""
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
    """Enumerate all trip orders and all within-trip permutations."""
    if not target_ids:
        yield []
        return
    for partition in _partitions(target_ids):
        trip_orders = [list(itertools.permutations(block)) for block in partition]
        for ordered_trips in itertools.product(*trip_orders):
            for trip_order in itertools.permutations(ordered_trips):
                yield [list(trip) for trip in trip_order]


def brute_force_station_cost(instance, station_type, target_ids, fixed_owners=None):
    """Independent tiny enumeration, scored solely by the complete evaluator."""
    ids = tuple(sorted(target_ids))
    best = math.inf
    for ld_mask in range(1 << len(ids)):
        if station_type != 2 and ld_mask:
            continue
        ld_ids = tuple(ids[i] for i in range(len(ids)) if ld_mask & (1 << i))
        sd_ids = tuple(nid for nid in ids if nid not in set(ld_ids))
        if fixed_owners is not None:
            if (set(ld_ids) != set(fixed_owners.get(0, ()))
                    or set(sd_ids) != set(fixed_owners.get(1, ()))):
                continue
        route0 = _route_sets(ld_ids) if station_type == 2 else ([],)
        for routes_ld, routes_sd in itertools.product(route0, _route_sets(sd_ids)):
            solution = empty_solution(instance, [station_type])
            solution["routes"][0] = [routes_ld, routes_sd]
            audit = evaluate(instance, solution)
            if audit["feasible"]:
                best = min(best, audit["operating_minutes"])
    return best


class StationSplitDPTests(unittest.TestCase):
    def budget(self):
        return WorkBudget(deadline=math.inf)

    def full_audit(self, ins, kind, result):
        solution = empty_solution(ins, [kind])
        solution["routes"][0] = result.routes
        return solution, evaluate(ins, solution)

    def assert_reference(self, ins, kind, result, expected_status="COMPLETE_JOINT_REFERENCE"):
        self.assertEqual(result.status, expected_status, result.detail)
        solution, audit = self.full_audit(ins, kind, result)
        self.assertTrue(audit["feasible"], audit["issues"])
        self.assertAlmostEqual(result.operating_minutes_dp, audit["operating_minutes"], delta=1e-8)
        self.assertEqual(sorted(n for slot in result.routes for trip in slot for n in trip),
                         sorted(ins.target_ids))
        self.assertTrue(all(trip for slot in result.routes for trip in slot))
        self.assertEqual(json.loads(json.dumps(result.as_dict()))["status"], expected_status)
        return solution, audit

    def test_joint_dabs_matches_exhaustive_assignment_partition_and_route_orders(self):
        for count in (1, 2, 3, 4):
            with self.subTest(target_count=count):
                ins = make_instance(count)
                result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
                _, audit = self.assert_reference(ins, 2, result)
                brute = brute_force_station_cost(ins, 2, ins.target_ids)
                self.assertAlmostEqual(audit["operating_minutes"], brute, delta=1e-8)

    def test_fixed_owner_matches_independent_exhaustive_enumeration(self):
        ins = make_instance(4)
        for owners in ({0: [1, 3], 1: [2, 4]}, {0: [], 1: [1, 2, 3, 4]},
                       {0: [1, 2, 3, 4], 1: []}):
            with self.subTest(owners=owners):
                result = solve_station(ins, 0, 2, ins.target_ids, self.budget(),
                                       fixed_slot_target_ids=owners)
                _, audit = self.assert_reference(ins, 2, result, "COMPLETE_FIXED_OWNER_REFERENCE")
                self.assertEqual({k: set(v) for k, v in result.slot_target_ids.items()},
                                 {str(k): set(v) for k, v in owners.items()})
                brute = brute_force_station_cost(ins, 2, ins.target_ids, owners)
                self.assertAlmostEqual(audit["operating_minutes"], brute, delta=1e-8)

    def test_fixed_owner_sabs_and_joint_sabs_match_exhaustive_multitrips(self):
        ins = make_instance(3, small_battery=0.5, small_duration=30.0)
        brute = brute_force_station_cost(ins, 1, ins.target_ids)
        for owners in (None, {1: ins.target_ids}):
            with self.subTest(fixed=owners is not None):
                result = solve_station(ins, 0, 1, ins.target_ids, self.budget(),
                                       fixed_slot_target_ids=owners)
                status = "COMPLETE_FIXED_OWNER_REFERENCE" if owners else "COMPLETE_JOINT_REFERENCE"
                _, audit = self.assert_reference(ins, 1, result, status)
                self.assertEqual(result.routes[0], [])
                self.assertGreater(len(result.routes[1]), 1)
                self.assertAlmostEqual(audit["operating_minutes"], brute, delta=1e-8)

    def test_dabs_small_slot_uses_large_station_radius_and_duration(self):
        ins = make_instance(1, small_radius=50.0, small_duration=1.0,
                            large_radius=500.0, large_duration=20.0)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget(),
                               fixed_slot_target_ids={0: [], 1: [1]})
        self.assert_reference(ins, 2, result, "COMPLETE_FIXED_OWNER_REFERENCE")
        self.assertEqual(result.slot_target_ids["1"], [1])
        self.assertAlmostEqual(result.slot_duty_slack["1"], 17.0)
        rejected = solve_station(ins, 0, 1, ins.target_ids, self.budget())
        self.assertEqual(rejected.status, "INPUT_INVALID")

    def test_heterogeneous_battery_forces_target_to_large_slot(self):
        ins = make_instance(1, small_battery=0.1, large_battery=0.8)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assert_reference(ins, 2, result)
        self.assertEqual(result.slot_target_ids["0"], [1])
        self.assertEqual(result.slot_target_ids["1"], [])
        forced = solve_station(ins, 0, 2, ins.target_ids, self.budget(),
                               fixed_slot_target_ids={0: [], 1: [1]})
        self.assertEqual(forced.status, "UNRESOLVED_FIXED_OWNER_INFEASIBLE")

    def test_returns_do_not_reset_cumulative_duty(self):
        ins = make_instance(2, points=((100.0, 0.0), (-100.0, 0.0)),
                            small_battery=0.3, large_battery=0.3,
                            small_duration=5.0, large_duration=5.0)
        result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_NO_FEASIBLE_PARTITION")
        self.assertIsNone(result.routes)
        solution = empty_solution(ins, [1])
        solution["routes"][0][1] = [[1], [2]]
        audit = evaluate(ins, solution)
        self.assertFalse(audit["feasible"])
        self.assertIn("cumulative_time:0:1", audit["issues"])
        self.assertFalse(any(i.startswith("energy:") for i in audit["issues"]))
        joint = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assert_reference(ins, 2, joint)
        self.assertTrue(joint.routes[0] and joint.routes[1])

    def test_empty_stations_and_slots_have_complete_witness(self):
        ins = make_instance(0)
        for kind in (0, 1, 2):
            with self.subTest(kind=kind):
                result = solve_station(ins, 0, kind, (), self.budget())
                self.assert_reference(ins, kind, result)
                self.assertEqual(result.routes, [[], []])
                self.assertEqual(result.operating_minutes_dp, 0.0)
        ins = make_instance(1)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assert_reference(ins, 2, result)
        self.assertTrue(any(not trips for trips in result.routes))

    def test_size_cap_remains_unresolved(self):
        ins = make_instance(13)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_SIZE_LIMIT")
        self.assertIsNone(result.routes)
        self.assertEqual(result.transition_checks, 0)

    def test_state_cap_remains_unresolved_before_work(self):
        ins = make_instance(3)
        with patch.object(dp_module, "MAX_STATE_CELLS", 0):
            result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_STATE_BOUND")
        self.assertIsNone(result.routes)
        self.assertGreater(result.state_cells, 0)
        self.assertEqual(result.transition_checks, 0)

    def test_transition_cap_is_returned_not_uncaught(self):
        ins = make_instance(3)
        result = solve_station(ins, 0, 2, ins.target_ids,
                               WorkBudget(deadline=math.inf, max_transitions=0))
        self.assertEqual(result.status, "UNRESOLVED_BOUND")
        self.assertEqual(result.detail, "transition_bound")
        self.assertIsNone(result.routes)

    def test_expired_deadline_is_returned_not_uncaught(self):
        ins = make_instance(3)
        result = solve_station(ins, 0, 2, ins.target_ids, WorkBudget(deadline=-math.inf))
        self.assertEqual(result.status, "UNRESOLVED_BOUND")
        self.assertEqual(result.detail, "map_wallclock_cap")
        self.assertIsNone(result.routes)

    def test_invalid_owner_partitions_are_rejected(self):
        ins = make_instance(3)
        for owners in ({0: [1, 2], 1: [2, 3]}, {0: [1], 1: [2]},
                       {0: [1, 2], 1: [3, 99]}, {2: [1, 2, 3]}):
            with self.subTest(owners=owners):
                result = solve_station(ins, 0, 2, ins.target_ids, self.budget(),
                                       fixed_slot_target_ids=owners)
                self.assertEqual(result.status, "INPUT_INVALID")
                self.assertIsNone(result.routes)
        illegal_slot = solve_station(ins, 0, 1, ins.target_ids, self.budget(),
                                     fixed_slot_target_ids={0: [1, 2, 3]})
        self.assertEqual(illegal_slot.status, "INPUT_INVALID")

    def test_invalid_index_type_target_and_coverage_rejected(self):
        ins = make_instance(3)
        cases = ((-1, 2, ins.target_ids), (1, 2, ins.target_ids),
                 (0, 3, ins.target_ids), (0, 2, (1, 1)), (0, 2, (999,)),
                 (0, 0, ins.target_ids))
        for index, kind, ids in cases:
            with self.subTest(index=index, kind=kind, ids=ids):
                result = solve_station(ins, index, kind, ids, self.budget())
                self.assertEqual(result.status, "INPUT_INVALID")
                self.assertIsNone(result.routes)
        outside = make_instance(1, small_radius=50.0, large_radius=50.0)
        result = solve_station(outside, 0, 2, outside.target_ids, self.budget())
        self.assertEqual(result.status, "INPUT_INVALID")

    def test_infeasible_pool_is_not_called_reference(self):
        ins = make_instance(1, small_battery=0.1, large_battery=0.1)
        result = solve_station(ins, 0, 2, ins.target_ids, self.budget())
        self.assertEqual(result.status, "UNRESOLVED_NO_FEASIBLE_PARTITION")
        self.assertIsNone(result.routes)
        self.assertTrue(math.isinf(brute_force_station_cost(ins, 2, ins.target_ids)))

    def test_resource_eps_boundary_on_tiny_axis_aligned_fixture(self):
        # Engineering predicate check only; not a general floating optimum proof.
        for deficit, feasible in ((0.5e-7, True), (2e-7, False)):
            with self.subTest(resource="battery", deficit=deficit):
                ins = make_instance(1, small_battery=0.21 - deficit)
                result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
                if feasible:
                    self.assert_reference(ins, 1, result)
                else:
                    self.assertEqual(result.status, "UNRESOLVED_NO_FEASIBLE_PARTITION")
            with self.subTest(resource="duty", deficit=deficit):
                ins = make_instance(1, small_duration=3.0 - deficit)
                result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
                if feasible:
                    self.assert_reference(ins, 1, result)
                else:
                    self.assertEqual(result.status, "UNRESOLVED_NO_FEASIBLE_PARTITION")
            with self.subTest(resource="coverage", deficit=deficit):
                ins = make_instance(1, small_radius=100.0 - deficit)
                result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
                if feasible:
                    self.assert_reference(ins, 1, result)
                else:
                    self.assertEqual(result.status, "INPUT_INVALID")

    def test_independent_evaluator_rejects_corrupted_witnesses(self):
        ins = make_instance(3)
        result = solve_station(ins, 0, 1, ins.target_ids, self.budget())
        good, _ = self.assert_reference(ins, 1, result)
        duplicate = copy.deepcopy(good)
        duplicate["routes"][0][1].append([1])
        audit = evaluate(ins, duplicate)
        self.assertFalse(audit["feasible"])
        self.assertIn("duplicate:1", audit["issues"])
        missing = copy.deepcopy(good)
        missing["routes"][0][1] = [[n for n in trip if n != 1]
                                            for trip in missing["routes"][0][1]]
        self.assertIn("missing:1", evaluate(ins, missing)["issues"])
        wrong_slot = copy.deepcopy(good)
        wrong_slot["routes"][0] = [wrong_slot["routes"][0][1], []]
        self.assertIn("large_drone_at_small_station:0", evaluate(ins, wrong_slot)["issues"])
        wrong_hash = copy.deepcopy(good)
        wrong_hash["instance_sha256"] = "wrong"
        self.assertIn("instance_hash", evaluate(ins, wrong_hash)["issues"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
