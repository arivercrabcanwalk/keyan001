"""Single-episode driver: intent -> run -> fsync rows.

Contract module #9.  The intent is written and fsynced BEFORE the episode
runs, and the row is fsynced before any aggregation, so a crash cannot lose
the fact that the episode was attempted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import sys
import time
import traceback

from env.causal_engine import CausalEngine, EngineConfig
from env.core import Particle, PublicPrefix, canonical_hash
from env.forecast_book import ErrorModel, ForecastBook
from env.latent_phase import FrozenModelParams, FrozenParticleModel
from env.snapshot import snapshot
from fixtures.build import f02_3s_6t, f05_storm_day
from policies.mu import make_mu


def _fsync_write(path: pathlib.Path, text: str, append: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _truth_particle(static, releases, horizon, seed):
    import random
    rng = random.Random(seed)
    blocks = []
    t = 0.0
    while t < horizon:
        blocks.append((t, rng.uniform(-0.2, 0.2), 0.0))
        t += 30.0
    from env.core import ExogenousFuture
    return Particle(particle_id=f"truth{seed}", seed=seed, hidden_past_wind=(),
                    hidden_phases=(), future=ExogenousFuture(
                        wind_blocks=tuple(blocks), releases=tuple(releases)))


def _publish(fb, particle, horizon, block_min=30.0, seed=11):
    import random
    rng = random.Random(seed)
    for k, tp in enumerate(fb.schedule):
        if tp > horizon:
            break
        truth, t = [], tp
        while t < min(tp + fb.valid_horizon_min, horizon + block_min):
            w = 0.0
            for t_from, u, _v in particle.future.wind_blocks:
                if t_from <= t + 1e-12:
                    w = u
            truth.append((t, w, 0.0))
            t += block_min
        fb.make_version(k, tp, tuple(truth), rng)


def run_episode(*, static, releases, faults=(), seed=7, mu_kind="lpt",
                horizon=None, deadline_s=1e9, out_dir=".", episode_key=None,
                extra_intent=None):
    out = pathlib.Path(out_dir)
    horizon = horizon if horizon is not None else (static.horizon_min or 240.0)
    key = episode_key or canonical_hash(
        {"static": static.sha256, "seed": seed, "mu": mu_kind,
         "releases": [[float(a), b] for a, b in releases],
         "faults": [[float(a), b] for a, b in faults]})[:16]
    intent = {
        "schema": "public_rollout_episode_intent_v1",
        "episode_key": key, "static_sha256": static.sha256,
        "seed": seed, "mu": mu_kind, "horizon": horizon,
        "deadline_s": deadline_s,
        "releases": [[float(a), b] for a, b in releases],
        "faults": [[float(a), b] for a, b in faults],
        "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": platform.node(), "python": sys.version.split()[0],
    }
    if extra_intent:
        intent["extra"] = extra_intent
    _fsync_write(out / "intents" / f"{key}.json",
                 json.dumps(intent, indent=2, sort_keys=True, allow_nan=False) + "\n")
    t0 = time.perf_counter()
    row = {"episode_key": key, "static_sha256": static.sha256}
    try:
        cfg = EngineConfig(horizon_min=horizon)
        prefix = PublicPrefix(static_sha256=static.sha256, t_min=0.0,
                              frontier_id=0, releases=tuple(releases))
        particle = _truth_particle(static, releases, horizon, seed)
        if faults:
            import dataclasses
            particle = dataclasses.replace(
                particle,
                future=dataclasses.replace(particle.future, faults=tuple(faults)))
        fb = ForecastBook([0.0, 60.0, 120.0, 180.0], 180.0,
                          error_model=ErrorModel(0.05, 0.05))
        _publish(fb, particle, horizon)
        eng = CausalEngine(static, prefix, particle, cfg, fb)
        rec = eng.run_with_frozen_mu(make_mu(mu_kind, static), deadline_s=deadline_s)
        row.update({"status": "DONE", "terminal": rec["terminal"],
                    "failure_code": rec["failure_code"],
                    "M_return": rec["metrics"]["M_return"],
                    "operating_minutes": rec["metrics"]["operating_minutes"],
                    "served": rec["metrics"]["served_count"],
                    "alarms": rec["alarms"],
                    "ledger_sha256": rec["ledger_sha256"]})
    except Exception:
        row.update({"status": "ERROR", "traceback_sha256": hashlib.sha256(
            traceback.format_exc().encode()).hexdigest()})
    row["wall_s"] = round(time.perf_counter() - t0, 6)
    row["deadline_s"] = deadline_s
    row["budget_exceeded"] = row["wall_s"] > deadline_s
    _fsync_write(out / "rows.jsonl",
                 json.dumps(row, sort_keys=True, allow_nan=False) + "\n", append=True)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="drivers_out")
    ap.add_argument("--fixture", default="f02")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--deadline", type=float, default=1e9)
    args = ap.parse_args(argv)
    static = f02_3s_6t() if args.fixture == "f02" else f05_storm_day()
    releases = tuple((0.0, tid) for tid in static.target_ids)
    row = run_episode(static=static, releases=releases, seed=args.seed,
                      deadline_s=args.deadline, out_dir=args.out)
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
