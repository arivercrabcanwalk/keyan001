import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "reviewer_package"
sys.path.insert(0, str(PACKAGE))

from lrphsd import fidelity_ops_v5 as baseline_ops
from lrphsd.evaluator import evaluate
from lrphsd.native_kernel import NativeEngine
from lrphsd.problem import Instance, Node, Parameters, empty_solution

PATCHED_OPS_PATH = Path(__file__).resolve().parents[1] / "patch" / "fidelity_ops_v5.py"
LIB_SUFFIX = ".dylib" if sys.platform == "darwin" else ".so"
BASELINE_C = Path(__file__).resolve().parents[1] / "patch" / f"libr6kernel_baseline{LIB_SUFFIX}"
PATCHED_C = Path(__file__).resolve().parents[1] / "patch" / f"libr6kernel_patched{LIB_SUFFIX}"


def load_patched_ops():
    spec = importlib.util.spec_from_file_location("differential_fidelity_ops_v5", PATCHED_OPS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(kind=2, energy=0.01):
    station = Node(10, 0.0, 0.0, 0.0, 0.0)
    target = Node(1, 100.0, 0.0, energy, 2.0)
    ins = Instance("empty_station_repair", (target,), (station,), "fixture-sha256", Parameters())
    solution = empty_solution(ins, [kind])
    return ins, solution, target.id


def python_repair(module, ins, sol, target, op):
    module.prepare(ins)
    return module.repair_candidate(ins, sol, [target], op)


def native_repair(lib_path, ins, sol, target, op):
    engine = NativeEngine(ins, str(lib_path))
    try:
        engine.load(0, sol)
        rc = engine.repair(0, op, [target])
        result = engine.export(0)
        return rc, result
    finally:
        engine.lib.r6_free()


def j1b_storage_guard_valid(sol):
    return all(kind != 1 or not station[0]
               for kind, station in zip(sol["station_types"], sol["routes"]))


class EmptyStationRepairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patched_ops = load_patched_ops()
        if not BASELINE_C.is_file() or not PATCHED_C.is_file():
            raise RuntimeError("Compile baseline and patched C libraries; see README.md")

    def test_ops_2_and_3_match_java_empty_receiver(self):
        for op in (2, 3):
            with self.subTest(op=op):
                ins, sol, target = fixture(kind=2)

                py_before = python_repair(baseline_ops, ins, sol, target, op)
                self.assertEqual(py_before["routes"], [[[], []]])
                self.assertFalse(evaluate(ins, py_before)["feasible"])

                rc_before, c_before = native_repair(BASELINE_C, ins, sol, target, op)
                self.assertEqual(rc_before, 0)
                self.assertEqual(c_before["routes"], [[[], []]])
                self.assertFalse(evaluate(ins, c_before)["feasible"])

                py_after = python_repair(self.patched_ops, ins, sol, target, op)
                self.assertEqual(py_after["routes"], [[[[1]], []]])
                self.assertTrue(evaluate(ins, py_after)["feasible"])

                rc_after, c_after = native_repair(PATCHED_C, ins, sol, target, op)
                self.assertEqual(rc_after, 1)
                self.assertEqual(c_after["routes"], [[[[1]], []]])
                self.assertTrue(evaluate(ins, c_after)["feasible"])

    def test_infeasible_singleton_rolls_back_in_all_versions(self):
        for op in (2, 3):
            with self.subTest(op=op):
                ins, sol, target = fixture(kind=2, energy=2.0)
                for module in (baseline_ops, self.patched_ops):
                    self.assertEqual(python_repair(module, ins, sol, target, op)["routes"], [[[], []]])
                for lib_path in (BASELINE_C, PATCHED_C):
                    rc, result = native_repair(lib_path, ins, sol, target, op)
                    self.assertEqual(rc, 0)
                    self.assertEqual(result["routes"], [[[], []]])

    def test_empty_sabs_slot_is_a_distinct_source_guard_case(self):
        ins, sol, target = fixture(kind=1)
        repaired = python_repair(self.patched_ops, ins, sol, target, 3)
        self.assertEqual(repaired["routes"], [[[[1]], []]])
        self.assertTrue(evaluate(ins, self.patched_ops.physical(repaired))["feasible"])
        # J1b Round4Guard rejects SABS slot 0; this test must not mislabel that
        # storage-profile diagnostic as a DABS receiver mismatch.
        self.assertFalse(j1b_storage_guard_valid(repaired))

    def test_op0_invalid_first_pending_rolls_back_whole_native_candidate(self):
        stations = (Node(10, 0.0, 0.0, 0.0, 0.0),
                    Node(20, 1000.0, 0.0, 0.0, 0.0))
        targets = (Node(1, 100.0, 0.0, 0.90, 2.0),
                   Node(2, 50.0, 0.0, 0.12, 479.0),
                   Node(3, 1000.0, 0.0, 0.31, 1.0),
                   Node(4, 1000.0, 0.0, 0.01, 1.0))
        ins = Instance("nearest_multi_pending_rollback", targets, stations,
                       "nearest-multi-pending-sha256", Parameters())
        sol = empty_solution(ins, [1, 2])
        sol["routes"] = [[[], [[2]]], [[[3]], []]]
        pending = [1, 4]

        # Run both pending targets in order, as in Java/C. The first target's
        # nearest fallback violates the small station's energy/time limits;
        # the later target can be routed at the large station, but final
        # validation must roll back the whole repair to the destroyed input.
        baseline_ops.prepare(ins)
        python_result = baseline_ops.repair_candidate(ins, sol, pending, 0)
        self.assertIs(python_result, sol)
        self.assertEqual(python_result["routes"], sol["routes"])

        engine = NativeEngine(ins, str(PATCHED_C))
        try:
            engine.load(0, sol)
            engine.clone(0, 3)  # Destroyed-state snapshot, matching tsalns_v6.
            engine.clone(0, 1)
            rc = engine.repair(1, 0, pending)
            direct = engine.export(1)
            self.assertEqual(rc, 1)
            self.assertTrue(engine.complete(1))
            self.assertFalse(engine.valid(1, True))

            # tsalns_v6 restores the complete pre-repair snapshot when the
            # native candidate fails r6_valid; no partial pending repair leaks.
            engine.clone(3, 1)
            self.assertEqual(engine.export(1)["routes"], sol["routes"])
            self.assertEqual(direct["routes"][0][1], [[2], [1]])
            self.assertEqual(sorted(n for station in direct["routes"]
                                    for drone in station for trip in drone
                                    for n in trip), [1, 2, 3, 4])
        finally:
            engine.lib.r6_free()


if __name__ == "__main__":
    unittest.main(verbosity=2)
