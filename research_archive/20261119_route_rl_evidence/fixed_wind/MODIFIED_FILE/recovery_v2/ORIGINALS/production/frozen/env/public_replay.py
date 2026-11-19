"""Exact finite-support public-history filtering by physical replay.

Every atom is a joint, pre-frozen model hypothesis, not the actual world.
Only public decision frames, legal sets and actions are observed. Rebuilt
hidden states belong to replayed atoms. No source engine/snapshot is accepted.
This finite, deterministic-observation model does not qualify continuous WX.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import math
import random

from .causal_engine import CausalEngine, EngineConfig
from .core import (ForecastView, ObservationFrame, Particle,
                   PauseAtPublicDecision, PublicPrefix, PublicRolloutError,
                   StaticContext, canonical_hash, validate_static)
from .forecast_book import ForecastBook
from .snapshot import snapshot


class ReplayHistoryError(PublicRolloutError):
    pass


class ZeroReplaySupport(PublicRolloutError):
    pass


@dataclass(frozen=True)
class PublicStep:
    frame: ObservationFrame
    legal: tuple
    action: tuple


@dataclass(frozen=True)
class PublicReplayHistory:
    static_sha256: str
    steps: tuple[PublicStep, ...]
    current: ObservationFrame
    current_legal: tuple


@dataclass(frozen=True)
class ReplayAtom:
    atom_id: str
    prior: float
    particle: Particle
    publications: tuple[ForecastView, ...]


@dataclass
class ReplayPosterior:
    model_sha256: str
    atom_ids: tuple
    weights: tuple
    states: tuple
    rejections: tuple

    def sample(self, seed: int) -> CausalEngine:
        u = random.Random(seed).random()
        total = 0.0
        for weight, state in zip(self.weights, self.states):
            total += weight
            if state is not None and u < total:
                return copy.deepcopy(state)
        return copy.deepcopy(next(
            s for w, s in reversed(tuple(zip(self.weights, self.states)))
            if w > 0 and s is not None))

    def snapshots(self) -> tuple:
        """Model-state snapshots, never an observation supplied by the world."""
        return tuple(None if state is None else snapshot(state)
                     for state in self.states)


def _same_public(got: ObservationFrame, want: ObservationFrame) -> bool:
    # No tolerance or hidden-phase proxy: exact discrete observation likelihood.
    return got.payload() == want.payload()


def _weights(masses: tuple) -> tuple:
    total = math.fsum(masses)
    if total <= 0:
        raise ZeroReplaySupport("ZERO_PUBLIC_REPLAY_SUPPORT")
    return tuple(m / total for m in masses)


def _book(versions: tuple[ForecastView, ...], horizon: float) -> ForecastBook:
    if not versions:
        raise ValueError("a frozen joint forecast path is required")
    book = ForecastBook([v.publication_t for v in versions], horizon)
    previous = -math.inf
    for index, version in enumerate(versions):
        if (type(version) is not ForecastView or version.version != index
                or version.publication_t <= previous
                or version.valid_from < version.publication_t
                or version.valid_to <= version.valid_from
                or not version.wind_blocks
                or any(t < version.publication_t or t >= version.valid_to
                       or not all(math.isfinite(x) for x in (t, u, v))
                       for t, u, v in version.wind_blocks)
                or version.content_sha256 != canonical_hash(
                    [[float(t), float(u), float(v)]
                     for t, u, v in version.wind_blocks])):
            raise ValueError("invalid frozen forecast publication")
        previous = version.publication_t
        book._published.append(version)
        book._content[index] = tuple([float(t), float(u), float(v)]
                                     for t, u, v in version.wind_blocks)
    return book


def _check_history(history: PublicReplayHistory, static: StaticContext) -> None:
    if type(history) is not PublicReplayHistory:
        raise TypeError("PublicReplayHistory required; source snapshots are forbidden")
    if history.static_sha256 != static.sha256 or len(history.steps) > 200:
        raise ReplayHistoryError("history identity/length mismatch")
    last_time = -math.inf
    for frame, legal, action in [(s.frame, s.legal, s.action) for s in history.steps] + [
            (history.current, history.current_legal, None)]:
        if (type(frame) is not ObservationFrame or not math.isfinite(frame.t_min)
                or frame.t_min < last_time or frame.t_min < 0
                or frame.decision_slot not in static.slots() or frame.nfz
                or not legal or (action is not None and action not in legal)):
            raise ReplayHistoryError("invalid complete public decision history")
        ForecastBook.assert_no_future_in(frame)
        for kind, tid in legal:
            if (kind not in ("TARGET", "RETURN")
                    or (kind == "RETURN" and tid is not None)
                    or (kind == "TARGET" and tid not in static.target_ids)):
                raise ReplayHistoryError("invalid physical action in public history")
        last_time = frame.t_min


def filter_public_history(static: StaticContext, history: PublicReplayHistory,
                          atoms: tuple[ReplayAtom, ...], *,
                          horizon: float) -> ReplayPosterior:
    """Condition an exact finite joint model on a complete decision journal.

    Decisions are interventions. For a policy using only this public history,
    its common action likelihood cancels between atoms. We compare every
    callback in order, including the final public frame and legal set.
    """
    validate_static(static)
    _check_history(history, static)
    if (not math.isfinite(horizon) or horizon <= history.current.t_min
            or not 1 <= len(atoms) <= 256
            or len({a.atom_id for a in atoms}) != len(atoms)):
        raise ValueError("bounded finite model and future horizon required")
    states, rejections, masses, identities = [], [], [], []
    for atom in atoms:
        if (type(atom) is not ReplayAtom or not math.isfinite(atom.prior)
                or atom.prior < 0 or atom.particle.hidden_phases
                or atom.particle.hidden_past_wind
                or sorted(atom.particle.future.releases)
                != [(0.0, t) for t in sorted(static.target_ids)]):
            raise ValueError("atom must be a from-start joint model with t=0 targets")
        book = _book(atom.publications, horizon)
        root = PublicPrefix(static.sha256, 0.0, 0,
                            releases=atom.particle.future.releases)
        engine = CausalEngine(static, root, atom.particle,
                              EngineConfig(horizon_min=horizon), book)
        index, reached = 0, False

        def replay(frame, key, legal):
            nonlocal index, reached
            if index < len(history.steps):
                step = history.steps[index]
                want_frame, want_legal = step.frame, step.legal
            else:
                want_frame, want_legal = history.current, history.current_legal
            if not _same_public(frame, want_frame) or legal != want_legal:
                raise ReplayHistoryError(f"PUBLIC_OBSERVATION_MISMATCH_AT_{index}")
            if index == len(history.steps):
                reached = True
                raise PauseAtPublicDecision()
            index += 1
            return step.action

        engine.run_with_frozen_mu(replay)
        compatible = reached and engine.terminal is None
        states.append(engine if compatible else None)
        masses.append(atom.prior if compatible else 0.0)
        rejections.append(None if compatible else engine.failure_code or engine.terminal)
        identities.append({"id": atom.atom_id, "prior": atom.prior,
                           "particle": atom.particle.sha256,
                           "publications": [v.__dict__ for v in atom.publications]})
    return ReplayPosterior(canonical_hash(identities),
                           tuple(a.atom_id for a in atoms), _weights(tuple(masses)),
                           tuple(states), tuple(rejections))
