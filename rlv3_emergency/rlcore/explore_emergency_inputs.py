"""Self-contained synthetic corpus for emergency-route exploration.

These are generated inputs and hand-set singleton routine routes, not the
authors' data, TSALNS solutions, or a reproduction of an author baseline.
Corpus seeds are independent of optimizer seeds and fixed across optimizer runs.
"""
import copy
import hashlib
import json
import math

import numpy as np

from .common import CAP, DABS_FIX, T_SVC, P2
from .env import Env
from .event_learning import derived_seed
from .urgent import make_requests

CORPUS_SEED = 20261120
PROFILES = {
    "quick": dict(train_maps=3, eval_maps=2, eval_days=2, targets_per_station=8,
                  bc_episodes=6, bc_epochs=2, pg_iterations=4, rollouts=4,
                  arch=dict(d=32, heads=4, layers=1)),
    "standard": dict(train_maps=12, eval_maps=8, eval_days=4, targets_per_station=12,
                     bc_episodes=36, bc_epochs=4, pg_iterations=64, rollouts=4,
                     arch=dict(d=64, heads=4, layers=2)),
}


def canonical_sha(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def make_layout(corpus_seed, split, index, targets_per_station=8):
    if split not in ("train", "evaluation") or targets_per_station <= 0:
        raise ValueError("invalid synthetic map split or size")
    rng = np.random.default_rng(derived_seed(corpus_seed, "map", split, index))
    stations, drones, targets, assign = [], [], {}, {}
    for station in range(2):
        x, y = station*5200.0, float(rng.uniform(-500.0, 500.0))
        ids = [len(drones), len(drones)+1]
        stations.append(dict(k=station, si=station, x=x, y=y, kind=2, R=3500.0, drones=ids))
        local = []
        for _ in range(targets_per_station):
            angle, radius = rng.uniform(0, 2*math.pi), rng.uniform(400.0, 2200.0)
            tid = len(targets)+1
            targets[tid] = (x+radius*math.cos(angle), y+radius*math.sin(angle), T_SVC, P2*T_SVC)
            assign[tid] = station
            local.append(tid)
        for drone_type, drone_id in enumerate(ids):
            # Fixed alternating ownership and singleton trips are transparent
            # setup choices; the online action domain allows station-wide work.
            trips = [[tid] for tid in local[drone_type::2]]
            drones.append(dict(i=drone_id, st=station, di=drone_type, cap=CAP[drone_type],
                               limit=600.0, trips=trips))
    return dict(stations=stations, drones=drones, targets=targets, assign=assign,
                fixed=2*DABS_FIX, n_open=2, n_dabs=2, types=[2, 2])


def _case(corpus_seed, split, map_index, day, pattern, level, layout):
    event_seed = derived_seed(corpus_seed, "events", split, map_index, day, pattern, level)
    locations = [(tid, *point[:2]) for tid, point in sorted(layout["targets"].items())]
    requests = make_requests(event_seed, locations, level=level, pattern=pattern)
    case = dict(case_id=f"{split}:map{map_index}:day{day}:{pattern}:{level}",
                split=split, map_id=f"{split}:map{map_index}", map_index=map_index, day=day,
                map_sha256=canonical_sha(layout), pattern=pattern, level=level,
                event_seed=event_seed, layout=layout, requests=requests)
    case["case_sha256"] = canonical_sha(case)
    return case


def build_inputs(corpus_seed=CORPUS_SEED, profile="quick"):
    cfg = PROFILES[profile]
    maps = {split: [make_layout(corpus_seed, split, index, cfg["targets_per_station"])
                    for index in range(count)]
            for split, count in (("train", cfg["train_maps"]), ("evaluation", cfg["eval_maps"]))}
    train_bc, train_pg, evaluation = [], [], []
    for stage, count, day_offset, result in (("bc", cfg["bc_episodes"], 10000, train_bc),
                                           ("pg", cfg["pg_iterations"], 20000, train_pg)):
        for index in range(count):
            map_index = index % cfg["train_maps"]
            result.append(_case(corpus_seed, "train", map_index, day_offset+index,
                                ("random", "clustered")[index % 2],
                                ("low", "mid", "high")[index % 3], maps["train"][map_index]))
    for map_index, layout in enumerate(maps["evaluation"]):
        for day in range(cfg["eval_days"]):
            for pattern in ("random", "clustered"):
                for level in ("low", "mid", "high"):
                    evaluation.append(_case(corpus_seed, "evaluation", map_index, 30000+day,
                                            pattern, level, layout))
    train_hashes = {case["map_sha256"] for case in train_bc+train_pg}
    eval_hashes = {case["map_sha256"] for case in evaluation}
    train_events = {case["event_seed"] for case in train_bc+train_pg}
    eval_events = {case["event_seed"] for case in evaluation}
    if train_hashes & eval_hashes or train_events & eval_events:
        raise AssertionError("training/evaluation maps or event streams overlap")
    return dict(schema="emergency_exploratory_corpus_v1", corpus_seed=corpus_seed, profile=profile,
                provenance="generated_synthetic_non_author_inputs_and_manual_singleton_anchor",
                physical_model="existing_Env_calm_author_simple_energy_and_cumulative_duty",
                generator_assumptions=dict(stations=2, kind="DABS", radius_m=3500,
                    station_spacing_m=5200, target_radial_range_m=[400, 2200],
                    service_min=T_SVC, service_energy=P2*T_SVC,
                    emergency_rate_per_tower=dict(low=.05, mid=.15, high=.30),
                    release_window_min=[0, 450], day_horizon_min=600,
                    high_arrival_sla_min=20, normal_arrival_sla_min=60,
                    priority_high_probability=.3),
                train_bc=train_bc, train_pg=train_pg, evaluation=evaluation)


def make_env(case, record=False):
    """Each call creates isolated mutable physical state and frozen inputs."""
    return Env(copy.deepcopy(case["layout"]), wx=None, requests=copy.deepcopy(case["requests"]),
               margin=0.0, record=record)
