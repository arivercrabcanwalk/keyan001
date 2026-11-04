"""CA-RL-TSALNS search engine.

One engine, one candidate generator, one independent validator; controllers
only decide which macro action to try.  Simulated annealing decides acceptance
exactly as in the TSALNS reproduction (cost-difference Metropolis rule), and
the best solution is kept separately from the current one.

Budget semantics: the wall-clock budget covers initialisation, controller
inference, candidate generation, repair, guard and bookkeeping.  The
independent evaluator on the returned solution is run *after* the budget and
reported separately.
"""
import copy
import math
import random

import numpy as np
import time

from lrphsd import fidelity_ops_v5 as ops
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build as greedy_build

from .core import Coverage, Mirror, fixed_cost
from .kernel import CAEngine, reset_library
from .neighborhood import Context, apply_move, generate
from .state import History, action_mask, encode
from .actions import N_ACTIONS, N_OPERATORS, OPERATOR_FAMILY, action_universe_mask

import json as _json
from pathlib import Path as _Path
REWARD_COST_SCALE = 100.0
_REF = None


def reference_point(name):
    """Method-independent normalisation (C_ref, M_ref) per instance: Liu's
    TSALNS (500 iters) cost and bug-fixed makespan measured once. Instances
    without a reference fall back to None (solver uses its initial solution)."""
    global _REF
    if _REF is None:
        p = _Path(__file__).resolve().parents[1] / "configs" / "morl_reference.json"
        _REF = _json.loads(p.read_text()) if p.exists() else {}
    r = _REF.get(name)
    return (r["C_ref"], r["M_ref"]) if r else None


def makespan(eng, slot, types):
    """Bug-fixed makespan: max drone working time over open stations
    (SABS only ever has drone slot 1; the evaluator forbids slot 0 there)."""
    mk = 0.0
    for si, kind in enumerate(types):
        if not kind:
            continue
        st = eng.station_stats(slot, si)
        mk = max(mk, st[2], st[3])
    return mk


def bottleneck_share(eng, slot, types):
    times = []
    for si, kind in enumerate(types):
        if kind:
            st = eng.station_stats(slot, si)
            times.extend((st[2], st[3]) if kind == 2 else (st[3],))
    tot = sum(times)
    return max(times) / tot if tot > 0 else 0.0
REWARD_TIME_WEIGHT = 0.0
REWARD_BEST_BONUS = 0.02


def transition_reward(cost_before, cost_after, initial_cost, duration_seconds,
                      budget_seconds, best_updated):
    """Dense objective reward with the explicit runtime penalty ablated.

    Positive values reward an accepted reduction in the current incumbent,
    not only a global-best update. A separate bonus marks global-best updates.
    The elapsed-time reward term is disabled for this A6 ablation; elapsed-time
    semi-Markov discounting in PPO remains unchanged.
    """
    if initial_cost <= 0 or budget_seconds <= 0:
        raise ValueError("initial cost and budget must be positive")
    if duration_seconds < 0:
        raise ValueError("duration must be nonnegative")
    delta = REWARD_COST_SCALE * (cost_before - cost_after) / initial_cost
    time_cost = REWARD_TIME_WEIGHT * duration_seconds / budget_seconds
    best_bonus = REWARD_BEST_BONUS if best_updated else 0.0
    return float(delta - time_cost + best_bonus)


class Trace:
    def __init__(self, start, checkpoints=(0.25, 0.5, 0.75, 1.0)):
        self.start = start
        self.best = math.inf
        self.checkpoints = tuple(checkpoints)
        self.at = {}

    def tick(self, elapsed, best, budget):
        # A candidate becomes available at `elapsed`, never retroactively.
        previous = self.best
        self.best = min(self.best, best)
        if not budget:
            return
        for c in self.checkpoints:
            deadline = c * budget
            if c not in self.at and elapsed >= deadline:
                self.at[c] = self.best if elapsed == deadline else previous

    def anytime(self):
        return {str(c): (None if math.isinf(self.at[c]) else self.at[c])
                for c in self.checkpoints if c in self.at}


def _clone_solution(sol):
    return {"schema_version": sol.get("schema_version", 1),
            "instance": sol["instance"], "instance_sha256": sol["instance_sha256"],
            "station_types": list(sol["station_types"]),
            "routes": copy.deepcopy(sol["routes"])}


def solve(ins, controller, seed=0, seconds=6.0, max_steps=500000,
          init_solution=None, collect=False, trace_checkpoints=(0.25, 0.5, 0.75, 1.0),
          temp0_factor=1.0, temp_end_factor=1e-3, zero_groups=(),
          families=(0, 1, 2, 3), intensities=(0, 1, 2), mask_mode="normal",
          cross_exchange=True, repair_scope_mode="local", lam=0.0, reserve=0.0):
    """lam: preference weight on makespan. Search objective
    F = cost + lam * (C_ref / M_ref) * makespan (lam=0 -> original A6 objective).
    reserve: battery reserve r; search uses capacities B/(1+r), i.e. every trip
    stays feasible if flight+hover energy grow by a factor (1+r)."""
    nominal_ins = ins
    if reserve and reserve > 0:
        from dataclasses import replace as _dc_replace
        from lrphsd.problem import Instance
        p = ins.params
        dp = _dc_replace(p, small_battery=p.small_battery / (1 + reserve),
                         large_battery=p.large_battery / (1 + reserve))
        ins = Instance(ins.name, ins.targets, ins.stations, ins.sha256, dp)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("seconds must be finite and positive")
    if repair_scope_mode not in (
            "local", "global_assignment", "global_joint", "global_assignment_joint"):
        raise ValueError(f"unknown repair_scope_mode: {repair_scope_mode}")
    wall0 = time.perf_counter()
    ops.prepare(ins)
    reset_library()
    eng = CAEngine(ins)
    engine_ready = time.perf_counter()
    rng = random.Random(seed * 1000003 + 17)
    if init_solution is None:
        init_solution = greedy_build(ins)
    sol = _clone_solution(init_solution)
    eng.load(0, sol)
    audit0 = evaluate(ins, sol)
    if not audit0["feasible"] and reserve:
        # derated greedy build can fail only if a single-target trip exceeds
        # the derated battery; nothing to do then.
        raise ValueError("initial solution infeasible under reserve")
    if not audit0["feasible"]:
        raise ValueError("initial solution infeasible: %s" % audit0["issues"][:5])
    types = list(sol["station_types"])
    init_cost = audit0["cost"]
    init_mk = makespan(eng, 0, types)
    ref = reference_point(getattr(ins, "name", ""))
    mk_w = float(lam) * ((ref[0] / ref[1]) if ref else (init_cost / max(init_mk, 1e-9)))
    obj = lambda c, m: c + mk_w * m
    cur_mk = init_mk
    init_obj = obj(init_cost, init_mk)
    cur_obj = init_obj
    best_obj = init_obj
    cur_cost = init_cost
    best_cost = init_cost
    archive = [(init_cost, init_mk)]
    eng.clone(0, 2)
    coverage = Coverage(ins)
    mirror = Mirror(ins, sol)
    ctx = Context(ins, eng, mirror, coverage, rng, cross_exchange=cross_exchange)
    ctx.cost = cur_cost
    ctx.best_cost = best_cost
    ctx.route_cost = eng.cost(0)

    history = History()
    trace = Trace(wall0, trace_checkpoints)
    trace.tick(time.perf_counter() - wall0, best_cost, seconds)

    temperature0 = temp0_factor * init_obj
    temperature_end = temp_end_factor * init_obj
    stagnation = 0
    window = []
    counters = {"steps": 0, "moves": 0, "generated": 0, "feasible": 0,
                "accepted": 0, "improved": 0, "best_updates": 0,
                "changed": 0, "no_change": 0,
                "family_attempts": [0, 0, 0, 0], "family_feasible": [0, 0, 0, 0],
                "family_changed": [0, 0, 0, 0],
                "family_accepted": [0, 0, 0, 0], "family_improved": [0, 0, 0, 0],
                "action_counts": [0] * N_ACTIONS,
                "selected_operator_counts": [0] * N_OPERATORS,
                "operator_attempts": {}, "operator_feasible": {},
                "operator_changed": {}, "operator_no_change": {},
                "operator_accepted": {}, "operator_improved": {},
                "operator_best": {},
                "policy_seconds": 0.0, "decision_seconds": 0.0,
                "step_seconds": 0.0, "move_seconds": 0.0,
                "export_seconds": 0.0, "deadline_rejected": 0}
    controller.begin(ins, seed)
    initialization_done = time.perf_counter()
    initialization_seconds = initialization_done - wall0

    pending = None
    step = 0
    while step < max_steps:
        elapsed = time.perf_counter() - wall0
        if elapsed >= seconds:
            break
        frac = elapsed / seconds
        temperature = temperature0 * (temperature_end / temperature0) ** frac
        if stagnation > 300:
            temperature = max(temperature, 0.01 * init_obj)
        accept_rate = (sum(window[-100:]) / len(window[-100:])) if window else 0.0
        improve_rate = counters["improved"] / max(counters["accepted"], 1)
        t_step = time.perf_counter()
        feat = encode(ctx, history, init_cost, elapsed, seconds, temperature,
                      stagnation, accept_rate, improve_rate, step,
                      zero_groups=zero_groups,
                      pref=(float(lam), cur_mk / max(init_mk, 1e-9),
                            bottleneck_share(eng, 0, types)))
        mask = action_mask(ctx, families=families, intensities=intensities)
        if mask_mode == "all":
            # Disable structural feasibility pruning, but retain family and
            # supported-intensity restrictions for controlled mask ablations.
            mask = action_universe_mask(families=families, intensities=intensities)
        if not mask.any():
            break
        if pending is not None:
            # Bellman bootstrap must use legal actions in s_{t+1}, not s_t.
            controller.observe(pending[0], pending[1], pending[2], feat, False,
                               mask, pending[4])
        t_policy = time.perf_counter()
        action = controller.act(feat, mask, step)
        policy_elapsed = time.perf_counter() - t_policy
        decision_elapsed = time.perf_counter() - t_step
        if int(action) < 0 or int(action) >= N_ACTIONS or not mask[int(action)]:
            raise RuntimeError(f"controller selected masked/invalid action: {action}")
        operator, intensity = divmod(int(action), 3)
        family = OPERATOR_FAMILY[operator]
        t_move = time.perf_counter()
        move = generate(ctx, operator, intensity)
        operator_tag = move.tag if move is not None else f"no_candidate_{operator}"
        counters["selected_operator_counts"][operator] += 1
        counters["operator_attempts"][operator_tag] = counters["operator_attempts"].get(operator_tag, 0) + 1
        counters["generated"] += 1
        counters["family_attempts"][family] += 1
        counters["action_counts"][int(action)] += 1
        ok = False
        changed = False
        new_types = None
        new_cost = math.inf
        new_obj = math.inf
        new_mk = math.inf
        if move is not None:
            new_types = apply_move(
                eng, move, types, ins, repair_scope_mode=repair_scope_mode)
            if new_types is not None:
                ok = True
                changed = not eng.same(0, 1)
                if changed:
                    new_cost = eng.cost(1) + fixed_cost(ins, new_types)
                    new_mk = makespan(eng, 1, new_types) if mk_w > 0 else 0.0
                    new_obj = obj(new_cost, new_mk)
        counters["moves"] += 1
        cost_before = cur_cost
        obj_before = cur_obj
        best_before = best_cost
        accepted = False
        improved = False
        best_flag = 0
        if time.perf_counter() - wall0 >= seconds:
            counters["deadline_rejected"] += 1
            ok = False
        if ok:
            counters["feasible"] += 1
            counters["family_feasible"][family] += 1
            counters["operator_feasible"][operator_tag] = counters["operator_feasible"].get(operator_tag, 0) + 1
            if changed:
                counters["changed"] += 1
                counters["family_changed"][family] += 1
                counters["operator_changed"][operator_tag] = counters["operator_changed"].get(operator_tag, 0) + 1
                if new_obj < cur_obj or rng.random() < math.exp((cur_obj - new_obj) / max(temperature, 1e-9)):
                    accepted = True
            else:
                counters["no_change"] += 1
                counters["operator_no_change"][operator_tag] = counters["operator_no_change"].get(operator_tag, 0) + 1
        t_export = 0.0
        if accepted:
            eng.clone(1, 0)
            types = new_types
            cur_cost = new_cost
            cur_mk = new_mk if mk_w > 0 else makespan(eng, 0, types)
            cur_obj = new_obj
            improved = new_obj < obj_before
            if not any(c <= cur_cost and m <= cur_mk for c, m in archive):
                archive = [(c, m) for c, m in archive if not (cur_cost <= c and cur_mk <= m)]
                archive.append((cur_cost, cur_mk))
            if new_obj < best_obj:
                eng.clone(0, 2)
                best_obj = new_obj
                best_cost = new_cost
                best_flag = 1
                counters["best_updates"] += 1
            counters["accepted"] += 1
            counters["family_accepted"][family] += 1
            counters["operator_accepted"][operator_tag] = counters["operator_accepted"].get(operator_tag, 0) + 1
            if improved:
                counters["improved"] += 1
                counters["family_improved"][family] += 1
                counters["operator_improved"][operator_tag] = counters["operator_improved"].get(operator_tag, 0) + 1
            if best_flag:
                counters["operator_best"][operator_tag] = counters["operator_best"].get(operator_tag, 0) + 1
            te = time.perf_counter()
            sol = eng.export(0)
            mirror.update(sol)
            t_export = time.perf_counter() - te
            ctx = Context(ins, eng, mirror, coverage, rng, cross_exchange=cross_exchange)
            ctx.cost = cur_cost
            ctx.best_cost = best_cost
            ctx.route_cost = eng.cost(0)
        stagnation = 0 if best_flag else stagnation + 1
        window.append(1 if accepted else 0)
        if len(window) > 400:
            del window[:200]
        history.record(operator, int(ok), int(accepted), int(improved), best_flag)
        move_elapsed = time.perf_counter() - t_move
        step_elapsed = time.perf_counter() - t_step
        counters["policy_seconds"] += policy_elapsed
        counters["decision_seconds"] += decision_elapsed
        counters["step_seconds"] += step_elapsed
        counters["move_seconds"] += move_elapsed
        counters["export_seconds"] += t_export
        # Reward current-incumbent improvement, charge elapsed search time,
        # and distinguish a global-best update with a small explicit bonus.
        reward = transition_reward(obj_before, cur_obj, init_obj,
                                   step_elapsed, seconds, bool(best_flag))
        trace.tick(time.perf_counter() - wall0, best_obj, seconds)
        pending = (feat, action, reward, mask,
                   {"feasible": ok, "accepted": accepted, "improved": improved,
                    "best_updated": bool(best_flag),
                    "duration_seconds": step_elapsed})
        step += 1

    if pending is not None:
        controller.observe(pending[0], pending[1], pending[2], pending[0], True,
                           pending[3], pending[4])
    if collect:
        controller.end_episode()

    search_end = time.perf_counter()
    search_seconds = search_end - initialization_done
    finalization_start = time.perf_counter()
    final = eng.export(2)
    final_mk = makespan(eng, 2, final["station_types"])
    eng.free()
    finalization_seconds = time.perf_counter() - finalization_start
    solver_elapsed = time.perf_counter() - wall0
    trace.tick(solver_elapsed, best_cost, seconds)
    eval0 = time.perf_counter()
    audit = evaluate(nominal_ins, final)
    evaluation_elapsed = time.perf_counter() - eval0
    elapsed = time.perf_counter() - wall0
    return {
        "solution": final,
        "feasible": audit["feasible"],
        "cost": audit["cost"],
        "audit": audit,
        "initial_cost": init_cost,
        "makespan": final_mk, "objective": best_obj, "lam": float(lam),
        "mk_weight": mk_w, "reserve": float(reserve),
        "archive": sorted(archive),
        "elapsed_seconds": elapsed,
        "solver_seconds": solver_elapsed,
        "initialization_seconds": initialization_seconds,
        "precompute_seconds": engine_ready - wall0,
        "search_seconds": search_seconds,
        "finalization_seconds": finalization_seconds,
        "budget_overrun_seconds": max(0.0, solver_elapsed - seconds),
        "evaluation_seconds": evaluation_elapsed,
        "steps": step,
        "counters": counters,
        "history": history.rates(),
        "anytime": trace.anytime(),
        "controller": controller.name,
        "seed": seed,
        "budget": seconds,
        "termination_reason": "step_limit" if step >= max_steps else ("time_budget" if solver_elapsed >= seconds else "empty_action_set"),
        "config": {"max_steps": max_steps, "temperature0": temperature0,
                   "temperature_end": temperature_end,
                   "n_actions": N_ACTIONS, "n_operators": N_OPERATORS,
                   "repair_scope_mode": repair_scope_mode},
    }
