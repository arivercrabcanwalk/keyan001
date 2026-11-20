"""Exploratory dynamic emergency routes; generated inputs, no wind.

Usage: python -m rlcore.explore_emergency --out ABS --seed 0 --device cpu --profile quick
This runnable research release compares transparent non-learning controls,
frozen behavior cloning and genuine on-policy REINFORCE. It supplies no claim of
novelty, author-baseline reproduction, strongest-baseline status or superiority.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import torch

from .agent import LEARNING_SCHEMA
from .common import seed_all
from .event_learning import (TensorRoutePolicy, collect_bc, fit_bc, parameter_sha,
                             rollout, train_pg)
from .explore_emergency_inputs import CORPUS_SEED, PROFILES, build_inputs, canonical_sha, make_env
from .model import Policy
from .policies import A1, Greedy, Reopt

METHODS = ("STATIC_FCFS", "EDF_NEAREST", "ROLLING_REOPT_CUSTOM", "BC_FROZEN", "PG_FINAL")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    os.replace(temporary, path)


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False)+"\n")
        stream.flush()


def summarize(rows):
    methods = {}
    for method in METHODS:
        group = [row for row in rows if row["method"] == method]
        completed = [row["metrics"] for row in group if row["status"] == "completed"]
        totals = {field: sum(row["metrics"].get(field, 0) for row in group)
                  for field in ("routine_total", "routine_done", "n_urgent", "urgent_done",
                                "high_total", "high_on_time", "norm_total", "norm_on_time",
                                "response_observed", "response_missing", "failed", "return_failures")}
        def ratio(numerator, denominator):
            return totals[numerator]/totals[denominator] if totals[denominator] else None
        response = [task["arrival"]-task["release"] for result in completed
                    for task in result["emergency_records"] if task["arrival"] is not None]
        censored = [((task["arrival"] if task["arrival"] is not None else 600.0)-task["release"])
                    for row in group for task in row["metrics"]["emergency_records"]]
        methods[method] = dict(episodes=len(group), completed_episodes=len(completed),
            error_episodes=len(group)-len(completed), **totals,
            routine_completion=ratio("routine_done", "routine_total"),
            urgent_completion=ratio("urgent_done", "n_urgent"),
            high_on_time_rate=ratio("high_on_time", "high_total"),
            normal_on_time_rate=ratio("norm_on_time", "norm_total"),
            response_observed_mean=float(np.mean(response)) if response else None,
            response_observed_p95=float(np.percentile(response, 95)) if response else None,
            response_censored_mean=float(np.mean(censored)) if censored else None,
            strict_rate=sum(result.get("complete_strict", 0) for result in completed)/len(group) if group else None,
            return_failure_rate=sum(row["metrics"].get("return_failure", 1) for row in group)/len(group) if group else None,
            mean_J_completed=float(np.mean([result["J"] for result in completed])) if completed else None,
            mean_cost_completed=float(np.mean([result["cost"] for result in completed])) if completed else None,
            mean_M_return_returned=float(np.mean([result["M_return"] for result in completed
                                                  if result["M_return"] is not None]))
                if any(result["M_return"] is not None for result in completed) else None)
    pairs = []
    for case_id in sorted({row["case_id"] for row in rows}):
        cell = {row["method"]: row for row in rows if row["case_id"] == case_id}
        if set(cell) != set(METHODS):
            raise ValueError("missing method from frozen same-day matrix")
        if len({row["input_sha256"] for row in cell.values()}) != 1:
            raise ValueError("paired methods received different inputs")
        for reference in METHODS[:-1]:
            policy, baseline = cell["PG_FINAL"], cell[reference]
            valid = policy["status"] == baseline["status"] == "completed"
            pairs.append(dict(case_id=case_id, reference=reference, paired_complete=valid,
                delta_J=policy["metrics"]["J"]-baseline["metrics"]["J"] if valid else None,
                delta_routine_done=policy["metrics"]["routine_done"]-baseline["metrics"]["routine_done"],
                delta_urgent_done=policy["metrics"]["urgent_done"]-baseline["metrics"]["urgent_done"]))
    return dict(methods=methods, paired_pg_minus_reference=pairs,
                error_policy="all_attempts_retained_with_original_task_denominators; unknown cost excluded explicitly",
                response_policy="observed_arrival_response_and_missing_counts_plus_day_end_censoring; no_zero_fill",
                selection="final_PG_checkpoint_fixed_before_evaluation; no_evaluation_selection")


def _checkpoint(path, model, arch, stage, seed, corpus_seed, input_sha256, optimizer_steps):
    torch.save(dict(model=model.state_dict(), arch=arch, feat_ablate="none", base="none",
                    learning_schema=LEARNING_SCHEMA, stage=stage, optimizer_seed=seed,
                    corpus_seed=corpus_seed, corpus_sha256=input_sha256,
                    optimizer_steps=optimizer_steps, parameter_sha256=parameter_sha(model)), path)


def run(args):
    folder = Path(args.out).expanduser()
    if not folder.is_absolute():
        raise ValueError("--out must be an absolute path")
    folder.mkdir(parents=True, exist_ok=False)
    folder = folder.resolve()
    started = time.perf_counter()
    manifest = dict(schema="emergency_exploratory_release_v1", status="running",
        experiment="B_dynamic_emergency_no_wind", optimizer_seed=args.seed,
        corpus_seed=args.corpus_seed, profile=args.profile, device=args.device,
        methods=list(METHODS), author_baseline=False, formal=False,
        action_space="released_TARGET_or_RETURN_or_WAIT; no_operator_selection",
        training_objective="Env.J_failure_penalized_author_cost_plus_arrival_lateness",
        bc_teacher="EDF_NEAREST_on_training_maps_and_events_only",
        nonlearning_sources=dict(STATIC_FCFS="manual_synthetic_singleton_plan_plus_station_FCFS",
            EDF_NEAREST="myopic_released_urgent_EDF_else_min_predicted_energy",
            ROLLING_REOPT_CUSTOM="existing_custom_insertion_relocate_2opt_merge; nominal_replan_budget_0.01s"),
        qualification="exploration_only; no_novelty_or_superiority_claim", config=PROFILES[args.profile],
        runtime=dict(python=sys.version, torch=torch.__version__, numpy=np.__version__,
                     cuda_runtime=torch.version.cuda),
        source_sha256={name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                       for name in ("explore_emergency.py", "explore_emergency_inputs.py", "event_learning.py",
                                    "env.py", "feat.py", "model.py", "policies.py", "solver.py", "urgent.py")},
        command=[sys.executable, "-m", "rlcore.explore_emergency", "--out", str(folder),
                 "--seed", str(args.seed), "--device", args.device, "--profile", args.profile,
                 "--corpus-seed", str(args.corpus_seed)])
    write_json(folder/"manifest.json", manifest)
    try:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")
        torch.set_num_threads(1)
        seed_all(args.seed)
        cfg = PROFILES[args.profile]
        inputs = build_inputs(args.corpus_seed, args.profile)
        corpus_sha = canonical_sha(inputs)
        write_json(folder/"inputs.json", inputs)
        manifest.update(corpus_sha256=corpus_sha,
                        evaluation_expected_rows=len(inputs["evaluation"])*len(METHODS))
        write_json(folder/"manifest.json", manifest)
        model = Policy(**cfg["arch"]).to(args.device)
        initialization_sha = parameter_sha(model)
        dataset, teachers = collect_bc(lambda index: make_env(inputs["train_bc"][index]),
                                       Greedy(), cfg["bc_episodes"])
        for index, result in enumerate(teachers):
            append_json(folder/"teacher_episodes.jsonl", dict(index=index, metrics=result))
        bc_records = fit_bc(model, dataset, cfg["bc_epochs"], args.device, args.seed)
        for record in bc_records:
            append_json(folder/"training.jsonl", record)
        frozen_bc = copy.deepcopy(model).eval()
        for parameter in frozen_bc.parameters():
            parameter.requires_grad_(False)
        bc_sha = parameter_sha(frozen_bc)
        bc_steps = sum(record["optimizer_steps"] for record in bc_records)
        _checkpoint(folder/"bc.pt", frozen_bc, cfg["arch"], "bc_frozen", args.seed,
                    args.corpus_seed, corpus_sha, bc_steps)
        pg_records = train_pg(model, lambda index: make_env(inputs["train_pg"][index]),
            cfg["pg_iterations"], cfg["rollouts"], args.device, args.seed,
            on_record=lambda record: append_json(folder/"training.jsonl", record))
        pg_steps = sum(record["optimizer_steps"] for record in pg_records)
        nonzero_steps = sum(record["gradient_norm"] > 0 and record["parameters_changed"] for record in pg_records)
        if parameter_sha(frozen_bc) != bc_sha:
            raise AssertionError("frozen BC control was modified by PG")
        _checkpoint(folder/"pg.pt", model, cfg["arch"], "pg_final", args.seed,
                    args.corpus_seed, corpus_sha, pg_steps)
        manifest.update(initialization_sha256=initialization_sha, bc_parameter_sha256=bc_sha,
                        pg_parameter_sha256=parameter_sha(model), bc_optimizer_steps=bc_steps,
                        pg_optimizer_steps=pg_steps, pg_nonzero_gradient_changed_steps=nonzero_steps,
                        bc_frozen_verified=True)
        write_json(folder/"manifest.json", manifest)
        # A flat reward/zero parameter change is an experimental result, not a reason to drop the endpoint.
        rows = []
        for case in inputs["evaluation"]:
            for method in METHODS:
                env = make_env(case)
                from .event_learning import input_sha
                row = dict(case_id=case["case_id"], map_id=case["map_id"], day=case["day"],
                    pattern=case["pattern"], level=case["level"], event_seed=case["event_seed"],
                    map_sha256=case["map_sha256"], case_sha256=case["case_sha256"],
                    optimizer_seed=args.seed, corpus_seed=args.corpus_seed,
                    method=method, input_sha256=input_sha(env))
                try:
                    policy = {"STATIC_FCFS": lambda: A1(), "EDF_NEAREST": lambda: Greedy(),
                        "ROLLING_REOPT_CUSTOM": lambda: Reopt(budget_s=.01),
                        "BC_FROZEN": lambda: TensorRoutePolicy(frozen_bc, args.device),
                        "PG_FINAL": lambda: TensorRoutePolicy(model, args.device)}[method]()
                    result = rollout(env, policy).metrics
                    row.update(status="completed", metrics=result)
                except Exception as exc:
                    # Preserve the full frozen denominator after an attempted run.
                    emergency_records = [dict(rid=request["rid"], release=request["t"],
                        deadline=request["dl"], priority=request["prio"], arrival=None,
                        completion=None, done=False, on_time=False) for request in case["requests"]]
                    row.update(status="error", error_type=type(exc).__name__, error=str(exc),
                        metrics=dict(routine_total=len(case["layout"]["targets"]), routine_done=0,
                            n_urgent=len(case["requests"]), urgent_done=0,
                            high_total=sum(request["prio"] == 1 for request in case["requests"]),
                            norm_total=sum(request["prio"] == 0 for request in case["requests"]),
                            high_on_time=0, norm_on_time=0, response_observed=0,
                            response_missing=len(case["requests"]), return_failure=1,
                            return_failures=len(case["layout"]["drones"]),
                            emergency_records=emergency_records))
                rows.append(row)
                append_json(folder/"evaluation.jsonl", row)
        summary = summarize(rows)
        summary.update(schema="emergency_exploratory_summary_v1", optimizer_seed=args.seed,
                       corpus_seed=args.corpus_seed, corpus_sha256=corpus_sha, profile=args.profile,
                       expected_rows=manifest["evaluation_expected_rows"], actual_rows=len(rows),
                       bc_optimizer_steps=bc_steps, pg_optimizer_steps=pg_steps,
                       pg_nonzero_gradient_changed_steps=nonzero_steps, formal=False,
                       input_provenance=inputs["provenance"])
        write_json(folder/"summary.json", summary)
        errors = sum(row["status"] != "completed" for row in rows)
        manifest.update(status="completed" if not errors else "completed_with_evaluation_errors",
                        evaluation_errors=errors, wall_seconds=time.perf_counter()-started,
                        artifact_sha256={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in folder.iterdir() if path.is_file() and path.name != "manifest.json"})
        write_json(folder/"manifest.json", manifest)
        # Read final JSON artifacts back before declaring completion.
        for name in ("manifest.json", "inputs.json", "summary.json"):
            json.loads((folder/name).read_text())
        print(json.dumps(dict(status=manifest["status"], out=str(folder), pg_optimizer_steps=pg_steps,
                              evaluation_rows=len(rows), evaluation_errors=errors), allow_nan=False), flush=True)
        return int(bool(errors))
    except BaseException as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                        wall_seconds=time.perf_counter()-started)
        write_json(folder/"manifest.json", manifest)
        (folder/"failure_traceback.txt").write_text(traceback.format_exc())
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=0, help="optimizer/action seed; does not change corpus")
    parser.add_argument("--corpus-seed", type=int, default=CORPUS_SEED)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="quick")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
