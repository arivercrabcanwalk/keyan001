"""Experiment runner: one task = (instance, method, seed, budget).

Methods
-------
m0  frozen V6 TSALNS (paper reproduction engine, budget-limited outer loop)
m1  joint neighborhood + uniform fixed policy
m1b joint neighborhood + cyclic fixed policy
m2  joint neighborhood + adaptive weights
m3  joint neighborhood + bottleneck rule
m4  joint neighborhood + LinUCB bandit
m5  joint neighborhood + tabular Q-learning
m6  joint neighborhood + MLP-PPO (checkpoint required)

All methods share the same instance, seed, wall-clock budget and independent
evaluator.  Each task runs in its own process.
"""
import gzip
import hashlib
import json
import os
import time
import traceback
from pathlib import Path

from lrphsd.problem import read_instance
from lrphsd.evaluator import evaluate


def _controller(method, seed, model_path, deterministic=False):
    from carl.controllers import (FixedPolicy, CyclicPolicy, AdaptiveWeights,
                                  RuleController, LinUCB, QLearning, PPOController,
                                  DistributionPolicy, ScheduledPolicy)
    if method in ("m1", "fixed"):
        return FixedPolicy()
    if method in ("m1b", "cyclic"):
        return CyclicPolicy()
    if method in ("m1c", "dist"):
        return DistributionPolicy()
    if method in ("m1d", "scheduled"):
        return ScheduledPolicy()
    if method in ("m2", "adaptive"):
        return AdaptiveWeights()
    if method in ("m3", "rule"):
        return RuleController()
    if method in ("m4", "bandit"):
        return LinUCB()
    if method in ("m5", "q"):
        return QLearning()
    if method in ("m6", "m6det", "m6bc", "m6bcdet", "ppo") or method.startswith("m6_"):
        from carl.ppo import load_model
        model = load_model(model_path)
        use_deterministic = True if method in ("m6det", "m6bcdet") else deterministic
        return PPOController(model, training=False, deterministic=use_deterministic)
    raise ValueError(method)


ABLATIONS = {
    "m6_nojoint": {"families": (0, 1, 2)},
    "m6_nomask": {"mask_mode": "all"},
    "m6_zeroasg": {"zero_groups": ("assignment",)},
    "m6_zerodrone": {"zero_groups": ("drone",)},
    "m6_zerohist": {"zero_groups": ("history",)},
    "m6_int2": {"intensities": (0, 1, 2)},
    "m1d_nojoint": {"controller": "m1d", "families": (0, 1, 2)},
    "m2_nojoint": {"controller": "m2", "families": (0, 1, 2)},
    "m1d_noxchg": {"controller": "m1d", "cross_exchange": False},
    "m2_noxchg": {"controller": "m2", "cross_exchange": False},
    "m1_global_asg": {"controller": "m1", "repair_scope_mode": "global_assignment"},
    "m1d_global_asg": {"controller": "m1d", "repair_scope_mode": "global_assignment"},
    "m2_global_asg": {"controller": "m2", "repair_scope_mode": "global_assignment"},
    "m2_global_nojoint": {"controller": "m2", "repair_scope_mode": "global_assignment",
                          "families": (0, 1, 2)},
    "m3_global_asg": {"controller": "m3", "repair_scope_mode": "global_assignment"},
    "m4_global_asg": {"controller": "m4", "repair_scope_mode": "global_assignment"},
    "m5_global_asg": {"controller": "m5", "repair_scope_mode": "global_assignment"},
    "m6_local_scope": {"controller": "m6", "repair_scope_mode": "local"},
    "m6_global_asg": {"controller": "m6", "repair_scope_mode": "global_assignment"},
    "m6_global_nojoint": {"controller": "m6", "repair_scope_mode": "global_assignment",
                          "families": (0, 1, 2)},
    "m6_global_nomask": {"controller": "m6", "repair_scope_mode": "global_assignment",
                         "mask_mode": "all"},
    "m6_global_zeroasg": {"controller": "m6", "repair_scope_mode": "global_assignment",
                          "zero_groups": ("assignment",)},
    "m6_global_zerodrone": {"controller": "m6", "repair_scope_mode": "global_assignment",
                            "zero_groups": ("drone",)},
    "m6_global_zerohist": {"controller": "m6", "repair_scope_mode": "global_assignment",
                           "zero_groups": ("history",)},
    "m6_global_zeroglobal": {"controller": "m6", "repair_scope_mode": "global_assignment",
                             "zero_groups": ("global",)},
    "m6_global_nohighint": {"controller": "m6", "repair_scope_mode": "global_assignment",
                            "intensities": (0, 1)},
    "m1d_global_joint": {"controller": "m1d", "repair_scope_mode": "global_joint"},
    "m2_global_joint": {"controller": "m2", "repair_scope_mode": "global_joint"},
    "m1d_global_all": {"controller": "m1d", "repair_scope_mode": "global_assignment_joint"},
    "m2_global_all": {"controller": "m2", "repair_scope_mode": "global_assignment_joint"},
}


def task_identity(task):
    """Bind cache entries to inputs, configuration, model bytes and code bytes."""
    root = Path(__file__).resolve().parents[1]
    method = task["method"]
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    config = {k: v for k, v in task.items()
              if k not in ("overwrite", "outdir", "instance_path", "model_path")}
    config["instance_sha256"] = digest(task["instance_path"])
    config["model_sha256"] = digest(task["model_path"]) if task.get("model_path") else None
    ablation = ABLATIONS.get(method, {})
    config["resolved_controller"] = ablation.get("controller", method)
    config["resolved_repair_scope_mode"] = ablation.get("repair_scope_mode", "local")
    if method in ("m0", "v6", "m0p", "m0paper", "m0frozen"):
        if method == "m0paper":
            baseline_name = "paper_parameters.json"
        elif method in ("m0", "v6"):
            baseline_name = "research_budget.json"
        else:
            baseline_name = "frozen_v6.json"
        config["baseline_config_sha256"] = digest(root / "configs" / baseline_name)
    else:
        config["baseline_config_sha256"] = None
    code = {}
    for directory in ("carl", "lrphsd", "native", "scripts", "configs"):
        for path in sorted((root / directory).glob("*")):
            if path.is_file() and path.suffix in (".py", ".c", ".so", ".dylib", ".dll"):
                code[str(path.relative_to(root))] = digest(path)
    ref_root = root / "reference" / "java"
    for source_dir in ("official_source", "instrumented_source"):
        for source_path in sorted((ref_root / source_dir).glob("*.java")):
            code[str(source_path.relative_to(root))] = digest(source_path)
    lock_path = ref_root / "SOURCE_LOCK.json"
    if lock_path.exists():
        code[str(lock_path.relative_to(root))] = digest(lock_path)
    config["code_sha256"] = hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest()
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest(), config


def run_one(task):
    task_started = time.perf_counter()
    identity_seconds = instance_load_seconds = controller_load_seconds = 0.0
    solution_write_seconds = result_write_seconds = 0.0
    method = task["method"]
    instance = task["instance"]
    seed = int(task["seed"])
    seconds = float(task["seconds"])
    outdir = Path(task["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    tag = f"{instance}__{method}__s{seed}__l{float(task.get('lam', 0.0)):g}__r{float(task.get('reserve', 0.0)):g}"
    outfile = outdir / (tag + ".json")
    identity_start = time.perf_counter()
    identity, provenance = task_identity(task)
    identity_seconds = time.perf_counter() - identity_start
    if outfile.exists() and not task.get("overwrite"):
        cached = json.loads(outfile.read_text())
        sol_path = outdir / (tag + ".solution.json.gz")
        if (cached.get("task_identity") != identity or cached.get("status") != "ok"
                or not sol_path.exists()):
            raise ValueError(f"cache identity/status/solution mismatch: {outfile}; use a new output directory")
        with gzip.open(sol_path, "rt") as f:
            cached_solution = json.load(f)
        audit = evaluate(read_instance(task["instance_path"]), cached_solution)
        if not audit["feasible"] or abs(audit["cost"] - cached["cost"]) > 1e-7:
            raise ValueError(f"cached solution failed independent validation: {sol_path}")
        return {"status": "cached", "file": str(outfile), "method": method,
                "instance": instance, "seed": seed,
                "task_identity_seconds": identity_seconds,
                "end_to_end_seconds": time.perf_counter() - task_started}
    try:
        load_start = time.perf_counter()
        ins = read_instance(task["instance_path"])
        instance_load_seconds = time.perf_counter() - load_start
        ctrl = None
        abl = ABLATIONS.get(method, {})
        controller_start = time.perf_counter()
        if method not in ("m0", "v6", "m0p", "m0paper", "m0frozen"):
            controller_method = abl.get("controller", method)
            if controller_method in ("m6", "m6det", "m6bc", "m6bcdet", "ppo") or controller_method.startswith("m6_"):
                import torch
                torch.set_num_threads(1)
            ctrl = _controller(controller_method, seed, task.get("model_path"),
                               bool(task.get("deterministic", False)))
        controller_load_seconds = time.perf_counter() - controller_start
        t0 = time.perf_counter()
        if method in ("m0", "v6", "m0p", "m0paper", "m0frozen"):
            from lrphsd.tsalns_v6 import solve as v6solve, reset_engine
            reset_engine()
            if method == "m0paper":
                config_name = "paper_parameters.json"
            elif method in ("m0", "v6"):
                config_name = "research_budget.json"
            else:
                config_name = "frozen_v6.json"
            cfg = json.loads((Path(__file__).resolve().parents[1] / "configs" / config_name).read_text())
            cfg["strict_deadline"] = True
            if method == "m0p":
                cfg["outer_iterations"] = 500
            if "outer" in task:
                cfg["outer_iterations"] = int(task["outer"])
            sol, meta = v6solve(ins, seed=seed, seconds=seconds, config=cfg)
            eval0 = time.perf_counter()
            audit = evaluate(ins, sol)
            evaluation_seconds = time.perf_counter() - eval0
            result = {"solution": sol, "feasible": audit["feasible"],
                      "cost": audit["cost"], "initial_cost": meta.get("initial_objective"),
                      "outer_iterations_attempted": meta.get("outer_iterations_attempted"),
                      "termination_reason": meta.get("termination_reason"),
                      "budget_overrun_seconds": meta.get("budget_overrun_seconds"),
                      "elapsed_seconds": meta.get("elapsed_seconds"),
                      "solver_seconds": meta.get("elapsed_seconds"),
                      "initialization_seconds": meta.get("initialization_seconds"),
                      "search_seconds": meta.get("search_seconds"),
                      "finalization_seconds": meta.get("finalization_seconds"),
                      "precompute_seconds": meta.get("precompute_seconds"),
                      "budget_overrun_seconds": meta.get("budget_overrun_seconds"),
                      "evaluation_seconds": evaluation_seconds,
                      "steps": None, "audit_issues": audit["issues"][:5],
                      "meta": {"outer_iterations_attempted": meta.get("outer_iterations_attempted"),
                               "evaluations": meta.get("evaluations"),
                               "termination_reason": meta.get("termination_reason"),
                               "budget_overrun_seconds": meta.get("budget_overrun_seconds")}}
            result["anytime"] = meta.get("anytime", {})
            result["baseline_config"] = cfg
            reset_engine()
        else:
            from carl.search import solve as ca_solve
            res = ca_solve(ins, ctrl, seed=seed, seconds=seconds,
                           max_steps=int(task.get("max_steps", 500000)),
                           temp0_factor=float(task.get("temp0", 1.0)),
                           temp_end_factor=float(task.get("temp_end", 1e-3)),
                           zero_groups=tuple(abl.get("zero_groups", task.get("zero_groups", ()))),
                           families=tuple(abl.get("families", task.get("families", (0, 1, 2, 3)))),
                           intensities=tuple(abl.get("intensities", task.get("intensities", (0, 1, 2)))),
                           mask_mode=str(abl.get("mask_mode", task.get("mask_mode", "normal"))),
                           cross_exchange=bool(abl.get("cross_exchange", task.get("cross_exchange", True))),
                           repair_scope_mode=str(abl.get("repair_scope_mode", task.get("repair_scope_mode", "local"))),
                           lam=float(task.get("lam", 0.0)), reserve=float(task.get("reserve", 0.0)))
            result = {k: res[k] for k in ("solution", "feasible", "cost",
                                          "initial_cost", "elapsed_seconds",
                                          "solver_seconds", "initialization_seconds",
                                          "search_seconds", "finalization_seconds",
                                          "precompute_seconds", "budget_overrun_seconds",
                                          "evaluation_seconds", "steps", "counters", "history",
                                          "anytime", "controller", "config",
                                          "makespan", "objective", "lam", "mk_weight",
                                          "reserve", "archive")}
            result["audit_issues"] = res["audit"]["issues"][:5]
            result["fixed_cost"] = res["audit"]["fixed_cost"]
            result["operating_minutes"] = res["audit"]["operating_minutes"]
            result["repair_scope_mode"] = res["config"].get("repair_scope_mode", "local")
        solve_and_eval_seconds = time.perf_counter() - t0
        result["budget_overrun_seconds"] = max(
            0.0, float(result.get("solver_seconds") or solve_and_eval_seconds) - seconds)
        result.update({"method": method, "instance": instance, "seed": seed,
                       "seconds": seconds, "wall_seconds": solve_and_eval_seconds,
                       "solve_and_evaluate_seconds": solve_and_eval_seconds,
                       "task_identity_seconds": identity_seconds,
                       "instance_load_seconds": instance_load_seconds,
                       "controller_load_seconds": controller_load_seconds,
                       "instance_path": str(task["instance_path"]),
                       "status": "ok" if result["feasible"] else "invalid"})
        result["protocol"] = ("paper-parameters-on-v6" if method == "m0paper" else
                              "frozen-v6-code-profile" if method in ("m0frozen", "m0p") else
                              "research-budget")
        result["task_identity"] = identity
        result["provenance"] = provenance
        sol_file = outdir / (tag + ".solution.json.gz")
        solution_write_start = time.perf_counter()
        with gzip.open(sol_file, "wt") as f:
            json.dump(result["solution"], f)
        solution_write_seconds = time.perf_counter() - solution_write_start
        result["solution_write_seconds"] = solution_write_seconds
        result["end_to_end_seconds"] = time.perf_counter() - task_started
        payload = dict(result)
        payload.pop("solution", None)
        write_start = time.perf_counter()
        with open(outfile, "w") as f:
            json.dump(payload, f, indent=1, default=str)
        result_write_seconds = time.perf_counter() - write_start
        payload["result_json_write_seconds"] = result_write_seconds
        payload["end_to_end_seconds"] = time.perf_counter() - task_started
        with open(outfile, "w") as f:
            json.dump(payload, f, indent=1, default=str)
        return {"status": payload["status"], "file": str(outfile),
                "method": method, "instance": instance, "seed": seed,
                "cost": payload["cost"], "wall": solve_and_eval_seconds,
                "makespan": payload.get("makespan"), "lam": payload.get("lam", 0.0),
                "reserve": payload.get("reserve", 0.0)}
    except Exception as exc:  # pragma: no cover - recorded, never hidden
        err = {"status": "error", "method": method, "instance": instance,
               "seed": seed, "seconds": seconds, "error": repr(exc),
               "task_identity_seconds": identity_seconds,
               "instance_load_seconds": instance_load_seconds,
               "controller_load_seconds": controller_load_seconds,
               "end_to_end_seconds": time.perf_counter() - task_started,
               "traceback": traceback.format_exc()[-4000:]}
        with open(outdir / (tag + ".error.json"), "w") as f:
            json.dump(err, f, indent=1)
        return err
