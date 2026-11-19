#!/usr/bin/env python3
"""Compare J1b Java operators with Python and native round-6 operators."""

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT
PROBE = HERE / "java" / "OperatorMatrixProbe.java"
BASELINE_OPS_PATH = ROOT / "pre_semfix" / "lrphsd" / "fidelity_ops_v5.py"
PATCHED_OPS_PATH = ROOT / "lrphsd" / "fidelity_ops_v5.py"
BASELINE_C_SOURCE = ROOT / "pre_semfix" / "native" / "r6_kernel.c"
PATCHED_C_SOURCE = ROOT / "native" / "r6_kernel.c"
sys.path.insert(0, str(PACKAGE))

from lrphsd.java_random import JavaRandom
from lrphsd.native_kernel import NativeEngine
from lrphsd.problem import Instance, Node, Parameters, empty_solution


class CountingJavaRandom(JavaRandom):
    def __init__(self, seed):
        super().__init__(seed)
        self.bit_calls = 0

    def bits(self, n):
        self.bit_calls += 1
        return super().bits(n)


def load_ops(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ops = load_ops(BASELINE_OPS_PATH, "baseline_fidelity_ops_v5")


def make_instance():
    xy = {
        1: (100, 100), 2: (300, 300), 3: (100, 300), 4: (300, 100),
        5: (500, 200), 6: (700, 100), 7: (800, 300), 8: (900, 100),
        9: (1100, 200), 10: (1200, 100), 11: (1300, 300), 12: (1400, 100),
        13: (1500, 200), 14: (600, 500), 15: (200, 0), 16: (900, 0),
    }
    targets = tuple(Node(i, *xy[i], 0.964 if i == 16 else 0.01,
                         598.0 if i == 16 else 2.0) for i in range(1, 17))
    stations = (Node(100, 0.0, 0.0, 0.0, 0.0), Node(101, 1000.0, 0.0, 0.0, 0.0))
    return Instance("operator_matrix", targets, stations, "operator-matrix-fixture", Parameters())


def make_repair_instance(fixture):
    base = make_instance()
    targets = list(base.targets)
    if fixture == "tie":
        tie_xy = {1: (100.0, 0.0), 2: (-100.0, 0.0), 4: (700.0, 200.0),
                  15: (0.0, 200.0)}
        targets = [Node(n.id, *tie_xy[n.id], n.energy, n.service) if n.id in tie_xy else n
                   for n in targets]
    return Instance("operator_matrix_repair_" + fixture, tuple(targets),
                    (Node(100, 0.0, 0.0, 0.0, 0.0),),
                    "operator-matrix-repair-" + fixture, Parameters())


def base_solution(ins):
    sol = empty_solution(ins, [2, 2])
    sol["routes"] = [
        [[[1, 2, 3, 4], [5]], [[6, 7]]],
        [[[8, 9], [10, 11]], [[12, 13]]],
    ]
    return sol


def repair_fixture(ins, fixture):
    if fixture == "tie":
        sol = empty_solution(ins, [2])
        sol["routes"] = [[[[1], [2]], [[4]]]]
        return sol, [15]
    if fixture == "boundary":
        sol = empty_solution(ins, [2])
        sol["routes"] = [[[[1]], []]]
        return sol, [16]
    if fixture == "boundary_multi":
        sol = empty_solution(ins, [2])
        sol["routes"] = [[[[1]], []]]
        return sol, [16, 14]
    sol = empty_solution(ins, [2])
    sol["routes"] = [[[[1, 2, 3], [4, 5]], [[6, 7]]]]
    return sol, [14]


def python_location(op, seed):
    types = [1, 2, 0, 1, 0]
    rng = CountingJavaRandom(seed)
    result = ops.location(types, rng, op)
    sentinel = rng.random().hex()
    return result, sentinel, rng


def python_local(ins, op, seed):
    rng = CountingJavaRandom(seed)
    result = ops.local_candidate(ins, base_solution(ins), op, rng)
    sentinel = rng.random().hex()
    return result, sentinel, rng


def python_destroy(ins, op, seed):
    rng = CountingJavaRandom(seed)
    source = base_solution(ins)
    result = ops.destroy_candidate(ins, source, op, rng)
    removed = sorted(set(n for s in source["routes"] for d in s for t in d for n in t) -
                     set(n for s in result["routes"] for d in s for t in d for n in t))
    sentinel = rng.random().hex()
    return result, removed, sentinel, rng


def native_destroy(ins, op, seed, lib):
    source = base_solution(ins)
    rng = CountingJavaRandom(seed)
    engine = NativeEngine(ins, str(lib))
    try:
        engine.load(0, source)
        removed, state_after, bit_calls = engine.destroy(0, 1, op, rng.seed)
        rng.seed = state_after
        result = engine.export(1)
        sentinel = rng.random().hex()
        return result, sorted(removed), sentinel, bit_calls
    finally:
        engine.lib.r6_free()


def python_repair(module, ins, fixture, op):
    sol, pending = repair_fixture(ins, fixture)
    module.prepare(ins)
    result = module.repair_candidate(ins, sol, pending, op)
    return result


def native_repair(ins, fixture, op, lib):
    sol, pending = repair_fixture(ins, fixture)
    engine = NativeEngine(ins, str(lib))
    try:
        engine.load(0, sol)
        engine.clone(0, 1)
        rc = engine.repair(0, op, pending)
        raw = engine.export(0)
        valid = engine.valid(0, True)
        rollback = not rc or not valid
        if rollback:
            engine.clone(1, 0)
        final = engine.export(0)
        return rc, raw, final, valid, rollback
    finally:
        engine.lib.r6_free()


def build_native_libraries(temp_dir):
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    if sys.platform == "darwin":
        platform_flags = ["-dynamiclib"]
    else:
        platform_flags = ["-fPIC", "-shared"]
    outputs = []
    for label, source in (("baseline", BASELINE_C_SOURCE), ("semfix", PATCHED_C_SOURCE)):
        output = Path(temp_dir) / f"libr6kernel_{label}{suffix}"
        subprocess.run(["cc", "-O2", *platform_flags, "-o", str(output), str(source), "-lm"], check=True)
        outputs.append(output)
    return outputs


def routes_of(value):
    return value["routes"] if isinstance(value, dict) else value


def same_hex_double(left, right):
    return float.fromhex(left) == float.fromhex(right)


def parse_remote(args):
    key = str(Path(args.ssh_key).expanduser())
    subprocess.run(["scp", "-P", str(args.port), "-i", key, "-o", "BatchMode=yes",
                    str(PROBE), f"{args.host}:<EXECUTION_PATH>"], check=True)
    command = (
        "set -e; "
        f"JDK={args.remote_jdk}; PKG={args.remote_pkg}; "
        f'OUT=<EXECUTION_PATH> mkdir -p "$OUT"; '
        '"$JDK/bin/javac" -encoding UTF-8 -d "$OUT" '
        '"$PKG"/reference/java/J1b_source/*.java <EXECUTION_PATH> '
        f'"$JDK/bin/java" -cp "$OUT" test1.OperatorMatrixProbe {args.seeds}'
    )
    result = subprocess.run(["ssh", "-p", str(args.port), "-i", key, "-o", "BatchMode=yes",
                             args.host, command], check=True, capture_output=True, text=True)
    rows = {}
    for line in result.stdout.splitlines():
        if not line.startswith("{"):
            continue
        import json
        row = json.loads(line)
        rows[(row["case"], row["seed"])] = row
    return rows


def compare_case(java, py_state, py_sentinel, rng, label, report):
    jstate = java["state"]
    state_match = (jstate.get("types") == py_state.get("station_types", jstate.get("types"))
                   and jstate["routes"] == routes_of(py_state))
    sentinel_match = same_hex_double(java["rng_after"], py_sentinel)
    report.append((label, state_match, sentinel_match, len(rng.draws), rng.bit_calls))
    return state_match and sentinel_match


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="root@<COMPUTE_ENDPOINT>")
    parser.add_argument("--port", type=int, default=<CONNECTION_PORT>)
    parser.add_argument("--ssh-key", default="<REMOVED_SSH_PATH>")
    parser.add_argument("--remote-jdk", default="<EXECUTION_PATH>")
    parser.add_argument("--remote-pkg", default="<EXECUTION_PATH>")
    parser.add_argument("--run-id", default="20261102a")
    parser.add_argument("--seeds", type=int, default=16)
    args = parser.parse_args()

    if not BASELINE_C_SOURCE.is_file() or not PATCHED_C_SOURCE.is_file():
        raise SystemExit("Both pre-semfix and semfix native C sources are required")
    native_build = tempfile.TemporaryDirectory(prefix="liu-operator-matrix-")
    baseline_c, patched_c = build_native_libraries(native_build.name)
    patched_ops = load_ops(PATCHED_OPS_PATH, "semfix_fidelity_ops_v5")
    ins = make_instance()
    ops.prepare(ins)
    java_rows = parse_remote(args)
    report = []
    all_ok = True

    for op in range(4):
        for seed in range(args.seeds):
            py, sentinel, rng = python_location(op, seed)
            row = java_rows[(f"location{op}", seed)]
            ok = compare_case(row, {"station_types": py, "routes": []}, sentinel, rng,
                              f"location{op}/s{seed}", report)
            all_ok &= ok

    for op in range(4):
        for seed in range(args.seeds):
            py, sentinel, rng = python_local(ins, op, seed)
            row = java_rows[(f"local{op}", seed)]
            ok = compare_case(row, py, sentinel, rng, f"local{op}/s{seed}", report)
            all_ok &= ok
    py, sentinel, rng = python_local(ins, 4, 0)
    row = java_rows[("local4", 0)]
    ok = compare_case(row, py, sentinel, rng, "local4/s0", report)
    all_ok &= ok

    for op in range(4):
        for seed in range(args.seeds):
            py, removed, sentinel, rng = python_destroy(ins, op, seed)
            row = java_rows[(f"destroy{op}", seed)]
            state_match = (row["state"]["routes"] == py["routes"]
                           and row["removed"] == removed)
            c, c_removed, c_sentinel, c_bits = native_destroy(ins, op, seed, baseline_c)
            state_match &= (row["state"]["routes"] == c["routes"]
                            and row["removed"] == c_removed)
            rng_match = (same_hex_double(row["rng_after"], sentinel)
                         and same_hex_double(row["rng_after"], c_sentinel))
            report.append((f"destroy{op}/s{seed}", state_match, rng_match,
                           len(rng.draws), f"pybits={rng.bit_calls},cbits={c_bits}"))
            all_ok &= state_match and rng_match

    baseline_raw_differences = []
    patched_raw_differences = []
    for op in range(4):
        for fixture in ("base", "tie", "boundary", "boundary_multi"):
            row = java_rows[(f"repair{op}_{fixture}", 0)]
            repair_ins = make_repair_instance(fixture)
            py = python_repair(ops, repair_ins, fixture, op)
            patched_py = python_repair(patched_ops, repair_ins, fixture, op)
            rc, c_raw, c_final, c_valid, c_rollback = native_repair(
                repair_ins, fixture, op, baseline_c)
            prc, pc_raw, pc_final, pc_valid, pc_rollback = native_repair(
                repair_ins, fixture, op, patched_c)
            expected = row["state"]["routes"]
            final_match = (expected == py["routes"] == patched_py["routes"]
                           == c_final["routes"] == pc_final["routes"])
            baseline_raw_match = expected == c_raw["routes"]
            patched_raw_match = expected == pc_raw["routes"]
            if not baseline_raw_match:
                baseline_raw_differences.append((op, fixture))
            if not patched_raw_match:
                patched_raw_differences.append((op, fixture))
            rollback_resolves_raw_delta = (
                (baseline_raw_match or (c_rollback and final_match))
                and (patched_raw_match or (pc_rollback and final_match)))
            rng_ok = same_hex_double(row["rng_after"], JavaRandom(0).random().hex())
            report.append((f"repair{op}/{fixture}", final_match and rollback_resolves_raw_delta,
                           rng_ok, 0,
                           f"baseline_raw_match={baseline_raw_match},baseline_rc={rc},valid={c_valid},"
                           f"rollback={c_rollback},patched_rc={prc},valid={pc_valid},"
                           f"patched_raw_match={patched_raw_match},rollback={pc_rollback}"))
            all_ok &= final_match and rollback_resolves_raw_delta
            all_ok &= rng_ok

    failures = [row for row in report if not row[1] or not row[2]]
    print(f"OPERATOR_MATRIX rows={len(report)} pass={len(report)-len(failures)} "
          f"fail={len(failures)} repair_raw_differences="
          f"baseline:{len(baseline_raw_differences)},patched:{len(patched_raw_differences)}")
    for category in ("location", "local", "destroy", "repair"):
        group = [row for row in report if "".join(
            ch for ch in row[0].split("/")[0] if not ch.isdigit()) == category]
        group_failures = [row for row in group if not row[1] or not row[2]]
        print(f"OPERATOR_GROUP {category} cases={len(group)} pass={len(group)-len(group_failures)} "
              f"fail={len(group_failures)}")
    for label, state, rng_match, api_draws, extra in report:
        if (not state or not rng_match or
                (isinstance(extra, str) and
                 ("baseline_raw_match=False" in extra or "patched_raw_match=False" in extra))):
            print(f"{label} state={state} rng={rng_match} api_draws={api_draws} {extra}")
    if failures or not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
