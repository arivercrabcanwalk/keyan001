#!/usr/bin/env python3
"""Audit J1b/J2b and pair with P1/P2 without treating J1/J2 as baselines."""

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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--maps-per-group", type=int, default=3)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "postguard_audit.json")
    args = parser.parse_args()
    reports = {}
    for java_profile, python_profile in (("J1b", "P1"), ("J2b", "P2")):
        directory = ("full_" + java_profile if args.maps_per_group == 10 else
                     "stratified_" + java_profile if args.maps_per_group == 3 else
                     "pilot_" + java_profile + "_12")
        base = ROOT / "results" / directory
        manifest = json.loads((base / "run_manifest.json").read_text())
        errors = []
        build_manifest = ROOT / "reference" / "java" / (java_profile + "_build_manifest.json")
        if digest(build_manifest) != manifest["variant_build_manifest_sha256"]:
            errors.append("variant build hash mismatch")
        build = json.loads(build_manifest.read_text())
        source_dir = ROOT / "reference" / "java" / (java_profile + "_source")
        for filename, expected_hash in build["source_hashes"].items():
            if digest(source_dir / filename) != expected_hash:
                errors.append(f"variant source hash mismatch {filename}")
        if digest(ROOT / "reference" / "java" / "SOURCE_LOCK.json") != manifest["official_source_lock_sha256"]:
            errors.append("official source lock mismatch")
        if digest(ROOT / "run_postguard_matrix.py") != manifest["runner_sha256"]:
            errors.append("runner hash mismatch")
        rows = {}
        pbase = ROOT / "results" / ("full_" + python_profile)
        paired = defaultdict(list)
        for name, input_hash in manifest["inputs"].items():
            instance_path = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg" / (name + ".txt")
            if digest(instance_path) != input_hash:
                errors.append(f"instance hash mismatch {name}")
            instance = read_instance(instance_path)
            for seed in manifest["seeds"]:
                stem = f"{java_profile}__{name}__s{seed}__o500"
                path = base / (stem + ".json")
                if not path.is_file():
                    continue
                row = json.loads(path.read_text())
                rows[(name, seed)] = row
                witness = base / (stem + ".solution.json.gz")
                raw = base / (stem + ".reference.json")
                if not witness.is_file() or digest(witness) != row.get("solution_sha256"):
                    errors.append(f"witness hash {stem}")
                    continue
                if not raw.is_file() or digest(raw) != row.get("raw_output_sha256"):
                    errors.append(f"raw hash {stem}")
                with gzip.open(witness, "rt", encoding="utf-8") as stream:
                    audit = evaluate(instance, json.load(stream))
                if not audit["feasible"] or not row.get("independently_feasible"):
                    errors.append(f"infeasible {stem}")
                if abs(audit["cost"] - row["independent_cost"]) > 1e-7 or row["source_objective_abs_error"] > 1e-7:
                    errors.append(f"cost mismatch {stem}")
                python_path = pbase / f"{python_profile}__{name}__s{seed}__o500.json"
                if python_path.is_file():
                    python_row = json.loads(python_path.read_text())
                    if python_row["status"] == "ok" and python_row["independently_feasible"]:
                        paired[name].append(100 * (row["independent_cost"] - python_row["independent_cost"]) / row["independent_cost"])
        expected = len(manifest["inputs"]) * len(manifest["seeds"])
        if not args.allow_partial and len(rows) != expected:
            errors.append(f"incomplete {len(rows)}/{expected}")
        values = [statistics.mean(data) for data in paired.values()]
        rng = random.Random(20261102)
        draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(20000)) if values else []
        report = {"profile": java_profile, "python_comparator": python_profile,
                  "completed": len(rows), "expected": expected, "audit_errors": errors,
                  "paired_maps": len(values), "paired_runs": sum(map(len, paired.values())),
                  "definition": "100*(Java cost - Python cost)/Java cost; positive favors Python",
                  "map_mean_pct": statistics.mean(values) if values else None,
                  "map_median_pct": statistics.median(values) if values else None,
                  "map_min_pct": min(values) if values else None,
                  "map_max_pct": max(values) if values else None,
                  "bootstrap95_pct": [draws[499], draws[19499]] if values else None,
                  "by_group_mean_pct": {group: statistics.mean(v for name, data in paired.items()
                                                          if name.rsplit("_", 1)[0] == group for v in data)
                                        for group in sorted({name.rsplit("_", 1)[0] for name in paired})}}
        reports[java_profile] = report
        print(json.dumps(report, sort_keys=True), flush=True)
    args.output.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n")
    return 1 if any(report["audit_errors"] for report in reports.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
