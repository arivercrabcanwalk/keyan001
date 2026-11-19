import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import phase_driver as driver


class FakeExclusionIndex:
    def __init__(self, paths):
        self.paths = list(paths)

    def require_research_ready(self):
        return None

    def collisions(self, raw_hash, geometry_hash):
        return []


class FakeGenerator:
    class ExclusionIndex:
        @staticmethod
        def from_paths(paths):
            return FakeExclusionIndex(paths)

    def __init__(self, *, duplicate_second=False):
        self.calls = []
        self.duplicate_second = duplicate_second

    @staticmethod
    def default_exclusion_paths():
        return [Path("permanent.json"), Path("synthetic.json")]

    def generate_allocated_instance(self, sites, targets, *, namespace,
                                    partition, ordinal, exclusions):
        index = len(self.calls)
        self.calls.append((namespace, partition, ordinal, exclusions))
        text = f"fixture-{index}\n"
        raw = hashlib.sha256(text.encode()).hexdigest()
        geometry = hashlib.sha256(f"geometry-{index}\n".encode()).hexdigest()
        if self.duplicate_second and index == 1:
            raw = hashlib.sha256(b"fixture-0\n").hexdigest()
            geometry = hashlib.sha256(b"geometry-0\n").hexdigest()
            text = "fixture-0\n"
        return {"status": "generated", "failure_reason": None,
                "raw_sha256": raw,
                "canonical_geometry_sha256": geometry,
                "solver_input_text": text}


class FakeRunner:
    def __init__(self, *, duplicate_second=False):
        self.generator = FakeGenerator(duplicate_second=duplicate_second)

    @staticmethod
    def scenario(raw):
        return {"instance_sha256": raw}


class RegistrationTests(unittest.TestCase):
    def test_frozen_controls_are_nonrl_and_matrix_is_40_rows(self):
        self.assertEqual(driver.METHODS,
                         ("greedy", "beam", "strict", "annealed", "multineighborhood_v2"))
        self.assertEqual(driver.BUDGETS, (6, 12))
        self.assertEqual(len(driver.METHODS) * len(driver.BUDGETS) * 4, 40)
        self.assertNotIn("PPO", driver.METHODS)

    def test_registration_rejects_method_or_budget_drift(self):
        base = {
            "namespace": driver.NAMESPACE,
            "slots": [f"calibration_{i}" for i in range(1, 5)],
            "generator_allocations": driver.allocations(),
            "methods": list(driver.METHODS), "budgets_s": list(driver.BUDGETS),
            "seed": 103, "schema": "g3_nonrl_calibration_v1",
            "family": [3, 20], "partition": "calibration", "author_profile": "J1b",
            "author_timeout_s": 180, "author_seed_namespace": driver.NAMESPACE + ":J1b",
            "phase_wall_cap_s": 2160, "generation_wall_cap_s": 120,
            "parent_timeout_grace_s": 2, "packaging_reserve_s": .25,
            "scenario_rule": "fixed-global-square-and-wind-v1", "no_replacement": True,
            "training_calls": 0, "formal_maps": 0,
            "identity_exclusion_manifest": str(driver.EXPOSURE_MANIFEST),
            "identity_exclusion_manifest_sha256": driver.sha(driver.EXPOSURE_MANIFEST),
            "dependencies": {}, "external_dependencies": {}, "project_root": ".",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registration.json"
            path.write_text(json.dumps(base), encoding="utf-8")
            self.assertEqual(driver.validate_registration(path)["methods"], list(driver.METHODS))
            changed = dict(base, methods=["greedy", "PPO"])
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "method/budget"):
                driver.validate_registration(path)

    def test_generation_binds_union_and_retains_collision_without_replacement(self):
        runner = FakeRunner(duplicate_second=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            rows = driver.generate_four({"slots": [f"calibration_{i}" for i in range(1, 5)],
                                         "identity_exclusion_manifest": str(driver.EXPOSURE_MANIFEST)},
                                        out, runner)
            self.assertEqual(len(rows), 4)
            self.assertEqual(len(runner.generator.calls), 4)
            self.assertEqual(rows[0]["status"], "generated")
            self.assertEqual(rows[1]["status"], "generation_failed")
            self.assertEqual(rows[1]["reason"], "within_allocation_identity_collision")
            self.assertTrue(all(call[3].paths[-1] == driver.EXPOSURE_MANIFEST
                                for call in runner.generator.calls))

    def test_generation_budget_exhaustion_does_not_call_generator(self):
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output"
            rows = driver.generate_four({"slots": [f"calibration_{i}" for i in range(1, 5)],
                                         "identity_exclusion_manifest": str(driver.EXPOSURE_MANIFEST)},
                                        out, runner, remaining=lambda: 10)
            self.assertEqual([row["status"] for row in rows], ["budget_skipped"] * 4)
            self.assertEqual(runner.generator.calls, [])

    def test_prior_exposure_manifest_is_complete_and_unique(self):
        manifest = json.loads(driver.EXPOSURE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["record_count"], 32)
        self.assertEqual(len({row["raw_sha256"] for row in manifest["records"]}), 32)
        self.assertEqual(len({row["canonical_geometry_sha256"] for row in manifest["records"]}), 32)
        self.assertEqual(sum(source["records"] for source in manifest["sources"]), 32)

    def test_frozen_registration_inputs_match_package_layout_and_ledger(self):
        package = Path(driver.__file__).resolve().parent
        g24 = package.parent
        multi = g24 / "next_stage_protocol_sol_20261104/strong_control/multineighborhood_v2"
        self.assertTrue((multi / "route_annealing.py").is_file())
        self.assertTrue((multi / "runner_adapter.py").is_file())
        ledger = json.loads((package / "RESOURCE_ALLOCATION.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["new_calibration_proposals"], 4)
        self.assertEqual(ledger["new_author_runs"], 4)
        self.assertEqual(ledger["new_comparison_rows"], 40)
        self.assertEqual(ledger["phase_wall_cap_s"], 2160)


if __name__ == "__main__":
    unittest.main(verbosity=2)
