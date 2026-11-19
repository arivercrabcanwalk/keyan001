"""Synthetic-only tests for the new same-objective non-RL controls."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
RETURN = HERE.parents[1]
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "route_rl_research/20261103/source_snapshot"))
sys.path.insert(0, str(RETURN))
sys.path.insert(0, str(HERE))

from lrphsd.problem import Instance, Node, Parameters, empty_solution
from baseline import _neighbours, solve
from scorer import CostAnchor, score_solution, validate_candidate


def balance_case():
    instance = Instance("synthetic_balance",
                        (Node(1, 1., 0., .01, 1.), Node(2, 2., 0., .01, 1.)),
                        (Node(0, 0., 0., 0., 0.),),
                        hashlib.sha256(b"synthetic_balance").hexdigest(),
                        Parameters(speed=1., flight_energy=.001,
                                   small_radius=1000., large_radius=1000.))
    anchor = empty_solution(instance, [2])
    anchor["routes"] = [[[[1], [2]], []]]
    return instance, anchor


class NonRLBaselineTests(unittest.TestCase):
    def test_lpt_balances_intact_trips_at_equal_full_cost(self):
        instance, anchor_solution = balance_case()
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        result = solve(instance, anchor, method="lpt", budget_s=1.,
                       started_at=0., clock=lambda: 0.)
        self.assertEqual(result["status"], "ONTIME_VALID")
        score = result["chosen_score"]
        self.assertTrue(score["admissible"], score)
        self.assertEqual(score["cost"], anchor.cost)
        self.assertLess(score["M_return"], anchor.makespan)
        self.assertEqual(result["chosen_solution"]["station_types"], [2])
        self.assertEqual(score["target_station"], {1: 0, 2: 0})

    def test_joint_minmax_never_returns_worse_than_lpt_or_over_cap(self):
        instance, anchor_solution = balance_case()
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        result = solve(instance, anchor, method="joint_minmax", budget_s=1.,
                       started_at=0., clock=lambda: 0., max_evaluations=1000)
        self.assertEqual(result["status"], "ONTIME_VALID")
        self.assertTrue(result["chosen_score"]["admissible"])
        self.assertLessEqual(result["chosen_score"]["M_return"], anchor.makespan)
        self.assertLessEqual(result["chosen_score"]["cost"], anchor.cost + 1e-7)
        self.assertEqual(len(result["candidate_certificates"]),
                         result["candidate_validation_calls"])

    def test_global_cost_cap_rejects_trip_split_that_increases_cost(self):
        instance, _ = balance_case()
        anchor_solution = empty_solution(instance, [2])
        anchor_solution["routes"] = [[[[1, 2]], []]]
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        split = deepcopy(anchor_solution)
        split["routes"] = [[[[1], [2]], []]]
        rejected = validate_candidate(instance, split, anchor)
        self.assertTrue(rejected["original_feasible"], rejected["issues"])
        self.assertGreater(rejected["cost"], anchor.cost + 1e-7)
        self.assertFalse(rejected["admissible"])
        result = solve(instance, anchor, method="joint_minmax", budget_s=1.,
                       started_at=0., clock=lambda: 0., max_evaluations=1000)
        self.assertGreater(result["rejected_inadmissible_candidates"], 0)
        self.assertLessEqual(result["chosen_score"]["cost"], anchor.cost + 1e-7)

    def test_deadline_failure_is_retained_not_relabelled_as_a_valid_route(self):
        instance, anchor_solution = balance_case()
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        ticks = iter(i * .001 for i in range(1000))
        result = solve(instance, anchor, method="joint_minmax", budget_s=.005,
                       started_at=0., clock=lambda: next(ticks), max_evaluations=1000)
        self.assertTrue(result["search_timed_out"])
        self.assertEqual(result["status"], "NO_ONTIME_VALID_OUTPUT")
        self.assertIsNone(result["chosen_solution"])
        self.assertTrue(result["raw_score"]["admissible"])

    def test_nonempty_station_routes_preserve_slot_and_duty_contract(self):
        instance, anchor_solution = balance_case()
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        result = solve(instance, anchor, method="joint_minmax", budget_s=1.,
                       started_at=0., clock=lambda: 0., max_evaluations=1000)
        checked = score_solution(instance, result["chosen_solution"])
        self.assertTrue(checked["original_feasible"], checked["issues"])
        self.assertEqual(set(checked["target_station"].values()), {0})
        self.assertEqual(len(checked["slot_duty"]), 2)

    def test_neighbor_generator_preserves_exact_target_multiset(self):
        instance = Instance("synthetic_neighbors",
                            tuple(Node(i, float(i), 0., .01, 1.) for i in range(1, 5)),
                            (Node(0, 0., 0., 0., 0.),),
                            hashlib.sha256(b"synthetic_neighbors").hexdigest(),
                            Parameters(speed=1., flight_energy=.001,
                                       small_radius=1000., large_radius=1000.))
        anchor = empty_solution(instance, [2])
        anchor["routes"] = [[[[1], [2, 3]], [[4]]]]
        expected = [1, 2, 3, 4]
        count = 0
        for _, routes, _ in _neighbours(anchor):
            observed = sorted(nid for slot in routes[0] for trip in slot for nid in trip)
            self.assertEqual(observed, expected)
            count += 1
        self.assertGreater(count, 0)

    def test_small_station_lpt_never_uses_large_slot(self):
        instance, _ = balance_case()
        anchor_solution = empty_solution(instance, [1])
        anchor_solution["routes"] = [[[], [[1], [2]]]]
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        result = solve(instance, anchor, method="lpt", budget_s=1.,
                       started_at=0., clock=lambda: 0.)
        self.assertTrue(result["chosen_score"]["admissible"])
        self.assertEqual(result["chosen_solution"]["routes"][0][0], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
