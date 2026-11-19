#!/usr/bin/env python3
"""Audit paper-level readiness without converting engineering evidence to science."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RETURN_MAKESPAN = ROOT.parent
LUNWEN = RETURN_MAKESPAN.parent.parent.parent
STATE = RETURN_MAKESPAN / "STATE.json"
CURRENT = ROOT / "current_release_audit_20261105/evidence/weather_current_release_audit_20261105.json"
FORMAL = ROOT / "formal_contracts_20261105/evidence/formal_contracts.json"
EMERGENCY_ROOT = LUNWEN / "audit/wind_ccfb_20261104/engineering/emergency"
EMERGENCY = EMERGENCY_ROOT / "evidence/emergency_release_audit_station_domain_20261104.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def audit() -> dict:
    current = load(CURRENT)
    formal = load(FORMAL)
    emergency = load(EMERGENCY)
    state = load(STATE)

    require(current.get("schema") == "weather_current_release_audit_v1", "current audit schema")
    require(current.get("status") == "PASS", "current weather release audit is not passing")
    require(formal.get("schema") == "formal_contracts_v1", "formal receipt schema")
    require(formal.get("status") == "PASS" and formal.get("check_count", 0) >= 2178,
            "formal receipt is below the current contract floor")
    require(emergency.get("schema") == "emergency_release_audit_v1", "emergency audit schema")
    require(emergency.get("status") == "PASS", "emergency release audit is not passing")
    require(emergency.get("smoke", {}).get("rows") == 120, "emergency smoke matrix is not 120 rows")
    require(emergency.get("boundary", {}).get("cases") == 13, "emergency boundary matrix is not 13 cases")
    require(emergency.get("paired_descriptive", {}).get("pairs") == 40,
            "emergency paired descriptive matrix is not 40 pairs")
    require(emergency.get("active_module_sha256") == current.get("current_source_sha256", {}).get("emergency_scenario.py"),
            "weather and emergency receipts do not bind the same emergency source")
    phase = emergency.get("station_action_domain_transaction")
    require(isinstance(phase, dict)
            and phase.get("modified_sha256") == emergency.get("active_module_sha256"),
            "emergency station-action-domain transaction does not bind the active source")
    emergency_bundle = emergency.get("windows_bundle")
    require(isinstance(emergency_bundle, dict)
            and emergency_bundle.get("files") == 60
            and emergency_bundle.get("active_module_sha256") == emergency.get("active_module_sha256"),
            "emergency hash-bound replay bundle is incomplete")
    weather_cross = current.get("emergency_cross_contract")
    require(isinstance(weather_cross, dict)
            and isinstance(weather_cross.get("windows_bundle"), dict)
            and weather_cross["windows_bundle"].get("sha256") == emergency_bundle.get("sha256"),
            "weather and emergency receipts disagree on the replay bundle")

    blockers = []
    if not state.get("rl_superiority_proven"):
        blockers.append({
            "gate": "G4",
            "reason": "No complete candidate and no demonstrated improvement over author and strongest same-objective non-RL control.",
            "evidence": "STATE.json:gates.G4; STATE.json:weather_v3_development",
        })
    if not state.get("innovation_experimentally_proven"):
        blockers.append({
            "gate": "G0/G6",
            "reason": "No mechanism was approved as distinct algorithmic novelty; ablation gate has not started.",
            "evidence": "STATE.json:g0_candidate; STATE.json:gates.G6",
        })
    if not state.get("paper_writing_enabled"):
        blockers.append({
            "gate": "G7/G8",
            "reason": "Paper-writing and clean-package gates remain closed.",
            "evidence": "STATE.json:paper_writing_enabled; STATE.json:gates.G7; STATE.json:gates.G8",
        })
    if state.get("current_gate") == "P3_NO_PPO_OR_VAL_DUE_TRAIN_FEASIBILITY_FAILURE":
        blockers.append({
            "gate": "P3",
            "reason": "Fixed-population common-BC feasibility gate failed before PPO/VAL; diagnostic replay did not reopen it.",
            "evidence": "STATE.json:P3_fixed_population; STATE.json:current_gate",
        })

    source_hashes = current.get("current_source_sha256", {})
    active_core = {
        "weather_oracle.py": source_hashes.get("weather_oracle.py"),
        "weather_replay.py": source_hashes.get("weather_replay.py"),
        "weather_full_map.py": source_hashes.get("weather_full_map.py"),
        "emergency_scenario.py": source_hashes.get("emergency_scenario.py"),
    }
    theorem_contracts = [
        {
            "id": "T1",
            "claim": "Piecewise-constant wind straight-leg integration is exact under the declared fixed-airspeed model.",
            "witness": "weather_oracle.py:_integrate_leg; weather_replay.py:_integrate",
            "scope": "finite knots, no waiting, one straight segment at a time",
        },
        {
            "id": "T2",
            "claim": "The visibility search is finite and deterministic under the no-wait/no-cycle simple-path contract.",
            "witness": "weather_oracle.py:plan_route; weather_replay.py:replay_route",
            "scope": "endpoint plus convex-NFZ-vertex graph; stable (arrival, distance, path) tie-break",
        },
        {
            "id": "T3",
            "claim": "Strict-interior NFZ overlap is rejected only when the integrated time interval overlaps the half-open active interval.",
            "witness": "weather_oracle.py:_inside_distance_interval; weather_replay.py:_strict_interior_distances",
            "scope": "convex polygon, boundary/tangent legs legal, active interval [on, off)",
        },
        {
            "id": "T4",
            "claim": "Weather observations expose only the declared causal frontier and the independent replay checks terminal route admissibility.",
            "witness": "weather_full_map.py:observation/step/replay_weather_solution; formal_contracts_20261105/evidence/formal_contracts.json",
            "scope": "fixed outer station/ownership contract; no claim of generalization",
        },
        {
            "id": "T5",
            "claim": "Emergency events have deterministic ordering and account only the executed finite-horizon position, energy, duty, and cost prefix.",
            "witness": "emergency_scenario.py:EmergencySimulator._accrue_event/_handle_event; PHASE_ACCOUNTING_PROOF.md; phase-accounting transaction",
            "scope": "finite drones/tasks, bounded waits, declared piecewise-constant trace, terminal failure stops a drone",
        },
        {
            "id": "T6",
            "claim": "Emergency rates use an explicit fixed denominator, including a null zero-emergency denominator.",
            "witness": "emergency_scenario.py:result; emergency_boundary_suite_release_20261105.json",
            "scope": "multiple emergency tasks, exact deadline, late delivery, zero-emergency case",
        },
        {
            "id": "T7",
            "claim": "Fixed station ownership is preserved by the ranking baselines, and action masks exclude busy, terminal, horizon, and invalid-index actions.",
            "witness": "STATION_ACTION_DOMAIN_PROOF.md; verify_station_action_domain.py; station-action-domain transaction",
            "scope": "2-4 fixed stations, normal/reversed task order, three baselines; bounded event model",
        },
    ]

    allowed = [
        "A deterministic synthetic weather/NFZ engineering environment with bounded contract evidence.",
        "Exactness and causal-frontier claims within the explicitly declared finite-domain model.",
        "A reproducible emergency event simulator with 120 smoke rows, 13 boundary cases, finite-horizon phase-accounting, and fixed-station action-domain witnesses.",
    ]
    prohibited = [
        "RL superiority over the author solution or strongest same-objective non-RL control.",
        "Distinct algorithmic novelty or a new metric novelty claim.",
        "Real-weather calibration, confirmation-set statistical power, or real-flight safety.",
        "A completed manuscript or G7/G8 publication readiness.",
    ]
    return {
        "schema": "paper_readiness_audit_v1",
        "status": "NOT_READY_FOR_CLAIMED_RL_PAPER" if blockers else "READY_FOR_CLAIM_REVIEW",
        "engineering_readiness": {
            "status": "PASS",
            "current_release_receipt": str(CURRENT),
            "formal_checks": formal["check_count"],
            "emergency_smoke_rows": emergency["smoke"]["rows"],
            "emergency_boundary_cases": emergency["boundary"]["cases"],
            "emergency_paired_scenarios": emergency["paired_descriptive"]["pairs"],
            "emergency_station_action_domain_transaction": phase["modified_sha256"],
            "emergency_windows_bundle": emergency_bundle,
            "v15_bundle": current["windows_bundle"],
        },
        "scientific_readiness": {
            "status": "NO_GO",
            "blockers": blockers,
            "state_status": state.get("status"),
            "current_gate": state.get("current_gate"),
        },
        "active_core_source_sha256": active_core,
        "bounded_theorem_contracts": theorem_contracts,
        "allowed_claims": allowed,
        "prohibited_claims": prohibited,
        "required_next_scientific_gate": (
            "Register a distinct non-rescue protocol with fixed train/validation populations, "
            "at least three independent seeds, author and strongest same-objective non-RL controls, "
            "complete-candidate accounting, and predeclared statistical analysis before any new run."
        ),
        "interpretation": (
            "Engineering PASS is evidence of implementation integrity only. The current state "
            "does not support a positive RL, novelty, generalization, or flight-safety conclusion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent / "evidence/paper_readiness_audit_20261105.json")
    args = parser.parse_args()
    try:
        receipt = audit()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"PAPER_READINESS_AUDIT=FAIL: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PAPER_READINESS_STATUS={receipt['status']}")
    print(f"PAPER_READINESS_JSON={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
