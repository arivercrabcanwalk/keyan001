#!/usr/bin/env python3
"""Audit complete solution artifacts and summarize the Liu full-run matrix."""

import argparse
import csv
import gzip
import hashlib
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lrphsd.evaluator import evaluate
from lrphsd.problem import read_instance
from run_matrix import PROFILES, source_digest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_profile(profile, full=True):
    base = ROOT / "results" / ("full_" + profile)
    manifest = json.loads((base / "run_manifest.json").read_text())
    errors = []
    if manifest["profile"] != profile or manifest["profile_config"] != PROFILES[profile]:
        errors.append("profile/config mismatch")
    if manifest["profile_source_sha256"] != source_digest(profile):
        errors.append("source digest mismatch")
    if manifest["official_source_lock_sha256"] != sha(ROOT / "reference" / "java" / "SOURCE_LOCK.json"):
        errors.append("official source lock mismatch")
    if manifest["runner_sha256"] != sha(ROOT / "run_matrix.py"):
        errors.append("runner source mismatch")
    if manifest["native_binary_sha256"] is not None and manifest["native_binary_sha256"] != sha(ROOT / "native" / "libr6kernel.so"):
        errors.append("native binary mismatch")
    instances = {}
    rows = {}
    seen_files = set()
    for name, input_hash in manifest["inputs"].items():
        path = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg" / (name + ".txt")
        if sha(path) != input_hash:
            errors.append(f"input hash mismatch: {name}")
        instances[name] = read_instance(path)
    for name in manifest["inputs"]:
        for seed in manifest["seeds"]:
            stem = f"{profile}__{name}__s{seed}__o{manifest['outer']}"
            row_path = base / (stem + ".json")
            if not row_path.is_file():
                continue
            seen_files.add(row_path.name)
            row = json.loads(row_path.read_text())
            key = (name, seed)
            if row["task_identity"] != f"{profile}|{name}|{seed}|outer{manifest['outer']}":
                errors.append(f"identity mismatch: {stem}")
            if row["input_sha256"] != manifest["inputs"][name]:
                errors.append(f"row input mismatch: {stem}")
            if row["status"] != "ok":
                rows[key] = row
                continue
            solution_path = base / (stem + ".solution.json.gz")
            if not solution_path.is_file() or sha(solution_path) != row["solution_sha256"]:
                errors.append(f"solution missing/hash mismatch: {stem}")
                continue
            with gzip.open(solution_path, "rt", encoding="utf-8") as stream:
                solution = json.load(stream)
            recalculated = evaluate(instances[name], solution)
            if recalculated["feasible"] != row["independent_audit"]["feasible"]:
                errors.append(f"feasibility mismatch: {stem}")
            if abs(recalculated["cost"] - row["independent_cost"]) > 1e-7:
                errors.append(f"objective mismatch: {stem}")
            if profile.startswith("J"):
                raw_path = base / (stem + ".reference.json")
                if not raw_path.is_file() or sha(raw_path) != row["raw_output_sha256"]:
                    errors.append(f"raw reference hash mismatch: {stem}")
                if row["source_objective_abs_error"] > 1e-7:
                    errors.append(f"Java/Python objective mismatch: {stem}")
            rows[key] = row
    extra = [path.name for path in base.glob(f"{profile}__*.json")
             if not path.name.endswith(".reference.json") and path.name not in seen_files]
    if extra:
        errors.append(f"extra result rows: {extra[:5]}")
    expected = len(manifest["inputs"]) * len(manifest["seeds"])
    status = Counter(row["status"] for row in rows.values())
    feasible = sum(row.get("independently_feasible", False) for row in rows.values())
    issues = Counter(str(issue).split(":")[0] for row in rows.values()
                     for issue in row.get("independent_audit", {}).get("issues", []))
    group = defaultdict(list)
    for (name, seed), row in rows.items():
        if row["status"] == "ok" and row["independently_feasible"]:
            group[name.rsplit("_", 1)[0]].append(row["independent_cost"])
    result = {"profile": profile, "expected": expected, "completed": len(rows),
              "coverage": len(rows) / expected, "status": dict(status),
              "independently_feasible": feasible, "infeasible": status["ok"] - feasible,
              "issue_categories": dict(issues), "audit_errors": errors,
              "group_feasible_mean": {key: statistics.mean(values) for key, values in sorted(group.items())},
              "elapsed_seconds_sum": sum(row.get("elapsed_seconds", 0.0) for row in rows.values())}
    if full and len(rows) != expected:
        result["audit_errors"].append("incomplete matrix")
    return result, rows


def paired(a, b, rows_a, rows_b):
    per_map = defaultdict(list)
    for key in sorted(rows_a.keys() & rows_b.keys()):
        ra, rb = rows_a[key], rows_b[key]
        if ra["status"] != "ok" or rb["status"] != "ok":
            continue
        if not ra["independently_feasible"] or not rb["independently_feasible"]:
            continue
        per_map[key[0]].append(100 * (ra["independent_cost"] - rb["independent_cost"]) / ra["independent_cost"])
    values = [statistics.mean(pair) for pair in per_map.values()]
    if not values:
        return {"a": a, "b": b, "paired_maps": 0}
    rng = random.Random(20261102)
    draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(20000))
    return {"a": a, "b": b, "definition": "100 * (A cost - B cost) / A cost; positive favors B",
            "paired_maps": len(values), "paired_runs": sum(len(pair) for pair in per_map.values()),
            "mean_pct": statistics.mean(values), "median_pct": statistics.median(values),
            "bootstrap95_pct": [draws[499], draws[19499]],
            "map_wlt_b": [sum(v > 1e-9 for v in values), sum(v < -1e-9 for v in values), sum(abs(v) <= 1e-9 for v in values)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "full_matrix_audit.json")
    args = parser.parse_args()
    results = {}
    rows = {}
    for profile in PROFILES:
        results[profile], rows[profile] = audit_profile(profile, full=not args.allow_partial)
        summary = results[profile]
        print(f"PROFILE {profile} {summary['completed']}/{summary['expected']} "
              f"status={summary['status']} feasible={summary['independently_feasible']} "
              f"infeasible={summary['infeasible']} audit_errors={len(summary['audit_errors'])}", flush=True)
    contrasts = [paired(a, b, rows[a], rows[b]) for a, b in (("J0", "J1"), ("J1", "P1"), ("J2", "P2"), ("P1", "P2"))]
    artifact = {"profiles": results, "contrasts": contrasts}
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    for contrast in contrasts:
        print("CONTRAST", contrast, flush=True)
    return 1 if any(result["audit_errors"] for result in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
