"""Causal engine: replay a public prefix forward under one frozen particle.

Contract section 4.  This module never imports, opens or references the private simulator
objects that produced the prefix; it only consumes (StaticContext,
PublicPrefix, Particle) and its own event loop.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Callable

from .core import (CompletionRecord, DispatchRecord, ExogenousFuture,
                   ForecastView, IllegalPhysicalAction, ObservationFrame,
                   Params, Particle, PublicPrefix, PublicRolloutError,
                   ReleasedTarget, ReturnRecord, SlotAlreadyDecidedAtFrontier,
                   SlotView, StaticContext, PHYS_TOL, _f, canonical_hash)
from .exogenous_stream import blocked_by_nfz, leg_crosses_nfz, nfz_from_payload
from .forecast_book import ForecastBook

TERMINALS = ("COMPLETE", "DUTY_LIMIT", "CRASH_SERVICE_ENERGY", "HORIZON",
             "PARTIAL_COVERAGE", "TIMEOUT", "ERROR", "INTERRUPTED")

ACTION_TARGET = "TARGET"
ACTION_RETURN = "RETURN"


@dataclass(frozen=True)
class EngineConfig:
    horizon_min: float = 240.0
    max_decisions: int = 200
    duty_tol: float = 1e-7
    energy_tol: float = 1e-12


@dataclass
class _Slot:
    station: int
    slot: int
    x: float
    y: float
    at_station: bool = True
    trip_energy: float = 0.0
    duty: float = 0.0
    on_trip: list = field(default_factory=list)
    target: int | None = None      # target currently being flown to / served
    phase: str = "IDLE"            # IDLE | FLYING | SERVING
    busy_until: float = 0.0
    service_left: float = 0.0
    service_total: float = 0.0
    service_energy: float = 0.0
    flight_energy_to_date: float = 0.0
    t_depart: float = 0.0
    pending_target: int | None = None
    pending_leg: float = 0.0

    def view(self) -> SlotView:
        return SlotView(self.station, self.slot, _f(self.x), _f(self.y),
                        self.at_station, _f(self.trip_energy), _f(self.duty),
                        tuple(self.on_trip))


class CausalEngine:
    def __init__(self, static: StaticContext, prefix: PublicPrefix,
                 particle: Particle, config: EngineConfig,
                 forecast: ForecastBook):
        self.static = static
        self.prefix = prefix
        self.particle = particle
        self.config = config
        self.forecast = forecast
        self.nfz = nfz_from_payload(prefix.nfz)
        self.slots: dict[tuple[int, int], _Slot] = {}
        self._restore(prefix)
        self.t = prefix.t_min
        self.frontier_id = prefix.frontier_id
        self.decisions = 0
        self.served: dict[int, float] = dict(prefix.served_at)
        self.failed: set[int] = set(prefix.failed_targets)
        self.dispatches = list(prefix.dispatches)
        self.completions = list(prefix.completions)
        self.returns = list(prefix.returns)
        self.observations = list(prefix.observations)
        self.decided_here: set[tuple[int, int]] = set(prefix.decided)
        self.terminal: str | None = prefix.terminal
        self.failure_code: str | None = None
        self.horizon_truncated = prefix.horizon_truncated
        self.reserved: dict[int, tuple[int, int]] = {}
        # Alarm law: an exogenous fault can re-open an already swept target.
        # The schedule is exogenous and public at its own time, never before.
        self.alarm_open: set[int] = set()
        self.alarm_done: set[int] = set()
        self.alarm_seen: set[int] = set()
        # alarms scheduled relative to a sweep (alarm law), never absolute
        self.alarm_delay = {tid: d for tid, d in particle.future.fault_delays}
        self.alarm_scheduled: list[tuple[float, int]] = []
        for d in self.dispatches:
            if d.action == ACTION_TARGET and d.target is not None:
                self.reserved[d.target] = (d.station, d.slot)
        self.budget_s = float("inf")
        self._started = time.perf_counter()
        self.trace: list[dict] = []

    # ------------------------------------------------------------------
    def _restore(self, prefix: PublicPrefix) -> None:
        rows = {(r["station"], r["slot"]): r for r in prefix.slot_state}
        for key in self.static.slots():
            r = rows.get(key)
            if r is None:
                si, sj = key
                st = self.static.stations[si]
                self.slots[key] = _Slot(si, sj, st.x, st.y)
                continue
            self.slots[key] = _Slot(
                station=key[0], slot=key[1], x=r["x"], y=r["y"],
                at_station=r["at_station"], trip_energy=r["trip_energy"],
                duty=r["cumulative_duty"], on_trip=list(r.get("on_trip", [])),
                target=r.get("target_in_service"), phase=r.get("phase", "IDLE"),
                busy_until=r.get("busy_until", 0.0),
                service_left=r.get("service_left", 0.0),
                service_total=r.get("service_total", 0.0),
                service_energy=r.get("service_energy", 0.0),
                flight_energy_to_date=r.get("flight_energy_to_date", 0.0),
                t_depart=r.get("t_depart", 0.0))

    # ------------------------------------------------------------------
    @property
    def shape(self) -> dict:
        return {"static_sha256": self.static.sha256, "t": _f(self.t),
                "frontier": self.frontier_id,
                "slots": [[k[0], k[1]] for k in sorted(self.slots)],
                "particle": self.particle.sha256,
                "config": canonical_hash(self.config.__dict__),
                "forecast_versions": len(self.forecast._published)}

    def engine_id(self) -> str:
        return canonical_hash(self.shape)

    # ------------------------------------------------------------------
    def _wind_at(self, t: float) -> tuple[float, float]:
        blocks = self.particle.future.wind_blocks
        cur = (0.0, 0.0)
        for t_from, u, v in blocks:
            if t_from <= t + 1e-12:
                cur = (u, v)
            else:
                break
        return cur

    def _leg_time(self, a_xy, b_xy, t: float) -> tuple[float, float]:
        dx, dy = b_xy[0] - a_xy[0], b_xy[1] - a_xy[1]
        dist = math.hypot(dx, dy)
        if dist <= 1e-12:
            return 0.0, dist
        u, v = self._wind_at(t)
        along = (u * dx + v * dy) / dist
        speed = max(self.static.params.speed + along, 1e-3)
        return dist / speed, dist

    # ------------------------------------------------------------------
    def _released(self) -> list[ReleasedTarget]:
        """Only targets the policy is allowed to know about.

        An unreleased background request is omitted entirely: listing it as
        UNRELEASED would leak its existence, which the W contract forbids.
        """
        out = []
        rel = {tid for tr, tid in self.prefix.releases if tr <= self.t + 1e-12}
        for tid in self.static.target_ids:
            if tid in self.alarm_open:
                out.append(ReleasedTarget(tid, "OPEN", "high"))
            elif tid in self.served:
                out.append(ReleasedTarget(tid, "SERVED"))
            elif tid in self.failed:
                out.append(ReleasedTarget(tid, "FAILED"))
            elif tid in self.reserved:
                out.append(ReleasedTarget(tid, "IN_FLIGHT"))
            elif tid in rel:
                out.append(ReleasedTarget(tid, "OPEN"))
        return out

    def observation(self, decision_slot=None,
                    pending: tuple = ()) -> ObservationFrame:
        vis = self.forecast.visible(self.t)
        if vis is None:
            vis = ForecastView(0, -1.0, -1.0, -1.0, canonical_hash([]), ())
        frame = ObservationFrame(
            t_min=_f(self.t), frontier_id=self.frontier_id,
            slots=tuple(self.slots[k].view() for k in sorted(self.slots)),
            released=tuple(self._released()),
            wind_now=self._wind_at(self.t),
            forecast=vis,
            pending_order=tuple(pending),
            decision_slot=decision_slot,
            nfz=tuple(tuple(r) for r in self.prefix.nfz))
        ForecastBook.assert_no_future_in(frame)
        return frame

    # ------------------------------------------------------------------
    def legal_actions(self, key: tuple[int, int]) -> tuple[tuple[str, int | None], ...]:
        s = self.slots[key]
        if s.phase != "IDLE" or self.terminal is not None:
            return ()
        p = self.static.params
        cap = p.battery(key[1])
        if self._return_legal(key):
            actions = [(ACTION_RETURN, None)]
        else:
            actions = []
        for r in self._released():
            if r.status != "OPEN":
                continue
            if self.static.station_of_target(r.target) != key[0]:
                continue
            node = self.static.nodes[r.target]
            if self.static.distance(self.static.stations[key[0]], node) > p.radius(
                    self.static.station_types[key[0]]) + PHYS_TOL:
                continue
            if self.nfz and (blocked_by_nfz(self.nfz, (node.x, node.y), self.t)
                             or leg_crosses_nfz(self.nfz, (s.x, s.y),
                                                (node.x, node.y), self.t)):
                continue
            leg_t, _ = self._leg_time((s.x, s.y), (node.x, node.y), self.t)
            need = s.trip_energy + leg_t * p.flight_energy + r_energy(node)
            if need > cap + 1e-9:
                continue
            limit = p.duty_limit(self.static.station_types[key[0]])
            if s.duty + leg_t + node.service > limit + self.config.duty_tol:
                continue
            actions.append((ACTION_TARGET, r.target))
        return tuple(actions)

    def _return_legal(self, key) -> bool:
        s = self.slots[key]
        if s.at_station and s.phase == "IDLE":
            return False
        st = self.static.stations[key[0]]
        leg_t, _ = self._leg_time((s.x, s.y), (st.x, st.y), self.t)
        limit = self.static.params.duty_limit(self.static.station_types[key[0]])
        return s.duty + leg_t <= limit + self.config.duty_tol

    # ------------------------------------------------------------------
    def apply_physical(self, key: tuple[int, int], action) -> None:
        if self.terminal is not None:
            raise IllegalPhysicalAction("engine already terminal")
        if key in self.decided_here:
            raise SlotAlreadyDecidedAtFrontier(
                f"SLOT_ALREADY_DECIDED_AT_FRONTIER:{key}")
        kind, target = action
        if (kind, target) not in self.legal_actions(key):
            raise IllegalPhysicalAction(f"illegal physical action {action} at {key}")
        s = self.slots[key]
        if kind == ACTION_RETURN:
            st = self.static.stations[key[0]]
            leg_t, _ = self._leg_time((s.x, s.y), (st.x, st.y), self.t)
            before = s.duty
            self.returns.append(ReturnRecord(_f(self.t), key[0], key[1],
                                             _f(before), _f(before + leg_t)))
            self.dispatches.append(DispatchRecord(_f(self.t), key[0], key[1],
                                                  ACTION_RETURN, None))
            # RETURN clears the trip battery and keeps cumulative duty; the
            # battery swap happens on arrival, so duty accrues with the leg.
            s.trip_energy = 0.0
            s.flight_energy_to_date = 0.0
            s.on_trip = []
            s.target = None
            s.pending_target = None
            s.pending_leg = leg_t
            s.phase = "FLYING" if leg_t > 0 else "IDLE"
            s.busy_until = self.t + leg_t
            self._check_duty(key)
        else:
            node = self.static.nodes[target]
            leg_t, dist = self._leg_time((s.x, s.y), (node.x, node.y), self.t)
            # two-phase: the drone is FLYING until busy_until, then SERVING.
            # Position and energy move only on arrival, so deadlines and
            # observations stay consistent with the clock.
            s.phase = "FLYING"
            s.pending_target = target
            s.pending_leg = leg_t
            s.busy_until = self.t + leg_t
            s.target = target
            if target not in self.served:
                self.reserved[target] = key
            s.t_depart = self.t
            self.dispatches.append(DispatchRecord(_f(self.t), key[0], key[1],
                                                  ACTION_TARGET, target))
        self.decided_here.add(key)
        self.decisions += 1
        self.trace.append({"t": _f(self.t), "slot": [key[0], key[1]],
                           "action": [kind, target], "frontier": self.frontier_id})

    # ------------------------------------------------------------------
    def _check_duty(self, key) -> None:
        s = self.slots[key]
        limit = self.static.params.duty_limit(self.static.station_types[key[0]])
        if s.duty > limit + self.config.duty_tol:
            self.terminal = "DUTY_LIMIT"
            self.failure_code = "DUTY_LIMIT"

    def _reveal_alarms(self) -> list[dict]:
        """Publish any alarm whose time has arrived.  Idempotent."""
        out = []
        due = list(self.particle.future.faults) + list(self.alarm_scheduled)
        for t_at, tid in due:
            if tid in self.alarm_seen:
                continue
            if t_at <= self.t + 1e-12:
                self.alarm_seen.add(tid)
                self.alarm_open.add(tid)
                out.append({'t': _f(t_at), 'target': tid})
        return out

    def _advance_to(self, t_next: float) -> list[tuple]:
        """Close every event at t_next, then open one new frontier."""
        closed = []
        for key in sorted(self.slots):
            s = self.slots[key]
            if s.phase == "FLYING" and s.busy_until <= t_next + 1e-12:
                t_arr = s.busy_until
                leg = s.pending_leg
                if s.pending_target is not None:
                    tid = s.pending_target
                    node = self.static.nodes[tid]
                    s.x, s.y = node.x, node.y
                    s.at_station = False
                    s.on_trip = list(s.on_trip) + [tid]
                    s.trip_energy += leg * self.static.params.flight_energy
                    s.flight_energy_to_date += leg * self.static.params.flight_energy
                    s.duty += leg
                    s.phase = "SERVING"
                    s.service_total = node.service
                    s.service_left = node.service
                    s.service_energy = node.energy
                    s.busy_until = t_arr + node.service
                    s.pending_leg = 0.0
                    s.pending_target = None
                    closed.append(("ARRIVE_TARGET", key, _f(t_arr)))
                    self._check_duty(key)
                else:
                    st = self.static.stations[key[0]]
                    s.x, s.y = st.x, st.y
                    s.at_station = True
                    s.duty += leg
                    s.pending_leg = 0.0
                    s.phase = "IDLE"
                    closed.append(("ARRIVE_HOME", key, _f(t_arr)))
                    self._check_duty(key)
            elif s.phase == "SERVING" and s.busy_until <= t_next + 1e-12:
                t_done = s.busy_until
                need = s.service_energy
                cap = self.static.params.battery(key[1])
                if s.trip_energy + need > cap + self.config.energy_tol:
                    self.failed.add(s.target)
                    self.completions.append(CompletionRecord(
                        _f(t_done), key[0], key[1], s.target, "FAILED_ENERGY"))
                    self.terminal = "CRASH_SERVICE_ENERGY"
                    self.failure_code = "CRASH_SERVICE_ENERGY"
                    s.phase = "IDLE"
                else:
                    s.trip_energy += need
                    s.duty += s.service_left
                    if s.target in self.alarm_open:
                        self.alarm_open.discard(s.target)
                        self.alarm_done.add(s.target)
                        self.completions.append(CompletionRecord(
                            _f(t_done), key[0], key[1], s.target,
                            "ALARM_SERVICED"))
                    else:
                        self.served[s.target] = t_done
                        self.completions.append(CompletionRecord(
                            _f(t_done), key[0], key[1], s.target, "SERVED"))
                        delay = self.alarm_delay.get(s.target)
                        if (delay is not None and delay >= 0.0
                                and s.target not in self.alarm_seen
                                and s.target not in self.alarm_done):
                            self.alarm_scheduled.append((t_done + delay, s.target))
                    s.phase = "IDLE"
                    s.service_left = 0.0
                    s.target = None
                closed.append(("SERVICE_END", key, _f(t_done)))
        self.t = t_next
        for ev in self._reveal_alarms():
            closed.append(('ALARM', None, ev['t']))
        return closed

    def _next_event_time(self) -> float:
        cands = []
        for s in self.slots.values():
            if s.phase != "IDLE":
                cands.append(s.busy_until)
        for v in self.forecast._published:
            if v.publication_t > self.t + 1e-12:
                cands.append(v.publication_t)
        for t_rel, _ in self.prefix.releases:
            if t_rel > self.t + 1e-12:
                cands.append(t_rel)
        for t_at, tid in self.particle.future.faults:
            if tid not in self.alarm_seen and t_at > self.t + 1e-12:
                cands.append(t_at)
        for t_at, tid in self.alarm_scheduled:
            if tid not in self.alarm_seen and t_at > self.t + 1e-12:
                cands.append(t_at)
        if self.config.horizon_min is not None:
            cands.append(self.config.horizon_min)
        return min(cands) if cands else self.config.horizon_min

    # ------------------------------------------------------------------
    def run_with_frozen_mu(self, mu: Callable, *, deadline_s: float = 1e9,
                           max_decisions: int | None = None) -> dict:
        self.budget_s = deadline_s
        max_dec = self.config.max_decisions if max_decisions is None else max_decisions
        try:
            while self.terminal is None:
                if time.perf_counter() - self._started > deadline_s:
                    self.terminal = "TIMEOUT"
                    self.failure_code = "WALL_CLOCK"
                    break
                if self.decisions >= max_dec:
                    self.terminal = "TIMEOUT"
                    self.failure_code = "MAX_DECISIONS"
                    break
                idle = [k for k in sorted(self.slots) if self.slots[k].phase == "IDLE"]
                if not idle:
                    t_next = self._next_event_time()
                    if t_next > self.config.horizon_min + 1e-12:
                        break
                    self._advance_to(t_next)
                    self.frontier_id += 1
                    self.decided_here = set()
                    if self.terminal is not None:
                        break
                    continue
                self.decided_here = set()
                self.frontier_id += 1
                pending = tuple(idle)
                for key in pending:
                    if self.terminal is not None:
                        break
                    if key in self.decided_here:
                        continue
                    frame = self.observation(decision_slot=key, pending=pending)
                    self.observations.append(frame)
                    action = mu(frame, key, self)
                    if action is None:
                        break
                    self.apply_physical(key, action)
                if self.terminal is not None:
                    break
                t_next = self._next_event_time()
                if t_next > self.config.horizon_min + 1e-12:
                    break
                if t_next <= self.t + 1e-12 and all(
                        self.slots[k].phase == "IDLE" for k in self.slots):
                    break
                self._advance_to(t_next)
        except Exception as exc:  # noqa: BLE001 - every failure is data
            self.terminal = "ERROR"
            self.failure_code = type(exc).__name__ + ": " + str(exc)
        if self.terminal is None:
            self.terminal = self._classify()
        return self.receipt()

    def _classify(self) -> str:
        self._reveal_alarms()
        missing = [t for t in self.static.target_ids
                   if t not in self.served and t not in self.failed]
        if missing or self.alarm_open:
            return "PARTIAL_COVERAGE"
        if self.t > self.config.horizon_min + 1e-12:
            self.horizon_truncated = True
            return "HORIZON"
        return "COMPLETE"

    # ------------------------------------------------------------------
    def _metrics(self) -> dict:
        p = self.static.params
        fixed = sum(self.static.params.time_cost * 0 for _ in ())
        station_makespan = []
        for si, kind in enumerate(self.static.station_types):
            if kind == 0:
                station_makespan.append(0.0)
                continue
            best = 0.0
            for key in sorted(self.slots):
                if key[0] != si:
                    continue
                st = self.slots[key]
                duty = st.duty
                if st.phase == "SERVING":
                    duty += st.service_left
                elif st.phase == "FLYING" and st.target is None:
                    duty += max(0.0, st.busy_until - self.t)
                best = max(best, duty)
            station_makespan.append(best)
        M_return = max(station_makespan, default=0.0)
        operating = sum(s.duty for s in self.slots.values())
        for s in self.slots.values():
            if s.phase == "SERVING":
                operating += s.service_left
            elif s.phase == "FLYING" and s.target is None:
                operating += max(0.0, s.busy_until - self.t)
        fixed = sum(_station_fixed(kind) for kind in self.static.station_types)
        cost = fixed + operating * p.time_cost
        return {"M_return": _f(M_return), "operating_minutes": _f(operating),
                "cost": _f(cost), "fixed_cost": _f(fixed),
                "station_makespan": station_makespan,
                "served_count": len(self.served),
                "failed_count": len(self.failed),
                "total_targets": len(self.static.target_ids)}

    def receipt(self) -> dict:
        met = self._metrics()
        return {
            "engine_id": self.engine_id(),
            "particle_id": self.particle.particle_id,
            "particle_sha256": self.particle.sha256,
            "model_sha256": self.particle_model_sha256 if hasattr(self, "particle_model_sha256") else None,
            "terminal": self.terminal,
            "failure_code": self.failure_code,
            "t_min": _f(self.t),
            "decisions": self.decisions,
            "horizon_truncated": self.horizon_truncated,
            "served": [[a, _f(b)] for a, b in sorted(self.served.items())],
            "failed": sorted(self.failed),
            "metrics": met,
            "ledger_sha256": canonical_hash({
                "disp": [d.as_list() for d in self.dispatches],
                "comp": [c.as_list() for c in self.completions],
                "ret": [r.as_list() for r in self.returns],
                "served": [[a, _f(b)] for a, b in sorted(self.served.items())],
            }),
            "obs_sha256": [o.sha256 for o in self.observations],
            "actions": [d.as_list() for d in self.dispatches],
            "completions": [c.as_list() for c in self.completions],
            "trace": self.trace,
            "inv_dd": self.verify_no_double_dispatch(),
            "alarms": {"open": sorted(self.alarm_open),
                       "scheduled": [[_f(a), b] for a, b in self.alarm_scheduled],
                       "serviced": sorted(self.alarm_done),
                       "seen": sorted(self.alarm_seen)},
        }

    def verify_no_double_dispatch(self) -> dict:
        seen: dict[int, list] = {}
        for d in self.dispatches:
            if d.action == ACTION_TARGET and d.target is not None:
                seen.setdefault(d.target, []).append([d.station, d.slot])
        multi = {t: v for t, v in seen.items() if len(v) > 1}
        return {"ok": not multi, "multi": multi}


def _station_fixed(kind: int) -> float:
    """Liu fixed cost: station + drones, by station type."""
    if kind == 0:
        return 0.0
    if kind == 1:
        return 22.8 + 5.0
    return 30.4 + 8.0 + 5.0


def r_energy(node) -> float:
    return node.energy