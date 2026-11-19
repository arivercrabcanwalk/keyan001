"""Frozen latent-past sampler (contract section 3, hypothesis H2).

The sampler only ever sees (StaticContext, PublicPrefix) and a seed.  It
produces particles whose hidden past and hidden phases are *compatible* with
the recorded public state by construction, and it refuses to emit a unique
"exact remaining service" because that quantity is not identifiable in
general (see recover_exact_phase).

Model constants are frozen here and must be fitted on an independent TRAIN
split before any scientific use; this module ships the engineering default.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from .core import (ExogenousFuture, Particle, ParticleIncompatible,
                   PhaseNotIdentifiable, PublicPrefix, PublicRolloutError,
                   SlotPhase, StaticContext, _f, canonical_hash)

MODEL_ID = "frozen-h3-bridge-v1"
MODEL_SHA256 = hashlib.sha256(
    b"frozen-h3-bridge-v1|wind_max=1.0|phase=elapsed-flight|gust=0").hexdigest()


@dataclass(frozen=True)
class FrozenModelParams:
    """Frozen; do not tune against outcomes."""

    wind_max: float = 1.0          # |along-track wind| bound, m/min
    phase_prior: str = "elapsed-flight-uniform"
    gust_prob: float = 0.0
    fault_rate: float = 0.0

    @property
    def sha256(self) -> str:
        return canonical_hash(self.__dict__)


class FrozenParticleModel:
    def __init__(self, params: FrozenModelParams | None = None):
        self.params = params or FrozenModelParams()
        self.model_id = MODEL_ID
        self.model_sha256 = MODEL_SHA256

    # -- introspection -----------------------------------------------------
    def info(self) -> dict:
        return {"model_id": self.model_id, "model_sha256": self.model_sha256,
                "params_sha256": self.params.sha256,
                "params": self.params.__dict__}

    # -- compatibility -----------------------------------------------------
    @staticmethod
    def _slot_rows(prefix: PublicPrefix) -> dict[tuple[int, int], dict]:
        return {(r["station"], r["slot"]): r for r in prefix.slot_state}

    def check_compatible(self, static: StaticContext, prefix: PublicPrefix,
                         particle: Particle) -> None:
        if prefix.static_sha256 != static.sha256:
            raise ParticleIncompatible("C0_STATIC_MISMATCH")
        rows = self._slot_rows(prefix)
        phases = {(p.station, p.slot): p for p in particle.hidden_phases}
        for key, row in rows.items():
            if row["at_station"]:
                continue
            phase = phases.get(key)
            if phase is None:
                raise ParticleIncompatible(f"C5_MISSING_PHASE:{key}")
            if not (0.0 - 1e-12 <= phase.remaining_service_min
                    <= row["service_duration"] + 1e-12):
                raise ParticleIncompatible(f"C5_PHASE_RANGE:{key}")
        for key in phases:
            if key not in rows:
                raise ParticleIncompatible(f"C5_UNKNOWN_SLOT:{key}")
        pmax = self.params.wind_max + 1e-12
        for _, u, v in particle.hidden_past_wind:
            if abs(u) > pmax or abs(v) > pmax:
                raise ParticleIncompatible("C2_WIND_OUT_OF_SUPPORT")
        for _, u, v in particle.future.wind_blocks:
            if abs(u) > pmax or abs(v) > pmax:
                raise ParticleIncompatible("C6_FUTURE_WIND_OUT_OF_SUPPORT")

    # -- sampling ----------------------------------------------------------
    def sample(self, static: StaticContext, prefix: PublicPrefix, *,
               seed: int, n_particles: int = 1,
               max_tries: int = 200) -> list[Particle]:
        out: list[Particle] = []
        tries = 0
        while len(out) < n_particles:
            if tries >= max_tries * n_particles:
                raise ParticleIncompatible("PARTICLE_INCOMPATIBLE: exhausted tries")
            tries += 1
            rng = random.Random((int(seed) << 20) ^ (tries * 0x9E3779B1))
            try:
                p = self._one(static, prefix, rng, idx=len(out))
                self.check_compatible(static, prefix, p)
                out.append(p)
            except ParticleIncompatible:
                continue
        return out

    def _one(self, static: StaticContext, prefix: PublicPrefix,
             rng: random.Random, idx: int) -> Particle:
        rows = self._slot_rows(prefix)
        phases: list[SlotPhase] = []
        past: list[tuple[float, float, float]] = []
        for key, row in sorted(rows.items()):
            if row["at_station"]:
                continue
            e_lo, e_hi = self._flight_window(static, row)
            # Elapsed flight time is the hidden coordinate.  It is consistent
            # with the recorded energy because flight energy and service
            # energy trade off along the leg.
            e = rng.uniform(e_lo, e_hi) if e_hi > e_lo else e_lo
            elapsed_service = max(0.0, (row["t_now"] - row["t_depart"]) - e)
            remaining = min(max(row["service_duration"] - elapsed_service, 0.0),
                            row["service_duration"])
            phases.append(SlotPhase(key[0], key[1], row["target_in_service"] or -1,
                                    _f(remaining)))
            tid = row.get("target_in_service")
            if tid is not None and tid in static.nodes:
                leg = static.distance(static.stations[row["station"]],
                                      static.nodes[tid])
            else:
                leg = 0.0
            w = (leg / e - static.params.speed) if e > 0 else 0.0
            w = min(max(w, -self.params.wind_max), self.params.wind_max)
            past.append((_f(0.0), _f(w), 0.0))
        future_blocks = []
        t = prefix.t_min
        horizon = static.horizon_min if static.horizon_min is not None else t + 240.0
        while t < horizon - 1e-12:
            future_blocks.append((_f(t), _f(rng.uniform(-self.params.wind_max,
                                                        self.params.wind_max)), 0.0))
            t += 30.0
        future = ExogenousFuture(wind_blocks=tuple(future_blocks),
                                 releases=tuple(prefix.releases), faults=())
        return Particle(particle_id=f"p{idx:04d}", seed=prefix.frontier_id * 1000 + idx,
                        hidden_past_wind=tuple(past), hidden_phases=tuple(phases),
                        future=future)

    # -- the physical window for the hidden elapsed flight time ------------
    @staticmethod
    def _flight_window(static: StaticContext, row: dict) -> tuple[float, float]:
        """Elapsed flight time consistent with the recorded trip energy.

        energy(trip) = flight_energy * e + (elapsed_service / duration) * E_service
        with elapsed_service = t_now - t_dep - e.  Solving for e under
        0 <= elapsed_service <= duration gives the admissible window.
        """
        t_dep = row["t_depart"]
        t_now = row["t_now"]
        dur = row["service_duration"]
        es = row["service_energy"]
        fe = static.params.flight_energy
        trip = row["trip_energy"]
        lo, hi = 0.0, max(0.0, t_now - t_dep)
        if es > 0 and dur > 0:
            # trip = fe*e + es*(t_now - t_dep - e)/dur
            # => e*(fe - es/dur) = trip - es*(t_now-t_dep)/dur
            k = fe - es / dur
            if abs(k) < 1e-15:
                return lo, hi          # energy is invariant in e: full alias
            e = (trip - es * (t_now - t_dep) / dur) / k
            return max(lo, min(e, hi)), max(lo, min(e, hi))
        if es == 0.0:
            if fe <= 0:
                return lo, hi
            e = trip / fe
            return max(lo, min(e, hi)), max(lo, min(e, hi))
        return lo, hi

    # -- identifiability of the hidden service phase ------------------------
    @staticmethod
    def recover_exact_phase(static: StaticContext, prefix: PublicPrefix,
                            station: int, slot: int, tol: float = 1e-12) -> float:
        """Return the remaining service time, or refuse.

        The recorded trip energy obeys

            trip = fe*e + E_service*(T - e)/dur,      T = t_now - t_depart

        which is linear in the elapsed flight time e with slope
        k = fe - E_service/dur.

          k != 0  ->  e is pinned, so the phase is identifiable;
          k == 0  ->  the equation is an identity for every e, so the same
                      public ledger supports a continuum of remaining
                      service values and any point answer would be fabricated.

        The alias fixture (f03) is exactly the k == 0 case.  We also refuse
        when the trip already served an earlier target, because then the
        accumulator contains that leg's service energy and the identity above
        no longer isolates the current leg.
        """
        rows = {(r["station"], r["slot"]): r for r in prefix.slot_state}
        row = rows.get((station, slot))
        if row is None:
            raise ParticleIncompatible(f"C5_UNKNOWN_SLOT:{(station, slot)}")
        if row.get("at_station", True):
            raise PhaseNotIdentifiable("PHASE_NOT_IDENTIFIABLE: slot is idle at station")
        on_trip = row.get("on_trip") or []
        if len(on_trip) != 1:
            raise PhaseNotIdentifiable(
                "PHASE_NOT_IDENTIFIABLE: trip served an earlier target, the "
                "energy accumulator no longer isolates the current leg")
        dur = float(row.get("service_duration") or 0.0)
        if dur <= 0.0:
            raise PhaseNotIdentifiable("PHASE_NOT_IDENTIFIABLE: zero service duration")
        es = float(row.get("service_energy") or 0.0)
        k = static.params.flight_energy - es / dur
        if abs(k) <= tol:
            raise PhaseNotIdentifiable(
                "PHASE_NOT_IDENTIFIABLE: flight power equals the service energy "
                "rate, so trip energy is invariant in the elapsed flight time")
        T = float(row["t_now"]) - float(row["t_depart"])
        e = (float(row["trip_energy"]) - es * T / dur) / k
        if e < -1e-9 or e > T + 1e-9:
            raise ParticleIncompatible(
                f"C4_PHASE_OUTSIDE_LEG: e={e} not in [0,{T}]")
        return dur - (T - e)
