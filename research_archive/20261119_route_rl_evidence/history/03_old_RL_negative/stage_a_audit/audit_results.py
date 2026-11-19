#!/usr/bin/env python3
"""Read-only audit of the frozen Route-RL Stage-A evaluation."""

import argparse
import gzip
import hashlib
import json
import random
import statistics
from pathlib import Path

from lrphsd.evaluator import evaluate
from lrphsd.problem import read_instance
from route_rl.evaluate import code_digest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("instance_dir", type=Path)
    args = parser.parse_args()
    root = args.result_dir
    manifest = json.loads((root / "run_manifest.json").read_text())
    expected = {
        (name, seed, budget, method)
        for name in manifest["maps"]
        for seed in manifest["solver_seeds"]
        for budget in manifest["budgets_seconds"]
        for method in manifest["methods"]
    }
    rows = {}
    failures = []
    instances = {}
    for path in sorted(root.glob("*.json")):
        if path.name in ("run_manifest.json", "summary.json"):
            continue
        row = json.loads(path.read_text())
        key = (row["instance"], row["solver_seed"], row["budget_seconds"], row["method"])
        if key in rows:
            failures.append(["duplicate", key])
            continue
        rows[key] = row
        solution_path = root / (path.stem + ".solution.json.gz")
        if not solution_path.is_file():
            failures.append(["missing_solution", key])
            continue
        if digest(solution_path) != row["solution_sha256"]:
            failures.append(["solution_hash", key])
        name = row["instance"]
        if name not in instances:
            instances[name] = read_instance(args.instance_dir / (name + ".txt"))
        instance = instances[name]
        if instance.sha256 != row["instance_sha256"] or instance.sha256 != manifest["maps"][name]:
            failures.append(["instance_hash", key])
        with gzip.open(solution_path, "rt", encoding="utf-8") as source:
            solution = json.load(source)
        audit = evaluate(instance, solution)
        if not audit["feasible"] or abs(audit["cost"] - row["final_cost"]) > 1e-7:
            failures.append(["independent_evaluation", key])
        if row["status"] != "ok" or not row["feasible"]:
            failures.append(["reported_status", key])
    missing = expected - rows.keys()
    extra = rows.keys() - expected
    if missing:
        failures.append(["missing_rows", len(missing)])
    if extra:
        failures.append(["extra_rows", len(extra)])
    if code_digest() != manifest["source_sha256"]:
        failures.append(["source_hash", code_digest()])
    print(f"AUDIT rows {len(rows)} expected {len(expected)} missing {len(missing)} extra {len(extra)} errors {len(failures)}")
    if failures:
        print("FIRST_ERRORS", failures[:5])
        return 1
    for budget in manifest["budgets_seconds"]:
        for method in manifest["methods"]:
            costs = [rows[(name, seed, budget, method)]["final_cost"]
                     for name in manifest["maps"] for seed in manifest["solver_seeds"]]
            print(f"MEAN {budget:g}s {method} {statistics.mean(costs):.6f}")
        values = []
        for name in manifest["maps"]:
            paired = [
                100 * (rows[(name, seed, budget, "route_alns")]["final_cost"]
                       - rows[(name, seed, budget, "route_rl")]["final_cost"])
                / rows[(name, seed, budget, "route_alns")]["final_cost"]
                for seed in manifest["solver_seeds"]
            ]
            values.append(statistics.mean(paired))
        rng = random.Random(20261102)
        draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(20000))
        wins = sum(value > 1e-9 for value in values)
        losses = sum(value < -1e-9 for value in values)
        ties = len(values) - wins - losses
        print(f"RL_VS_ALNS {budget:g}s mean {statistics.mean(values):+.6f}% "
              f"CI [{draws[499]:+.6f},{draws[19499]:+.6f}]% WLT {wins}/{losses}/{ties}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
