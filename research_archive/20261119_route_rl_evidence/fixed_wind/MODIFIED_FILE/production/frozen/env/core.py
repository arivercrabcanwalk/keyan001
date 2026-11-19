"""public_rollout core objects.

Faithful, self-contained implementation of the object model in
PUBLIC_ROLLOUT_CONTRACT.md sections 2 and 7.  Standard library only.

Three objects are kept strictly separate:
  StaticContext  -- instance-level constants, shared by every method
  PublicPrefix   -- the immutable causal ledger (everything the policy saw)
  Particle       -- one frozen-model sample of the hidden past and future
                    (never visible to a policy)

Deviations from the contract's ten-module split are documented in
DOCS/MODULE_MAP.md; the object and invariant names are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence

PHYS_TOL = 1e-7
POS_TOL = 1e-9
ENERGY_TOL = 1e-12
DUTY_TOL = 1e-12


class PublicRolloutError(RuntimeError):
    """Base class for every fail-closed error in this package."""


class PhaseNotIdentifiable(PublicRolloutError):
    """Raised when the hidden service phase cannot be recovered uniquely."""


class ParticleIncompatible(PublicRolloutError):
    """Raised when no compatible latent sample can be found."""


class SlotAlreadyDecidedAtFrontier(PublicRolloutError):
    """Raised when a caller tries to re-decide a slot at the same frontier."""


class PublicationRewrite(PublicRolloutError):
    """Raised when a published forecast version is mutated or reused."""


class IllegalPhysicalAction(PublicRolloutError):
    """Raised for an action outside {(slot,target), (slot,RETURN)} or illegal."""


class PauseAtPublicDecision(PublicRolloutError):
    """Yield computation before dispatch; this is not a physical WAIT action."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def _f(x: float) -> float:
    if not math.isfinite(x):
        raise ValueError("non-finite value in a public object")
    return float(x)


@dataclass(frozen=True)
class Params:
    speed: float = 900.0
    flight_energy: float = 0.018
    small_battery: float = 0.81
    large_battery: float = 1.0
    small_radius: float = 4000.0
    large_radius: float = 5000.0
    small_duration: float = 480.0
    large_duration: float = 600.0
    time_cost: float = 0.5

    def battery(self, slot: int) -> float:
        return self.large_battery if slot == 0 else self.small_battery

    def radius(self, kind: int) -> float:
        return self.small_radius if kind == 1 else self.large_radius

    def duty_limit(self, kind: int) -> float:
        return self.small_duration if kind == 1 else self.large_duration


@dataclass(frozen=True)
class Node:
    node_id: int
    x: float
    y: float
    energy: float
    service: float


@dataclass(frozen=True)
class StaticContext:
    """A-01..A-13 are checked by validate_static()."""

    instance_sha256: str
    params: Params
    stations: tuple[Node, ...]
    targets: tuple[Node, ...]
    station_types: tuple[int, ...]
    target_station: tuple[tuple[int, int], ...]
    mode: str = "S"
    day_id: str = "d0"
    horizon_min: float | None = None
    # (target, deadline_min, priority) for the W contract.  Empty means every
    # target is routine with an infinite deadline, which is the S contract.
    deadlines: tuple[tuple[int, float, str], ...] = ()

    # ---- derived, cheap, and public -------------------------------------
    @property
    def nodes(self) -> dict[int, Node]:
        return {n.node_id: n for n in self.targets + self.stations}

    @property
    def target_ids(self) -> tuple[int, ...]:
        return tuple(n.node_id for n in self.targets)

    def station_of_target(self, tid: int) -> int:
        return dict(self.target_station)[tid]

    def slots(self) -> tuple[tuple[int, int], ...]:
        out = []
        for si, kind in enumerate(self.station_types):
            if kind == 1:
                out.append((si, 1))
            elif kind == 2:
                out += [(si, 0), (si, 1)]
        return tuple(out)

    def distance(self, a: Node, b: Node) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    def payload(self) -> dict:
        return {
            "instance_sha256": self.instance_sha256,
            "params": {k: _f(v) for k, v in self.params.__dict__.items()},
            "stations": [[n.node_id, _f(n.x), _f(n.y), _f(n.energy), _f(n.service)]
                         for n in self.stations],
            "targets": [[n.node_id, _f(n.x), _f(n.y), _f(n.energy), _f(n.service)]
                        for n in self.targets],
            "station_types": list(self.station_types),
            "target_station": [list(p) for p in self.target_station],
            "mode": self.mode,
            "day_id": self.day_id,
            "horizon_min": self.horizon_min,
            "deadlines": [[a, _f(b), c] for a, b, c in self.deadlines],
        }

    @property
    def sha256(self) -> str:
        return canonical_hash(self.payload())


def validate_static(ctx: StaticContext) -> None:
    """A-01..A-13: fail closed on any malformed static context."""
    if not ctx.stations:
        raise PublicRolloutError("A-01: no stations")
    if not ctx.targets:
        raise PublicRolloutError("A-02: no targets")
    ids = [n.node_id for n in ctx.stations + ctx.targets]
    if len(set(ids)) != len(ids):
        raise PublicRolloutError("A-03: duplicate node id")
    if len(ctx.station_types) != len(ctx.stations):
        raise PublicRolloutError("A-04: station_types length mismatch")
    if any(t not in (0, 1, 2) for t in ctx.station_types):
        raise PublicRolloutError("A-05: illegal station type")
    if sorted(t[0] for t in ctx.target_station) != sorted(ctx.target_ids):
        raise PublicRolloutError("A-06: target_station must cover every target once")
    for tid, si in ctx.target_station:
        if not 0 <= si < len(ctx.stations):
            raise PublicRolloutError("A-07: target station out of range")
        if ctx.station_types[si] == 0:
            raise PublicRolloutError("A-08: target assigned to a closed station")
        if ctx.distance(ctx.stations[si], ctx.nodes[tid]) > ctx.params.radius(ctx.station_types[si]) + PHYS_TOL:
            raise PublicRolloutError("A-09: target outside station radius")
    if ctx.params.small_battery > ctx.params.large_battery:
        raise PublicRolloutError("A-10: battery ordering")
    if ctx.params.small_radius > ctx.params.large_radius:
        raise PublicRolloutError("A-11: radius ordering")
    if ctx.params.small_duration > ctx.params.large_duration:
        raise PublicRolloutError("A-12: duration ordering")
    if ctx.mode not in ("S", "W"):
        raise PublicRolloutError("A-13: unknown mode")
    if ctx.deadlines:
        seen = set()
        for tid, ddl, prio in ctx.deadlines:
            if tid not in ctx.nodes:
                raise PublicRolloutError("A-14: deadline for an unknown target")
            if tid in seen:
                raise PublicRolloutError("A-15: duplicate deadline entry")
            seen.add(tid)
            if not math.isfinite(ddl) or ddl <= 0:
                raise PublicRolloutError("A-16: deadline must be finite and positive")
            if prio not in ("high", "routine"):
                raise PublicRolloutError("A-17: unknown priority")
        if seen != set(ctx.target_ids):
            raise PublicRolloutError("A-18: deadlines must cover every target once")


# ---------------------------------------------------------------------------
# Public ledger records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlotView:
    station: int
    slot: int
    x: float
    y: float
    at_station: bool
    trip_energy: float
    cumulative_duty: float
    on_trip: tuple[int, ...]

    def as_list(self) -> list:
        return [self.station, self.slot, _f(self.x), _f(self.y), self.at_station,
                _f(self.trip_energy), _f(self.cumulative_duty), list(self.on_trip)]


@dataclass(frozen=True)
class ReleasedTarget:
    target: int
    status: str          # OPEN | RESERVED | IN_FLIGHT | SERVED | FAILED | UNRELEASED
    priority: str = "routine"
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class ForecastView:
    version: int
    publication_t: float
    valid_from: float
    valid_to: float
    content_sha256: str
    wind_blocks: tuple[tuple[float, float, float], ...]  # (t_from, u, v)


@dataclass(frozen=True)
class ObservationFrame:
    """The ONLY thing a policy may read.  Field set is whitelisted (T2-A5)."""

    t_min: float
    frontier_id: int
    slots: tuple[SlotView, ...]
    released: tuple[ReleasedTarget, ...]
    wind_now: tuple[float, float]
    forecast: ForecastView
    pending_order: tuple[tuple[int, int], ...]
    decision_slot: tuple[int, int] | None
    nfz: tuple[tuple, ...] = ()
    alarm_jobs: tuple[tuple, ...] = ()

    def payload(self) -> dict:
        return {
            "t_min": _f(self.t_min),
            "frontier_id": self.frontier_id,
            "slots": [s.as_list() for s in self.slots],
            "released": [[r.target, r.status, r.priority, _f(r.x), _f(r.y)]
                         for r in self.released],
            "wind_now": [_f(self.wind_now[0]), _f(self.wind_now[1])],
            "forecast": [self.forecast.version, _f(self.forecast.publication_t),
                         _f(self.forecast.valid_from), _f(self.forecast.valid_to),
                         self.forecast.content_sha256,
                         [[_f(a), _f(b), _f(c)] for a, b, c in self.forecast.wind_blocks]],
            "pending_order": [list(p) for p in self.pending_order],
            "decision_slot": None if self.decision_slot is None else list(self.decision_slot),
            "nfz": [[_f(x) for x in row] for row in self.nfz],
            "alarm_jobs": [list(row) for row in self.alarm_jobs],
        }

    @property
    def sha256(self) -> str:
        return canonical_hash(self.payload())


OBSERVATION_FIELDS = frozenset(ObservationFrame.__dataclass_fields__)
FORBIDDEN_OBSERVATION_FIELDS = frozenset(
    {"remaining_service_min", "progress", "phase", "weight", "hidden", "truth"})


@dataclass(frozen=True)
class DispatchRecord:
    t: float
    station: int
    slot: int
    action: str            # TARGET | RETURN
    target: int | None
    job_id: str | None = None

    def as_list(self) -> list:
        return [_f(self.t), self.station, self.slot, self.action, self.target,
                self.job_id]


@dataclass(frozen=True)
class CompletionRecord:
    t: float
    station: int
    slot: int
    target: int
    outcome: str           # SERVED | FAILED_ENERGY

    def as_list(self) -> list:
        return [_f(self.t), self.station, self.slot, self.target, self.outcome]


@dataclass(frozen=True)
class ReturnRecord:
    t: float
    station: int
    slot: int
    duty_before: float
    duty_after: float

    def as_list(self) -> list:
        return [_f(self.t), self.station, self.slot, _f(self.duty_before), _f(self.duty_after)]


@dataclass(frozen=True)
class PublicPrefix:
    """Immutable causal ledger.  Everything here was public at the time."""

    static_sha256: str
    t_min: float
    frontier_id: int
    observations: tuple[ObservationFrame, ...] = ()
    dispatches: tuple[DispatchRecord, ...] = ()
    completions: tuple[CompletionRecord, ...] = ()
    returns: tuple[ReturnRecord, ...] = ()
    releases: tuple[tuple[float, int], ...] = ()
    publications: tuple[ForecastView, ...] = ()
    served_at: tuple[tuple[int, float], ...] = ()
    failed_targets: tuple[int, ...] = ()
    slot_state: tuple[tuple, ...] = ()
    pending_order: tuple[tuple[int, int], ...] = ()
    decided: tuple[tuple[int, int], ...] = ()
    nfz: tuple[tuple, ...] = ()
    alarm_ledger: tuple[tuple, ...] = ()
    horizon_truncated: bool = False
    terminal: str | None = None

    def append(self, **kw) -> "PublicPrefix":
        return replace(self, **kw)

    def ledger_sha256(self) -> str:
        return canonical_hash({
            "static": self.static_sha256, "t": _f(self.t_min),
            "frontier": self.frontier_id,
            "obs": [o.sha256 for o in self.observations],
            "disp": [d.as_list() for d in self.dispatches],
            "comp": [c.as_list() for c in self.completions],
            "ret": [r.as_list() for r in self.returns],
            "rel": [[_f(a), b] for a, b in self.releases],
            "pub": [[p.version, _f(p.publication_t), p.content_sha256] for p in self.publications],
            "served": [[a, _f(b)] for a, b in self.served_at],
            "failed": list(self.failed_targets),
            "alarms": [list(row) for row in self.alarm_ledger],
            "slot": [list(s) for s in self.slot_state],
            "pending": [list(p) for p in self.pending_order],
            "decided": [list(p) for p in self.decided],
            "trunc": self.horizon_truncated,
            "term": self.terminal,
        })

    def verify_inv_dd(self) -> dict:
        """INV-DD: each planned task and each released alarm job is dispatched once."""
        seen: dict[str, int] = {}
        for d in self.dispatches:
            if d.action != "TARGET" or d.target is None:
                continue
            key = d.job_id or f"planned:{d.target}"
            seen[key] = seen.get(key, 0) + 1
        multi = {t: c for t, c in seen.items() if c > 1}
        return {"ok": not multi, "dispatchers": seen, "multi": multi}


# ---------------------------------------------------------------------------
# Particle (hidden; never enters ObservationFrame)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlotPhase:
    """Hidden remaining service for a busy slot (minutes)."""

    station: int
    slot: int
    target: int
    remaining_service_min: float


@dataclass(frozen=True)
class AlarmJob:
    job_id: str
    target: int
    release: float
    deadline: float
    priority: str

    def as_list(self) -> list:
        return [self.job_id, self.target, _f(self.release),
                _f(self.deadline), self.priority]


@dataclass(frozen=True)
class ExogenousFuture:
    wind_blocks: tuple[tuple[float, float, float], ...]
    releases: tuple[tuple[float, int], ...]
    faults: tuple[tuple[float, int], ...] = ()
    # Legacy service-relative law is rejected by the W engine.
    fault_delays: tuple[tuple[int, float], ...] = ()
    alarm_jobs: tuple[AlarmJob, ...] = ()


@dataclass(frozen=True)
class Particle:
    particle_id: str
    seed: int
    hidden_past_wind: tuple[tuple[float, float, float], ...]
    hidden_phases: tuple[SlotPhase, ...]
    future: ExogenousFuture
    weight: float = 1.0

    def payload(self) -> dict:
        return {
            "particle_id": self.particle_id, "seed": self.seed,
            "past": [[_f(a), _f(b), _f(c)] for a, b, c in self.hidden_past_wind],
            "phases": [[p.station, p.slot, p.target, _f(p.remaining_service_min)]
                       for p in self.hidden_phases],
            "future": {
                "wind": [[_f(a), _f(b), _f(c)] for a, b, c in self.future.wind_blocks],
                "releases": [[_f(a), b] for a, b in self.future.releases],
                "faults": [[_f(a), b] for a, b in self.future.faults],
                "fault_delays": [[a, _f(b)] for a, b in self.future.fault_delays],
                "alarm_jobs": [j.as_list() for j in self.future.alarm_jobs],
            },
            "weight": _f(self.weight),
        }

    @property
    def sha256(self) -> str:
        return canonical_hash(self.payload())
