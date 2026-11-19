#!/usr/bin/env python3
"""Reopen, validate and compare the semfix P1/P2 result matrices."""

import argparse
import gzip
import hashlib
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lrphsd.evaluator import evaluate
from lrphsd.problem import read_instance
from run_matrix import PROFILES, source_digest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_python(profile, result_dir, full=True):
    manifest_path = result_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    errors = []
    if manifest.get("profile") != profile or manifest.get("profile_config") != PROFILES[profile]:
        errors.append("profile/config mismatch")
    official_dir = ROOT / "external/LRPHSD<EXECUTION_PATH>"
    official_names = {path.stem for path in official_dir.glob("*.txt")}
    if len(official_names) != 120 or set(manifest.get("inputs", {})) != official_names:
        errors.append("official 120-map input set mismatch")
    if manifest.get("seeds") != [0, 1, 2, 3, 4] or manifest.get("outer") != 500:
        errors.append("seed/outer-iteration protocol mismatch")
    if manifest.get("profile_source_sha256") != source_digest(profile):
        errors.append("source digest mismatch")
    if manifest.get("official_source_lock_sha256") != digest(ROOT / "reference/java/SOURCE_LOCK.json"):
        errors.append("official source lock mismatch")
    if manifest.get("runner_sha256") != digest(ROOT / "run_matrix.py"):
        errors.append("runner source mismatch")
    binary = result_dir / "libr6kernel.so"
    if not binary.is_file() or manifest.get("native_binary_sha256") != digest(binary):
        errors.append("native binary mismatch")

    instances = {}
    rows = {}
    for name, input_hash in manifest["inputs"].items():
        path = ROOT / "external/LRPHSD<EXECUTION_PATH>" / (name + ".txt")
        if digest(path) != input_hash:
            errors.append(f"input hash mismatch: {name}")
        instances[name] = read_instance(path)
    for name in manifest["inputs"]:
        for seed in manifest["seeds"]:
            stem = f"{profile}__{name}__s{seed}__o{manifest['outer']}"
            row_path = result_dir / (stem + ".json")
            if not row_path.is_file():
                continue
            row = json.loads(row_path.read_text())
            rows[(name, seed)] = row
            if row.get("task_identity") != f"{profile}|{name}|{seed}|outer{manifest['outer']}":
                errors.append(f"identity mismatch: {stem}")
            if row.get("input_sha256") != manifest["inputs"][name]:
                errors.append(f"row input mismatch: {stem}")
            if (row.get("local_iterations") != PROFILES[profile]["local"]
                    or row.get("alns_iterations") != 5000
                    or row.get("weight_lower") != 0.1
                    or row.get("weight_upper") != PROFILES[profile]["weight_upper"]):
                errors.append(f"row parameter mismatch: {stem}")
            if row.get("status") != "ok" or not row.get("independently_feasible"):
                errors.append(f"failed/infeasible row: {stem}")
                continue
            witness = result_dir / (stem + ".solution.json.gz")
            if not witness.is_file() or digest(witness) != row.get("solution_sha256"):
                errors.append(f"solution hash mismatch: {stem}")
                continue
            with gzip.open(witness, "rt", encoding="utf-8") as stream:
                solution = json.load(stream)
            audit = evaluate(instances[name], solution)
            if not audit["feasible"]:
                errors.append(f"reopened solution infeasible: {stem}")
            if abs(audit["cost"] - row["independent_cost"]) > 1e-7:
                errors.append(f"recomputed objective mismatch: {stem}")
            if row.get("independent_audit", {}).get("feasible") is not True:
                errors.append(f"recorded feasibility mismatch: {stem}")
            if abs(audit["cost"] - row.get("independent_audit", {}).get("cost", float("inf"))) > 1e-7:
                errors.append(f"recorded audit objective mismatch: {stem}")
    expected_stems = {
        f"{profile}__{name}__s{seed}__o{manifest['outer']}"
        for name in manifest["inputs"] for seed in manifest["seeds"]
    }
    actual_stems = {path.name[:-5] for path in result_dir.glob(profile + "__*.json")}
    if actual_stems != expected_stems:
        errors.append(f"result row file set mismatch: missing={len(expected_stems-actual_stems)} extra={len(actual_stems-expected_stems)}")
    expected = len(manifest["inputs"]) * len(manifest["seeds"])
    if full and len(rows) != expected:
        errors.append(f"incomplete matrix: {len(rows)}/{expected}")
    return {"profile": profile, "expected": expected, "completed": len(rows),
            "feasible": sum(r.get("status") == "ok" and r.get("independently_feasible") for r in rows.values()),
            "audit_errors": errors}, rows


def audit_java_rows(profile, result_dir):
    manifest = json.loads((result_dir / "run_manifest.json").read_text())
    errors = []
    expected_local, expected_weight = (100, 5.0) if profile == "J1b" else (500, 0.5)
    official_dir = ROOT / "external/LRPHSD<EXECUTION_PATH>"
    official_names = {path.stem for path in official_dir.glob("*.txt")}
    if (manifest.get("profile") != profile
            or manifest.get("profile_config") != {"kind": "java", "class_dir": profile + "_classes",
                                                    "guard": True, "local": expected_local,
                                                    "weight_upper": expected_weight}
            or manifest.get("outer") != 500
            or manifest.get("seeds") != [0, 1, 2, 3, 4]
            or len(official_names) != 120
            or set(manifest.get("inputs", {})) != official_names):
        errors.append("Java manifest protocol mismatch")
    if manifest.get("official_source_lock_sha256") != digest(ROOT / "reference/java/SOURCE_LOCK.json"):
        errors.append("Java official source lock mismatch")
    if manifest.get("runner_sha256") != digest(ROOT / "run_postguard_matrix.py"):
        errors.append("Java runner source mismatch")
    build_manifest = ROOT / "reference/java" / f"{profile}_build_manifest.json"
    if digest(build_manifest) != manifest["variant_build_manifest_sha256"]:
        errors.append("Java build manifest hash mismatch")
    build = json.loads(build_manifest.read_text())
    source_dir = ROOT / "reference/java" / f"{profile}_source"
    for filename, expected in build["source_hashes"].items():
        if digest(source_dir / filename) != expected:
            errors.append(f"Java source hash mismatch: {filename}")
    rows = {}
    for name in manifest["inputs"]:
        instance_path = ROOT / "external/LRPHSD<EXECUTION_PATH>" / (name + ".txt")
        if digest(instance_path) != manifest["inputs"][name]:
            errors.append(f"Java input hash mismatch: {name}")
        instance = read_instance(instance_path)
        for seed in manifest["seeds"]:
            stem = f"{profile}__{name}__s{seed}__o500"
            row_path = result_dir / (stem + ".json")
            if not row_path.is_file():
                errors.append(f"missing Java row: {stem}")
                continue
            row = json.loads(row_path.read_text())
            rows[(name, seed)] = row
            if row.get("task_identity") != f"{profile}|{name}|{seed}|outer500":
                errors.append(f"Java task identity mismatch: {stem}")
            witness = result_dir / (stem + ".solution.json.gz")
            if (row.get("status") != "ok" or not row.get("independently_feasible")
                    or row.get("input_sha256") != manifest["inputs"][name]
                    or row.get("local_iterations") != expected_local
                    or row.get("weight_upper") != expected_weight):
                errors.append(f"Java failed/infeasible row: {stem}")
            elif not witness.is_file() or digest(witness) != row.get("solution_sha256"):
                errors.append(f"Java solution hash mismatch: {stem}")
            else:
                with gzip.open(witness, "rt", encoding="utf-8") as stream:
                    solution = json.load(stream)
                audit = evaluate(instance, solution)
                if not audit["feasible"] or abs(audit["cost"] - row.get("independent_cost", float("inf"))) > 1e-7:
                    errors.append(f"Java reopened witness mismatch: {stem}")
            raw = result_dir / (stem + ".reference.json")
            if not raw.is_file() or digest(raw) != row.get("raw_output_sha256"):
                errors.append(f"Java raw output hash mismatch: {stem}")
            if row.get("source_objective_abs_error", float("inf")) > 1e-7:
                errors.append(f"Java objective mismatch: {stem}")
    expected_stems = {
        f"{profile}__{name}__s{seed}__o500"
        for name in manifest["inputs"] for seed in manifest["seeds"]
    }
    actual_stems = {path.name[:-5] for path in result_dir.glob(profile + "__*.json")
                    if not path.name.endswith(".reference.json")}
    if actual_stems != expected_stems:
        errors.append(f"Java result row file set mismatch: missing={len(expected_stems-actual_stems)} extra={len(actual_stems-expected_stems)}")
    return rows, errors


def paired(java_rows, python_rows):
    per_map = defaultdict(list)
    for key in sorted(java_rows.keys() & python_rows.keys()):
        j, p = java_rows[key], python_rows[key]
        if j.get("status") == p.get("status") == "ok" and j.get("independently_feasible") and p.get("independently_feasible"):
            per_map[key[0]].append(100 * (j["independent_cost"] - p["independent_cost"]) / j["independent_cost"])
    values = [statistics.mean(v) for v in per_map.values()]
    if not values:
        return {"paired_maps": 0, "paired_runs": 0}
    rng = random.Random(20261102)
    draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(20000))
    return {"paired_maps": len(values), "paired_runs": sum(map(len, per_map.values())),
            "definition": "100*(Java cost - Python cost)/Java cost; positive favors Python",
            "map_mean_pct": statistics.mean(values), "map_median_pct": statistics.median(values),
            "map_min_pct": min(values), "map_max_pct": max(values),
            "map_cluster_bootstrap95_pct": [draws[499], draws[19499]],
            "map_wlt_python": [sum(v > 1e-9 for v in values), sum(v < -1e-9 for v in values), sum(abs(v) <= 1e-9 for v in values)]}


def paper_comparison(profile, result_dir):
    published = json.loads((ROOT / "published_table1.json").read_text())["groups"]
    by_map = defaultdict(list)
    for path in result_dir.glob(profile + "__*.json"):
        row = json.loads(path.read_text())
        if row.get("status") == "ok" and row.get("independently_feasible"):
            by_map[row["instance"]].append(row["independent_cost"])
    result = {}
    for index, (group, paper) in enumerate(published.items()):
        maps = sorted(name for name in by_map if name.rsplit("_", 1)[0] == group)
        means = [statistics.mean(by_map[name]) for name in maps]
        bests = [min(by_map[name]) for name in maps]
        if means:
            rng = random.Random(20261102 + index)
            mean_draws = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(20000))
            rng = random.Random(20261202 + index)
            best_draws = sorted(statistics.mean(rng.choices(bests, k=len(bests))) for _ in range(20000))
        else:
            mean_draws, best_draws = [], []
        result[group] = {
            "maps": len(maps), "runs": sum(map(len, (by_map[name] for name in maps))),
            "paper_average": paper["average"], "run_average": statistics.mean(means) if means else None,
            "run_average_bootstrap95": [mean_draws[499], mean_draws[19499]] if means else None,
            "paper_average_inside_bootstrap95": bool(means) and mean_draws[499] <= paper["average"] <= mean_draws[19499],
            "average_gap_pct": 100 * (statistics.mean(means) - paper["average"]) / paper["average"] if means else None,
            "paper_best": paper["best"], "mean_map_best": statistics.mean(bests) if bests else None,
            "mean_map_best_bootstrap95": [best_draws[499], best_draws[19499]] if bests else None,
            "paper_best_inside_bootstrap95": bool(bests) and best_draws[499] <= paper["best"] <= best_draws[19499],
            "best_gap_pct": 100 * (statistics.mean(bests) - paper["best"]) / paper["best"] if bests else None,
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/semfix_full_matrix_audit.json")
    parser.add_argument("--profiles", default="P1,P2")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    reports = {}
    profile_java = {"P1": "J1b", "P2": "J2b"}
    selected = [value.strip() for value in args.profiles.split(",") if value.strip()]
    if not selected or any(value not in profile_java for value in selected):
        raise SystemExit("--profiles must be a nonempty subset of P1,P2")
    for profile in selected:
        java_profile = profile_java[profile]
        result_dir = ROOT / "results" / ("semfix_full_" + profile)
        summary, py_rows = audit_python(profile, result_dir, full=not args.allow_partial)
        java_rows, java_errors = audit_java_rows(java_profile, ROOT / "results" / ("full_" + java_profile))
        summary["java_profile"] = java_profile
        summary["java_audit_errors"] = java_errors
        summary["paired"] = paired(java_rows, py_rows)
        summary["published_table1"] = paper_comparison(profile, result_dir)
        reports[profile] = summary
        print(f"SEMFiX_AUDIT {profile} {summary['completed']}/{summary['expected']} feasible={summary['feasible']} errors={len(summary['audit_errors'])} java_errors={len(java_errors)} paired={summary['paired']}", flush=True)
    args.output.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n")
    has_errors = any(r["audit_errors"] or r["java_audit_errors"] for r in reports.values())
    if args.allow_partial:
        has_errors = any(r["audit_errors"] or r["java_audit_errors"] for r in reports.values())
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
