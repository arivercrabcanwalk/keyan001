"""Author-witness to fixed-outer weather-anchor preflight tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from weather_author_anchor import _exact_json, _load_author_runner, prepare_author_weather_anchor
from weather_scenario_io import SCHEMA


class WeatherAuthorAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.instance = self.root / "map.txt"
        self.instance.write_text("CUST_NO XCOORD YCOORD SERVICE_ENERGY SERVICE_TIME\n"
                                 "1 100 0 0.1 1\n100 0 0 0 0\n", encoding="utf-8")
        self.runner, self.runner_path = _load_author_runner()
        self.source = self.runner.source_root_default()
        self.scorer = self.runner.scorer_default()
        self.java_home = self.root / "fake-jdk"
        (self.java_home / "bin").mkdir(parents=True)
        java = self.runner.jdk_executable(self.java_home, "java")
        self.java_bin = java
        javac = self.runner.jdk_executable(self.java_home, "javac")
        self.javac_bin = javac
        raw_template = {"station_types": [1], "routes": [[[], [[1]]]], "reference_integrity_issues": [],
                        "reference_reported_cost": 28.41111111111111}
        self.raw_payload = json.dumps(raw_template, indent=2, sort_keys=True) + "\n"
        java.write_text("synthetic java identity\n", encoding="utf-8")
        javac.write_text("synthetic javac identity\n", encoding="utf-8")
        java.chmod(0o755)
        javac.chmod(0o755)
        self.replay_payload = self.raw_payload
        self.replay_stdout = "latest completion time: 1.2222222222222223\n"
        self.replay_exit_code = 0
        self.replay_write_output = True
        self.replay_calls = []
        version_patch = patch.object(self.runner.subprocess, "run", side_effect=self._fake_version)
        process_patch = patch.object(self.runner.subprocess, "Popen", side_effect=self._fake_popen)
        version_patch.start()
        self.addCleanup(version_patch.stop)
        process_patch.start()
        self.addCleanup(process_patch.stop)
        self.run = self.root / "author"
        self.run.mkdir()
        self.build = self.root / "build"
        self.build_manifest = self.runner.prepare(self.source, "J1b", self.java_home, self.build)
        self._write_full_provenance_run()
        instance = self.runner.validate_input(self.instance, self.source, self.scorer)
        self.scenario = self.root / "scenario.json"
        self.scenario.write_text(json.dumps({"schema": SCHEMA, "name": "calm", "instance_sha256": instance.sha256,
                 "wind_knots": [{"time_s": 0.0, "east_mps": 0.0, "north_mps": 0.0}], "no_fly_zone": None,
                 "flight": {"speed_m_per_min": 900.0, "flight_energy_per_min": 0.018}}), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def _fake_version(self, command, **kwargs):
        self.assertEqual(command[1:], ["-version"])
        self.assertEqual(kwargs, {"capture_output": True, "text": True, "timeout": 15})
        self.assertIn(Path(command[0]), (self.java_bin, self.javac_bin))
        is_java = Path(command[0]) == self.java_bin
        return subprocess.CompletedProcess(command, 0, "" if is_java else "javac 17.0.99\n",
                                           'openjdk version "17.0.99"\n' if is_java else "")

    def _fake_popen(self, command, *, cwd, stdout, stderr, text, encoding, errors):
        self.assertEqual((stdout, stderr, text, encoding, errors),
                         (subprocess.PIPE, subprocess.PIPE, True, "utf-8", "replace"))
        executable = Path(command[0])
        self.assertIn(executable, (self.java_bin, self.javac_bin))
        test = self

        class FakeChild:
            returncode = 0

            def communicate(self, timeout=None):
                if executable == test.javac_bin:
                    test.assertEqual(timeout, 60.0)
                    test.assertEqual(Path(cwd), (test.build / "J1b").resolve())
                    class_dir = Path(command[command.index("-d") + 1])
                    test.assertEqual(class_dir, (test.build / "J1b/classes").resolve())
                    (class_dir / "test1").mkdir()
                    (class_dir / "test1/Main.class").write_bytes(b"synthetic class")
                    return "", ""
                test.assertEqual(timeout, 1.0)
                outputs = [arg.removeprefix("-Drepro.output=") for arg in command
                           if arg.startswith("-Drepro.output=")]
                test.assertEqual(len(outputs), 1)
                test.assertEqual(Path(outputs[0]).parent.resolve(), Path(cwd).resolve())
                test.assertEqual(command, test.runner.command_for(
                    test.java_bin, test.instance, 7, Path(outputs[0]), test.build, "J1b"))
                test.replay_calls.append((list(command), Path(cwd), timeout))
                self.returncode = test.replay_exit_code
                if test.replay_write_output:
                    Path(outputs[0]).write_text(test.replay_payload, encoding="utf-8")
                return test.replay_stdout, ""

            def kill(self):
                raise AssertionError("unexpected process timeout")

        return FakeChild()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_full_provenance_run(self):
        instance = self.runner.validate_input(self.instance, self.source, self.scorer)
        raw = {"station_types": [1], "routes": [[[], [[1]]]], "reference_integrity_issues": []}
        first = self.runner.audit_raw(instance, dict(raw, reference_reported_cost=0.0),
                                      self.source, self.scorer, 0.0)
        raw["reference_reported_cost"] = first["independent_audit"]["cost"]
        self.assertEqual(self.raw_payload, json.dumps(raw, indent=2, sort_keys=True) + "\n")
        audit = self.runner.audit_raw(instance, raw, self.source, self.scorer,
                                      first["return_score"]["M_return"])
        for name, value in (("reference.json", raw), ("solution.json", audit.pop("solution")),
                            ("independent_audit.json", audit.pop("independent_audit")),
                            ("return_score.json", audit.pop("return_score"))):
            self.runner.write_json(self.run / name, value)
        (self.run / "stdout.log").write_text(
            f"latest completion time: {audit['source_reported_latest_time']}\n", encoding="utf-8")
        (self.run / "stderr.log").write_text("", encoding="utf-8")
        # The preflight executes the frozen J1b command a second time. This
        # test JDK's fixed implementation writes the same deterministic raw
        # witness only when given a ``-Drepro.output`` destination.
        command = self.runner.command_for(self.java_bin, self.instance, 7,
                                          self.run / "reference.json", self.build, "J1b")
        process = {"command": command, "exit_code": 0, "timed_out": False, "elapsed_process_seconds": 0.01}
        artifact_names = ("reference.json", "solution.json", "independent_audit.json", "return_score.json",
                          "stdout.log", "stderr.log")
        record = {"schema": "single_author_anchor_run_v1", "profile": "J1b", "input_path": str(self.instance),
                  "input_sha256": instance.sha256, "seed": 7,
                  "source_identity": self.runner.profile_identity(self.source, "J1b"),
                  "build_manifest_sha256": self.digest(self.build / "J1b/BUILD_MANIFEST.json"),
                  "class_hashes": self.build_manifest["class_hashes"], "java": self.build_manifest["jdk"]["java"],
                  "runner_sha256": self.digest(self.runner_path),
                  "independent_dependency_hashes": {str(path): self.digest(path) for path in
                      (self.source / "lrphsd/problem.py", self.source / "lrphsd/evaluator.py", self.scorer)},
                  "timeout_seconds": 1.0, "command": command, "process": process,
                  "anchor_eligible": self.runner.anchor_eligible(process, audit), "status": "ok",
                  "artifacts": {name: self.digest(self.run / name) for name in artifact_names},
                  "witness_audit": audit}
        self.runner.write_json(self.run / "RUN.json", record)

    def test_verified_author_witness_becomes_a_weather_anchor(self):
        receipt = prepare_author_weather_anchor(self.instance, self.run, self.scenario)
        self.assertEqual(receipt["status"], "eligible")
        self.assertTrue(receipt["author_weather_replay"]["admissible"])
        self.assertAlmostEqual(receipt["weather_cost_cap"], receipt["author_weather_replay"]["weather_cost"])
        self.assertEqual(len(self.replay_calls), 1)

    def test_reexecution_must_match_raw_witness(self):
        self.replay_payload += "\n"
        with self.assertRaisesRegex(ValueError, "raw author reference differs"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)
        self.assertEqual(len(self.replay_calls), 1)

    def test_reexecution_must_match_source_clock(self):
        self.replay_stdout = "latest completion time: 9.0\n"
        with self.assertRaisesRegex(ValueError, "source clock differs"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)
        self.assertEqual(len(self.replay_calls), 1)

    def test_reexecution_must_succeed_and_produce_output(self):
        for exit_code, write_output in ((1, True), (0, False)):
            with self.subTest(exit_code=exit_code, write_output=write_output):
                self.replay_exit_code = exit_code
                self.replay_write_output = write_output
                with self.assertRaisesRegex(ValueError, "did not produce a raw reference"):
                    prepare_author_weather_anchor(self.instance, self.run, self.scenario)
        self.assertEqual(len(self.replay_calls), 2)

    def test_json_score_integer_keys_use_serialized_order(self):
        expected = {"completion": {i: i * 0.5 for i in range(1, 12)}}
        score = self.root / "score.json"
        score.write_text(json.dumps(expected, sort_keys=True), encoding="utf-8")
        _exact_json(score, expected, "score")
        score.write_text('{"completion":{"1":0.5,"10":5.1}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            _exact_json(score, {"completion": {1: 0.5, 10: 5.0}}, "score")

    def test_json_score_rejects_duplicate_or_colliding_keys(self):
        score = self.root / "score.json"
        score.write_text('{"completion":{"1":1,"1":2}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            _exact_json(score, {"completion": {1: 2}}, "score")
        score.write_text('{"1":2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            _exact_json(score, {1: 1, "1": 2}, "score")

    def test_minimal_hand_authored_run_is_rejected(self):
        run_path = self.run / "RUN.json"
        run_path.write_text(json.dumps({"anchor_eligible": True, "status": "ok"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "provenance"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)

    def test_solution_hash_mismatch_is_rejected(self):
        solution_path = self.run / "solution.json"
        solution_path.write_text(solution_path.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)

    def test_input_path_and_timeout_are_semantically_checked(self):
        run_path = self.run / "RUN.json"
        run = json.loads(run_path.read_text())
        run["input_path"] = str(self.root / "wrong-map.txt")
        self.runner.write_json(run_path, run)
        with self.assertRaisesRegex(ValueError, "input path"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)
        run["input_path"] = str(self.instance)
        run["timeout_seconds"] = -1.0
        self.runner.write_json(run_path, run)
        with self.assertRaisesRegex(ValueError, "timeout"):
            prepare_author_weather_anchor(self.instance, self.run, self.scenario)


if __name__ == "__main__":
    unittest.main(verbosity=2)
