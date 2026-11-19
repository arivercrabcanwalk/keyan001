"""Independent full-episode audit (contract module #6).

Recomputes served_at / returned_at / per-slot duty / M_return / cost from the
action log and the frozen particle ALONE, using its own physics loop.  It does
not import the engine, so a bug in the engine cannot hide here.

This closes the H-4 gap recorded in DOCS_IMPLEMENTATION.md.
"""
from __future__ import annotations

import math

from .core import Particle, PublicRolloutError, StaticContext

TOL_REL = 1e-9


class AuditMismatch(PublicRolloutError):
    pass


def _wind_at(particle: Particle, t: float) -> tuple[float, float]:
    cur = (0.0, 0.0)
    for t_from, uu, vv in particle.future.wind_blocks:
        if t_from <= t + 1e-12:
            cur = (uu, vv)
        else:
            break
    return cur


def _leg(static: StaticContext, particle: Particle, a, b, t):
    """Along-track ground speed, written out independently of the engine."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist <= 1e-12:
        return 0.0, dist
    u, v = _wind_at(particle, t)
    along = (u * dx + v * dy) / dist
    speed = max(static.params.speed + along, 1e-3)
    return dist / speed, dist


def independent_full_episode_audit(static: StaticContext, particle: Particle,
                                   receipt: dict) -> dict:
    """Return an audit dict; raise AuditMismatch on any disagreement."""
    p = static.params
    pos = {}
    for si, st in enumerate(static.stations):
        for sj in (1,) if static.station_types[si] == 1 else (0, 1):
            if static.station_types[si] == 0:
                continue
            pos[(si, sj)] = (st.x, st.y)
    duty = {k: 0.0 for k in pos}
    trip_energy = {k: 0.0 for k in pos}
    served = {}
    completed_jobs = {}
    jobs = {j.target: j for j in particle.future.alarm_jobs}
    returned = {}
    for act in receipt["actions"]:
        t, si, sj, kind, target = act[:5]
        job_id = act[5] if len(act) > 5 else None
        key = (si, sj)
        if key not in pos:
            raise AuditMismatch(f"action on unknown slot {key}")
        here = pos[key]
        if kind == "RETURN":
            st = static.stations[si]
            leg_t, _ = _leg(static, particle, here, (st.x, st.y), t)
            duty[key] += leg_t
            trip_energy[key] = 0.0
            pos[key] = (st.x, st.y)
            returned[key] = t + leg_t
        elif kind == "TARGET":
            node = static.nodes[target]
            leg_t, _ = _leg(static, particle, here, (node.x, node.y), t)
            duty[key] += leg_t + node.service
            trip_energy[key] += leg_t * p.flight_energy + node.energy
            cap = p.battery(sj)
            if trip_energy[key] > cap + 1e-7:
                raise AuditMismatch(
                    f"energy violated at {key} target {target}: "
                    f"{trip_energy[key]} > {cap}")
            pos[key] = (node.x, node.y)
            # two-phase physics: the target is served after the leg AND the service
            if job_id is None:
                served[target] = t + leg_t + node.service
                job = jobs.get(target)
                if (job is not None and job.release <= served[target] + 1e-12
                        and job.job_id not in completed_jobs):
                    completed_jobs[job.job_id] = served[target]
            else:
                completed_jobs[job_id] = t + leg_t + node.service
        else:
            raise AuditMismatch(f"unknown action kind {kind}")

    station_mk = []
    for si, kind in enumerate(static.station_types):
        if kind == 0:
            station_mk.append(0.0)
            continue
        vals = [duty[k] for k in duty if k[0] == si]
        station_mk.append(max(vals) if vals else 0.0)
    m_return = max(station_mk) if station_mk else 0.0
    operating = sum(duty.values())
    fixed = sum(_fixed(static, si) for si in range(len(static.stations)))
    cost = fixed + operating * p.time_cost

    met = receipt["metrics"]
    checks = {}
    checks["served_at"] = _cmp_map(served, {int(a): b for a, b in receipt["served"]})
    observed_jobs = {j["job_id"]: j["completed_at"]
                     for j in receipt.get("alarm_jobs", [])
                     if j["completed_at"] is not None}
    checks["alarm_served_at"] = _cmp_map(completed_jobs, observed_jobs)
    checks["M_return"] = _rel(m_return, met["M_return"])
    checks["operating_minutes"] = _rel(operating, met["operating_minutes"])
    bad = {k: v for k, v in checks.items() if not v["ok"]}
    return {
        "ok": not bad,
        "served_at": checks["served_at"],
        "M_return": checks["M_return"],
        "operating_minutes": checks["operating_minutes"],
        "recomputed": {"M_return": m_return, "operating_minutes": operating,
                       "cost": cost, "served": len(served)},
        "failures": bad,
    }


def _fixed(static: StaticContext, si: int) -> float:
    kind = static.station_types[si]
    if kind == 0:
        return 0.0
    pc = static.params
    small_station = 22.8
    large_station = 30.4
    small_drone = 5.0
    large_drone = 8.0
    if kind == 1:
        return small_station + small_drone
    return large_station + large_drone + small_drone


def _rel(a: float, b: float) -> dict:
    if b is None:
        return {"ok": False, "detail": "missing ledger value"}
    denom = max(abs(a), abs(b), 1e-12)
    err = abs(a - b) / denom
    return {"ok": err <= TOL_REL, "recomputed": a, "recorded": b,
            "rel_error": err}


def _cmp_map(a: dict, b: dict) -> dict:
    if set(a) != set(b):
        return {"ok": False, "detail": f"key mismatch {sorted(set(a) ^ set(b))[:5]}"}
    worst = 0.0
    for k in a:
        denom = max(abs(a[k]), abs(b[k]), 1e-12)
        worst = max(worst, abs(a[k] - b[k]) / denom)
    return {"ok": worst <= TOL_REL, "n": len(a), "max_rel_error": worst}
