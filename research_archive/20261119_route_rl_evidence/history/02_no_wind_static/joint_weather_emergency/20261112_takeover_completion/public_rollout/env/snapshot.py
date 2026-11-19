"""Export a PublicPrefix from a running engine (the only way a prefix is born)."""
from __future__ import annotations

from .core import PublicPrefix, canonical_hash


def snapshot(engine, releases: tuple = (), pending: tuple = ()) -> PublicPrefix:
    rows = []
    for key in sorted(engine.slots):
        s = engine.slots[key]
        rows.append({
            "station": s.station, "slot": s.slot,
            "x": s.x, "y": s.y, "at_station": s.at_station,
            "trip_energy": s.trip_energy, "cumulative_duty": s.duty,
            "on_trip": list(s.on_trip),
            "target_in_service": s.target,
            "phase": s.phase,
            "busy_until": s.busy_until,
            "service_left": s.service_left,
            "service_total": s.service_total,
            "service_energy": s.service_energy,
            "flight_energy_to_date": s.flight_energy_to_date,
            "t_now": engine.t,
            "t_depart": s.t_depart,
            "service_duration": s.service_total,
        })
    return PublicPrefix(
        static_sha256=engine.static.sha256,
        t_min=engine.t,
        frontier_id=engine.frontier_id,
        observations=tuple(engine.observations),
        dispatches=tuple(engine.dispatches),
        completions=tuple(engine.completions),
        returns=tuple(engine.returns),
        releases=tuple(releases) if releases else tuple(engine.prefix.releases),
        publications=tuple(engine.forecast.publications_until(engine.t)),
        served_at=tuple(sorted(engine.served.items())),
        failed_targets=tuple(sorted(engine.failed)),
        slot_state=tuple(rows),
        pending_order=tuple(pending),
        nfz=tuple(tuple(r) for r in engine.prefix.nfz),
        decided=tuple(sorted(engine.decided_here)),
        horizon_truncated=engine.horizon_truncated,
        terminal=engine.terminal,
    )


def prefix_sha256(prefix: PublicPrefix) -> str:
    return prefix.ledger_sha256()