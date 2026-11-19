import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch


DRIVER_PATH = Path(__file__).with_name("run_station_g2.py")
SPEC = importlib.util.spec_from_file_location("station_g2_driver_under_test", DRIVER_PATH)
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


class DummyBudget:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FakeResult:
    def __init__(self, status, routes=None, minutes=10.0, station_type=2, target_ids=(1, 2)):
        self.status = status
        self.station_idx = 0
        self.station_type = station_type
        self.target_ids = tuple(target_ids)
        self.routes = copy.deepcopy(routes)
        self.operating_minutes_dp = minutes
        self.slot_target_ids = None
        self.slot_dp_minutes = None
        self.slot_energy_slack_min = None
        self.slot_duty_slack = None
        self.trip_metrics = None
        self.state_cells = 0
        self.transition_checks = 0
        self.elapsed_seconds = 0.0
        self.detail = None

    def as_dict(self):
        return {
            "status": self.status,
            "station_idx": self.station_idx,
            "station_type": self.station_type,
            "target_ids": list(self.target_ids),
            "routes": copy.deepcopy(self.routes),
            "operating_minutes_dp": self.operating_minutes_dp,
            "state_cells": self.state_cells,
            "transition_checks": self.transition_checks,
        }


def _fixture(tmp, name="synthetic"):
    instance_file = Path(tmp) / f"{name}.txt"
    instance_file.write_text("fixture input identity\n")
    instance_sha = _sha(instance_file)
    parent = {
        "schema_version": 1,
        "instance": name,
        "instance_sha256": instance_sha,
        "station_types": [2],
        "routes": [[[[1]], [[2]]]],
    }
    ins = SimpleNamespace(
        name=name,
        sha256=instance_sha,
        params=SimpleNamespace(time_cost=1.0),
        target_ids=(1, 2),
        stations=[SimpleNamespace(x=0.0, y=0.0)],
        nodes={1: SimpleNamespace(x=1.0, y=0.0), 2: SimpleNamespace(x=2.0, y=0.0)},
        radius=lambda kind: 10.0,
    )
    audit = {
        "feasible": True,
        "cost": 100.0,
        "fixed_cost": 90.0,
        "operating_minutes": 10.0,
        "details": [{"station": 0, "time_min": 10.0}],
        "issues": [],
    }
    return instance_file, ins, parent, audit


def _evaluate(ins, solution):
    routes = solution["routes"]
    if len(solution.get("station_types", [])) != 1 or len(routes) != 1:
        return {"feasible": False, "cost": None, "fixed_cost": 90.0, "operating_minutes": 0.0,
                "details": [], "issues": ["station_dimension"]}
    targets = [nid for slot in routes[0] for trip in slot for nid in trip]
    feasible = solution["station_types"] == [2] and sorted(targets) == [1, 2]
    return {"feasible": feasible, "cost": 100.0 if feasible else None,
            "fixed_cost": 90.0, "operating_minutes": 10.0 if feasible else None,
            "details": [{"station": 0, "time_min": 10.0}] if feasible else [],
            "issues": [] if feasible else ["invalid_fixture_solution"]}


def _archive_cells(directory, ins, parent, omit=None):
    directory.mkdir(parents=True, exist_ok=True)
    for budget in driver.CONFIG["archive_budgets"]:
        for seed in driver.CONFIG["archive_seeds"]:
            stem = f"{ins.name}__route_alns__s{seed}__b{budget}"
            if omit == stem:
                continue
            solution_path = directory / f"{stem}.solution.json.gz"
            solution_path.write_bytes(gzip.compress(json.dumps(parent).encode()))
            meta = {
                "status": "ok", "instance": ins.name, "instance_sha256": ins.sha256,
                "method": "route_alns", "solver_seed": seed, "budget_seconds": float(budget),
                "solution_sha256": _sha(solution_path), "task_identity": f"{ins.name}|route_alns|s{seed}|b{budget}",
                "final_cost": 100.0, "end_to_end_seconds": float(budget), "search_seconds": float(budget),
                "model_load_seconds": 0.0,
            }
            (directory / f"{stem}.json").write_text(json.dumps(meta))


class G2DriverSyntheticTests(unittest.TestCase):
    def test_rejected_reference_with_missing_cost_is_retained(self):
        _, ins, parent, parent_audit = _fixture(tempfile.mkdtemp())
        result = FakeResult("COMPLETE_JOINT_REFERENCE", parent["routes"][0])

        def reject(_ins, _solution):
            return {"feasible": False, "cost": None, "details": [], "issues": ["bad_witness"]}

        checked = driver.validate_reference(ins, parent, parent_audit, 0, result, reject, False)
        self.assertEqual(checked["status"], "NUMERICAL_OR_IMPLEMENTATION_UNRESOLVED")
        self.assertFalse(checked["integration_accepted"])
        self.assertIsNone(checked["complete_cost_dp_evaluator_residual"])
        self.assertEqual(checked["complete_trial_audit"]["issues"], ["bad_witness"])
        self.assertEqual(checked["routes"], parent["routes"][0])

    def test_fixed_owner_slot_change_is_rejected(self):
        _, ins, parent, parent_audit = _fixture(tempfile.mkdtemp())
        changed = [[[1, 2]], []]
        result = FakeResult("COMPLETE_FIXED_OWNER_REFERENCE", changed)
        checked = driver.validate_reference(ins, parent, parent_audit, 0, result, _evaluate, True)
        self.assertEqual(checked["status"], "NUMERICAL_OR_IMPLEMENTATION_UNRESOLVED")
        self.assertTrue(checked["complete_trial_audit"]["feasible"])
        self.assertNotIn("station_union_changed", checked["validation_violations"])
        self.assertIn("fixed_owner_changed", checked["validation_violations"])

    def test_archived_comparator_preserves_missing_cell_and_disables_best3(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, ins, parent, _ = _fixture(tmp)
            archive = Path(tmp) / "archive"
            missing = f"{ins.name}__route_alns__s102__b6"
            _archive_cells(archive, ins, parent, omit=missing)
            with patch.object(driver, "ARCHIVE", archive):
                rows, best = driver.archived_comparators(ins, parent, _evaluate(ins, parent), _evaluate)
            self.assertEqual(len(rows), 6)
            row = next(r for r in rows if r["seed"] == 102 and r["budget"] == 6)
            self.assertEqual(row["status"], "ARCHIVE_UNRESOLVED")
            self.assertTrue(row["issues"])
            self.assertEqual(best["6"]["status"], "ARCHIVE_UNRESOLVED")
            self.assertEqual(best["12"]["status"], "THREE_ARCHIVED_RUNS_NOT_SINGLE_BUDGET")

    def test_run_map_keeps_parent_routes_for_unresolved_station(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, ins, parent, parent_audit = _fixture(tmp)
            archive = Path(tmp) / "archive"
            _archive_cells(archive, ins, parent)
            out = Path(tmp) / "out"
            out.mkdir()
            expected_saved = {"maps": [{"map": ins.name, "canonical_solution": parent}]}
            original_read = driver.read
            canonical_path = driver.HERE.parent / "failure/G2_ALNS_GREEDY_PARENTS.json"

            def fake_read(path):
                if Path(path) == canonical_path:
                    return expected_saved
                return original_read(path)

            def fake_build(_ins):
                return copy.deepcopy(parent)

            calls = []

            def fake_solve(_ins, si, kind, ids, budget, fixed_slot_target_ids=None):
                calls.append((si, fixed_slot_target_ids))
                if fixed_slot_target_ids is None:
                    return FakeResult("UNRESOLVED_TRANSITION_LIMIT", None, None, kind, ids)
                return FakeResult("COMPLETE_FIXED_OWNER_REFERENCE", parent["routes"][0], 10.0, kind, ids)

            with patch.object(driver, "read", side_effect=fake_read), patch.object(driver, "ARCHIVE", archive):
                row = driver.run_map(
                    {"name": ins.name, "path": str(input_path), "sha256": ins.sha256}, out,
                    float("inf"), _evaluate, fake_build, lambda _p: ins, DummyBudget, fake_solve,
                )
            partial = json.loads((out / ins.name / "joint.solution.json").read_text())
            self.assertEqual(row["status"], "PARTIAL_FEASIBLE_INCUMBENT_WITH_UNRESOLVED_STATIONS")
            self.assertTrue(row["fixed_and_joint_feasible"])
            self.assertEqual(partial, parent)
            self.assertEqual(calls[0][1], {0: [1], 1: [2]})
            self.assertIsNone(calls[1][1])
            self.assertEqual(row["remaining_opportunity_upper_bound"],
                             "NOT_CERTIFIED; INCONCLUSIVE_FOR_UNRESOLVED_DOMAIN")

    def test_reconstructed_parent_must_match_saved_canonical_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, ins, parent, _ = _fixture(tmp)
            out = Path(tmp) / "out"
            out.mkdir()
            changed = copy.deepcopy(parent)
            changed["routes"][0][0][0] = [2]
            canonical_path = driver.HERE.parent / "failure/G2_ALNS_GREEDY_PARENTS.json"
            original_read = driver.read

            def fake_read(path):
                if Path(path) == canonical_path:
                    return {"maps": [{"map": ins.name, "canonical_solution": parent}]}
                return original_read(path)

            with patch.object(driver, "read", side_effect=fake_read):
                with self.assertRaisesRegex(RuntimeError, "differs from archived parent"):
                    driver.run_map(
                        {"name": ins.name, "path": str(input_path), "sha256": ins.sha256}, out,
                        float("inf"), _evaluate, lambda _ins: changed, lambda _p: ins,
                        DummyBudget, lambda *_a, **_k: self.fail("solver should not run"),
                    )

    def test_archived_comparator_preserves_solution_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, ins, parent, _ = _fixture(tmp)
            archive = Path(tmp) / "archive"
            _archive_cells(archive, ins, parent)
            stem = f"{ins.name}__route_alns__s101__b6"
            sp, mp = archive / f"{stem}.solution.json.gz", archive / f"{stem}.json"
            changed = copy.deepcopy(parent)
            changed["instance_sha256"] = "wrong-instance-sha"
            sp.write_bytes(gzip.compress(json.dumps(changed).encode()))
            meta = json.loads(mp.read_text())
            meta["solution_sha256"] = _sha(sp)
            mp.write_text(json.dumps(meta))
            with patch.object(driver, "ARCHIVE", archive):
                rows, best = driver.archived_comparators(ins, parent, _evaluate(ins, parent), _evaluate)
            cell = next(r for r in rows if r["budget"] == 6 and r["seed"] == 101)
            self.assertEqual(len(rows), 6)
            self.assertEqual(cell["status"], "ARCHIVE_UNRESOLVED")
            self.assertIn("solution_identity", cell["issues"])
            self.assertEqual(cell["archived_solution"], changed)
            self.assertEqual(best["6"]["status"], "ARCHIVE_UNRESOLVED")

    def test_archived_comparator_retains_infeasible_audit_with_null_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, ins, parent, _ = _fixture(tmp)
            archive = Path(tmp) / "archive"
            _archive_cells(archive, ins, parent)

            def rejecting_audit(_ins, _solution):
                return {"feasible": False, "cost": None, "details": [], "issues": ["synthetic_rejection"]}

            with patch.object(driver, "ARCHIVE", archive):
                rows, best = driver.archived_comparators(ins, parent, _evaluate(ins, parent), rejecting_audit)
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r["status"] == "ARCHIVE_UNRESOLVED" for r in rows))
            self.assertTrue(all(r["independent_audit"]["issues"] == ["synthetic_rejection"] for r in rows))
            self.assertTrue(all(r["archived_solution"] == parent for r in rows))
            self.assertEqual(best["6"]["status"], "ARCHIVE_UNRESOLVED")
            self.assertEqual(best["12"]["status"], "ARCHIVE_UNRESOLVED")

    def test_run_map_expired_batch_records_unattempted_without_solve(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path, ins, parent, _ = _fixture(tmp)
            out = Path(tmp) / "out"
            out.mkdir()
            archive = Path(tmp) / "archive"
            _archive_cells(archive, ins, parent)
            canonical_path = driver.HERE.parent / "failure/G2_ALNS_GREEDY_PARENTS.json"
            original_read = driver.read

            def fake_read(path):
                if Path(path) == canonical_path:
                    return {"maps": [{"map": ins.name, "canonical_solution": parent}]}
                return original_read(path)

            with patch.object(driver, "read", side_effect=fake_read), patch.object(driver, "ARCHIVE", archive):
                row = driver.run_map(
                    {"name": ins.name, "path": str(input_path), "sha256": ins.sha256}, out,
                    time.perf_counter() - 1.0, _evaluate, lambda _i: copy.deepcopy(parent), lambda _p: ins,
                    DummyBudget, lambda *_a, **_k: self.fail("solve must not run after deadline"),
                )
            stations = json.loads((out / ins.name / "stations.json").read_text())
            self.assertEqual(stations[0]["fixed_owner"]["status"], "UNATTEMPTED_BATCH_DEADLINE")
            self.assertEqual(stations[0]["joint"]["status"], "UNATTEMPTED_BATCH_DEADLINE")
            self.assertEqual(row["status"], "PARTIAL_FEASIBLE_INCUMBENT_WITH_UNRESOLVED_STATIONS")

    def test_reference_cost_residual_is_separate_from_feasibility(self):
        _, ins, parent, parent_audit = _fixture(tempfile.mkdtemp())
        result = FakeResult("COMPLETE_JOINT_REFERENCE", parent["routes"][0], 10.01)
        checked = driver.validate_reference(ins, parent, parent_audit, 0, result, _evaluate, False)
        self.assertTrue(checked["complete_trial_audit"]["feasible"])
        self.assertFalse(checked["integration_accepted"])
        self.assertIn("dp_evaluator_residual", checked["validation_violations"])
        self.assertNotIn("independent_evaluator_rejected", checked["validation_violations"])


if __name__ == "__main__":
    unittest.main()
