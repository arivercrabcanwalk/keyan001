"""Uniform constant wind, track-holding airspeed, time-linear flight energy.

This is an explicit static model: no alarms, background arrivals or NFZ.
It does not modify or qualify the earlier dynamic WX engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .causal_engine import CausalEngine
from .core import PublicRolloutError, validate_static


@dataclass(frozen=True)
class ConstantWind:
    wx: float
    wy: float
    airspeed: float

    def __post_init__(self):
        if (not all(math.isfinite(x) for x in (self.wx, self.wy, self.airspeed))
                or self.airspeed <= 0):
            raise ValueError("finite wind and positive airspeed required")
        if math.hypot(self.wx, self.wy) >= self.airspeed:
            raise ValueError("NO_CLOSED_TOUR_SUPPORT: wind must be below airspeed")

    @property
    def discriminant(self):
        return self.airspeed**2 - self.wx**2 - self.wy**2

    def ground_speed(self, dx: float, dy: float) -> float:
        length = math.hypot(dx, dy)
        if not math.isfinite(length):
            raise ValueError("finite displacement required")
        if length == 0:
            return self.airspeed
        along = (self.wx * dx + self.wy * dy) / length
        cross = (self.wx * dy - self.wy * dx) / length
        return along + math.sqrt(self.airspeed**2 - cross**2)

    def flight_time(self, origin, destination) -> float:
        dx, dy = destination[0] - origin[0], destination[1] - origin[1]
        return math.hypot(dx, dy) / self.ground_speed(dx, dy)

    def transform(self, point) -> tuple[float, float]:
        """Symmetric closed-tour metric, in minutes; geometry eligibility stays original."""
        magnitude = math.hypot(self.wx, self.wy)
        if magnitude == 0:
            return point[0] / self.airspeed, point[1] / self.airspeed
        parallel = (self.wx * point[0] + self.wy * point[1]) / magnitude
        perpendicular = (-self.wy * point[0] + self.wx * point[1]) / magnitude
        return (self.airspeed * parallel / self.discriminant,
                perpendicular / math.sqrt(self.discriminant))

    def edge_decomposition(self, origin, destination) -> tuple[float, float]:
        a, b = self.transform(origin), self.transform(destination)
        symmetric = math.dist(a, b)
        potential_delta = (self.wx * (destination[0] - origin[0])
                           + self.wy * (destination[1] - origin[1])) / self.discriminant
        return symmetric, potential_delta


class ConstantWindEngine(CausalEngine):
    """Static physical-route engine with a complete known-return reservation."""

    def __init__(self, static, prefix, particle, config, forecast):
        validate_static(static)
        if (particle.future.faults or particle.future.fault_delays
                or particle.future.alarm_jobs or prefix.alarm_ledger
                or prefix.nfz or particle.hidden_phases or particle.hidden_past_wind
                or sorted(particle.future.releases)
                != [(0.0, t) for t in sorted(static.target_ids)]):
            raise PublicRolloutError("STATIC_CONSTANT_WIND_SCOPE_REQUIRED")
        blocks = particle.future.wind_blocks
        if (not blocks or blocks[0][0] != 0
                or any((u, v) != blocks[0][1:] for _, u, v in blocks)):
            raise PublicRolloutError("CONSTANT_WIND_VECTOR_REQUIRED")
        self.wind_model = ConstantWind(*blocks[0][1:], static.params.speed)
        self.return_energy_ledger = []
        super().__init__(static, prefix, particle, config, forecast)

    def _leg_time(self, origin, destination, t):
        return self.wind_model.flight_time(origin, destination), math.dist(origin, destination)

    def legal_actions(self, key):
        actions = super().legal_actions(key)
        slot = self.slots[key]
        station = self.static.stations[key[0]]
        params = self.static.params
        cap = params.battery(key[1])
        duty_limit = params.duty_limit(self.static.station_types[key[0]])
        result = []
        for kind, tid in actions:
            if kind == "RETURN":
                result.append((kind, tid))
                continue
            node = self.static.nodes[tid]
            leg, _ = self._leg_time((slot.x, slot.y), (node.x, node.y), self.t)
            back, _ = self._leg_time((node.x, node.y), (station.x, station.y), self.t)
            if (slot.trip_energy + (leg + back) * params.flight_energy + node.energy
                    > cap + self.config.energy_tol):
                continue
            if slot.duty + leg + node.service + back > duty_limit + self.config.duty_tol:
                continue
            result.append((kind, tid))
        return tuple(result)

    def _return_legal(self, key):
        slot = self.slots[key]
        if slot.phase != "IDLE" or slot.at_station:
            return False
        home = self.static.stations[key[0]]
        duration, _ = self._leg_time((slot.x, slot.y), (home.x, home.y), self.t)
        params = self.static.params
        return (slot.trip_energy + duration * params.flight_energy
                <= params.battery(key[1]) + self.config.energy_tol
                and slot.duty + duration <= params.duty_limit(
                    self.static.station_types[key[0]]) + self.config.duty_tol)

    def _settle_return(self, key, previous_energy, previous_flight, leg, arrived_at):
        slot = self.slots[key]
        spent = leg * self.static.params.flight_energy
        total = previous_energy + spent
        self.return_energy_ledger.append({
            "station": key[0], "slot": key[1], "arrived_at": arrived_at,
            "energy_before_return": previous_energy, "return_energy": spent,
            "total_trip_energy": total})
        if total > self.static.params.battery(key[1]) + self.config.energy_tol:
            self.terminal = "CRASH_RETURN_ENERGY"
            self.failure_code = "CRASH_RETURN_ENERGY"
            return
        slot.trip_energy = 0.0
        slot.flight_energy_to_date = 0.0
        slot.on_trip = []
        home = self.static.stations[key[0]]
        slot.x, slot.y, slot.at_station = home.x, home.y, True

    def apply_physical(self, key, action):
        slot = self.slots[key]
        previous_energy, previous_flight = slot.trip_energy, slot.flight_energy_to_date
        previous_trip = list(slot.on_trip)
        super().apply_physical(key, action)
        if action[0] == "RETURN":
            # The inherited engine clears on departure; this variant swaps only at home.
            slot.trip_energy, slot.flight_energy_to_date = previous_energy, previous_flight
            slot.on_trip = previous_trip
            if slot.pending_leg == 0:
                self._settle_return(key, previous_energy, previous_flight, 0.0, self.t)

    def _advance_to(self, t_next):
        home_arrivals = [(key, s.trip_energy, s.flight_energy_to_date,
                          s.pending_leg, s.busy_until)
                         for key, s in self.slots.items()
                         if s.phase == "FLYING" and s.pending_target is None
                         and s.busy_until <= t_next + 1e-12]
        events = super()._advance_to(t_next)
        for key, energy, flight, leg, at in home_arrivals:
            self._settle_return(key, energy, flight, leg, at)
        return events

    def receipt(self):
        result = super().receipt()
        result["physics_model"] = "uniform-constant-wind-track-holding-linear-energy-v1"
        result["constant_wind"] = [self.wind_model.wx, self.wind_model.wy]
        result["return_energy_ledger"] = list(self.return_energy_ledger)
        return result
