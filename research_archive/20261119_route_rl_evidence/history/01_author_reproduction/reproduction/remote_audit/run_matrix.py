#!/usr/bin/env python3
"""Resumable, single-worker Liu source/port experiment matrix.

Run from a copy of the frozen v5 tree. Every task is written atomically and
validated before an existing result is reused. No failed task is skipped.
"""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lrphsd.evaluator import evaluate
from lrphsd.problem import read_instance
from lrphsd.tsalns_v6 import reset_engine, solve

PROFILES = {
    "J0": {"kind": "java", "class_dir": "classes", "guard": False, "local": 100, "weight_upper": 5.0},
    "J1": {"kind": "java", "class_dir": "guarded_classes", "guard": True, "local": 100, "weight_upper": 5.0},
    "J2": {"kind": "java", "class_dir": "paper_guarded_classes", "guard": True, "local": 500, "weight_upper": 0.5},
    "P1": {"kind": "python", "local": 100, "weight_upper": 5.0},
    "P2": {"kind": "python", "local": 500, "weight_upper": 0.5},
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(profile):
    profile_config = PROFILES[profile]
    if profile_config["kind"] == "java":
        source_dir = ROOT / "reference" / "java" / {
            "J0": "instrumented_source", "J1": "guarded_source", "J2": "paper_guarded_source"
        }[profile]
        files = sorted(source_dir.glob("*.java"))
    else:
        files = sorted((ROOT / "lrphsd").glob("*.py")) + [ROOT / "native" / "r6_kernel.c"]
    return hashlib.sha256("".join(digest(path) for path in files).encode()).hexdigest()


def write_json(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def execute(path, profile, seed, outer, timeout, output_dir):
    config = PROFILES[profile]
    instance = read_instance(path)
    start = time.perf_counter()
    row = {
        "task_identity": f"{profile}|{path.stem}|{seed}|outer{outer}",
        "instance": path.stem,
        "input_sha256": digest(path),
        "profile": profile,
        "seed": seed,
        "outer_iterations_requested": outer,
        "local_iterations": config["local"],
        "alns_iterations": 5000,
        "weight_lower": 0.1,
        "weight_upper": config["weight_upper"],
    }
    stem = f"{profile}__{path.stem}__s{seed}__o{outer}"
    try:
        if config["kind"] == "java":
            raw_path = output_dir / (stem + ".reference.json")
            java = Path(os.environ["JAVA_HOME"]) / "bin" / "java"
            command = [str(java), "-XX:ActiveProcessorCount=1", "-XX:+UseSerialGC", "-Xms32m", "-Xmx512m",
                       f"-Drepro.instance={path}", f"-Drepro.seed={seed}", "-Drepro.seconds=0",
                       f"-Drepro.output={raw_path}", f"-Drepro.guard={'true' if config['guard'] else 'false'}",
                       "-cp", str(ROOT / "reference" / "java" / config["class_dir"]), "test1.Main"]
            if outer != 500:
                raise ValueError("Java full-source variants require outer=500; use fixed12 scripts for partial runs")
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
            (output_dir / (stem + ".stdout.log")).write_text(result.stdout)
            (output_dir / (stem + ".stderr.log")).write_text(result.stderr)
            row["command"] = command
            row["exit_code"] = result.returncode
            if result.returncode or not raw_path.is_file():
                raise RuntimeError(f"Java exit={result.returncode}, raw_output_exists={raw_path.is_file()}")
            raw = json.loads(raw_path.read_text())
            solution = {"schema_version": 1, "instance": instance.name,
                        "instance_sha256": instance.sha256,
                        "station_types": raw["station_types"], "routes": raw["routes"]}
            row["source_reported_cost"] = raw["reference_reported_cost"]
            row["source_integrity_issues"] = raw.get("reference_integrity_issues", [])
            row["raw_output_sha256"] = digest(raw_path)
        else:
            reset_engine()
            solution, meta = solve(instance, seed=seed, seconds=None,
                                   config={"outer_iterations": outer,
                                           "local_iterations": config["local"],
                                           "alns_iterations": 5000,
                                           "weight_lower": 0.1,
                                           "weight_upper": config["weight_upper"],
                                           "initial_temperature": 1000.0,
                                           "cooling_rate": 0.95,
                                           "final_temperature": 0.001,
                                           "strict_deadline": False},
                                   rng_mode="shared", removed_order="sorted_id")
            reset_engine()
            row["outer_iterations_attempted"] = meta["outer_iterations_attempted"]
            row["evaluations"] = meta["evaluations"]
        audit = evaluate(instance, solution)
        row["independent_audit"] = audit
        row["independently_feasible"] = bool(audit["feasible"]) and not row.get("source_integrity_issues")
        row["independent_cost"] = audit["cost"]
        if "source_reported_cost" in row:
            row["source_objective_abs_error"] = abs(row["source_reported_cost"] - audit["cost"])
        witness = output_dir / (stem + ".solution.json.gz")
        with gzip.open(witness, "wt", encoding="utf-8") as stream:
            json.dump(solution, stream, separators=(",", ":"))
        row["solution_sha256"] = digest(witness)
        row["status"] = "ok"
    except Exception as exc:
        row["status"] = "error"
        row["error_type"] = type(exc).__name__
        row["error"] = str(exc)
    row["elapsed_seconds"] = time.perf_counter() - start
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--outer", type=int, default=500)
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--names", default="", help="comma-separated instance stems for a stratified pilot")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    instance_dir = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"
    paths = sorted(instance_dir.glob("*.txt"))
    if len(paths) != 120:
        raise SystemExit(f"expected 120 official instances, got {len(paths)}")
    if args.names:
        names = set(args.names.split(","))
        paths = [path for path in paths if path.stem in names]
        if {path.stem for path in paths} != names:
            raise SystemExit("unknown instance in --names")
    if args.limit:
        paths = paths[:args.limit]
    seeds = [int(value) for value in args.seeds.split(",")]
    manifest_path = args.out / "run_manifest.json"
    manifest = {"schema": "liu-repro-matrix-v1", "profile": args.profile,
                "profile_config": PROFILES[args.profile], "outer": args.outer,
                "seeds": seeds, "inputs": {path.stem: digest(path) for path in paths},
                "official_source_lock_sha256": digest(ROOT / "reference" / "java" / "SOURCE_LOCK.json"),
                "profile_source_sha256": source_digest(args.profile),
                "native_binary_sha256": digest(ROOT / "native" / "libr6kernel.so") if PROFILES[args.profile]["kind"] == "python" else None,
                "runner_sha256": digest(Path(__file__)),
                "started_unix": time.time()}
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text())
        for key in ("profile", "profile_config", "outer", "seeds", "inputs", "official_source_lock_sha256", "profile_source_sha256", "native_binary_sha256", "runner_sha256"):
            if prior[key] != manifest[key]:
                raise SystemExit(f"manifest mismatch: {key}")
    else:
        write_json(manifest_path, manifest)
    failures = 0
    for index, path in enumerate(paths, 1):
        for seed in seeds:
            name = f"{args.profile}__{path.stem}__s{seed}__o{args.outer}"
            output = args.out / (name + ".json")
            if output.exists():
                old = json.loads(output.read_text())
                if old["input_sha256"] != digest(path) or old["profile"] != args.profile or old["status"] != "ok":
                    raise SystemExit(f"existing task requires review: {output}")
                witness = args.out / (name + ".solution.json.gz")
                if not witness.is_file() or digest(witness) != old["solution_sha256"]:
                    raise SystemExit(f"existing witness hash mismatch: {output}")
                continue
            row = execute(path, args.profile, seed, args.outer, args.timeout, args.out)
            write_json(output, row)
            print(json.dumps({key: row.get(key) for key in ("task_identity", "status", "independently_feasible", "independent_cost", "elapsed_seconds", "error")}), flush=True)
            if row["status"] != "ok":
                failures += 1
        print(f"PROGRESS {index}/{len(paths)} maps profile={args.profile}", flush=True)
    print(f"COMPLETE profile={args.profile} maps={len(paths)} seeds={len(seeds)} failures={failures}", flush=True)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
