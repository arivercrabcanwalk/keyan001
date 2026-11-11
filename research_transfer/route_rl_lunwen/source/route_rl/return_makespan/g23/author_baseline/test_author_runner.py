#!/usr/bin/env python3
"""Engineering fixtures only; no official or new scientific maps are solved."""
from pathlib import Path
import copy
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import author_runner as runner


class AuthorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.work = Path(self.temporary.name)
        self.source = runner.source_root_default()
        self.scorer = runner.scorer_default()
        self.instance_path = self.work / "synthetic_noncontiguous.txt"
        self.instance_path.write_text("CUST_NO XCOORD YCOORD SERVICE_ENERGY SERVICE_TIME\n"
                                      "101 900 0 0.1 2\n"
                                      "709 0 0 0 0\n")
        self.instance = runner.validate_input(self.instance_path, self.source, self.scorer)
        self.raw = {"station_types": [1], "routes": [[[], [[101]]]],
                    "reference_reported_cost": 29.8, "reference_integrity_issues": []}

    def tearDown(self):
        self.temporary.cleanup()

    def audit(self, raw=None, latest=4.0):
        return runner.audit_raw(self.instance, self.raw if raw is None else raw,
                                self.source, self.scorer, latest)

    def test_noncontiguous_ids_complete_witness_and_two_scores(self):
        audit = self.audit(latest=4.0)
        self.assertTrue(audit["witness_passed"])
        self.assertEqual(audit["solution"]["routes"], [[[], [[101]]]])
        self.assertEqual(audit["return_score"]["M_return"], 4.0)
        self.assertAlmostEqual(audit["independent_audit"]["cost"], 29.8)

    def test_duplicate_is_retained_as_failure(self):
        raw = copy.deepcopy(self.raw)
        raw["routes"][0][1] = [[101, 101]]
        audit = self.audit(raw)
        self.assertFalse(audit["witness_passed"])
        self.assertIn("duplicate:101", audit["independent_audit"]["issues"])
        self.assertEqual(audit["solution"]["routes"][0][1], [[101, 101]])

    def test_source_cost_mismatch_blocks_anchor(self):
        raw = dict(self.raw, reference_reported_cost=29.7)
        self.assertIn("source_cost_mismatch", self.audit(raw)["audit_errors"])

    def test_source_integrity_issue_blocks_even_feasible_canonical_routes(self):
        raw = dict(self.raw, reference_integrity_issues=["base_endpoints:0:1"])
        audit = self.audit(raw)
        self.assertTrue(audit["independent_audit"]["feasible"])
        self.assertFalse(audit["witness_passed"])

    def test_source_clock_mismatch_blocks_anchor(self):
        self.assertIn("source_latest_time_mismatch", self.audit(latest=3.0)["audit_errors"])

    def test_missing_source_clock_blocks_anchor(self):
        self.assertIn("source_latest_time_missing", self.audit(latest=None)["audit_errors"])

    def test_large_drone_at_small_station_rejected(self):
        raw = dict(self.raw, routes=[[[[101]], []]])
        audit = self.audit(raw)
        self.assertFalse(audit["witness_passed"])
        self.assertIn("large_drone_at_small_station:0", audit["independent_audit"]["issues"])

    def test_nan_cost_rejected(self):
        with self.assertRaises(ValueError):
            self.audit(dict(self.raw, reference_reported_cost=float("nan")))

    def test_java_integer_id_syntax_enforced(self):
        self.instance_path.write_text(self.instance_path.read_text().replace("101 ", "101.0 "))
        with self.assertRaisesRegex(ValueError, "integer token"):
            runner.validate_input(self.instance_path, self.source, self.scorer)

    def test_java_signed_int32_id_range_enforced(self):
        self.instance_path.write_text(self.instance_path.read_text().replace("101 ", "2147483648 "))
        with self.assertRaisesRegex(ValueError, "signed int32"):
            runner.validate_input(self.instance_path, self.source, self.scorer)

    def test_command_preserves_paths_as_arguments_and_exact_source_profile(self):
        command = runner.command_for(Path("/jdk fixture/bin/java"), self.instance_path,
            9223372036854775807, self.work / "out space/reference.json", self.work / "build", "J1b")
        self.assertIn("-Drepro.seed=9223372036854775807", command)
        self.assertIn("-Drepro.seconds=0", command)
        self.assertIn("-Drepro.guard=true", command)
        self.assertEqual(command[-1], "test1.Main")
        self.assertEqual(command[-2], str((self.work / "build/J1b/classes").resolve()))
        self.assertTrue(any("out space" in value for value in command))
        with self.assertRaises(ValueError):
            runner.command_for(Path("java"), self.instance_path, 1 << 63,
                               self.work / "raw", self.work, "J1b")

    def test_jdk_executable_uses_windows_extension_only_on_windows(self):
        home = self.work / "jdk 17"
        self.assertEqual(runner.jdk_executable(home, "java", platform_name="nt").name, "java.exe")
        self.assertEqual(runner.jdk_executable(home, "javac", platform_name="nt").name, "javac.exe")
        self.assertEqual(runner.jdk_executable(home, "java", platform_name="posix").name, "java")
        with self.assertRaises(ValueError):
            runner.jdk_executable(home, "jar", platform_name="nt")

    def test_map_seed_is_prospective_and_long_compatible(self):
        seed = runner.seed_for_input(self.instance.sha256, "test-fixture-v1")
        self.assertEqual(seed, runner.seed_for_input(self.instance.sha256, "test-fixture-v1"))
        self.assertTrue(0 <= seed < 1 << 63)
        self.assertNotEqual(seed, runner.seed_for_input(self.instance.sha256, "test-fixture-v2"))

    def test_plan_cli_writes_exact_invocation_without_solving(self):
        destination = self.work / "plan with spaces"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = runner.main(["plan", "--profile", "J1b", "--instance", str(self.instance_path),
                "--seed", "1234567", "--java-home", "/opt/jdk17", "--build-dir", "/tmp/java-build",
                "--out", str(destination), "--timeout", "180"])
        plan = runner.read_json(destination / "PLAN.json")
        self.assertEqual(status, 0)
        self.assertFalse(plan["solver_executed"])
        self.assertEqual(plan["seed"], 1234567)
        self.assertEqual(plan["command"][0], str(runner.jdk_executable(Path("/opt/jdk17"), "java").resolve()))
        self.assertIn("-Drepro.instance=", " ".join(plan["command"]))
        self.assertEqual(plan["instance_sha256"], self.instance.sha256)

    def test_source_profile_exactly_matches_accepted_manifests(self):
        identities = {name: runner.profile_identity(self.source, name) for name in ("J1b", "J2b")}
        self.assertEqual(identities["J1b"]["parameters"]["local_iterations"], 100)
        self.assertEqual(identities["J2b"]["parameters"]["local_iterations"], 500)
        self.assertEqual(len(identities["J1b"]["source_hashes"]), 15)
        self.assertNotEqual(identities["J1b"]["source_hashes"]["Main.java"],
                            identities["J2b"]["source_hashes"]["Main.java"])

    def test_prepare_builds_only_a_hash_locked_copy(self):
        source_hashes_before = {path.name: runner.sha256(path) for path in
            sorted((self.source / "reference/java/J1b_source").glob("*.java"))}
        fake_home = self.work / "fake-jdk"
        (fake_home / "bin").mkdir(parents=True)
        java = runner.jdk_executable(fake_home, "java")
        javac = runner.jdk_executable(fake_home, "javac")
        java.write_text("synthetic java identity\n")
        javac.write_text("synthetic javac identity\n")
        java.chmod(0o755)
        javac.chmod(0o755)
        build = self.work / "isolated-build"
        version_calls = []
        compile_calls = []

        def fake_version(command, **kwargs):
            version_calls.append((command, kwargs))
            self.assertEqual(command[1:], ["-version"])
            self.assertEqual(kwargs, {"capture_output": True, "text": True, "timeout": 15})
            is_java = Path(command[0]) == java
            self.assertIn(Path(command[0]), (java, javac))
            return subprocess.CompletedProcess(command, 0,
                "" if is_java else "javac 17.0.99\n",
                'openjdk version "17.0.99"\n' if is_java else "")

        def fake_compile(command, *, cwd, stdout, stderr, text, encoding, errors):
            compile_calls.append((command, cwd))
            self.assertEqual(Path(command[0]), javac)
            self.assertEqual((stdout, stderr, text, encoding, errors),
                             (subprocess.PIPE, subprocess.PIPE, True, "utf-8", "replace"))
            class_dir = Path(command[command.index("-d") + 1])
            self.assertEqual(class_dir, (build / "J1b/classes").resolve())
            self.assertEqual(Path(cwd), (build / "J1b").resolve())

            class FakeChild:
                returncode = 0

                def communicate(self, timeout=None):
                    if timeout != 60.0:
                        raise AssertionError(f"unexpected compile timeout: {timeout}")
                    (class_dir / "test1").mkdir()
                    (class_dir / "test1/Main.class").write_bytes(b"synthetic class")
                    return "compile stdout\n", ""

                def kill(self):
                    raise AssertionError("unexpected compile timeout")

            return FakeChild()

        with patch.object(runner.subprocess, "run", side_effect=fake_version) as run_mock, \
             patch.object(runner.subprocess, "Popen", side_effect=fake_compile) as popen_mock:
            manifest = runner.prepare(self.source, "J1b", fake_home, build)
            runner.verify_build(self.source, "J1b", fake_home, build)
            self.assertEqual(run_mock.call_count, 6)
            self.assertEqual(popen_mock.call_count, 1)
        self.assertEqual(len(version_calls), 6)
        self.assertEqual(len(compile_calls), 1)
        self.assertEqual(manifest["status"], "ok")
        self.assertEqual(manifest["command"][0], str(javac.resolve()))
        self.assertTrue((build / "J1b/source_snapshot/Main.java").is_file())
        self.assertTrue((build / "J1b/classes/test1/Main.class").is_file())
        self.assertEqual(source_hashes_before, {path.name: runner.sha256(path) for path in
            sorted((self.source / "reference/java/J1b_source").glob("*.java"))})

    def test_timeout_reaps_process_and_retains_output_but_blocks_anchor(self):
        command = [sys.executable, "-c", "import time; print('synthetic_saved_witness', flush=True); time.sleep(5)"]
        process = runner.execute_process(command, self.work, .2)
        self.assertTrue(process["timed_out"])
        self.assertNotEqual(process["exit_code"], 0)
        self.assertIn("synthetic_saved_witness", process["stdout"])
        self.assertFalse(runner.anchor_eligible(process, self.audit()))

    def test_nonzero_exit_with_valid_witness_blocks_anchor(self):
        process = runner.execute_process([sys.executable, "-c", "print('synthetic_error'); raise SystemExit(7)"], self.work, 2)
        self.assertEqual(process["exit_code"], 7)
        self.assertFalse(runner.anchor_eligible(process, self.audit()))
        self.assertTrue(runner.anchor_eligible({"exit_code": 0, "timed_out": False}, self.audit()))
        self.assertFalse(runner.anchor_eligible({"exit_code": 0, "timed_out": False}, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
