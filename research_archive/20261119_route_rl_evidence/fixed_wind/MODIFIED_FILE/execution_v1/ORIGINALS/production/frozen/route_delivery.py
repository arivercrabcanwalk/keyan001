"""Observe complete process delivery, then retain every row for ITT.

Worker-side decoding, loading, search, validation and durable serialization are
inside the deadline. Controller duplicate validation is additionally charged.
Controller receipt writing after the decision does not generate a method plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from baselines import wind_scorer
from route_method import load_input, write_json


DELIVERY_CONTRACT = "actual_exit_and_independent_validation_v1"


def timing_accepts(budget_s, exit_status, process_elapsed_s, admission_elapsed_s,
                   timed_out, valid_output):
    values = (budget_s, process_elapsed_s, admission_elapsed_s)
    return (all(type(v) in (int, float) and math.isfinite(v) for v in values)
            and budget_s > 0 and min(process_elapsed_s, admission_elapsed_s) >= 0
            and admission_elapsed_s >= process_elapsed_s
            and exit_status == 0 and not timed_out and valid_output
            and process_elapsed_s <= budget_s and admission_elapsed_s <= budget_s)


def verify_payload(payload, instance, anchor, input_sha256, expected_method):
    if (not isinstance(payload, dict)
            or payload.get("schema") != "physical_route_delivery_output_v1"
            or payload.get("input_sha256") != input_sha256
            or payload.get("instance_sha256") != instance.sha256
            or payload.get("physics_sha256") != wind_scorer.physics_identity(instance, anchor.wind)
            or payload.get("parameter_sha256") != wind_scorer.parameter_identity(instance)
            or payload.get("method") != expected_method):
        return False, "PROTOCOL_OR_IDENTITY_MISMATCH", None
    score = wind_scorer.validate_candidate(instance, payload.get("solution"), anchor)
    if not score["admissible"]:
        return False, "INADMISSIBLE_OUTPUT", score
    if score["M_return"] > anchor.makespan:
        return False, "WORSE_THAN_ANCHOR", score
    expected = {k: score[k] for k in ("admissible", "solution_sha256", "cost", "M_return")}
    if payload.get("claimed") != expected:
        return False, "CLAIM_MISMATCH", score
    return True, None, score


def run(bundle_path, out, *, budget_s, method, seed, command_factory=None):
    if type(budget_s) not in (int, float) or not math.isfinite(budget_s) or budget_s <= 0:
        raise ValueError("FINITE_POSITIVE_BUDGET_REQUIRED")
    start = time.perf_counter()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    bundle, instance, anchor, input_hash = load_input(bundle_path)
    result_path = out / "RAW_RESULT.json"
    command = ([sys.executable, "-m", "route_method", "--bundle", str(Path(bundle_path).resolve()),
                "--result", str(result_path.resolve()), "--method", method,
                "--budget", str(budget_s), "--seed", str(seed)]
               if command_factory is None else command_factory(result_path.resolve()))
    write_json(out / "INTENT.json", {
        "contract": DELIVERY_CONTRACT, "command": command,
        "bundle_path": str(Path(bundle_path).resolve()), "input_sha256": input_hash,
        "budget_s": budget_s, "method": method, "seed": seed,
        "run_role": bundle["run_role"], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "clock_start": start, "includes_controller_duplicate_verification": True})
    child_env = dict(os.environ, ROUTE_DELIVERY_STARTED=repr(start),
                     PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
                     OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    timed_out = False
    launch_error = None
    child = None
    with (out / "STDOUT.txt").open("x") as stream:
        try:
            remaining = budget_s - (time.perf_counter() - start)
            if remaining <= 0:
                raise TimeoutError("PREPARATION_EXHAUSTED_BUDGET")
            child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                     env=child_env, start_new_session=True)
            try:
                child.wait(timeout=max(0.0, budget_s - (time.perf_counter() - start)))
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        except TimeoutError:
            timed_out = True
        except OSError as exc:
            # A launcher failure is an attempted row too; retain the exception
            # and its anchor ITT value even though no child exit exists.
            launch_error = type(exc).__name__ + ":" + str(exc)
        finally:
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    process_elapsed = time.perf_counter() - start
    exit_status = None if child is None else child.returncode
    payload = None
    score = None
    raw_sha256 = None
    valid = False
    reason = "MISSING_OUTPUT"
    if result_path.exists():
        raw = result_path.read_bytes()
        raw_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            if len(raw) > 4 * 1024**2:
                raise ValueError("RESULT_FILE_TOO_LARGE")
            payload = json.loads(raw)
            valid, reason, score = verify_payload(payload, instance, anchor, input_hash, method)
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            reason = "MALFORMED_OUTPUT:" + type(exc).__name__
    admission_elapsed = time.perf_counter() - start
    accepted = timing_accepts(budget_s, exit_status, process_elapsed,
                              admission_elapsed, timed_out, valid)
    if launch_error is not None:
        reason = "LAUNCH_ERROR"
    elif timed_out or process_elapsed > budget_s:
        reason = "PROCESS_LATE_OR_TIMEOUT"
    elif exit_status != 0:
        reason = "NONZERO_EXIT"
    elif admission_elapsed > budget_s:
        reason = "INDEPENDENT_VALIDATION_LATE"
    elif accepted:
        reason = None
    anchor_score = wind_scorer.validate_candidate(instance, anchor.solution(), anchor)
    effective = score if accepted else anchor_score
    decision = {
        "schema": "physical_route_delivery_decision_v1", "contract": DELIVERY_CONTRACT,
        "delivery_status": "ONTIME_VALID" if accepted else "NO_ONTIME_VALID_OUTPUT",
        "failure_reason": reason, "exit_status": exit_status, "timed_out": timed_out,
        "launch_error": launch_error,
        "budget_s": budget_s, "process_wall_s": process_elapsed,
        "admission_wall_s": admission_elapsed, "method": method, "seed": seed,
        "input_sha256": input_hash, "raw_output_sha256": raw_sha256,
        "raw_output_retained": result_path.exists(),
        "raw_validation": score, "accepted": accepted,
        "itt_anchor_used": not accepted, "itt_M_return": effective["M_return"],
        "itt_cost": effective["cost"], "anchor_M_return": anchor.makespan,
        "anchor_cost": anchor.cost, "itt_solution": payload["solution"] if accepted else anchor.solution(),
        "delivered_solution_file": str(result_path.resolve()) if accepted else None,
        "run_role": bundle["run_role"], "scientific_primary_changed": False,
        "new_scientific_population_qualified": False,
    }
    write_json(out / "DECISION.json", decision)
    return decision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--method", choices=("strong", "strong_bank"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    decision = run(args.bundle, args.out, budget_s=args.budget, method=args.method, seed=args.seed)
    print("DELIVERY=" + decision["delivery_status"] + " ITT_ANCHOR=" + str(decision["itt_anchor_used"]).lower())


if __name__ == "__main__":
    main()
