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

REWARD_COST_SCALE = 100.0
REWARD_TIME_WEIGHT = 0.25
REWARD_BEST_BONUS = 0.02


def transition_reward(cost_before, cost_after, initial_cost, duration_seconds,
                      budget_seconds, best_updated):
    """Dense objective reward with an explicit wall-clock cost.

    Positive values reward an accepted reduction in the current incumbent,
    not only a global-best update. Every decision pays a small elapsed-time
    penalty, including infeasible/no-change/rejected candidates. A separate
    bonus marks global-best updates. Time-aware discounting is additionally
    handled by semi-Markov GAE.
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
          cross_exchange=True, repair_scope_mode="local"):
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
    if not audit0["feasible"]:
        raise ValueError("initial solution infeasible: %s" % audit0["issues"][:5])
    types = list(sol["station_types"])
    init_cost = audit0["cost"]
    cur_cost = init_cost
    best_cost = init_cost
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

    temperature0 = temp0_factor * init_cost
    temperature_end = temp_end_factor * init_cost
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
            temperature = max(temperature, 0.01 * init_cost)
        accept_rate = (sum(window[-100:]) / len(window[-100:])) if window else 0.0
        improve_rate = counters["improved"] / max(counters["accepted"], 1)
        t_step = time.perf_counter()
        feat = encode(ctx, history, init_cost, elapsed, seconds, temperature,
                      stagnation, accept_rate, improve_rate, step,
                      zero_groups=zero_groups)
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
        if move is not None:
            new_types = apply_move(
                eng, move, types, ins, repair_scope_mode=repair_scope_mode)
            if new_types is not None:
                ok = True
                changed = not eng.same(0, 1)
                if changed:
                    new_cost = eng.cost(1) + fixed_cost(ins, new_types)
        counters["moves"] += 1
        cost_before = cur_cost
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
                if new_cost < cur_cost or rng.random() < math.exp((cur_cost - new_cost) / max(temperature, 1e-9)):
                    accepted = True
            else:
                counters["no_change"] += 1
                counters["operator_no_change"][operator_tag] = counters["operator_no_change"].get(operator_tag, 0) + 1
        t_export = 0.0
        if accepted:
            eng.clone(1, 0)
            types = new_types
            cur_cost = new_cost
            improved = new_cost < cost_before
            if new_cost < best_cost:
                eng.clone(0, 2)
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
        reward = transition_reward(cost_before, cur_cost, init_cost,
                                   step_elapsed, seconds, bool(best_flag))
        trace.tick(time.perf_counter() - wall0, best_cost, seconds)
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
    eng.free()
    finalization_seconds = time.perf_counter() - finalization_start
    solver_elapsed = time.perf_counter() - wall0
    trace.tick(solver_elapsed, best_cost, seconds)
    eval0 = time.perf_counter()
    audit = evaluate(ins, final)
    evaluation_elapsed = time.perf_counter() - eval0
    elapsed = time.perf_counter() - wall0
    return {
        "solution": final,
        "feasible": audit["feasible"],
        "cost": audit["cost"],
        "audit": audit,
        "initial_cost": init_cost,
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
