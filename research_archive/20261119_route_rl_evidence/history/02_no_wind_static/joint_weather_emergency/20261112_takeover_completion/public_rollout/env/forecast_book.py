"""ForecastBook: versioned, published, never-rewritten public forecasts.

Contract sections 5.1-5.6.  A forecast is generated JOINTLY with the truth
(truth + independent noise) so it can never contain the future, and it becomes
visible only at its publication time.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, replace
from typing import Sequence

from .core import (ForecastView, PublicationRewrite, PublicRolloutError,
                   _f, canonical_hash)


@dataclass(frozen=True)
class ErrorModel:
    """Registered, frozen forecast error model."""

    model_id: str = "frozen-gaussian-v1"
    sigma_u: float = 0.8
    sigma_v: float = 0.8
    bias_u: float = 0.0
    bias_v: float = 0.0

    def sample(self, truth_uv: tuple[float, float], rng: random.Random) -> tuple[float, float]:
        u = truth_uv[0] + self.bias_u + rng.gauss(0.0, self.sigma_u)
        v = truth_uv[1] + self.bias_v + rng.gauss(0.0, self.sigma_v)
        return (_f(u), _f(v))


class ForecastBook:
    """Publication schedule + immutable published versions."""

    def __init__(self, schedule: Sequence[float], valid_horizon_min: float,
                 block_min: float = 30.0, error_model: ErrorModel | None = None):
        self.schedule = tuple(sorted(float(x) for x in schedule))
        if not self.schedule:
            raise PublicRolloutError("forecast schedule must be non-empty")
        self.valid_horizon_min = float(valid_horizon_min)
        self.block_min = float(block_min)
        self.error_model = error_model or ErrorModel()
        self._published: list[ForecastView] = []
        self._content: dict[int, tuple] = {}

    # ---- generation (truth -> forecast, joint draw) ---------------------
    def make_version(self, version: int, publication_t: float,
                     truth_blocks: Sequence[tuple[float, float, float]],
                     rng: random.Random) -> ForecastView:
        """Jointly generate the published content from truth + independent noise."""
        if self._published and publication_t <= self._published[-1].publication_t:
            raise PublicationRewrite("publication times must strictly increase")
        if version != len(self._published):
            raise PublicationRewrite("versions must be issued in order 0,1,2,...")
        out = []
        for t_from, u, v in truth_blocks:
            if t_from < publication_t:
                raise PublicRolloutError("published block starts before publication time")
            if t_from >= publication_t + self.valid_horizon_min:
                continue
            fu, fv = self.error_model.sample((u, v), rng)
            out.append((_f(t_from), fu, fv))
        if not out:
            raise PublicRolloutError("empty forecast publication")
        payload = [[a, b, c] for a, b, c in out]
        content = canonical_hash(payload)
        view = ForecastView(version=version, publication_t=_f(publication_t),
                            valid_from=_f(out[0][0]),
                            valid_to=_f(publication_t + self.valid_horizon_min),
                            content_sha256=content,
                            wind_blocks=tuple(out))
        self._published.append(view)
        self._content[version] = tuple(payload)
        return view

    # ---- visibility ------------------------------------------------------
    def visible(self, t: float) -> ForecastView | None:
        """Latest version whose publication time is <= t.  Future versions are hidden."""
        best = None
        for v in self._published:
            if v.publication_t <= t + 1e-12:
                best = v
            else:
                break
        return best

    def at_version(self, t: float, version: int) -> ForecastView | None:
        v = self.visible(t)
        if v is None or v.version < version:
            return None
        return v if v.version == version else None

    def publications_until(self, t: float) -> tuple[ForecastView, ...]:
        return tuple(v for v in self._published if v.publication_t <= t + 1e-12)

    def assert_not_rewritten(self, version: int) -> None:
        want = self._content.get(version)
        if want is None:
            raise PublicationRewrite(f"unknown version {version}")
        got = tuple([[a, b, c] for a, b, c in self._published[version].wind_blocks])
        if got != want:
            raise PublicationRewrite(f"version {version} was mutated after publication")

    @staticmethod
    def assert_no_future_in(frame) -> None:
        """A frame may never expose a publication later than its own timestamp."""
        f = frame.forecast
        if f.publication_t > frame.t_min + 1e-12:
            raise PublicRolloutError(
                "forecast publication time is in the future relative to the frame")


def truth_blocks_from_wind(wind_at, t0: float, t1: float, block_min: float) -> tuple:
    """Sample the true wind into blocks; the forecast is derived from these."""
    out = []
    t = t0
    while t < t1 - 1e-12:
        u, v = wind_at(t)
        out.append((_f(t), _f(u), _f(v)))
        t += block_min
    return tuple(out)
