#!/usr/bin/env python3
"""Turn a verified static author witness into a weather-domain anchor receipt."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[3]
for candidate in (PACKAGE, ROOT / "reproduction/reviewer_package_semfix", PACKAGE.parent):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from lrphsd.problem import read_instance
from scorer import CostAnchor
from weather_full_map import replay_weather_solution
from weather_scenario_io import load_weather_scenario


SCHEMA = "weather_author_anchor_preflight_v1"
AUTHOR_RUN_SCHEMA = "single_author_anchor_run_v1"
PRIMARY_AUTHOR_PROFILE = "J1b"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_json(raw: str):
    def reject_constant(token):
        raise ValueError(f"non-finite JSON value: {token}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)


def _read_json(path: Path):
    return _parse_json(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_author_runner():
    path = PACKAGE.parent / "g23/author_baseline/author_runner.py"
    if not path.is_file():
        raise ValueError(f"bundled author runner is missing: {path}")
    spec = importlib.util.spec_from_file_location("weather_anchor_author_runner", path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, path


def _exact_json(path: Path, expected, label: str) -> None:
    actual_canonical = json.dumps(_read_json(path), sort_keys=True, separators=(",", ":"), allow_nan=False)
    normalized = _parse_json(json.dumps(expected, allow_nan=False))
    expected_canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if actual_canonical != expected_canonical:
        raise ValueError(f"{label} does not match the independently reconstructed author witness")


def _verify_author_run(instance_path: Path, author_run_dir: Path):
    """Verify all locally available G23 evidence before using an author anchor.

    This cannot make an unsigned local filesystem a cryptographic attestation.
    It does prevent a minimal hand-written eligibility JSON or a substituted
    feasible route from being treated as a G23 author result: source/build/JDK,
    command, raw witness, dual scores, stdout clock and every artifact are
    rechecked against the current frozen runner.
    """
    runner, runner_path = _load_author_runner()
    source_root = ROOT / "reproduction/reviewer_package_semfix"
    scorer_path = PACKAGE.parent / "scorer.py"
    instance = runner.validate_input(instance_path, source_root, scorer_path)
    run_path = author_run_dir / "RUN.json"
    run = _read_json(run_path)
    required = {"schema", "profile", "input_path", "input_sha256", "seed", "source_identity",
                "build_manifest_sha256", "class_hashes", "java", "runner_sha256",
                "independent_dependency_hashes", "timeout_seconds", "command", "process",
                "anchor_eligible", "status", "artifacts", "witness_audit"}
    missing = required - set(run)
    if missing:
        raise ValueError(f"author RUN.json lacks required provenance fields: {sorted(missing)}")
    if run["schema"] != AUTHOR_RUN_SCHEMA or run["profile"] != PRIMARY_AUTHOR_PROFILE:
        raise ValueError("author RUN.json schema/profile is not the frozen J1b primary profile")
    if run["status"] != "ok" or run["anchor_eligible"] is not True:
        raise ValueError("author run is not an eligible static anchor")
    if Path(run["input_path"]).resolve() != instance_path:
        raise ValueError("author run input path does not match the supplied map")
    timeout = run["timeout_seconds"]
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not (0 < timeout <= 300):
        raise ValueError("author run timeout is outside the frozen preflight range")
    if run["input_sha256"] != instance.sha256:
        raise ValueError("author run input SHA-256 does not match the supplied map")
    if run["runner_sha256"] != _sha256(runner_path):
        raise ValueError("author run was not made by this frozen author runner")
    expected_identity = runner.profile_identity(source_root, PRIMARY_AUTHOR_PROFILE)
    if run["source_identity"] != expected_identity:
        raise ValueError("author run Java source/profile identity mismatch")
    expected_dependencies = {str(path): _sha256(path) for path in
                             (source_root / "lrphsd/problem.py", source_root / "lrphsd/evaluator.py", scorer_path)}
    if run["independent_dependency_hashes"] != expected_dependencies:
        raise ValueError("author run independent scorer dependency identity mismatch")
    process = run["process"]
    if not isinstance(process, dict) or process.get("exit_code") != 0 or process.get("timed_out") is not False:
        raise ValueError("author process was not an on-time successful invocation")
    java_record = run.get("java")
    if not isinstance(java_record, dict):
        raise ValueError("author run Java receipt is malformed")
    java_path = Path(java_record.get("path", ""))
    if not java_path.is_file() or not re.fullmatch(r"java(?:\.exe)?", java_path.name, re.IGNORECASE):
        raise ValueError("author run Java executable path is invalid or unavailable")
    java_home = java_path.parent.parent
    jdk = runner.jdk_tools(java_home)
    if java_record != jdk["java"]:
        raise ValueError("author run JDK receipt does not match the current JDK")
    classpath = None
    command = run["command"]
    if not isinstance(command, list) or process.get("command") != command:
        raise ValueError("author process command record is missing or inconsistent")
    if "-cp" in command:
        index = command.index("-cp")
        if index + 1 < len(command):
            classpath = Path(command[index + 1])
    if classpath is None or classpath.name != "classes" or classpath.parent.name != PRIMARY_AUTHOR_PROFILE:
        raise ValueError("author command does not reference the isolated J1b class directory")
    build_dir = classpath.parent.parent
    expected_command = runner.command_for(java_path, instance_path, run["seed"],
                                          author_run_dir / "reference.json", build_dir, PRIMARY_AUTHOR_PROFILE)
    if command != expected_command:
        raise ValueError("author command differs from the frozen input/seed/output invocation")
    build_manifest = build_dir / PRIMARY_AUTHOR_PROFILE / "BUILD_MANIFEST.json"
    if not build_manifest.is_file() or run["build_manifest_sha256"] != _sha256(build_manifest):
        raise ValueError("author build manifest is missing or mismatched")
    build = runner.verify_build(source_root, PRIMARY_AUTHOR_PROFILE, java_home, build_dir)
    if run["class_hashes"] != build["class_hashes"]:
        raise ValueError("author class hashes do not match the verified isolated build")
    names = {"reference.json", "solution.json", "independent_audit.json", "return_score.json", "stdout.log", "stderr.log"}
    if set(run["artifacts"]) != names:
        raise ValueError("author run artifact set is incomplete or unexpected")
    for name in names:
        path = author_run_dir / name
        if not path.is_file() or run["artifacts"][name] != _sha256(path):
            raise ValueError(f"author artifact hash mismatch: {name}")
    stdout = (author_run_dir / "stdout.log").read_text(encoding="utf-8")
    values = re.findall(r"latest completion time:\s*([^\s]+)", stdout)
    if not values:
        raise ValueError("author stdout does not contain a latest completion time")
    latest_literal = values[-1]
    latest = float(latest_literal)
    raw = _read_json(author_run_dir / "reference.json")
    audit = runner.audit_raw(instance, raw, source_root, scorer_path, latest)
    expected_solution = audit.pop("solution")
    expected_independent = audit.pop("independent_audit")
    expected_return = audit.pop("return_score")
    _exact_json(author_run_dir / "solution.json", expected_solution, "solution.json")
    _exact_json(author_run_dir / "independent_audit.json", expected_independent, "independent_audit.json")
    _exact_json(author_run_dir / "return_score.json", expected_return, "return_score.json")
    if run["witness_audit"] != audit or not runner.anchor_eligible(process, audit):
        raise ValueError("author witness audit does not support anchor eligibility")
    # A complete record can still be hand-authored on a mutable filesystem. Run
    # the hash-locked Java profile again and require its raw witness and printed
    # source clock to reproduce the retained author result before admission.
    with tempfile.TemporaryDirectory(prefix="weather_author_reverify_") as temporary:
        replay_dir = Path(temporary)
        replay_raw = replay_dir / "reference.json"
        replay_command = runner.command_for(java_path, instance_path, run["seed"], replay_raw,
                                            build_dir, PRIMARY_AUTHOR_PROFILE)
        replay_process = runner.execute_process(replay_command, replay_dir, float(timeout))
        if replay_process.get("exit_code") != 0 or replay_process.get("timed_out") or not replay_raw.is_file():
            raise ValueError("independent re-execution of the author profile did not produce a raw reference")
        replay_values = re.findall(r"latest completion time:\s*([^\s]+)", replay_process["stdout"])
        if not replay_values or replay_values[-1] != latest_literal:
            raise ValueError("independent re-execution source clock differs from the retained author result")
        if _sha256(replay_raw) != _sha256(author_run_dir / "reference.json"):
            raise ValueError("independent re-execution raw author reference differs from the retained result")
    return instance, expected_solution, run


def prepare_author_weather_anchor(instance_path: Path, author_run_dir: Path, scenario_path: Path) -> dict:
    instance_path, author_run_dir, scenario_path = (Path(value).resolve()
                                                     for value in (instance_path, author_run_dir, scenario_path))
    instance, solution, run = _verify_author_run(instance_path, author_run_dir)
    run_path, solution_path = author_run_dir / "RUN.json", author_run_dir / "solution.json"
    scenario, scenario_receipt = load_weather_scenario(scenario_path, expected_instance_sha256=instance.sha256)
    anchor = CostAnchor.from_solution(instance, solution)
    uncapped = replay_weather_solution(instance, anchor, scenario, solution, strict_weather_cap=False)
    if not uncapped["admissible"]:
        raise ValueError(f"author solution is weather-infeasible: {uncapped['issues']}")
    weather_cost_cap = uncapped["weather_cost"]
    replay = replay_weather_solution(instance, anchor, scenario, solution, weather_cost_cap=weather_cost_cap)
    if not replay["admissible"]:
        raise AssertionError(f"weather replay failed its own measured cap: {replay['issues']}")
    return {"schema": SCHEMA, "status": "eligible", "instance_path": str(instance_path),
            "instance_sha256": instance.sha256, "author_run_path": str(author_run_dir),
            "author_run_sha256": _sha256(run_path), "author_solution_sha256": _sha256(solution_path),
            "scenario": scenario_receipt, "fixed_outer_anchor_cost": anchor.cost,
            "weather_cost_cap": weather_cost_cap, "author_weather_replay": replay,
            "comparison_boundary": "This receipt authorizes only fixed-outer weather-domain candidate admission; it is not a quality comparison result."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--author-run", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.out.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    try:
        receipt = prepare_author_weather_anchor(args.instance, args.author_run, args.scenario)
        _write_json(output / "AUTHOR_WEATHER_ANCHOR.json", receipt)
        print(json.dumps({"status": receipt["status"], "receipt": str(output / "AUTHOR_WEATHER_ANCHOR.json")}, sort_keys=True))
        return 0
    except Exception as error:
        _write_json(output / "AUTHOR_WEATHER_ANCHOR_ERROR.json", {"schema": SCHEMA, "status": "error",
                    "error_type": type(error).__name__, "error": str(error)})
        print(json.dumps({"status": "error", "error_type": type(error).__name__, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
