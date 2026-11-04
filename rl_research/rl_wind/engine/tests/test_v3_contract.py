import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lrphsd import fidelity_ops_v5 as ops
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from lrphsd.exact import solve_exact
from lrphsd.tsalns_v6 import solve as solve_v6, get_engine, reset_engine
from carl.core import Coverage, Mirror, fixed_cost
from carl.kernel import CAEngine
from carl.neighborhood import Context
from carl.state import FEATURE_NAMES, N_FEATURES, STATE_SCHEMA, ACTION_SCHEMA, History, encode

INST = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


def test_exact_certificates():
    cert_path = ROOT.parent / "audit_evidence" / "exact_certificates.json"
    certs = json.loads(cert_path.read_text())
    assert len(certs) == 10
    for cert in certs:
        ins = read_instance(INST / (cert["instance"] + ".txt"))
        sol, meta = solve_exact(ins)
        audit = evaluate(ins, sol)
        assert audit["feasible"], (cert["instance"], audit["issues"][:5])
        assert abs(audit["cost"] - cert["cost"]) < 1e-8
        assert abs(meta["optimal_objective"] - audit["cost"]) < 1e-8


def test_state_time_and_per_drone_energy_slack():
    ins = read_instance(INST / "5_35_1.txt")
    ops.prepare(ins)
    eng = CAEngine(ins)
    sol = build(ins)
    eng.load(0, sol)
    ctx = Context(ins, eng, Mirror(ins, sol), Coverage(ins), random.Random(3))
    cost = eng.cost(0) + fixed_cost(ins, sol["station_types"])
    ctx.cost = cost
    ctx.best_cost = cost
    ctx.route_cost = eng.cost(0)
    for si, kind in enumerate(sol["station_types"]):
        if not kind:
            continue
        stats = eng.station_stats(0, si)
        duration_slack = 1.0 - max(stats[2], stats[3]) / ins.duration(kind)
        assert abs(ctx.slack[si] - max(0.0, duration_slack)) < 1e-12
        assert abs(ctx.load[si] - max(stats[2], stats[3]) / ins.duration(kind)) < 1e-12
        for di in range(2):
            active = (kind == 2) or (kind == 1 and di == 1)
            if not active:
                continue
            cap = ins.capacity(di)
            trips = sol["routes"][si][di]
            expected = min((cap - ops.path_energy(ins, si, tr) for tr in trips), default=cap)
            actual = stats[7 + di]
            assert abs(actual - expected) < 1e-9, (si, di, actual, expected)
            stored = ctx.dslack0[si] if di == 0 else ctx.dslack1[si]
            assert abs(stored - expected) < 1e-9
    features = encode(ctx, History(), cost, 0.0, 6.0, 100.0, 0, 0.0, 0.0, 0)
    assert STATE_SCHEMA.startswith("carl-state-v4-")
    assert ACTION_SCHEMA.startswith("carl-action-v4-")
    assert len(FEATURE_NAMES) == N_FEATURES == len(features) == 75
    eng.free()


def test_v6_strict_deadline_and_anytime_initialization():
    ins = read_instance(INST / "3_10_1.txt")
    try:
        sol, meta = solve_v6(ins, seed=7, seconds=1e-6,
                             config={"outer_iterations": 20, "strict_deadline": True})
        audit = evaluate(ins, sol)
        assert audit["feasible"], audit["issues"][:5]
        assert meta["outer_iterations_attempted"] == 0
        assert meta["initialization_seconds"] >= 1e-6
        assert meta["search_seconds"] >= 0.0
        assert meta["budget_overrun_seconds"] > 0.0
        assert all(meta["anytime"].get(str(cp)) is None for cp in (.25, .5, .75, 1.0))
    finally:
        reset_engine()


def test_versioned_baseline_parameter_profiles():
    paper = json.loads((ROOT / "configs" / "paper_parameters.json").read_text())
    frozen = json.loads((ROOT / "configs" / "frozen_v6.json").read_text())
    research = json.loads((ROOT / "configs" / "research_budget.json").read_text())
    assert (paper["outer_iterations"], paper["local_iterations"], paper["alns_iterations"]) == (500, 500, 5000)
    assert (paper["weight_lower"], paper["weight_upper"]) == (0.1, 0.5)
    assert (paper["initial_temperature"], paper["cooling_rate"]) == (1000.0, 0.95)
    assert (frozen["outer_iterations"], frozen["local_iterations"], frozen["weight_upper"]) == (500, 100, 5.0)
    assert (research["outer_iterations"], research["local_iterations"], research["weight_upper"]) == (100000, 100, 5.0)


def test_engine_cache_parameter_identity():
    from dataclasses import replace
    path = INST / "5_35_1.txt"
    a = read_instance(path)
    b = read_instance(path, replace(a.params, time_cost=a.params.time_cost * 2))
    ops.prepare(a)
    sol = build(a)
    try:
        ea = get_engine(a)
        ea.load(0, sol)
        ca = ea.cost(0)
        eb = get_engine(b)
        eb.load(0, sol)
        cb = eb.cost(0)
        assert abs(cb - 2.0 * ca) < 1e-8
    finally:
        reset_engine()


if __name__ == "__main__":
    failures = 0
    total = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            total += 1
            try:
                fn()
                print("PASS", name, flush=True)
            except Exception as exc:
                failures += 1
                print("FAIL", name, repr(exc), flush=True)
    print("RESULT", total - failures, "/", total, flush=True)
    raise SystemExit(bool(failures))
