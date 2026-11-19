#!/usr/bin/env python3
"""Replay frozen Stage-A Greedy routes through the joint physical-route env."""
import argparse
import copy
import hashlib
import json
import math
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


FREEZE = SNAPSHOT / "ROUTE_RL_STAGEA_FREEZE_20261102.json"
DEFAULT_DATA = ROOT / "completion/code/external/LRPHSD<EXECUTION_PATH>"
OUT = HERE / "G1_STAGEA_REPLAY.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(routes):
    return [
        [[list(trip) for trip in trips if trip] for trips in station]
        for station in routes
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text())
    frozen_maps = freeze["data_split"]["validation_maps"]
    started = time.perf_counter()
    map_records = []
    station_count = 0
    active_station_count = 0
    max_reward_error = 0.0

    for name, expected_sha in sorted(frozen_maps.items()):
        path = args.instance_dir / f"{name}.txt"
        actual_sha = sha(path)
        if actual_sha != expected_sha:
            raise RuntimeError(f"frozen input hash mismatch for {name}")
        ins = read_instance(path)
        initial = build(ins)
        before = evaluate(ins, initial)
        if not before["feasible"]:
            raise RuntimeError(f"frozen Greedy is infeasible on {name}: {before['issues'][:5]}")
        candidate = copy.deepcopy(initial)
        assigned_all = []
        map_max_reward_error = 0.0

        for si, kind in enumerate(initial["station_types"]):
            station_count += 1
            source_routes = initial["routes"][si]
            station_targets = [nid for trips in source_routes for trip in trips for nid in trip]
            if kind == 0:
                if station_targets:
                    raise RuntimeError(f"closed station has assigned targets: {name}:{si}")
                continue
            active_station_count += 1
            if len(station_targets) != len(set(station_targets)):
                raise RuntimeError(f"duplicate station target in source route: {name}:{si}")
            assigned_all.extend(station_targets)
            env = StationRouteEnv(ins, si, int(kind), station_targets)
            for slot in (0, 1):
                for trip in source_routes[slot]:
                    if not trip:
                        continue
                    for nid in trip:
                        action = RouteAction(slot, int(nid))
                        if not env.legal(action):
                            raise RuntimeError(f"source action masked on {name}:{si}:{action}")
                        _, _, _, _ = env.step(action)
                    action = RouteAction(slot)
                    if not env.legal(action):
                        raise RuntimeError(f"source RETURN masked on {name}:{si}:{slot}")
                    _, _, _, _ = env.step(action)

            replay = env.result()
            station_routes = [[list(t) for t in replay["routes"][d]] for d in (0, 1)]
            if station_routes != normalized([source_routes])[0]:
                raise RuntimeError(f"route witness changed during replay on {name}:{si}")
            candidate["routes"][si] = station_routes
            reward_error = abs(
                replay["reward"] + replay["operating_minutes"] * ins.params.time_cost
            )
            map_max_reward_error = max(map_max_reward_error, reward_error)

        if sorted(assigned_all) != sorted(ins.target_ids):
            raise RuntimeError(f"station assignment does not cover targets exactly once on {name}")
        after = evaluate(ins, candidate)
        if not after["feasible"]:
            raise RuntimeError(f"replayed full solution is infeasible on {name}: {after['issues'][:5]}")
        if not math.isclose(before["cost"], after["cost"], rel_tol=0.0, abs_tol=1e-8):
            raise RuntimeError(f"objective changed on {name}: {before['cost']} vs {after['cost']}")
        max_reward_error = max(max_reward_error, map_max_reward_error)
        map_records.append({
            "map": name,
            "input_sha256": actual_sha,
            "source_greedy_feasible": before["feasible"],
            "replay_feasible": after["feasible"],
            "source_cost": before["cost"],
            "replay_cost": after["cost"],
            "targets": len(ins.target_ids),
            "stations": len(ins.stations),
            "max_reward_reconciliation_error": map_max_reward_error,
        })

    report = {
        "schema": "route_station_env_stageA_replay_g1_v1",
        "purpose": "engineering interface/replay validation only; exposed historical validation data",
        "source_snapshot_freeze_sha256": sha(FREEZE),
        "independent_evaluator_sha256": sha(SNAPSHOT / "lrphsd/evaluator.py"),
        "environment_sha256": sha(HERE / "station_env.py"),
        "map_count": len(map_records),
        "station_count": station_count,
        "active_station_count": active_station_count,
        "all_source_and_replay_solutions_feasible": True,
        "all_full_objectives_unchanged_abs_tol_1e-8": True,
        "max_reward_reconciliation_error": max_reward_error,
        "elapsed_seconds": time.perf_counter() - started,
        "maps": map_records,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
