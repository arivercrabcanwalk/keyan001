"""Multi-station deterministic-forecast weather environment tests."""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parent
for path in (str(PACKAGE), str(ROOT / "reproduction/reviewer_package_semfix"), str(PACKAGE.parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from lrphsd.problem import Instance, Node, Parameters, empty_solution
from scorer import CostAnchor, score_solution
from weather_full_map import (WeatherFullMapEnv, WeatherMapAction, WeatherMapScenario,
                              replay_weather_solution)
from weather_oracle import NoFlyZone, Point, WindField, WindKnot


def fixture():
    params = Parameters(speed=900.0, flight_energy=0.018, small_battery=1.0,
                        large_battery=1.2, small_radius=4000.0, large_radius=5000.0,
                        small_duration=60.0, large_duration=70.0)
    stations = (Node(100, 0.0, 0.0, 0.0, 0.0), Node(200, 6000.0, 0.0, 0.0, 0.0))
    targets = (Node(1, 900.0, 0.0, 0.12, 1.0), Node(2, 6900.0, 0.0, 0.12, 1.0))
    instance = Instance("two_station", targets, stations, "two-station-hash", params)
    solution = empty_solution(instance, [2, 1])
    solution["routes"] = [[[[1]], []], [[], [[2]]]]
    return instance, solution, CostAnchor.from_solution(instance, solution)


def calm_scenario():
    return WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0),)), name="calm")


def temporal_fixture(battery=99.0, wind_case=False):
    params = Parameters(speed=900.0, flight_energy=0.018, small_battery=battery,
                        large_battery=99.0, small_radius=10000.0, large_radius=10000.0,
                        small_duration=999.0, large_duration=999.0, time_cost=1.0)
    targets = (Node(1, 900.0, 0.0, 0.0, 0.0),
               Node(2, 1000.0 if wind_case else 900.0, 0.0 if wind_case else 100.0,
                    0.0, 3.0 if wind_case else 10.0))
    instance = Instance("temporal", targets, (Node(100, 0, 0, 0, 0),), "temporal-hash", params)
    solution = empty_solution(instance, [1])
    solution["routes"] = [[[], [[1, 2]]]]
    anchor = CostAnchor.from_solution(instance, solution)
    if wind_case:
        scenario = WeatherMapScenario(WindField((WindKnot(0, 0, 0), WindKnot(60, 20, 0),
                                                 WindKnot(200, 0, 0))), name="wind")
    else:
        zone = NoFlyZone((Point(300, -400), Point(700, -400), Point(700, 400),
                          Point(300, 400)), 0, 500)
        scenario = WeatherMapScenario(WindField((WindKnot(0, 0, 0),)), zone, name="nfz")
    return instance, solution, anchor, scenario


class WeatherFullMapTests(unittest.TestCase):
    def execute(self, env, ordering):
        for action in ordering:
            self.assertTrue(env._legal(action), action)
            _, _, _, info = env.step(action)
            self.assertIsNone(info["failure"])
        self.assertTrue(env.done)
        return env.result()

    def test_zero_weather_reproduces_original_multi_slot_clock_and_cost(self):
        instance, solution, anchor = fixture()
        original = score_solution(instance, solution)
        replay = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                         weather_cost_cap=original["cost"])
        self.assertTrue(replay["admissible"], replay["issues"])
        self.assertAlmostEqual(replay["weather_cost"], original["cost"], places=7)
        self.assertAlmostEqual(replay["M_return"], original["M_return"], places=7)
        env = WeatherFullMapEnv(instance, anchor, calm_scenario(), weather_cost_cap=original["cost"])
        result = self.execute(env, (WeatherMapAction(0, 0, 1), WeatherMapAction(1, 1, 2),
                                    WeatherMapAction(0, 0), WeatherMapAction(1, 1)))
        self.assertAlmostEqual(result["replay"]["weather_cost"], original["cost"], places=7)
        self.assertAlmostEqual(result["replay"]["M_return"], original["M_return"], places=7)
        self.assertAlmostEqual(result["reward"], -original["M_return"], places=7)

    def test_temporal_closure_does_not_mask_feasible_anchor_prefix(self):
        for battery in (99.0, 0.05):
            with self.subTest(battery=battery):
                instance, solution, anchor, scenario = temporal_fixture(battery)
                raw = replay_weather_solution(instance, anchor, scenario, solution, strict_weather_cap=False)
                self.assertTrue(raw["admissible"], raw["issues"])
                env = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=raw["weather_cost"])
                result = self.execute(env, (WeatherMapAction(0, 1, 1), WeatherMapAction(0, 1, 2),
                                            WeatherMapAction(0, 1)))
                self.assertTrue(result["replay"]["admissible"])
                self.assertAlmostEqual(result["reward"], -raw["M_return"])

    def test_infeasible_immediate_return_can_become_feasible_later(self):
        instance, solution, anchor, scenario = temporal_fixture(wind_case=True)
        raw = replay_weather_solution(instance, anchor, scenario, solution, strict_weather_cap=False)
        self.assertTrue(raw["admissible"], raw["issues"])
        env = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=raw["weather_cost"])
        first = WeatherMapAction(0, 1, 1)
        self.assertFalse(env._project_target(first)["inbound"].legal)
        obs = env.observation()
        index = obs["actions"].index(first)
        self.assertTrue(obs["mask"][index])
        self.assertEqual(obs["candidates"][index, -1], 0.0)
        self.execute(env, (first, WeatherMapAction(0, 1, 2), WeatherMapAction(0, 1)))

    def test_colocated_targets_and_return_preserve_departures(self):
        instance = Instance("colocated", (Node(1, 0, 0, 0.1, 1), Node(2, 0, 0, 0.2, 2)),
                            (Node(100, 0, 0, 0, 0),), "colocated", Parameters())
        solution = empty_solution(instance, [1])
        solution["routes"] = [[[], [[1, 2]]]]
        anchor = CostAnchor.from_solution(instance, solution)
        raw = replay_weather_solution(instance, anchor, calm_scenario(), solution, strict_weather_cap=False)
        self.assertTrue(raw["admissible"], raw["issues"])
        env = WeatherFullMapEnv(instance, anchor, calm_scenario(), weather_cost_cap=raw["weather_cost"])
        result = self.execute(env, (WeatherMapAction(0, 1, 1), WeatherMapAction(0, 1, 2),
                                    WeatherMapAction(0, 1)))
        legs = result["replay"]["slot_rows"][1]["legs"]
        self.assertEqual([leg["departure_s"] for leg in legs], [0.0, 60.0, 180.0])
        self.assertEqual([leg["arrival_s"] for leg in legs], [0.0, 60.0, 180.0])

    def test_interleaved_decode_order_does_not_serialise_slot_clocks(self):
        instance, solution, anchor = fixture()
        cap = score_solution(instance, solution)["cost"]
        a = WeatherFullMapEnv(instance, anchor, calm_scenario(), weather_cost_cap=cap)
        b = WeatherFullMapEnv(instance, anchor, calm_scenario(), weather_cost_cap=cap)
        result_a = self.execute(a, (WeatherMapAction(0, 0, 1), WeatherMapAction(1, 1, 2),
                                    WeatherMapAction(0, 0), WeatherMapAction(1, 1)))
        result_b = self.execute(b, (WeatherMapAction(1, 1, 2), WeatherMapAction(0, 0, 1),
                                    WeatherMapAction(1, 1), WeatherMapAction(0, 0)))
        self.assertEqual(result_a["replay"]["M_return"], result_b["replay"]["M_return"])
        self.assertEqual(result_a["replay"]["weather_cost"], result_b["replay"]["weather_cost"])

    def test_sabs_has_no_large_slot_and_fixed_ownership_cannot_move(self):
        instance, solution, anchor = fixture()
        env = WeatherFullMapEnv(instance, anchor, calm_scenario())
        actions = env.observation()["actions"]
        self.assertNotIn(WeatherMapAction(1, 0, 2), actions)
        self.assertFalse(env._legal(WeatherMapAction(0, 0, 2)))

    def test_replay_is_not_coupled_to_primary_oracle(self):
        instance, solution, anchor = fixture()
        import weather_full_map
        original = weather_full_map.plan_route
        weather_full_map.plan_route = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("broken"))
        try:
            replay = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                             weather_cost_cap=score_solution(instance, solution)["cost"])
        finally:
            weather_full_map.plan_route = original
        self.assertTrue(replay["admissible"], replay["issues"])

    def test_forecast_features_expose_future_schedule(self):
        instance, solution, anchor = fixture()
        first = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0), WindKnot(30.0, 3.0, 0.0))), name="a")
        second = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0), WindKnot(30.0, -3.0, 0.0))), name="b")
        self.assertFalse((WeatherFullMapEnv(instance, anchor, first).observation()["global"] ==
                          WeatherFullMapEnv(instance, anchor, second).observation()["global"]).all())

    def test_primary_nfz_detour_is_replayed_by_independent_oracle(self):
        instance, solution, anchor = fixture()
        zone = NoFlyZone((Point(300.0, -200.0), Point(700.0, -200.0),
                          Point(700.0, 200.0), Point(300.0, 200.0)), 0.0, 1000.0)
        scenario = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0),)), zone, name="nfz")
        env = WeatherFullMapEnv(instance, anchor, scenario)
        self.assertTrue(env._legal(WeatherMapAction(0, 0, 1)))
        env.step(WeatherMapAction(0, 0, 1))
        self.assertGreater(env.slots[(0, 0)].clock_s / 60.0, 1.0)

    def test_wind_must_cover_zero(self):
        with self.assertRaisesRegex(ValueError, "cover time zero"):
            WindField((WindKnot(1.0, 0.0, 0.0),))

    def test_initial_weather_dead_end_has_a_stable_failure_code(self):
        instance, solution, anchor = fixture()
        impossible = WeatherMapScenario(WindField((WindKnot(0.0, -20.0, 0.0),)), name="headwind")
        env = WeatherFullMapEnv(instance, anchor, impossible)
        self.assertTrue(env.dead_end)
        self.assertTrue(env.terminated)
        self.assertEqual(env.failure, "dead_end")

    def test_weather_cap_boundary_is_replayed_strictly(self):
        instance, solution, anchor = fixture()
        score = replay_weather_solution(instance, anchor, calm_scenario(), solution)
        accepted = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                           weather_cost_cap=score["weather_cost"] + 1e-7)
        rejected = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                           weather_cost_cap=score["weather_cost"] - 2e-7)
        self.assertTrue(accepted["admissible"], accepted["issues"])
        self.assertFalse(rejected["admissible"])
        self.assertIn("weather_cost_cap", rejected["issues"])

    def test_raw_measurement_mode_cannot_bypass_an_explicit_failed_weather_cap(self):
        instance, solution, anchor = fixture()
        raw = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                      strict_weather_cap=False)
        rejected = replay_weather_solution(instance, anchor, calm_scenario(), solution,
                                           weather_cost_cap=raw["weather_cost"] - 1.0,
                                           strict_weather_cap=False)
        self.assertFalse(rejected["admissible"])
        self.assertIn("weather_cost_cap", rejected["issues"])

    def test_original_anchor_cap_remains_a_terminal_admission_requirement(self):
        params = Parameters(speed=900.0, flight_energy=0.018, small_battery=99.0,
                            large_battery=99.0, small_radius=10000.0, large_radius=10000.0,
                            small_duration=999.0, large_duration=999.0, time_cost=1.0)
        targets = (Node(1, -3000.0, -3000.0, 0.0, 0.0), Node(2, -3000.0, 0.0, 0.0, 0.0),
                   Node(3, 3000.0, -3000.0, 0.0, 0.0))
        instance = Instance("cap", targets, (Node(100, 0.0, 0.0, 0.0, 0.0),), "cap-witness", params)
        anchor_solution = empty_solution(instance, [2])
        candidate = empty_solution(instance, [2])
        anchor_solution["routes"] = [[[[1, 2, 3]], []]]
        candidate["routes"] = [[[[1, 3, 2]], []]]
        anchor = CostAnchor.from_solution(instance, anchor_solution)
        scenario = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 14.0),)), name="north")
        reference = replay_weather_solution(instance, anchor, scenario, anchor_solution,
                                            weather_cost_cap=1e9)
        replay = replay_weather_solution(instance, anchor, scenario, candidate,
                                         weather_cost_cap=reference["weather_cost"])
        self.assertGreater(score_solution(instance, candidate)["cost"], anchor.cost)
        self.assertFalse(replay["admissible"])
        self.assertIn("original_cost_or_domain_cap", replay["issues"])

    def test_capped_observation_masks_an_unflyable_candidate_without_throwing(self):
        instance, solution, anchor = fixture()
        scenario = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0),
                                                 WindKnot(150.0, 0.0, 100.0))), name="mixed")
        env = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=1e9)
        observation = env.observation()
        self.assertTrue((~observation["mask"]).any())
        self.assertIsInstance(observation["dead_end"], bool)

    def test_replay_and_primary_share_crosswind_boundary(self):
        from weather_oracle import FlightParams, plan_route
        from weather_replay import replay_route
        flight = FlightParams(speed=900.0, flight_energy=0.018)
        wind = WindField((WindKnot(0.0, 1.0, 15.0000000005),))
        primary = plan_route(Point(0.0, 0.0), Point(900.0, 0.0), 0.0, wind, flight)
        secondary = replay_route(Point(0.0, 0.0), Point(900.0, 0.0), 0.0, wind, flight)
        self.assertFalse(primary.legal)
        self.assertFalse(secondary.legal)
        self.assertEqual(primary.failure, secondary.failure)

    def test_forecast_padding_masks_distinguish_valid_zero_vertex(self):
        instance, solution, anchor = fixture()
        wind = WindField((WindKnot(0.0, 0.0, 0.0),))
        tri = NoFlyZone((Point(0.0, -300.0), Point(300.0, -300.0), Point(300.0, 0.0)), 0.0, 1000.0)
        quad = NoFlyZone((Point(0.0, -300.0), Point(300.0, -300.0),
                          Point(300.0, 0.0), Point(0.0, 0.0)), 0.0, 1000.0)
        a = WeatherFullMapEnv(instance, anchor, WeatherMapScenario(wind, tri, name="tri")).observation()
        b = WeatherFullMapEnv(instance, anchor, WeatherMapScenario(wind, quad, name="quad")).observation()
        self.assertFalse((a["global"] == b["global"]).all())
        self.assertEqual(len(a["state_receipt"]["slots"]), 3)

    def test_policy_global_tensor_contains_slot_and_target_state_tables(self):
        instance, solution, anchor = fixture()
        env = WeatherFullMapEnv(instance, anchor, calm_scenario(), weather_cost_cap=1000.0)
        before = env.observation()["global"].copy()
        env.step(WeatherMapAction(0, 0, 1))
        after = env.observation()["global"]
        self.assertEqual(before.size, WeatherFullMapEnv.global_dim)
        self.assertFalse((before == after).all())

    def test_policy_capacity_uses_active_physical_slots_not_station_count(self):
        params = Parameters(speed=900.0, flight_energy=0.018, small_battery=99.0,
                            large_battery=99.0, small_radius=1000.0, large_radius=1000.0,
                            small_duration=999.0, large_duration=999.0)
        stations = tuple(Node(100 + index, index * 100.0, 0.0, 0.0, 0.0) for index in range(11))
        targets = tuple(Node(index + 1, index * 100.0 + 1.0, 0.0, 0.0, 0.0) for index in range(11))
        instance = Instance("slots", targets, stations, "slot-cap", params)
        solution = empty_solution(instance, [2] * 11)
        solution["routes"] = [[[[index + 1]], []] for index in range(11)]
        anchor = CostAnchor.from_solution(instance, solution)
        with self.assertRaisesRegex(ValueError, "policy-state table capacity"):
            WeatherFullMapEnv(instance, anchor, calm_scenario())

        sparse_stations = tuple(Node(200 + index, index * 100.0, 0.0, 0.0, 0.0) for index in range(21))
        sparse = Instance("sparse", (Node(1, 1.0, 0.0, 0.0, 0.0),), sparse_stations,
                          "sparse-stations", params)
        sparse_solution = empty_solution(sparse, [1] + [0] * 20)
        sparse_solution["routes"] = [[[], [[1]]]] + [[[], []] for _ in range(20)]
        sparse_anchor = CostAnchor.from_solution(sparse, sparse_solution)
        self.assertEqual(len(WeatherFullMapEnv(sparse, sparse_anchor, calm_scenario()).slots), 1)

    def test_nfz_coordinates_share_the_policy_coordinate_frame(self):
        params = Parameters(speed=900.0, flight_energy=0.018, small_battery=99.0,
                            large_battery=99.0, small_radius=1000.0, large_radius=1000.0,
                            small_duration=999.0, large_duration=999.0)

        def environment(inactive_x, vertices):
            instance = Instance("nfz-scale", (Node(1, 50.0, 50.0, 0.0, 0.0),
                                               Node(2, 150.0, 0.0, 0.0, 0.0)),
                                (Node(100, 0.0, 0.0, 0.0, 0.0),
                                 Node(200, inactive_x, 0.0, 0.0, 0.0)),
                                f"nfz-scale-{inactive_x}", params)
            solution = empty_solution(instance, [1, 0])
            solution["routes"] = [[[], [[1, 2]]], [[], []]]
            anchor = CostAnchor.from_solution(instance, solution)
            zone = NoFlyZone(tuple(Point(x, y) for x, y in vertices), 0.0, 1000.0)
            return WeatherFullMapEnv(instance, anchor, WeatherMapScenario(
                WindField((WindKnot(0.0, 0.0, 0.0),)), zone, name="nfz-scale"))

        first = environment(1000.0, ((95.0, 20.0), (105.0, 20.0),
                                     (105.0, 30.0), (95.0, 30.0)))
        second = environment(2000.0, ((190.0, 40.0), (210.0, 40.0),
                                      (210.0, 60.0), (190.0, 60.0)))
        before_first = first.observation()
        before_second = second.observation()
        self.assertFalse((before_first["global"] == before_second["global"]).all())
        first.step(WeatherMapAction(0, 1, 1))
        second.step(WeatherMapAction(0, 1, 1))
        after_first = first.observation()
        after_second = second.observation()
        self.assertFalse((after_first["global"] == after_second["global"]).all())
        self.assertFalse((after_first["candidates"] == after_second["candidates"]).all())

    def test_original_cost_cap_is_in_the_policy_state_and_candidate_projection(self):
        params = Parameters(speed=900.0, flight_energy=0.018, small_battery=99.0,
                            large_battery=99.0, small_radius=10000.0, large_radius=10000.0,
                            small_duration=999.0, large_duration=999.0, time_cost=1.0)
        instance = Instance("cap-state", (Node(1, -3000.0, -3000.0, 0.0, 0.0),
                                            Node(2, -3000.0, 0.0, 0.0, 0.0),
                                            Node(3, 3000.0, -3000.0, 0.0, 0.0)),
                            (Node(100, 0.0, 0.0, 0.0, 0.0),), "cap-state-hash", params)

        def anchor_for(order):
            solution = empty_solution(instance, [2])
            solution["routes"] = [[[list(order)], []]]
            return CostAnchor.from_solution(instance, solution)

        scenario = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 0.0),)), name="calm")
        tight = WeatherFullMapEnv(instance, anchor_for((2, 1, 3)), scenario, weather_cost_cap=1e9)
        loose = WeatherFullMapEnv(instance, anchor_for((1, 3, 2)), scenario, weather_cost_cap=1e9)
        before_tight, before_loose = tight.observation(), loose.observation()
        self.assertFalse((before_tight["global"] == before_loose["global"]).all())
        tight.step(WeatherMapAction(0, 0, 1))
        loose.step(WeatherMapAction(0, 0, 1))
        after_tight, after_loose = tight.observation(), loose.observation()
        self.assertFalse((after_tight["global"] == after_loose["global"]).all())
        self.assertFalse((after_tight["candidates"] == after_loose["candidates"]).all())

    def test_uncapped_terminal_solution_is_not_weather_admissible(self):
        instance, solution, anchor = fixture()
        env = WeatherFullMapEnv(instance, anchor, calm_scenario())
        for action in (WeatherMapAction(0, 0, 1), WeatherMapAction(1, 1, 2),
                       WeatherMapAction(0, 0), WeatherMapAction(1, 1)):
            env.step(action)
        self.assertTrue(env.done)
        self.assertEqual(env.failure, "terminal_replay_rejected")
        with self.assertRaisesRegex(RuntimeError, "weather-admissible"):
            env.result()

    def test_training_records_zero_transition_failures(self):
        from run_full_map_smoke import fixture as smoke_fixture, train
        instance, solution, anchor, scenario = smoke_fixture()
        impossible = WeatherMapScenario(WindField((WindKnot(0.0, 0.0, 100.0),)), name="all-infeasible")
        _, result, history = train(instance, anchor, impossible, None, "PPO", 103, updates=1, episodes=2)
        self.assertIsNone(result)
        self.assertEqual(history[0]["complete"], 0)
        self.assertEqual(history[0]["failures"], ["dead_end", "dead_end"])
        self.assertTrue(history[0]["skipped_update_no_transitions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
