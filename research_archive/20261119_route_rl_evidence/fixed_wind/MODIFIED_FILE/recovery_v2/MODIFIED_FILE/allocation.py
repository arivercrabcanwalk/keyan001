#!/usr/bin/env python3
"""Static F3 G3 allocation/manifest builder; never generate or solve a map.

This intentionally has no scientific-execution mode. Its source is reviewable
before population generation. Root must supply the missing thin execution
interfaces and cumulative CPU guard identified in G3_EXECUTION_FREEZE.md.
Only the Python standard library is imported; generator/physics/model modules
are not imported. Seed assignment hashes strings, not experimental data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


NAMESPACE = "f3-g3-20261114-authorized-v1"
WORKSPACE = Path("/Users/USER/Documents/ChatGPT/lunwen")
FAMILIES = ((3, 10), (3, 15), (3, 20), (4, 20), (4, 25), (4, 30),
            (5, 35), (6, 50), (7, 65), (8, 80), (9, 95), (10, 110))
ORDINALS = (1, 2)
WINDS = (("W00", (0, 0)), ("W04E", (240, 0)), ("W08N", (0, 480)))
RUN_SEEDS = tuple(range(2026111401, 2026111411))
DEADLINES = (6, 12)
AUTHOR_TIMEOUT_S = 1800
CPU_TOTAL_CAP_S = 172800
CPU_CORE_WORK_S = 155520
CPU_PREPARATION_AUDIT_RESERVE_S = 17280
AUTHORIZATION_REL = "joint_weather_emergency/20261114_f3_g3_authorized_v1/AUTHORIZATION.json"
AUTHORIZATION_SHA256 = "0bc963d17f599835f8b740b315c43c20759a8cca517d4cca8100346c3c04efe8"

SOURCE_PINS = {
    "route_rl_research/20261103/return_makespan/g23/data/generator_v2/generator_v2.py":
        "7a5f2e5c06acf7c70cccc55b20a1f8f1d30c481f73b14390b2b66b77894781e8",
    "route_rl_research/20261103/return_makespan/g23/data/generator_reconstruction/PERMANENT_EXCLUSION_MANIFEST.json":
        "90ea8233bbe281adc978af0c421ec6a0962346877125dbe21d7382015f8862d6",
    "route_rl_research/20261103/return_makespan/g23/data/generator_reconstruction/SYNTHETIC_SMOKE_EXCLUSION.json":
        "6e62b16158f9332d782068390889034899a80a4a46363e4f6c862eae8c60ace2",
    "route_rl_research/20261103/return_makespan/g23/data/generator_v2/SYNTHETIC_EXCLUSION_MANIFEST.json":
        "623be2a46ee20e93d0997cba4903e8eba7df35ef352af5338646143440beae63",
    "route_rl_research/20261103/return_makespan/g23/data/generator_v2/WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json":
        "8d78dfd793557645f8410aac4d6034c39683f991c67375bd0bbc949acae44161",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/status_reconciliation_g3_20261105/EXPOSURE_EXCLUSIONS_40.json":
        "520d03933578b9e30fb9a608b3bc4ee4c4ab0ff4187e2a7cd8d13b0f0f1ff593",
    "joint_weather_emergency/20261106_control_qualification_C/exclusions/JOINT_EXPOSED.json":
        "5c7a31ecd468cdd09e7a1ba31cef311f21e7638cce3318e50e4d3fdeda6c240b",
    "joint_weather_emergency/20261112_takeover_completion/results/g3_pop/population_index.json":
        "05a0f7c1b4fa5b8eef3964aa691322683cef0e234dba40cc9a9fd929e8d85692",
    "joint_weather_emergency/20261112_takeover_completion/results/g3_confirm/population_index.json":
        "b1ffcb6736d62d0ce6fabb11456e5183abf2130dd9f66479a675751dc61d70c7",
    "joint_weather_emergency/20261113_author_final_recorder_fix_v1/validation/fullsolve_driver.py":
        "850263f393712a553b45a8c875d9439d0d733a792664ab6a4530ea2f61222d30",
    "joint_weather_emergency/20261113_author_final_recorder_fix_v1/SOURCE_LOCK.json":
        "924edf85366c30b4b242e2d69b0d41ad409ec71e5393822e787b1e7ddcaf475f",
    "joint_weather_emergency/20261113_author_final_recorder_fix_v1/builds/wind_adapted_fixed/BUILD_MANIFEST.json":
        "edbb6795ca7d04b47b2f50f25a0b753c398e2184d209f3567d6daa099979856d",
    "joint_weather_emergency/20261113_author_final_recorder_fix_v1/frozen/baselines/author_anchor.py":
        "cecdfc44b43201c7219678199a16fa7cde1575415666293bce71bc8128962a63",
    "joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/baselines/minmax_alns.py":
        "e43521f0f6284ddd45e3ce76890adb0f97cefaf3f87964e1ce016e27122e3e60",
    "joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/baselines/constant_wind_adapter.py":
        "6deb20c25ca286c091b51fb63b3eaa04ea03a845ce7137c3eb6220494d19c119",
    "joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/route_delivery.py":
        "59a191ce18190bc18cd88e4d2307c026a043418617c22827d45a17a9ad31abc0",
    "joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/prefix_sampler.py":
        "f78f5ccbbfb0928465f5fd63d49d81c3dc3ff0fa108e479225308d9bb3a9c817",
    "joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/schedule_credit.py":
        "0642db80faa95c06e01a563426e3d14e55a89eac6acbc0624e6fb39231d4bdae",
    "joint_weather_emergency/20261114_solxhigh_research_round_v1/deadline_control/MODIFIED_FILE.py":
        "4685e959232a2f8350cd91b028c54913def89b20308d0ae296f9675246b9b3bb",
    "joint_weather_emergency/20261114_solxhigh_research_round_v1/deadline_control/WORKER_MODIFIED.py":
        "6b051b69687dab509713249cf2ffed0ffa6cc94c4eeefe6f8b2e9bc075b38347",
}

BLOCKERS = (
    "G0_AIR2_actual_qualification_pending_root_decision",
    "complete_post20261106_exposure_union_missing",
    "new_population_full_author_thin_CLI_not_yet_implemented",
    "common_H_schedule_and_cross_H_bank_merge_CLI_missing",
    "public_T_still_has_14_trip_engineering_assertion",
    "aggregate_172800_CPU_second_enforcement_not_yet_installed_verified",
    "new_execution_source_closure_and_manifest_not_yet_frozen",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def hash_u64(value):
    return int.from_bytes(hashlib.sha256(canonical(value).encode("ascii")).digest()[:8], "big")


def allocation():
    """String-hash allocation only; no RNG draw or map construction occurs."""
    rows = []
    for sites, targets in FAMILIES:
        for ordinal in ORDINALS:
            map_id = f"{NAMESPACE}:opportunity:{sites}x{targets}:o{ordinal}"
            seeds = {}
            for stream in ("coordinates", "target_ids"):
                value = hash_u64({"schema": "route_rl_sequential_v2_seed_v1",
                    "namespace": NAMESPACE, "family": [sites, targets],
                    "partition": "opportunity", "ordinal": ordinal, "stream": stream})
                seeds[stream + "_seed_u64_decimal"] = str(value)
            author_seed = hash_u64({"schema": "f3_g3_author_seed_v1",
                                   "namespace": NAMESPACE, "map_id": map_id}) & ((1 << 63) - 1)
            rows.append({"map_id": map_id, "short_id": f"{sites}x{targets}_o{ordinal}",
                         "family": [sites, targets], "partition": "opportunity",
                         "ordinal": ordinal, **seeds,
                         "author_seed_i63_decimal": str(author_seed),
                         "expected_raw_sha256": None,
                         "expected_canonical_geometry_sha256": None,
                         "generation_status": "NOT_GENERATED"})
    return rows


def planned_control_rows():
    """A deterministic schedule, not solver calls. Full registration has 2880 rows."""
    result = []
    maps = allocation()
    # Ordinal-major traversal spreads the twelve families across early progress.
    ordered = sorted(maps, key=lambda r: (r["ordinal"], FAMILIES.index(tuple(r["family"]))))
    for map_index, row in enumerate(ordered):
        wind_order = WINDS[map_index % 3:] + WINDS[:map_index % 3]
        for wind_index, (wind_id, wind) in enumerate(wind_order):
            for seed_index, seed in enumerate(RUN_SEEDS):
                for deadline in DEADLINES:
                    methods = ["native_strong_minmax_ALNS", "independent_common_H"]
                    if (map_index + wind_index + seed_index + deadline // 6) % 2:
                        methods.reverse()
                    for method in methods:
                        result.append({"map_id": row["map_id"], "wind_id": wind_id,
                            "wind_m_per_min": list(wind), "run_seed": seed,
                            "deadline_s": deadline, "method": method,
                            "status": "PLANNED_NOT_LAUNCHED"})
    return result


def verify_sources(workspace):
    result = []
    for relative, expected in {AUTHORIZATION_REL: AUTHORIZATION_SHA256, **SOURCE_PINS}.items():
        path = workspace / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result.append({"path": str(path), "expected_sha256": expected,
                       "actual_sha256": actual, "match": actual == expected})
    return result


def plan(*, include_control_rows=False, source_checks=None):
    result = {"schema": "f3_g3_static_execution_allocation_v1",
        "status": "STATIC_DESIGN_WITH_EXPLICIT_LAUNCH_BLOCKERS",
        "execution_supported": False, "ready_to_launch": False,
        "namespace": NAMESPACE, "host": "EXECUTION_HOST", "owner": "root",
        "authorization_sha256": AUTHORIZATION_SHA256,
        "map_allocations": allocation(),
        "winds": [{"id": k, "vector_m_per_min": list(v), "weight_rational": "1/3"} for k, v in WINDS],
        "run_seeds": list(RUN_SEEDS), "deadlines_s": list(DEADLINES),
        "author_attempts_cap": 72, "control_rows_registered": 2880,
        "author_timeout_s": AUTHOR_TIMEOUT_S,
        "cpu_total_cap_s": CPU_TOTAL_CAP_S, "cpu_core_work_s": CPU_CORE_WORK_S,
        "cpu_preparation_audit_reserve_s": CPU_PREPARATION_AUDIT_RESERVE_S,
        "common_H_schedule": {"rho_rational": ["1", "9/10", "4/5"],
            "reference": "original_same_wind_author_M_return",
            "pass_search_time_weights_rational": ["1/3", "1/3", "1/3"],
            "finalization_reserve_s": 0.25,
            "merge_banks_all_passes": True,
            "final_combiner": "existing_schedule_credit_Context.solve"},
        "source_pins": dict(SOURCE_PINS), "launch_blockers": list(BLOCKERS),
        "maps_generated": 0, "solver_calls": 0, "training": 0, "Formal": 0}
    if include_control_rows:
        result["planned_controls"] = planned_control_rows()
    if source_checks is not None:
        result["source_readback"] = source_checks
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--include-control-rows", action="store_true")
    parser.add_argument("--verify-sources", action="store_true")
    args = parser.parse_args()
    checks = verify_sources(args.workspace.resolve()) if args.verify_sources else None
    print(json.dumps(plan(include_control_rows=args.include_control_rows, source_checks=checks),
                     sort_keys=True, indent=2, allow_nan=False))
    return 0 if checks is None or all(row["match"] for row in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
