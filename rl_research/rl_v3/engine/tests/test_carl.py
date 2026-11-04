"""Correctness tests for the CA-RL engine and joint neighborhoods.

Run on the server with:
    /opt/conda/bin/python -B -m pytest -q tests/test_carl.py
or without pytest:
    /opt/conda/bin/python -B tests/test_carl.py
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lrphsd import fidelity_ops_v5 as ops
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build as greedy_build
from lrphsd.problem import read_instance

from carl.core import Coverage, Mirror, fixed_cost
from carl.kernel import CAEngine
from carl.neighborhood import Context, apply_move, generate
from carl.search import solve
from carl.controllers import FixedPolicy

INST = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


def _instance(name="5_35_1"):
    ins = read_instance(INST / (name + ".txt"))
    ops.prepare(ins)
    return ins


def test_kernel_cost_matches_evaluator():
    ins = _instance()
    eng = CAEngine(ins)
    sol = greedy_build(ins)
    eng.load(0, sol)
    got = eng.cost(0) + fixed_cost(ins, sol["station_types"])
    ref = evaluate(ins, sol)["cost"]
    assert abs(got - ref) < 1e-9, (got, ref)
    eng.free()


def test_remove_ids_preserves_other_targets():
    ins = _instance()
    eng = CAEngine(ins)
    sol = greedy_build(ins)
    eng.load(0, sol)
    ids = list(ins.target_ids)[:3]
    import ctypes
    before = evaluate(ins, sol)
    assert eng.remove_ids(0, ids) == 3
    out = eng.export(0)
    remaining = {n for st in out["routes"] for d in st for tr in d for n in tr}
    assert remaining == set(ins.target_ids) - set(ids)
    assert not eng.complete(0)
    # repair back with a global mask must restore completeness
    assert eng.repair_scoped(0, 0, ids, 0, 0, 1, 1) == 1
    assert eng.complete(0)
    after = evaluate(ins, eng.export(0))
    assert after["feasible"], after["issues"][:3]
    eng.free()


def test_masked_repair_respects_station_scope():
    ins = _instance()
    eng = CAEngine(ins)
    sol = greedy_build(ins)
    eng.load(0, sol)
    src = sol["station_types"].index(2)
    other = [i for i, k in enumerate(sol["station_types"]) if k == 2 and i != src][0]
    ids = [n for n in ins.target_ids if ins.dist[ins.stations[other].id, n] <= ins.params.large_radius][:2]
    if not ids:
        eng.free()
        return
    # remove them, then force repair only at `other`
    assert eng.remove_ids(0, ids) == len(ids)
    assert eng.repair_scoped(0, 0, ids, 1 << other, 0, 1, 1) == 1
    out = eng.export(0)
    placed = {n for d in out["routes"][other] for tr in d for n in tr}
    assert set(ids) <= placed
    eng.free()


def test_two_opt_non_increasing_distance():
    ins = _instance()
    eng = CAEngine(ins)
    sol = greedy_build(ins)
    eng.load(0, sol)
    changed = 0
    for si, st in enumerate(sol["routes"]):
        for di, trips in enumerate(st):
            for ti, trip in enumerate(trips):
                if len(trip) >= 3:
                    before = _trip_len(ins, sol["station_types"][si], ins.stations[si].id, trip)
                    eng.two_opt(0, si, di, ti)
                    out = eng.export(0)
                    after = _trip_len(ins, out["station_types"][si], ins.stations[si].id,
                                      out["routes"][si][di][ti])
                    assert after <= before + 1e-9
                    changed += 1
    assert changed >= 0
    eng.free()


def _trip_len(ins, kind, depot, trip):
    if not trip:
        return 0.0
    total = ins.dist[depot, trip[0]] + ins.dist[trip[-1], depot]
    for a, b in zip(trip, trip[1:]):
        total += ins.dist[a, b]
    return total


def test_every_operator_generates_feasible_candidates():
    from carl.actions import N_OPERATORS, OPERATOR_FAMILY
    from carl.neighborhood import operator_available
    ins = _instance()
    rng = random.Random(11)
    eng = CAEngine(ins)
    sol = greedy_build(ins)
    eng.load(0, sol)
    cov = Coverage(ins)
    mir = Mirror(ins, sol)
    ctx = Context(ins, eng, mir, cov, rng)
    ok = [0] * N_OPERATORS
    tried = [0] * N_OPERATORS
    for operator in range(N_OPERATORS):
        if not operator_available(ctx, operator):
            continue
        for i in range(60):
            intensity = 0 if operator == 8 else i % 3
            mv = generate(ctx, operator, intensity)
            tried[operator] += 1
            if mv is None:
                continue
            assert mv.family == OPERATOR_FAMILY[operator]
            types = apply_move(eng, mv, list(mir.types), ins)
            if types is None:
                continue
            audit = evaluate(ins, eng.export(1))
            assert audit["feasible"], (operator, mv.tag, audit["issues"][:5])
            ok[operator] += 1
    family_ok = [sum(ok[i] for i, family in enumerate(OPERATOR_FAMILY) if family == f)
                 for f in range(4)]
    print("feasible candidates per operator:", ok, "family totals:", family_ok)
    assert all(x > 0 for x in family_ok), (ok, family_ok)
    eng.free()


def test_solution_is_feasible_and_cost_consistent():
    ins = _instance()
    r = solve(ins, FixedPolicy(), seed=3, seconds=1.0, max_steps=400)
    assert r["feasible"], r["audit"]["issues"][:5]
    assert abs(r["cost"] - evaluate(ins, r["solution"])["cost"]) < 1e-9
    assert r["cost"] <= r["initial_cost"] + 1e-9


def test_deterministic_with_fixed_steps():
    ins = _instance("3_20_1")
    a = solve(ins, FixedPolicy(), seed=5, seconds=1e9, max_steps=150)
    b = solve(ins, FixedPolicy(), seed=5, seconds=1e9, max_steps=150)
    assert abs(a["cost"] - b["cost"]) < 1e-12
    assert a["steps"] == b["steps"] == 150


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:
                failures += 1
                print("FAIL", name, repr(exc))
    raise SystemExit(1 if failures else 0)
