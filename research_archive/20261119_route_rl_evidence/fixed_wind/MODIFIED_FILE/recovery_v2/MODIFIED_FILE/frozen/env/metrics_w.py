"""W-contract metrics: high-priority on-time rate, tardiness CVaR90, cost ratio.

Contract sections 7.5 and 7.6.  Every metric states its denominator; an
unserved task is never dropped from a denominator.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .core import StaticContext, _f

CVAR_LEVEL = 0.90
HIGH = "high"


def cvar90(values, level: float = CVAR_LEVEL) -> float | None:
    """Mean of the worst (1-level) tail.  Zeros are KEPT, not filtered."""
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    k = max(1, math.ceil((1.0 - level) * len(vals)))
    if math.isinf(vals[-1]):
        return math.inf
    return _f(sum(vals[-k:]) / k)


@dataclass(frozen=True)
class WRow:
    map_id: str
    M_return: float
    cost: float
    high_total: int
    high_on_time: int
    tardiness: tuple[float, ...]
    unserved: tuple[int, ...]
    unserved_jobs: tuple[str, ...] = ()

    @property
    def high_on_time_rate(self) -> float | None:
        return None if self.high_total == 0 else self.high_on_time / self.high_total

    @property
    def cvar90(self) -> float | None:
        return cvar90(self.tardiness)

    def as_json(self) -> dict:
        tail = self.cvar90
        return {"map_id": self.map_id, "M_return": self.M_return,
                "cost": self.cost, "high_total": self.high_total,
                "high_on_time": self.high_on_time,
                "high_on_time_rate": self.high_on_time_rate,
                "cvar90_min": "INF_UNSERVED" if tail == math.inf else tail,
                "unserved": list(self.unserved),
                "unserved_jobs": list(self.unserved_jobs)}


def evaluate(static: StaticContext, receipt: dict, map_id: str = "") -> WRow:
    """Score one episode under the W contract.

    high-priority on-time rate denominator = every declared planned high task
    plus every released high-priority alarm job, including unserved ones.
    tardiness CVaR90 = mean of the worst 10% of per-task lateness, where an
    unserved task contributes INF and therefore forces the tail.
    """
    ddl = {tid: (d, p) for tid, d, p in static.deadlines}
    served = {int(a): float(b) for a, b in receipt.get("served", [])}
    high_total = high_on_time = 0
    tard: list[float] = []
    unserved: list[int] = []
    unserved_jobs: list[str] = []
    for tid in static.target_ids:
        d, prio = ddl.get(tid, (math.inf, "routine"))
        t = served.get(tid)
        if t is None:
            unserved.append(tid)
            tard.append(math.inf if math.isfinite(d) else 0.0)
        else:
            tard.append(max(0.0, t - d) if math.isfinite(d) else 0.0)
        if prio == HIGH:
            high_total += 1
            if t is not None and math.isfinite(d) and t <= d + 1e-9:
                high_on_time += 1
    for job in receipt.get("alarm_jobs", []):
        job_id = str(job["job_id"])
        deadline = float(job["deadline"])
        completed = job.get("completed_at")
        if completed is None:
            tard.append(math.inf)
            unserved_jobs.append(job_id)
        else:
            tard.append(max(0.0, float(completed) - deadline))
        if job["priority"] == HIGH:
            high_total += 1
            if completed is not None and float(completed) <= deadline + 1e-9:
                high_on_time += 1
    met = receipt.get("metrics", {})
    return WRow(map_id=map_id, M_return=_f(met.get("M_return", 0.0)),
                cost=_f(met.get("cost", 0.0)) if met.get("cost") is not None else float("nan"),
                high_total=high_total, high_on_time=high_on_time,
                tardiness=tuple(tard), unserved=tuple(unserved),
                unserved_jobs=tuple(unserved_jobs))


def cost_ratio_ci(ratios, n_boot: int = 10000, seed: int = 20261112,
                  level: float = 0.95, threshold: float = 1.01) -> dict:
    """Map-level bootstrap CI for the mean cost ratio (candidate / reference)."""
    vals = [float(r) for r in ratios]
    if not vals:
        return {"n": 0}
    bad = [i for i, v in enumerate(vals) if not math.isfinite(v)]
    if bad:
        return {"n": len(vals), "status": "NONFINITE_COST",
                "nonfinite_indices": bad, "upper_le_threshold": False}
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(n_boot))
    lo = means[int((1 - level) / 2 * n_boot)]
    hi = means[int((1 + level) / 2 * n_boot) - 1]
    point = sum(vals) / n
    return {"n": n, "mean": point, "ci": [lo, hi],
            "upper_le_threshold": hi <= threshold + 1e-12,
            "threshold": threshold, "n_boot": n_boot, "seed": seed}
