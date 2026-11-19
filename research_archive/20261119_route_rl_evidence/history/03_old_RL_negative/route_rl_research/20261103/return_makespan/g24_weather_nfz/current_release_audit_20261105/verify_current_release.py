#!/usr/bin/env python3
"""Create a current-source engineering release receipt for weather/NFZ work.

The receipt binds the current weather implementation to its bounded formal
contracts, the hardening transaction, the emergency cross-contract, and a
payload-identical Windows smoke bundle. It is an engineering integrity gate,
not evidence of route-quality, RL superiority, or flight safety.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile


AUDIT_ROOT = Path(__file__).resolve().parent
WEATHER = AUDIT_ROOT.parent
RETURN_MAKESPAN = WEATHER.parent
LUNWEN = RETURN_MAKESPAN.parents[2]
EMERGENCY = LUNWEN / "audit/wind_ccfb_20261104/engineering/emergency"
FORMAL = WEATHER / "formal_contracts_20261105/evidence/formal_contracts.json"
HARDENING = WEATHER / "weather_hardening_20261105"
DEFAULT_BUNDLE = WEATHER / "route_rl_windows_cpu_bundle_20261105_v15.zip"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(result, dict):
        raise ValueError(f"JSON object required: {path}")
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def run_checked(name: str, command: list[str], *, cwd: Path, env: dict[str, str], log_root: Path) -> dict:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = f"[stdout]\n{completed.stdout}\n[stderr]\n{completed.stderr}"
    log_path = log_root / f"{name}.log"
    log_path.write_text(output, encoding="utf-8")
    result = {
        "command": command,
        "cwd": str(cwd),
        "exit_status": completed.returncode,
        "log": str(log_path),
        "log_sha256": sha256(log_path),
    }
    require(completed.returncode == 0, f"{name} failed; inspect {log_path}")
    return result


def run_current_commands(log_root: Path) -> dict:
    environment = os.environ.copy()
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "CUDA_VISIBLE_DEVICES": ""})
    commands = {}
    commands["unit_regression"] = run_checked(
        "unit_regression",
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=WEATHER,
        env=environment,
        log_root=log_root,
    )
    text = Path(commands["unit_regression"]["log"]).read_text(encoding="utf-8")
    match = re.search(r"Ran (\d+) tests", text)
    require(match is not None and int(match.group(1)) >= 70,
            "unit regression did not report the current 70-test floor")
    commands["unit_regression"]["tests"] = int(match.group(1))

    commands["formal_contracts"] = run_checked(
        "formal_contracts",
        [sys.executable, "formal_contracts_20261105/verify_contracts.py"],
        cwd=WEATHER,
        env=environment,
        log_root=log_root,
    )
    commands["weather_hardening"] = run_checked(
        "weather_hardening",
        [sys.executable, "weather_hardening_20261105/test_hardening.py"],
        cwd=WEATHER,
        env={
            **environment,
            "ORACLE_MODULE": str(HARDENING / "MODIFIED_FILE/weather_oracle.py"),
            "REPLAY_MODULE": str(HARDENING / "MODIFIED_FILE/weather_replay.py"),
        },
        log_root=log_root,
    )
    commands["weather_rollback"] = run_checked(
        "weather_rollback",
        [str(HARDENING / "transaction/ROLLBACK.sh")],
        cwd=WEATHER,
        env=environment,
        log_root=log_root,
    )
    commands["emergency_release"] = run_checked(
        "emergency_release",
        [sys.executable, "verify_emergency_release.py"],
        cwd=EMERGENCY,
        env=environment,
        log_root=log_root,
    )
    return commands


def source_hashes() -> dict[str, str]:
    return {
        "weather_oracle.py": sha256(WEATHER / "weather_oracle.py"),
        "weather_replay.py": sha256(WEATHER / "weather_replay.py"),
        "weather_full_map.py": sha256(WEATHER / "weather_full_map.py"),
        "emergency_scenario.py": sha256(EMERGENCY / "MODIFIED_FILE/emergency_scenario.py"),
    }


def verify_formal(current: dict[str, str]) -> dict:
    receipt = load_json(FORMAL)
    require(receipt.get("schema") == "formal_contracts_v1", "unexpected formal-contract schema")
    require(receipt.get("status") == "PASS", "formal contracts are not passing")
    require(receipt.get("source_sha256") == current,
            "formal-contract receipt source hashes do not match current source")
    count = receipt.get("check_count")
    require(isinstance(count, int) and count >= 2178,
            "formal-contract receipt has fewer than the 2,178 current checks")
    require(receipt.get("weather", {}).get("direct_cases") == 160,
            "formal-contract weather direct-case matrix differs")
    require(receipt.get("emergency", {}).get("runs") == 120,
            "formal-contract emergency matrix differs")
    require(receipt.get("emergency", {}).get("phase_accounting_scenarios") == 4,
            "formal-contract receipt lacks phase-accounting scenarios")
    return {"receipt": str(FORMAL), "check_count": count,
            "phase_accounting_scenarios": 4}


def verify_hardening(current: dict[str, str]) -> dict:
    verification = HARDENING / "transaction/VERIFICATION.txt"
    content = verification.read_text(encoding="utf-8")
    require(f"MODIFIED_SHA256=weather_oracle.py:{current['weather_oracle.py']}" in content,
            "weather hardening verification does not bind current weather_oracle.py")
    # The original hardening receipt is retained as historical evidence. The
    # independent replay boundary correction has its own transaction below.
    historical_replay = re.search(r"MODIFIED_SHA256=weather_replay.py:([0-9a-f]{64})", content)
    require(historical_replay is not None,
            "weather hardening verification lacks historical replay hash")
    rollback = HARDENING / "transaction/ROLLBACK.sh"
    require(rollback.is_file() and os.access(rollback, os.X_OK),
            "weather hardening rollback script is missing or not executable")
    require("ROLLBACK_RESULT=BASELINE_BEHAVIOR_RESTORED" in content,
            "weather hardening verification lacks rollback behavior")
    return {"verification": str(verification), "rollback": str(rollback),
            "historical_replay_modified_sha256": historical_replay.group(1)}


def verify_replay_hardening(current: dict[str, str]) -> dict:
    root = WEATHER / "weather_replay_boundary_hardening_20261105"
    verification = root / "transaction/VERIFICATION.txt"
    rollback = root / "transaction/ROLLBACK.sh"
    content = verification.read_text(encoding="utf-8")
    require(f"MODIFIED_SHA256=weather_replay.py:{current['weather_replay.py']}" in content,
            "replay boundary verification does not bind current weather_replay.py")
    require("BASELINE_EXIT_STATUS=1" in content and "MODIFIED_EXIT_STATUS=0" in content,
            "replay boundary verification lacks red-to-green evidence")
    require("ROLLBACK_RESULT=BASELINE_BEHAVIOR_RESTORED" in content,
            "replay boundary verification lacks rollback behavior")
    require(rollback.is_file() and os.access(rollback, os.X_OK),
            "replay boundary rollback script is missing or not executable")
    return {"verification": str(verification), "rollback": str(rollback)}


def verify_cross_oracle_boundaries() -> dict:
    """Check exact-zero and positive-sub-epsilon legs in both route engines."""
    if str(WEATHER) not in sys.path:
        sys.path.insert(0, str(WEATHER))
    import weather_oracle
    import weather_replay

    wind = weather_oracle.WindField((weather_oracle.WindKnot(0.0, 0.0, 0.0),))
    flight = weather_oracle.FlightParams(speed=900.0, flight_energy=0.018)
    start = weather_oracle.Point(0.0, 0.0)
    tiny = weather_oracle.Point(5e-10, 0.0)
    primary_zero = weather_oracle.integrate_leg(start, start, 0.0, wind, flight)
    replay_zero = weather_replay.replay_route(start, start, 0.0, wind, flight)
    primary_tiny = weather_oracle.integrate_leg(start, tiny, 0.0, wind, flight)
    replay_tiny = weather_replay.replay_route(start, tiny, 0.0, wind, flight)
    require(primary_zero.arrival_time_s == replay_zero.arrival_s == 0.0,
            "exact-zero leg diverges between primary and replay")
    require(replay_tiny.legal and primary_tiny.arrival_time_s is not None,
            "positive sub-EPS leg was rejected")
    require(math.isclose(primary_tiny.arrival_time_s, replay_tiny.arrival_s, rel_tol=0.0, abs_tol=1e-15),
            "positive sub-EPS leg arrival diverges between primary and replay")
    require(math.isclose(primary_tiny.energy, replay_tiny.energy, rel_tol=0.0, abs_tol=1e-18),
            "positive sub-EPS leg energy diverges between primary and replay")
    return {"exact_zero": "matched", "positive_sub_eps": "matched", "distance_m": 5e-10}


def verify_emergency(current: dict[str, str]) -> dict:
    receipt_path = EMERGENCY / "evidence/emergency_release_audit_station_domain_20261104.json"
    receipt = load_json(receipt_path)
    require(receipt.get("schema") == "emergency_release_audit_v1", "unexpected emergency-audit schema")
    require(receipt.get("status") == "PASS", "emergency release audit is not passing")
    require(receipt.get("active_module_sha256") == current["emergency_scenario.py"],
            "emergency release audit does not bind current emergency source")
    formal = receipt.get("cross_module_formal")
    require(isinstance(formal, dict) and formal.get("checks", 0) >= 2190,
            "emergency audit does not bind the current formal-contract floor")
    phase = receipt.get("station_action_domain_transaction")
    require(isinstance(phase, dict)
            and phase.get("modified_sha256") == current["emergency_scenario.py"],
            "emergency audit lacks the current station-action-domain transaction")
    bundle = receipt.get("windows_bundle")
    require(isinstance(bundle, dict)
            and bundle.get("active_module_sha256") == current["emergency_scenario.py"]
            and bundle.get("files") == 60,
            "emergency audit lacks the current hash-bound Windows replay bundle")
    bundle_path = Path(bundle.get("path", ""))
    require(bundle_path.is_file() and bundle.get("sha256") == sha256(bundle_path),
            "emergency audit Windows replay bundle no longer matches its receipt")
    return {"receipt": str(receipt_path), "active_module_sha256": receipt["active_module_sha256"],
            "phase_accounting_transaction": phase["modified_sha256"],
            "windows_bundle": bundle}


def verify_bundle(bundle_path: Path) -> dict:
    if str(WEATHER) not in sys.path:
        sys.path.insert(0, str(WEATHER))
    import build_windows_bundle as bundle

    require(bundle_path.is_file(), f"bundle is missing: {bundle_path}")
    internal = bundle.verify_archive(bundle_path)
    with zipfile.ZipFile(bundle_path) as archive:
        archived = json.loads(archive.read("lunwen/WINDOWS_BUNDLE_MANIFEST.json"))
    live = bundle.manifest_for(bundle.project_files())
    require(archived.get("manifest_sha256") == live.get("manifest_sha256"),
            "bundle payload does not match the current source closure")
    require(archived.get("manifest_sha256") == internal.get("manifest_sha256"),
            "bundle internal verification disagrees with its manifest")
    return {
        "path": str(bundle_path.resolve()),
        "archive_sha256": sha256(bundle_path),
        "manifest_sha256": internal["manifest_sha256"],
        "payload_files": internal["file_count"],
    }


def audit(bundle_path: Path, commands: dict | None) -> dict:
    current = source_hashes()
    return {
        "schema": "weather_current_release_audit_v1",
        "status": "PASS",
        "current_source_sha256": current,
        "formal_contracts": verify_formal(current),
        "weather_hardening": verify_hardening(current),
        "weather_replay_boundary_hardening": verify_replay_hardening(current),
        "cross_oracle_boundaries": verify_cross_oracle_boundaries(),
        "emergency_cross_contract": verify_emergency(current),
        "windows_bundle": verify_bundle(bundle_path),
        "commands": commands,
        "interpretation": (
            "current-source implementation integrity only; no registered-map, route-quality, "
            "RL-superiority, confirmation-set, or real-flight-safety claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--run-commands", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=AUDIT_ROOT / "evidence/weather_current_release_audit_20261105.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        commands = run_current_commands(args.output.parent) if args.run_commands else None
        receipt = audit(args.bundle.resolve(), commands)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"WEATHER_CURRENT_RELEASE_AUDIT=FAIL: {error}")
        return 1
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WEATHER_CURRENT_RELEASE_AUDIT=PASS")
    print(f"WEATHER_CURRENT_RELEASE_AUDIT_JSON={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
