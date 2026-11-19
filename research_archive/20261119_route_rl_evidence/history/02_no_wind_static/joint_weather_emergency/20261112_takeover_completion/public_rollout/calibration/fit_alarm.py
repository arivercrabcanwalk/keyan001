"""Alarm-law calibration: estimator, receipts, and its honest scope.

This module turns "p and the delay distribution are engineering defaults" into
"the estimator exists, is validated on synthetic data with known ground truth,
and has never been applied to real fault data".  It does not manufacture
provenance.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass

from env.core import _f, canonical_hash


@dataclass(frozen=True)
class AlarmSample:
    """One observed (or simulated) sweep and the fault it produced, if any."""

    episode: str
    target: int
    swept: bool
    delay: float | None      # None = no fault observed for this sweep


def fit_alarm(samples, n_boot: int = 2000, seed: int = 20261112) -> dict:
    """MLE for p and the empirical delay distribution, with a bootstrap CI."""
    swept = [s for s in samples if s.swept]
    if not swept:
        raise ValueError("no swept targets: p is not identified")
    events = [s for s in swept if s.delay is not None]
    n = len(swept)
    k = len(events)
    p_hat = k / n
    delays = sorted(float(s.delay) for s in events)
    rng = random.Random(seed)
    p_boot = []
    for _ in range(n_boot):
        draw = [swept[rng.randrange(n)] for _ in range(n)]
        p_boot.append(sum(1 for s in draw if s.delay is not None) / n)
    p_boot.sort()
    lo = p_boot[int(0.025 * n_boot)]
    hi = p_boot[int(0.975 * n_boot) - 1]
    dmean = sum(delays) / len(delays) if delays else None
    dq = {}
    if delays:
        for q in (0.1, 0.5, 0.9):
            idx = min(len(delays) - 1, max(0, int(round(q * (len(delays) - 1)))))
            dq[f"q{int(q*100)}"] = _f(delays[idx])
    ks_uniform = _ks_uniform(delays, lo=0.0, hi=20.0) if delays else None
    return {
        "schema": "alarm_law_calibration_v1",
        "n_swept": n, "n_events": k,
        "p_hat": _f(p_hat), "p_ci95": [_f(lo), _f(hi)],
        "delay_mean": None if dmean is None else _f(dmean),
        "delay_quantiles": dq,
        "ks_uniform_0_20": ks_uniform,
        "n_boot": n_boot, "seed": seed,
        "samples_sha256": canonical_hash(
            [[s.episode, s.target, bool(s.swept),
              None if s.delay is None else round(float(s.delay), 9)]
             for s in samples]),
    }


def _ks_uniform(delays, lo: float, hi: float) -> float:
    """Kolmogorov-Smirnov distance to U[lo, hi] (diagnostic, not a p-value)."""
    n = len(delays)
    xs = sorted((d - lo) / (hi - lo) for d in delays)
    worst = 0.0
    for i, x in enumerate(xs, 1):
        worst = max(worst, abs(x - i / n), abs((i - 1) / n - x))
    return _f(worst)


def simulate(prob: float, delay_lo: float, delay_hi: float, *,
             n_episodes: int, targets_per_episode: int, seed: int) -> list:
    """Synthetic ground truth for validating the estimator."""
    rng = random.Random(seed)
    out = []
    for e in range(n_episodes):
        for tid in range(1, targets_per_episode + 1):
            if rng.random() < prob:
                out.append(AlarmSample(f"e{e:03d}", tid, True,
                                       rng.uniform(delay_lo, delay_hi)))
            else:
                out.append(AlarmSample(f"e{e:03d}", tid, True, None))
    return out


def receipt(result: dict, *, synthetic_truth: dict | None = None,
            applied_to_real_data: bool = False) -> dict:
    rec = dict(result)
    rec["applied_to_real_data"] = applied_to_real_data
    rec["synthetic_truth"] = synthetic_truth
    rec["status"] = ("VALIDATED_ON_SYNTHETIC_ONLY" if synthetic_truth
                     and not applied_to_real_data
                     else ("APPLIED_TO_REAL_DATA" if applied_to_real_data
                           else "UNVALIDATED"))
    if synthetic_truth:
        rec["recovered"] = {
            "p": abs(result["p_hat"] - synthetic_truth["prob"])
            <= (result["p_ci95"][1] - result["p_ci95"][0]) / 2 + 1e-12,
        }
    return rec
