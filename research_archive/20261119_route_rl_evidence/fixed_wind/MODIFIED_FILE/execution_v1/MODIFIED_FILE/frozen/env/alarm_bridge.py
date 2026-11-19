"""Finite alarm-only conditioning bridge, not a full weather/phase posterior.

Uses the existing frozen finite fault law. Only public released ledger fields
are converted; no Scenario, private future queue or engine is accepted.
"""
from dataclasses import dataclass
import math
import random

from .core import AlarmJob, PublicPrefix, PublicRolloutError
from .fault_conditioning import (PublicAlarm, PublicFaultLaw,
                                 PublicPrefix as FaultHistory)


@dataclass(frozen=True)
class AlarmBridgeSample:
    model_id: str
    particle_id: str
    weights: tuple
    jobs: tuple
    beyond_horizon: tuple
    absent: tuple


def condition_alarm_jobs(prefix: PublicPrefix, law: PublicFaultLaw, *,
                         seed: int, horizon: float,
                         high_probability: float = 0.4,
                         high_due: float = 20.0, routine_due: float = 45.0,
                         weather_log_likelihood=None) -> AlarmBridgeSample:
    """Convert public history to a finite model sample at an all-idle frontier.

    The restriction prevents this adapter being used as an unqualified busy-
    phase reconstruction. Weather likelihood, if supplied, is an external
    frozen public-observation-model term, not inferred by this module.
    """
    if not isinstance(prefix, PublicPrefix) or not isinstance(law, PublicFaultLaw):
        raise TypeError("public prefix and frozen finite model required")
    if (not math.isfinite(high_probability) or not 0 <= high_probability <= 1
            or not math.isfinite(high_due) or high_due <= 0
            or not math.isfinite(routine_due) or routine_due <= 0):
        raise ValueError("valid fixed priority/deadline model required")
    if any(row.get("phase", "IDLE") != "IDLE"
           or row.get("target_in_service") is not None
           for row in prefix.slot_state):
        raise PublicRolloutError("BUSY_PHASE_POSTERIOR_NOT_QUALIFIED")
    history = FaultHistory(prefix.t_min,
                           tuple(PublicAlarm(int(row[1]), float(row[2]))
                                 for row in prefix.alarm_ledger))
    weights = law.weights(history, weather_log_likelihood)
    future = law.sample_future(history, seed, horizon=horizon,
                               weather_log_likelihood=weather_log_likelihood)
    jobs = [AlarmJob(row[0], int(row[1]), float(row[2]), float(row[3]), row[4])
            for row in prefix.alarm_ledger]
    rng = random.Random(seed ^ 0x51A7C0DE)
    for alarm in future.releases:
        priority = "high" if rng.random() < high_probability else "routine"
        deadline = alarm.released_at + (high_due if priority == "high" else routine_due)
        jobs.append(AlarmJob(f"storm:{alarm.target_id}", alarm.target_id,
                             alarm.released_at, deadline, priority))
    return AlarmBridgeSample(law.model_id, future.particle_id, weights,
                              tuple(sorted(jobs, key=lambda j: (j.release, j.target))),
                              future.beyond_horizon_target_ids,
                              future.no_future_fault_target_ids)
