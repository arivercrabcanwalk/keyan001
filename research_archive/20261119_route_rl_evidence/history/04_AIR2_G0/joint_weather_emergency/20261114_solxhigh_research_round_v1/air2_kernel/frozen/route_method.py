"""Timed, single-process fixed-wind physical route method; no learning."""
from __future__ import annotations

# The launcher supplies its monotonic start before Popen. Imports count too.
import os
import time

PROCESS_IMPORT_STARTED = time.perf_counter()

import argparse
import hashlib
import json
from pathlib import Path

from baselines import problem, wind_scorer


def load_input(bundle_path):
    path = Path(bundle_path).resolve()
    raw = path.read_bytes()
    bundle = json.loads(raw)
    if bundle["schema"] != "physical_route_delivery_input_v1":
        raise ValueError("INPUT_SCHEMA")
    instance_path = path.parent / bundle["instance_file"]
    instance = problem.read_instance(
        instance_path, params=problem.Parameters(**bundle["parameters"]))
    anchor = wind_scorer.CostAnchor.from_solution(
        instance, bundle["anchor"], wind=tuple(bundle["wind"]))
    return bundle, instance, anchor, hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    data = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def payload_for(instance, anchor, solution, input_sha256, method):
    score = wind_scorer.validate_candidate(instance, solution, anchor)
    if not score["admissible"]:
        raise ValueError("METHOD_FINAL_VALIDATION_FAILED:" + str(score["issues"]))
    if score["M_return"] > anchor.makespan:
        raise ValueError("METHOD_WORSE_THAN_ANCHOR")
    return {
        "schema": "physical_route_delivery_output_v1",
        "input_sha256": input_sha256,
        "instance_sha256": instance.sha256,
        "physics_sha256": score["physics_sha256"],
        "parameter_sha256": score["parameter_sha256"],
        "method": method,
        "solution": solution,
        "claimed": {k: score[k] for k in ("admissible", "solution_sha256", "cost", "M_return")},
    }


def run_method(args):
    t0 = float(os.environ.get("ROUTE_DELIVERY_STARTED", PROCESS_IMPORT_STARTED))
    _, instance, anchor, input_hash = load_input(args.bundle)
    from baselines import constant_wind_adapter
    if args.method == "strong_bank":
        import station_bank
    # Keep a fixed, declared reserve for combining and final durable output.
    # Budget is relative to the launcher's start, including input/import time.
    search_budget = args.budget - (0.25 if args.method == "strong_bank" else 0.10)
    if search_budget <= 0:
        raise ValueError("INSUFFICIENT_METHOD_BUDGET")
    strong = constant_wind_adapter.solve(
        instance, anchor, search_budget, started_at=t0, seed=args.seed)
    solution = strong["solution"]
    details = {"strong": strong, "external_parent_pool_used": False}
    if args.method == "strong_bank":
        combination = station_bank.solve(instance, [solution], anchor)
        solution = combination["solution"]
        details["bank"] = combination
        details["pool_generation"] = "anchor plus this timed ALNS final solution"
    payload = payload_for(instance, anchor, solution, input_hash, args.method)
    payload["details"] = details
    payload["method_output_ready_elapsed_s"] = time.perf_counter() - t0
    write_json(args.result, payload)
    print("METHOD=" + args.method + " COMPLETE_OUTPUT_DURABLE=true", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--method", choices=("strong", "strong_bank"), required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    run_method(parser.parse_args())


if __name__ == "__main__":
    main()
