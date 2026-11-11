import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / "route_rl_research/20261103/source_snapshot"
sys.path.insert(0, str(SNAPSHOT))
sys.path.insert(0, str(Path(__file__).parent))

from lrphsd.evaluator import evaluate
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from station_env import IllegalAction, RouteAction, StationRouteEnv


def make_instance(target_count=3, **overrides):
    stations = (Node(0, 0.0, 0.0, 0.0, 0.0),)
    all_targets = (
        Node(1, 100.0, 0.0, 0.01, 1.0),
        Node(2, 200.0, 0.0, 0.01, 1.0),
        Node(3, -200.0, 0.0, 0.01, 1.0),
    )
    targets = all_targets[:target_count]
    raw = "|".join(str(n) for n in stations + targets).encode()
    parameters = {
        "speed": 100.0,
        "flight_energy": 0.1,
        "small_battery": 0.8,
        "large_battery": 1.0,
        "small_radius": 1000.0,
        "large_radius": 1000.0,
        "small_duration": 20.0,
        "large_duration": 20.0,
        "time_cost": 0.5,
    }
    parameters.update(overrides)
    return Instance(
        "synthetic_station",
        targets,
        stations,
        hashlib.sha256(raw).hexdigest(),
        Parameters(**parameters),
    )


class StationRouteEnvTests(unittest.TestCase):
    def setUp(self):
        self.ins = make_instance()

    def test_joint_routes_are_complete_and_match_independent_evaluator(self):
        env = StationRouteEnv(self.ins, 0, 2, (1, 2, 3))
        total_reward = 0.0
        for action in (
            RouteAction(0, 1), RouteAction(0),
            RouteAction(1, 2), RouteAction(1),
            RouteAction(0, 3), RouteAction(0),
        ):
            self.assertTrue(env.legal(action), action)
            _, reward, _, _ = env.step(action)
            total_reward += reward
        result = env.result()
        solution = empty_solution(self.ins, [2])
        solution["routes"][0] = result["routes"]
        audit = evaluate(self.ins, solution)
        self.assertTrue(audit["feasible"], audit["issues"])
        self.assertAlmostEqual(total_reward, -audit["operating_minutes"] * self.ins.params.time_cost)
        self.assertAlmostEqual(result["reward"], total_reward)

    def test_return_resets_trip_state_but_preserves_cumulative_duty(self):
        env = StationRouteEnv(self.ins, 0, 2, (1, 2))
        env.step(RouteAction(1, 2))
        duty_before = env.cumulative_duty[1]
        env.step(RouteAction(1))
        self.assertEqual(env.current_pos[1], self.ins.stations[0].id)
        self.assertEqual(env.trip_energy[1], 0.0)
        self.assertEqual(env.trip_elapsed[1], 0.0)
        self.assertGreater(env.cumulative_duty[1], duty_before)
        self.assertEqual(len(env.routes[1]), 1)

    def test_target_is_assigned_once_and_illegal_repeat_is_rejected(self):
        env = StationRouteEnv(self.ins, 0, 2, (1, 2))
        env.step(RouteAction(0, 1))
        self.assertFalse(env.legal(RouteAction(1, 1)))
        with self.assertRaises(IllegalAction):
            env.step(RouteAction(1, 1))

    def test_sabs_exposes_only_small_physical_slot(self):
        ins = make_instance(1)
        env = StationRouteEnv(ins, 0, 1, (1,))
        self.assertEqual(env.slots, (1,))
        self.assertFalse(env.legal(RouteAction(0, 1)))
        env.step(RouteAction(1, 1))
        env.step(RouteAction(1))
        sol = empty_solution(ins, [1])
        sol["routes"][0] = env.result()["routes"]
        self.assertTrue(evaluate(ins, sol)["feasible"])

    def test_done_requires_all_targets_and_all_open_trips_closed(self):
        env = StationRouteEnv(self.ins, 0, 2, (1,))
        env.step(RouteAction(0, 1))
        self.assertFalse(env.done)
        env.step(RouteAction(0))
        self.assertTrue(env.done)

    def test_mask_enforces_cumulative_duty_across_closed_trips(self):
        ins = make_instance(2, small_duration=7.0)
        env = StationRouteEnv(ins, 0, 1, (1, 2))
        env.step(RouteAction(1, 1))
        env.step(RouteAction(1))
        self.assertAlmostEqual(env.cumulative_duty[1], 3.0)
        self.assertFalse(env.legal(RouteAction(1, 2)))

    def test_mask_enforces_round_trip_battery_not_outbound_only(self):
        ins = make_instance(1, small_battery=0.2)
        env = StationRouteEnv(ins, 0, 1, (1,))
        self.assertFalse(env.legal(RouteAction(1, 1)))
        self.assertTrue(env.observation()["mask"])
        self.assertFalse(any(env.observation()["mask"]))

    def test_dead_end_is_explicit_and_does_not_return_a_partial_solution(self):
        ins = make_instance(2, small_duration=6.5)
        env = StationRouteEnv(ins, 0, 1, (1, 2))
        env.step(RouteAction(1, 1))
        env.step(RouteAction(1))
        obs = env.observation()
        self.assertFalse(env.done)
        self.assertTrue(obs["dead_end"])
        self.assertFalse(any(obs["mask"]))
        self.assertGreater(env.operating_minutes, 0.0)
        with self.assertRaises(RuntimeError):
            env.result()

        feasible = StationRouteEnv(ins, 0, 1, (1, 2))
        feasible.step(RouteAction(1, 1))
        feasible.step(RouteAction(1, 2))
        feasible.step(RouteAction(1))
        self.assertTrue(feasible.done)


if __name__ == "__main__":
    unittest.main(verbosity=2)
