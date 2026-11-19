"""Qualify recorded routes without repairing or relabelling their origin.

This interface qualifies an engineering witness, not a scientific G3 batch.
The source manifest must be independently verified against the frozen build.
"""
from __future__ import annotations

import hashlib
import json
import math

from . import wind_scorer as scorer


IDENTITIES = {
    "AUTHOR_OUTPUT_RESCORED": "J1b_original",
    "AUTHOR_ALGORITHM_WIND_ADAPTED": "J1b_constant_wind_v1",
    "AUTHOR_ALGORITHM_WIND_ADAPTED_TERMINATION_FIXED": "J1b_constant_wind_single_station_guard_v1",
    "AUTHOR_ALGORITHM_WIND_ADAPTED_FINAL_RECORD_FIXED": "J1b_constant_wind_final_record_v1",
    "REPAIRED_COMMON_ANCHOR": "explicit_repair",
}
TIMED_PHASES = (
    "input_decode", "wind_setup", "spawn", "solve", "read_output",
    "source_audit", "wind_audit", "serialize",
)


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def _digest(x):
    return isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x)


def budget_verdict(record):
    """Total output-ready wall clock, including verification and serialization.

    Frozen build preparation and common-anchor generation are separately charged
    by a future scientific protocol. Their absence never means zero cost.
    """
    issues = []
    if not isinstance(record, dict):
        return {"qualified": False, "issues": ["timing_record_missing"]}
    budget, ready = record.get("budget_s"), record.get("output_ready_s")
    if type(budget) not in (int, float) or budget not in (6, 12):
        issues.append("budget_not_frozen_6_or_12")
    if not _number(ready) or ready < 0:
        issues.append("output_ready_time_invalid")
    elif _number(budget) and ready > budget:
        issues.append("output_ready_after_budget")
    if record.get("exit_status") != 0 or type(record.get("exit_status")) is not int:
        issues.append("process_exit_nonzero_or_missing")
    if record.get("timed_out") is not False:
        issues.append("process_timed_out_or_missing")
    if record.get("fallback_used") is not False:
        issues.append("fallback_or_missing")
    phases = record.get("phases")
    if not isinstance(phases, list) or len(phases) != len(TIMED_PHASES):
        issues.append("timing_phases_missing")
    else:
        previous = 0.0
        for phase, name in zip(phases, TIMED_PHASES):
            if not isinstance(phase, dict):
                issues.append("timing_phase_format")
                break
            start, end = phase.get("start_s"), phase.get("end_s")
            if (phase.get("name") != name or not _number(start) or not _number(end)
                    or start != previous or end < start):
                issues.append("timing_order_or_gap")
                break
            previous = end
        if previous != ready:
            issues.append("timing_ready_mismatch")
    return {"qualified": not issues, "issues": issues, "budget_s": budget,
            "output_ready_s": ready}


def qualify_output(instance, raw_bytes, record, *, wind, verified_source_manifest):
    """Keep source-score agreement separate from target-wind feasibility.

    The original reported cost is checked in its *source* physics. It need not
    equal the independently rescored cost in the requested wind. No repair,
    task deletion, station reassignment or slot reassignment occurs here.
    """
    issues = []
    out = {"schema": "fixed_wind_author_anchor_qualification_v1",
           "anchor_identity": record.get("anchor_identity"),
           "run_role": record.get("run_role"),
           "source_record_qualified": False, "wind_witness_qualified": False,
           "scientific_G3_qualified": False,
           "primary_C_Liu_replacement_authorized": False,
           "issued_cost_anchor": None, "issues": issues}
    kind = record.get("anchor_identity")
    expected_profile = IDENTITIES.get(kind)
    manifest = verified_source_manifest
    if (expected_profile is None or not isinstance(manifest, dict)
            or manifest.get("identity") != expected_profile
            or record.get("source_manifest_sha256") != scorer.identity(manifest)
            or record.get("source_hashes") != manifest.get("source_hashes")
            or not manifest.get("source_hashes")
            or not manifest.get("class_hashes")):
        issues.append("source_identity_or_manifest_mismatch")
    if record.get("instance_sha256") != instance.sha256:
        issues.append("record_instance_hash_mismatch")
    if record.get("parameter_sha256") != scorer.parameter_identity(instance):
        issues.append("record_parameter_hash_mismatch")
    if not isinstance(raw_bytes, bytes):
        issues.append("raw_output_bytes_required")
        return dict(out, status="SOURCE_RECORD_REJECTED")
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    out["raw_output_sha256"] = raw_sha256
    if record.get("raw_output_sha256") != raw_sha256:
        issues.append("raw_output_hash_mismatch")
    if kind == "REPAIRED_COMMON_ANCHOR":
        if not all(_digest(record.get(k)) for k in
                   ("parent_artifact_sha256", "repair_manifest_sha256")):
            issues.append("repair_lineage_missing")
    source_wind = record.get("source_wind")
    if kind == "AUTHOR_OUTPUT_RESCORED" and source_wind != [0, 0]:
        issues.append("original_author_requires_zero_source_wind")
    if kind in ("AUTHOR_ALGORITHM_WIND_ADAPTED", "AUTHOR_ALGORITHM_WIND_ADAPTED_TERMINATION_FIXED", "AUTHOR_ALGORITHM_WIND_ADAPTED_FINAL_RECORD_FIXED") and source_wind != list(wind):
        issues.append("adapted_source_wind_mismatch")
    if record.get("process", {}).get("exit_status") != 0:
        issues.append("source_process_nonzero_or_missing")
    if record.get("process", {}).get("timed_out") is not False:
        issues.append("source_process_timeout_or_missing")
    if record.get("source_guard_passed") is not True:
        issues.append("source_guard_rejected_or_missing")
    try:
        def reject_constant(value):
            raise ValueError(value)
        raw = json.loads(raw_bytes, parse_constant=reject_constant)
        if not isinstance(raw, dict):
            raise ValueError("object required")
        integrity = raw.get("reference_integrity_issues")
        if not isinstance(integrity, list) or integrity:
            issues.append("source_integrity_issue_or_missing")
        solution = {"schema_version": 1, "instance": instance.name,
                    "instance_sha256": instance.sha256,
                    "station_types": raw["station_types"], "routes": raw["routes"]}
        source_solution = dict(solution, physics_sha256=scorer.physics_identity(instance, source_wind))
        source_score = scorer.score_solution(instance, source_solution, wind=source_wind)
        target_solution = dict(solution, physics_sha256=scorer.physics_identity(instance, wind))
        wind_score = scorer.score_solution(instance, target_solution, wind=wind)
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
        issues.append("raw_or_source_physics_invalid")
        return dict(out, status="SOURCE_RECORD_REJECTED")
    out.update(source_score=source_score, wind_score=wind_score,
               source_solution=source_solution, wind_solution=target_solution)
    if not source_score["original_feasible"]:
        issues.append("source_independently_infeasible")
    for name, reported in (("cost", raw.get("reference_reported_cost")),
                           ("M_return", record.get("source_M_return"))):
        value = source_score[name]
        if not _number(reported) or value is None or abs(reported - value) > 1e-7:
            issues.append("source_" + name + "_mismatch")
    out["source_record_qualified"] = not issues
    if issues:
        return dict(out, status="SOURCE_RECORD_REJECTED")
    if not wind_score["original_feasible"]:
        issues.append("target_wind_infeasible")
        return dict(out, status="WIND_PHYSICS_REJECTED")
    out["wind_witness_qualified"] = True
    # This is a newly named wind reference; it never rewrites historical C_Liu.
    anchor = scorer.CostAnchor.from_solution(instance, target_solution, wind=wind)
    out["issued_cost_anchor"] = {
        "reference_name": "C_" + kind.lower() + "_wind",
        "cost": anchor.cost, "M_return": anchor.makespan,
        "solution_sha256": anchor.solution_sha256,
        "source_manifest_sha256": record["source_manifest_sha256"],
        "scientific_use_requires_domain_and_timing_protocol": True,
    }
    return dict(out, status="ENGINEERING_WIND_WITNESS_QUALIFIED")
