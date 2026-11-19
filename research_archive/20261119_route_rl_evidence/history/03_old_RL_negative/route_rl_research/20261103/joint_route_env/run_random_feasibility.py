#!/usr/bin/env python3
"""One frozen random-legal-action engineering stress pass on exposed maps."""
import argparse
import copy
import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SNAPSHOT = ROOT / "route_rl_research/20261103/source_snapshot"
sys.path.insert(0, str(SNAPSHOT))
sys.path.insert(0, str(HERE))

from lrphsd.evaluator import evaluate
from lrphsd.greedy import build
from lrphsd.problem import read_instance
from station_env import RouteAction, StationRouteEnv

SEED = 20261103
FREEZE = SNAPSHOT / "ROUTE_RL_STAGEA_FREEZE_20261102.json"
DEFAULT_DATA = ROOT / "completion/code/external/LRPHSD<EXECUTION_PATH>"
OUT = HERE / "G1_RANDOM_FEASIBILITY.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    maps = json.loads(FREEZE.read_text())["data_split"]["validation_maps"]
    rng = random.Random(SEED)
    started = time.perf_counter()
    map_records = []

    for name, expected_hash in sorted(maps.items()):
        path = args.instance_dir / f"{name}.txt"
        actual_hash = sha(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"frozen input hash mismatch for {name}")
        ins = read_instance(path)
        initial = build(ins)
        candidate = copy.deepcopy(initial)
        failures = []
        active_stations = 0

        for si, kind in enumerate(initial["station_types"]):
            source = initial["routes"][si]
            targets = [nid for trips in source for trip in trips for nid in trip]
            if kind == 0:
                continue
            active_stations += 1
            env = StationRouteEnv(ins, si, int(kind), targets)
            prefix = []
            step_cap = 2 * len(targets) + len(env.slots) + 1
            for _ in range(step_cap):
                obs = env.observation()
                if obs["done"]:
                    break
                legal = [action for action, enabled in zip(obs["actions"], obs["mask"]) if enabled]
                if not legal:
                    failures.append({
                        "station_idx": si,
                        "station_type": int(kind),
                        "target_count": len(targets),
                        "status": "DEAD_END",
                        "action_prefix": [
                            {"slot": a.slot, "target_id": a.target_id} for a in prefix
                        ],
                        "remaining_target_ids": list(obs["remaining_target_ids"]),
                        "slot_state": {
                            str(slot): {
                                "current_pos": data["current_pos"],
                                "current_trip": list(data["current_trip"]),
                                "closed_trips": [list(t) for t in data["closed_trips"]],
                                "trip_energy": data["trip_energy"],
                                "trip_elapsed": data["trip_elapsed"],
                                "cumulative_duty": data["cumulative_duty"],
                            }
                            for slot, data in obs["slots"].items()
                        },
                        "fallback_used": False,
                    })
                    break
                action = rng.choice(legal)
                prefix.append(action)
                _, _, done, _ = env.step(action)
                if done:
                    candidate["routes"][si] = env.result()["routes"]
                    break
            else:
                failures.append({
                    "station_idx": si,
                    "station_type": int(kind),
                    "target_count": len(targets),
                    "status": "STEP_CAP",
                    "action_prefix": [
                        {"slot": a.slot, "target_id": a.target_id} for a in prefix
                    ],
                    "remaining_target_ids": sorted(env.remaining),
                    "fallback_used": False,
                })

        complete = not failures
        validator = None
        if complete:
            validator = evaluate(ins, candidate)
            map_status = "COMPLETE_FEASIBLE" if validator["feasible"] else "COMPLETE_VALIDATOR_REJECTED"
        else:
            map_status = "INCOMPLETE_DEAD_END_OR_CAP"
        map_records.append({
            "map": name,
            "input_sha256": actual_hash,
            "targets": len(ins.target_ids),
            "active_stations": active_stations,
            "status": map_status,
            "full_solution_validator_feasible": None if validator is None else validator["feasible"],
            "validator_issues": [] if validator is None else validator["issues"],
            "failure_count": len(failures),
            "failures": failures,
            "fallback_used": False,
        })

    report = {
        "schema": "route_station_env_g1_random_feasibility_v1",
        "protocol": "G1_RANDOM_FEASIBILITY_PROTOCOL.md",
        "seed": SEED,
        "purpose": "single engineering stress sample; exposed validation data; no quality objective reported",
        "protocol_sha256": sha(HERE / "G1_RANDOM_FEASIBILITY_PROTOCOL.md"),
        "environment_sha256": sha(HERE / "station_env.py"),
        "source_freeze_sha256": sha(FREEZE),
        "independent_evaluator_sha256": sha(SNAPSHOT / "lrphsd/evaluator.py"),
        "map_count": len(map_records),
        "map_complete_feasible_count": sum(r["status"] == "COMPLETE_FEASIBLE" for r in map_records),
        "map_incomplete_count": sum(r["status"] == "INCOMPLETE_DEAD_END_OR_CAP" for r in map_records),
        "station_dead_end_count": sum(r["failure_count"] for r in map_records),
        "fallback_used_count": 0,
        "elapsed_seconds": time.perf_counter() - started,
        "maps": map_records,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
