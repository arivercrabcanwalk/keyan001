import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import development_runner as runner
from run_full_map_smoke import fixture
from weather_full_map import replay_weather_solution
from weather_scenario_io import load_weather_scenario


class DevelopmentRunnerTests(unittest.TestCase):
    def test_registration_is_bounded_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.json"
            r = runner.register(path, "engineering-test-namespace", 1, 1)
            self.assertEqual([x["split"] for x in r["slots"]],
                             ["train"] * 4 + ["validation", "heldout_development"])
            self.assertEqual(runner.verify(path)["family"], [3, 20])
            r["family"] = [3, 10]
            path.write_text(json.dumps(r), encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.verify(path)

    def test_v2_registration_freezes_posix_dependencies_and_all_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register.json"
            r = runner.register(path, "engineering-test-namespace", 1, 1)
            self.assertEqual(r["algorithms"], ["PPO", "A2C", "REINFORCE"])
            self.assertTrue(all("\\" not in key for key in r["dependencies"]))
            self.assertEqual(r["resource_limits"]["cpu_threads"], 1)
            r["resource_limits"]["max_episode_steps"] += 1
            path.write_text(json.dumps(r), encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.verify(path)

    @unittest.skipUnless((runner.G24 / "linux_migration_20261104/evidence_local/windows_development_probe_20261104"
                          / "route_rl_windows_development_registration_probe.json").is_file(),
                         "local Windows v1 provenance fixture is not included in the portable source bundle")
    def test_v1_to_v2_amendment_binds_existing_six_maps_without_replacement(self):
        base = runner.G24 / "linux_migration_20261104/evidence_local/windows_development_probe_20261104"
        legacy_registration = base / "route_rl_windows_development_registration_probe.json"
        legacy_materialization = base / "remote_output"
        legacy_bundle = runner.G24 / "linux_migration_20261104/evidence_local/windows_development_v1.zip"
        if not (legacy_registration.is_file() and (legacy_materialization / "MATERIALIZATION.json").is_file()
                and legacy_bundle.is_file()):
            self.skipTest("optional v1 amendment provenance fixture is not packaged")
        with tempfile.TemporaryDirectory() as tmp:
            v2 = Path(tmp) / "amended.json"
            r = runner.amend(v2, "windows-development-amendment-v2", 1, 1, legacy_registration,
                             legacy_materialization, legacy_bundle)
            self.assertEqual(runner.validate_materialization(v2, legacy_materialization)[1]["slots"],
                             runner.read(legacy_materialization / "MATERIALIZATION.json")["slots"])
            self.assertTrue((Path(tmp) / "amended.AMENDMENT_RECEIPT.json").is_file())
            with self.assertRaises(ValueError):
                runner.materialize(v2, Path(tmp) / "replacement")

    @unittest.skipUnless((runner.G24 / "linux_migration_20261104/evidence_local/windows_development_probe_20261104"
                          / "route_rl_windows_development_registration_probe.json").is_file(),
                         "local Windows v1 provenance fixture is not included in the portable source bundle")
    def test_v1_bundle_dependency_tamper_is_rejected(self):
        base = runner.G24 / "linux_migration_20261104/evidence_local/windows_development_probe_20261104"
        legacy_registration = base / "route_rl_windows_development_registration_probe.json"
        legacy_bundle = runner.G24 / "linux_migration_20261104/evidence_local/windows_development_v1.zip"
        if not (legacy_registration.is_file() and legacy_bundle.is_file()):
            self.skipTest("optional v1 amendment provenance fixture is not packaged")
        with tempfile.TemporaryDirectory() as tmp:
            registration = runner.read(legacy_registration)
            registration["dependencies"][next(iter(registration["dependencies"]))] = "0" * 64
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(registration), encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.verify_legacy_bundle(bad, legacy_bundle)

    def test_fixed_weather_serialization_and_instance_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "scenario.json"
            runner.write(p, runner.scenario("a" * 64))
            weather, receipt = load_weather_scenario(p, expected_instance_sha256="a" * 64)
            self.assertEqual(receipt["nfz_vertex_count"], 4)
            self.assertEqual(weather.no_fly_zone.on_s, 300)
            with self.assertRaises(ValueError):
                load_weather_scenario(p, expected_instance_sha256="b" * 64)

    def test_generator_exceptions_are_retained_without_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            registration = Path(tmp) / "register.json"
            runner.register(registration, "engineering-test-namespace", 1, 1)
            out = Path(tmp) / "output"
            with mock.patch.object(runner.generator, "load_required_exclusions", return_value=object()), \
                    mock.patch.object(runner.generator, "generate_allocated_instance", side_effect=RuntimeError("probe")):
                runner.materialize(registration, out)
            slots = runner.read(out / "MATERIALIZATION.json")["slots"]
            self.assertEqual(len(slots), 6)
            self.assertTrue(all(row["status"] == "generation_exception" for row in slots))
            self.assertTrue(all("probe" in row["reason"] for row in slots))

    def test_greedy_is_a_physical_route_and_replay_is_authoritative(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        episode = runner.run_episode((instance, anchor, weather, replay["weather_cost"] + 100))
        self.assertTrue(episode["events"])
        self.assertTrue(all(set(event) == {"station_idx", "slot", "target", "reward", "completion_min",
                                         "failure", "elapsed_s"} for event in episode["events"]))
        if episode["complete"]:
            self.assertTrue(episode["result"]["replay"]["admissible"])
        else:
            self.assertIsNotNone(episode["failure"])

    def test_author_demonstration_replays_only_legal_physical_actions(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        case = (instance, anchor, weather, replay["weather_cost"] + 100)
        demonstration = runner.author_demonstration(case, solution, max_steps=128)
        self.assertTrue(demonstration["complete"])
        self.assertIsNone(demonstration["failure"])
        self.assertTrue(demonstration["transitions"])
        self.assertEqual(demonstration["result"]["replay"]["admissible"], True)
        self.assertTrue(all(isinstance(item["action"], int) and bool(item["mask"][item["action"]])
                            for item in demonstration["transitions"]))
        with self.assertRaises(TimeoutError):
            runner.author_demonstration(case, solution, deadline=0.0)
        with self.assertRaises(RuntimeError):
            runner.author_demonstration(case, solution, max_steps=0)
        invalid = json.loads(json.dumps(solution))
        for routes in invalid["routes"]:
            if routes[0]:
                routes[0][0].append(routes[0][0][0])
                break
        with self.assertRaises(ValueError):
            runner.author_demonstration(case, invalid)

    def test_deadline_records_failure(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        episode = runner.run_episode((instance, anchor, weather, replay["weather_cost"]), deadline=0)
        self.assertFalse(episode["complete"])
        self.assertEqual(episode["failure"], "deadline")

    def test_step_limit_records_failure(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        episode = runner.run_episode((instance, anchor, weather, replay["weather_cost"]), max_steps=0)
        self.assertFalse(episode["complete"])
        self.assertEqual(episode["failure"], "step_limit")

    def test_optional_beam_is_a_direct_physical_route_control(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        episode = runner.beam_episode((instance, anchor, weather, replay["weather_cost"] + 100), 0,
                                      max_steps=128)
        self.assertFalse(episode["complete"])
        self.assertEqual(episode["failure"], "deadline")
        self.assertIn("events", episode)

    def test_synthetic_experiment_persists_all_algorithms_and_comparisons(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        case = (instance, anchor, weather, replay["weather_cost"] + 100)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registration = root / "registration.json"
            r = runner.register(registration, "synthetic-experiment-v2", 1, 1)
            material = {"slots": r["slots"]}
            anchors = {"registration_sha256": runner.sha(registration),
                       "slots": [{"id": row["id"], "status": "eligible", "reason": None,
                                  "artifact_hashes": {}}
                                 for row in r["slots"]]}
            runner.write(root / "ANCHORS.json", anchors)
            for row in r["slots"]:
                solution_path = root / row["id"] / "author/solution.json"
                solution_path.parent.mkdir(parents=True)
                solution_path.write_text(json.dumps(solution), encoding="utf-8")
                strict_replay = replay_weather_solution(instance, anchor, weather, solution,
                                                       weather_cost_cap=case[3])
                runner.write(root / row["id"] / "weather_anchor.json",
                             {"author_weather_replay": strict_replay})
            with mock.patch.object(runner, "validate_materialization", return_value=(r, material)), \
                    mock.patch.object(runner, "load_case", return_value=case):
                runner.experiment(registration, root)
            report = runner.read(root / "experiment/RESULTS.json")
            self.assertEqual(report["status"], "completed")
            self.assertEqual(len(report["training"]), 9)
            self.assertTrue(all(row["status"] == "ok" and row["last_completed_update"] == 0
                                for row in report["training"]))
            self.assertTrue(all(row["warm_start"]["algorithm"] == "behavior_cloning"
                                for row in report["training"]))
            self.assertEqual(report["demonstrations"]["transition_count"], 32)
            self.assertEqual(len(report["controls"]), 3)
            self.assertEqual(len(report["comparisons"]), 56)
            self.assertTrue(all(t["matched_bc_initialization_verified"] for t in report["training"]))
            controls = {t["seed"]: t for t in report["controls"]}
            self.assertTrue(all(t["bc_state_dict_sha256"] == controls[t["seed"]]["state_dict_sha256"]
                                for t in report["training"]))
            learned = [t for t in report["comparisons"] if t["training_regime"] != "nonRL"]
            self.assertEqual(len(learned), 48)
            self.assertTrue(all(t["candidate"]["events"] for t in learned))
            self.assertTrue(all("FileNotFoundError" not in str(t["candidate"].get("failure"))
                                and "checkpoint" not in str(t["candidate"].get("failure")) for t in learned))
            self.assertTrue(all(t["demonstration_receipt_sha256"] == report["demonstration_receipt_sha256"]
                                and t["demonstration_transition_count"] == 32 for t in learned))
            self.assertTrue(all(t["method"].startswith(("BC-only_", "BC+")) for t in learned))
            self.assertTrue((root / "experiment/TRAINING_UPDATES.jsonl").is_file())
            self.assertTrue((root / "experiment/COMPARISONS.jsonl").is_file())
            self.assertTrue((root / "experiment/DEMONSTRATIONS.json").is_file())

    def test_demonstration_failures_always_write_terminal_result(self):
        instance, solution, anchor, weather = fixture()
        replay = replay_weather_solution(instance, anchor, weather, solution, strict_weather_cap=False)
        case = (instance, anchor, weather, replay["weather_cost"] + 100)
        for failure in (TimeoutError("demonstration_deadline"), ValueError("invalid_demo"),
                        RuntimeError("demonstration_transition_limit")):
            with self.subTest(failure=str(failure)), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); registration = root / "registration.json"
                r = runner.register(registration, "synthetic-demo-failure-v3", 1, 1)
                material = {"slots": r["slots"]}
                runner.write(root / "ANCHORS.json", {"registration_sha256": runner.sha(registration),
                    "slots": [{"id": row["id"], "status": "eligible", "artifact_hashes": {}}
                              for row in r["slots"]]})
                for row in r["slots"]:
                    runner.write(root / row["id"] / "author/solution.json", solution)
                with mock.patch.object(runner, "validate_materialization", return_value=(r, material)), \
                        mock.patch.object(runner, "load_case", return_value=case), \
                        mock.patch.object(runner, "author_demonstration", side_effect=failure):
                    runner.experiment(registration, root)
                result = runner.read(root / "experiment/RESULTS.json")
                self.assertEqual(result["status"], "demonstration_failed")
                self.assertIn(str(failure), result["demonstrations"]["error"])
                self.assertEqual(result["training"], [])

    def test_import_preserves_failed_rows_and_all_original_bytes_without_solver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source_out = root / "source"; out = root / "target"
            source_reg = root / "source_reg.json"; target_reg = root / "target_reg.json"
            target = {"amendment": {"marker": "same"}, "author_seed_namespace": "fixed",
                      "dependencies": {"scorer.py": "1" * 64}}
            runner.write(source_reg, {**target, "schema": "weather_common_map_development_v2"})
            runner.write(target_reg, target)
            rows = [{"id": slot["id"], "status": "anchor_failed" if i % 2 else "eligible",
                     "reason": "retained_failure" if i % 2 else None, "artifact_hashes": {}}
                    for i, slot in enumerate(runner.slots())]
            for row in rows:
                runner.write(source_out / row["id"] / "author/solution.json", {"id": row["id"]})
            runner.write(source_out / "MATERIALIZATION.json", {"slots": runner.slots()})
            runner.write(source_out / "ANCHORS.json", {"schema": "weather_common_map_development_v2",
                "registration_sha256": runner.sha(source_reg), "slots": rows})
            runner.write(source_out / "experiment/RESULTS.json", {"old_run": True})
            args = (target_reg, out, source_reg, source_out,
                    runner.sha(source_reg), runner.sha(source_out / "ANCHORS.json"))
            with mock.patch.object(runner, "validate_materialization", return_value=(target, {"slots": runner.slots()})), \
                    mock.patch.object(runner.author_runner, "run_one", side_effect=AssertionError("must not solve")):
                receipt = runner.import_anchors(*args)
                self.assertEqual(receipt["author_solver_calls"], 0)
                self.assertEqual(runner.read(out / "ANCHORS.json")["slots"], rows)
                self.assertEqual(runner.sha(out / "SOURCE_ANCHORS.v2.json"), args[-1])
                self.assertFalse((out / "experiment").exists())
                for row in rows:
                    self.assertEqual(runner.sha(out / row["id"] / "author/solution.json"),
                                     runner.sha(source_out / row["id"] / "author/solution.json"))
                with self.assertRaises(ValueError):
                    runner.import_anchors(target_reg, root / "bad", source_reg, source_out, "0" * 64, args[-1])

    def test_fallback_and_overrun_are_distinct(self):
        anchor = {"M_return": 12.0}
        failed = {"complete": False}
        on_time = runner.select_timed_result(failed, anchor, 5.9, 6.0)
        self.assertEqual(on_time["selected"], "author_anchor")
        late = runner.select_timed_result(failed, anchor, 6.1, 6.0)
        self.assertEqual(late["status"], "deadline_missed")
        self.assertIsNone(late["selected_score"])
        self.assertEqual(runner.select_timed_result(failed, None, 1.0, 6.0)["status"], "fallback_unavailable")
        better = {"complete": True, "result": {"replay": {"M_return": 11.0}}}
        self.assertEqual(runner.select_timed_result(better, anchor, 5.0, 6.0)["selected"], "candidate")


if __name__ == "__main__":
    unittest.main()
