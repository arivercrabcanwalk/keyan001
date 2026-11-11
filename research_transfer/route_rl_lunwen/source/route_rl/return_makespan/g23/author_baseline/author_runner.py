#!/usr/bin/env python3
"""Isolated one-instance J1b/J2b author runner; never edits accepted sources.

``prepare`` verifies and copies the accepted Java profile, then compiles it.
``plan`` constructs an exact invocation without running the solver.
``run`` records every completed, failed and timed-out invocation and witness.
The profile and seed must be fixed before viewing map-quality outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


PROFILES = {
    "J1b": {"local_iterations": 100, "weight_upper": 5.0,
            "identity": "released_java_parameter_profile"},
    "J2b": {"local_iterations": 500, "weight_upper": 0.5,
            "identity": "paper_Table_A1_parameter_profile"},
}
COST_TOLERANCE = 1e-7


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(data, encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "reproduction/reviewer_package_semfix").is_dir():
            return parent
    raise ValueError("project root not found; use --source-root and --scorer-path")


def source_root_default() -> Path:
    return project_root() / "reproduction/reviewer_package_semfix"


def scorer_default() -> Path:
    return project_root() / "route_rl_research/20261103/return_makespan/scorer.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def independent_modules(source_root: Path, scorer_path: Path):
    problem = load_module("author_baseline_problem", source_root / "lrphsd/problem.py")
    evaluator = load_module("author_baseline_evaluator", source_root / "lrphsd/evaluator.py")
    scorer = load_module("author_baseline_return_scorer", scorer_path)
    return problem, evaluator, scorer


def validate_input(path: Path, source_root: Path, scorer_path: Path):
    """Enforce Java's integer-token node IDs in addition to Python's reader."""
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()[1:], 2):
        if line.strip():
            token = line.split()[0]
            if not re.fullmatch(r"[+-]?\d+", token):
                raise ValueError(f"Java node ID must be an integer token: line {line_number}")
            if not -(1 << 31) <= int(token) < (1 << 31):
                raise ValueError(f"Java node ID exceeds signed int32: line {line_number}")
    problem, _, _ = independent_modules(source_root, scorer_path)
    return problem.read_instance(path)


def seed_for_input(input_sha256: str, namespace: str) -> int:
    """Pure prospective rule; namespace is frozen once for the complete map set."""
    if not re.fullmatch(r"[0-9a-f]{64}", input_sha256) or not namespace:
        raise ValueError("a SHA256 and nonempty frozen seed namespace are required")
    digest = hashlib.sha256((namespace + ":" + input_sha256).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def profile_identity(source_root: Path, profile: str) -> dict:
    if profile not in PROFILES:
        raise ValueError(f"unknown author profile: {profile}")
    base = source_root / "reference/java"
    manifest_path = base / f"{profile}_build_manifest.json"
    manifest = read_json(manifest_path)
    if manifest["profile"] != profile or manifest["exit_code"] != 0:
        raise ValueError("accepted profile manifest identity/build mismatch")
    sources = base / f"{profile}_source"
    actual = {path.name: sha256(path) for path in sorted(sources.glob("*.java"))}
    if actual != manifest["source_hashes"]:
        raise ValueError("accepted Java profile source hashes mismatch")
    return {
        "profile": profile,
        "parameters": dict(PROFILES[profile], outer_iterations=500, alns_iterations=5000,
                           weight_lower=0.1, feasibility_guard=True, pre_alns_guard=False),
        "source_hashes": actual,
        "accepted_build_manifest_sha256": sha256(manifest_path),
        "official_source_lock_sha256": sha256(base / "SOURCE_LOCK.json"),
    }


def jdk_executable(java_home: Path, name: str, *, platform_name: str | None = None) -> Path:
    """Resolve a JDK tool once for POSIX and ordinary Windows JDK layouts."""
    if name not in ("java", "javac"):
        raise ValueError(f"unsupported JDK tool: {name}")
    platform_name = os.name if platform_name is None else platform_name
    if platform_name not in ("nt", "posix"):
        raise ValueError(f"unsupported platform name: {platform_name}")
    suffix = ".exe" if platform_name == "nt" else ""
    return java_home.resolve() / "bin" / f"{name}{suffix}"


def jdk_tools(java_home: Path) -> dict:
    java_home = java_home.resolve()
    result = {}
    for name in ("java", "javac"):
        path = jdk_executable(java_home, name)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"JDK executable missing: {path}")
        version = subprocess.run([str(path), "-version"], capture_output=True, text=True,
                                 timeout=15)
        output = (version.stdout + version.stderr).strip()
        if version.returncode or not re.search(r'(?:version\s+"?|javac\s+)17[.\s"]', output):
            raise ValueError(f"JDK 17 required: {name}: {output}")
        result[name] = {"path": str(path), "sha256": sha256(path), "version": output}
    return result


def prepare(source_root: Path, profile: str, java_home: Path, build_dir: Path) -> dict:
    identity = profile_identity(source_root, profile)
    jdk = jdk_tools(java_home)
    destination = build_dir.resolve() / profile
    manifest_path = destination / "BUILD_MANIFEST.json"
    if manifest_path.exists():
        old = read_json(manifest_path)
        if old.get("source_identity") != identity or old.get("jdk") != jdk:
            raise ValueError("existing build identity mismatch; use a new isolated build directory")
        verify_build(source_root, profile, java_home, build_dir)
        return old
    if destination.exists():
        raise ValueError("partial build directory exists; preserve it and use another build directory")
    snapshot = destination / "source_snapshot"
    classes = destination / "classes"
    snapshot.mkdir(parents=True)
    classes.mkdir()
    accepted = source_root / "reference/java" / f"{profile}_source"
    for name in identity["source_hashes"]:
        shutil.copy2(accepted / name, snapshot / name)
    command = [jdk["javac"]["path"], "-encoding", "UTF-8", "-d", str(classes)]
    command.extend(str(path) for path in sorted(snapshot.glob("*.java")))
    start = time.perf_counter()
    process = execute_process(command, destination, 60.0)
    (destination / "compile.stdout.log").write_text(process.pop("stdout"), encoding="utf-8")
    (destination / "compile.stderr.log").write_text(process.pop("stderr"), encoding="utf-8")
    class_hashes = {str(path.relative_to(classes)): sha256(path)
                    for path in sorted(classes.rglob("*.class"))}
    manifest = {"schema": "isolated_author_java_build_v1", "source_identity": identity,
                "jdk": jdk, "command": command, "process": process,
                "class_hashes": class_hashes,
                "elapsed_seconds": time.perf_counter() - start,
                "status": "ok" if process["exit_code"] == 0 and class_hashes else "error"}
    write_json(manifest_path, manifest)
    if manifest["status"] != "ok":
        raise ValueError(f"isolated Java compile failed; evidence retained at {destination}")
    verify_build(source_root, profile, java_home, build_dir)
    return manifest


def verify_build(source_root: Path, profile: str, java_home: Path, build_dir: Path) -> dict:
    destination = build_dir.resolve() / profile
    manifest = read_json(destination / "BUILD_MANIFEST.json")
    if manifest.get("source_identity") != profile_identity(source_root, profile):
        raise ValueError("build/source identity mismatch")
    if manifest.get("status") != "ok" or manifest.get("process", {}).get("exit_code") != 0:
        raise ValueError("build is not a successful compilation")
    if manifest.get("jdk") != jdk_tools(java_home):
        raise ValueError("JDK identity differs from the build")
    classes = destination / "classes"
    actual = {str(path.relative_to(classes)): sha256(path)
              for path in sorted(classes.rglob("*.class"))}
    if not actual or actual != manifest.get("class_hashes"):
        raise ValueError("compiled class hash mismatch")
    snapshot = destination / "source_snapshot"
    if {path.name: sha256(path) for path in snapshot.glob("*.java")} != manifest["source_identity"]["source_hashes"]:
        raise ValueError("build source snapshot mismatch")
    return manifest


def command_for(java: Path, instance: Path, seed: int, raw_output: Path,
                build_dir: Path, profile: str) -> list[str]:
    if type(seed) is not int or not -(1 << 63) <= seed < (1 << 63):
        raise ValueError("seed must fit Java's signed 64-bit Long")
    if profile not in PROFILES:
        raise ValueError("only J1b/J2b are eligible author profiles")
    return [str(java.resolve()), "-XX:ActiveProcessorCount=1", "-XX:+UseSerialGC",
            "-Xms32m", "-Xmx512m", f"-Drepro.instance={instance.resolve()}",
            f"-Drepro.seed={seed}", "-Drepro.seconds=0",
            f"-Drepro.output={raw_output.resolve()}", "-Drepro.guard=true", "-cp",
            str(build_dir.resolve() / profile / "classes"), "test1.Main"]


def execute_process(command: list[str], cwd: Path, timeout: float) -> dict:
    """Kill and reap on timeout; a saved partial best never becomes a valid anchor."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("positive finite timeout required")
    start = time.perf_counter()
    child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        child.kill()
        stdout, stderr = child.communicate()
    return {"command": command, "exit_code": child.returncode, "timed_out": timed_out,
            "elapsed_process_seconds": time.perf_counter() - start,
            "stdout": stdout, "stderr": stderr}


def audit_raw(instance, raw, source_root: Path, scorer_path: Path,
              source_latest_time: float | None = None) -> dict:
    """Retain raw invalid solutions; agreement and feasibility are separate fields."""
    _, evaluator, scorer = independent_modules(source_root, scorer_path)
    if not isinstance(raw, dict):
        raise ValueError("raw Java output must be an object")
    reported = raw.get("reference_reported_cost")
    if type(reported) not in (int, float) or not math.isfinite(reported):
        raise ValueError("raw Java cost must be finite")
    integrity = raw.get("reference_integrity_issues")
    if not isinstance(integrity, list) or any(not isinstance(x, str) for x in integrity):
        raise ValueError("raw Java integrity-issue field must be a string list")
    solution = {"schema_version": 1, "instance": instance.name,
                "instance_sha256": instance.sha256,
                "station_types": raw["station_types"], "routes": raw["routes"]}
    clock = scorer.score_solution(instance, solution)
    original = evaluator.evaluate(instance, solution)
    cost = clock.get("cost")
    errors = []
    if not original["feasible"] or not clock["original_feasible"]:
        errors.append("independent_infeasible")
    if integrity:
        errors.append("source_integrity_issue")
    if cost is None or abs(reported - cost) > COST_TOLERANCE:
        errors.append("source_cost_mismatch")
    if cost is None or original["cost"] is None or abs(original["cost"] - cost) > COST_TOLERANCE:
        errors.append("independent_cost_mismatch")
    if source_latest_time is None:
        errors.append("source_latest_time_missing")
    elif (not math.isfinite(source_latest_time) or clock["M_return"] is None
            or abs(source_latest_time - clock["M_return"]) > COST_TOLERANCE):
        errors.append("source_latest_time_mismatch")
    return {"solution": solution, "independent_audit": original, "return_score": clock,
            "source_reported_cost": reported, "source_integrity_issues": integrity,
            "source_reported_latest_time": source_latest_time,
            "source_objective_abs_error": None if cost is None else abs(reported - cost),
            "audit_errors": errors, "witness_passed": not errors}


def anchor_eligible(process: dict, audit: dict | None) -> bool:
    return (process.get("exit_code") == 0 and not process.get("timed_out", True)
            and audit is not None and audit.get("witness_passed") is True)


def run_one(instance_path: Path, profile: str, seed: int, output_dir: Path,
            source_root: Path, scorer_path: Path, java_home: Path,
            build_dir: Path, timeout: float) -> dict:
    start = time.perf_counter()
    instance_path, output_dir = instance_path.resolve(), output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.glob("RUN.json")) or (output_dir / "reference.json").exists():
        raise ValueError("run directory already contains a run; preserve it and use a fresh directory")
    source = profile_identity(source_root, profile)
    instance = validate_input(instance_path, source_root, scorer_path)
    build = verify_build(source_root, profile, java_home, build_dir)
    java = jdk_executable(java_home, "java")
    raw_path = output_dir / "reference.json"
    command = command_for(java, instance_path, seed, raw_path, build_dir, profile)
    record = {"schema": "single_author_anchor_run_v1", "profile": profile,
              "input_path": str(instance_path), "input_sha256": instance.sha256,
              "instance_name_is_display_only": instance.name, "seed": seed,
              "seed_selection": "supplied_prospectively; never_selected_by_cost_or_M",
              "source_identity": source, "build_manifest_sha256": sha256(build_dir.resolve() / profile / "BUILD_MANIFEST.json"),
              "class_hashes": build["class_hashes"], "java": build["jdk"]["java"],
              "runner_sha256": sha256(Path(__file__)),
              "independent_dependency_hashes": {str(path): sha256(path) for path in
                  (source_root / "lrphsd/problem.py", source_root / "lrphsd/evaluator.py", scorer_path)},
              "timeout_seconds": timeout, "command": command,
              "anchor_eligible": False, "status": "error", "artifacts": {}}
    audit = None
    try:
        process = execute_process(command, output_dir, timeout)
        stdout, stderr = process.pop("stdout"), process.pop("stderr")
        (output_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (output_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        record["process"] = process
        latest_values = re.findall(r"latest completion time:\s*([^\s]+)", stdout)
        latest = float(latest_values[-1]) if latest_values else None
        if raw_path.exists():
            record["artifacts"]["reference.json"] = sha256(raw_path)
            audit = audit_raw(instance, read_json(raw_path), source_root, scorer_path, latest)
            for key in ("solution", "independent_audit", "return_score"):
                target = output_dir / f"{key}.json"
                write_json(target, audit.pop(key))
                record["artifacts"][target.name] = sha256(target)
            record["witness_audit"] = audit
        else:
            record["missing_raw_output"] = True
        record["anchor_eligible"] = anchor_eligible(process, audit)
        record["status"] = ("ok" if record["anchor_eligible"] else
                            "timeout" if process["timed_out"] else "error")
    except Exception as error:
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
    for name in ("stdout.log", "stderr.log"):
        if (output_dir / name).exists():
            record["artifacts"][name] = sha256(output_dir / name)
    record["total_elapsed_seconds"] = time.perf_counter() - start
    write_json(output_dir / "RUN.json", record)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "plan", "run", "derive-seed"))
    parser.add_argument("--profile", choices=tuple(PROFILES), default="J1b")
    parser.add_argument("--instance", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seed-namespace")
    parser.add_argument("--input-sha256")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--scorer-path", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        if args.action == "derive-seed":
            print(seed_for_input(args.input_sha256 or "", args.seed_namespace or ""))
            return 0
        source_root = (args.source_root or source_root_default()).resolve()
        scorer_path = (args.scorer_path or scorer_default()).resolve()
        if args.build_dir is None or args.java_home is None:
            parser.error("--build-dir and --java-home are required")
        if args.action == "prepare":
            manifest = prepare(source_root, args.profile, args.java_home, args.build_dir)
            print(json.dumps({"profile": args.profile, "status": manifest["status"],
                              "class_count": len(manifest["class_hashes"])}))
            return 0
        if args.instance is None or args.seed is None or args.out is None:
            parser.error("--instance, --seed and --out are required for plan/run")
        if args.action == "plan":
            instance = validate_input(args.instance.resolve(), source_root, scorer_path)
            plan = {"schema": "author_anchor_plan_v1", "solver_executed": False,
                    "instance_sha256": instance.sha256, "seed": args.seed,
                    "source_identity": profile_identity(source_root, args.profile),
                    "command": command_for(jdk_executable(args.java_home, "java"), args.instance,
                        args.seed, args.out / "reference.json", args.build_dir, args.profile),
                    "timeout_seconds": args.timeout}
            args.out.mkdir(parents=True, exist_ok=True)
            write_json(args.out / "PLAN.json", plan)
            print(json.dumps(plan, sort_keys=True))
            return 0
        record = run_one(args.instance, args.profile, args.seed, args.out, source_root,
                         scorer_path, args.java_home, args.build_dir, args.timeout)
        print(json.dumps({key: record.get(key) for key in
                          ("profile", "status", "seed", "input_sha256", "anchor_eligible", "error")}))
        return 0 if record["anchor_eligible"] else 2
    except Exception as error:
        print(json.dumps({"status": "error", "error_type": type(error).__name__,
                          "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
