"""Engineering-only paired intervention: identical storm wind, cell rule on/off.

Both arms retain the same complete synthetic weather, including cell outflow.
The clear interface removes both exclusion enforcement and explicit cell
observations. This is not a contrast between actual storm and storm-free weather.
"""
import hashlib
import json
import math
import pickle
from pathlib import Path

from .weather import WeatherDay, T_MAX


def _time(t):
    if not math.isfinite(t) or not 0 <= t <= T_MAX:
        raise ValueError("time outside paired weather horizon [0,T_MAX]")


class PairedWeather:
    """Narrow policy-facing interface; clear has no forwarded cell metadata.

    Python object introspection is not an adversarial security boundary. The
    supported policy interface returns no clear-arm cell geometry or count.
    """
    __slots__ = ("__source", "cells_enabled", "pair_world_sha256")
    calm = False
    public_future_sampler_verified = False
    engineering_only = True
    causal_estimand = "same_storm_weather_remove_exclusion_rule_and_explicit_cell_observations"

    def __init__(self, source, cells_enabled):
        if source.mode != "storm" or source.calm:
            raise ValueError("paired source must be a forced-storm WeatherDay")
        if type(cells_enabled) is not bool:
            raise ValueError("cells_enabled must be boolean")
        self.__source = source
        self.cells_enabled = cells_enabled
        self.pair_world_sha256 = hashlib.sha256(pickle.dumps(source, protocol=4)).hexdigest()

    @property
    def horizon(self):
        return self.__source.horizon

    @property
    def ncell(self):
        return self.__source.ncell if self.cells_enabled else 0

    def truth_wind(self, x, y, t):
        return self.__source.truth_wind(x, y, t)

    def forecast_wind(self, t_now, t):
        return self.__source.forecast_wind(t_now, t)

    def nowcast(self, t):
        _time(t)
        return self.__source.nowcast(t) if self.cells_enabled else []

    def in_cell(self, x, y, t):
        _time(t)
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("finite position required")
        return self.__source.in_cell(x, y, t) if self.cells_enabled else False

    def truth_segment_hits(self, x1, y1, x2, y2, t0, dur):
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2, dur)) or dur < 0:
            raise ValueError("finite segment and nonnegative duration required")
        _time(t0); _time(t0 + dur)
        return self.__source.truth_segment_hits(x1, y1, x2, y2, t0, dur) if self.cells_enabled else False

    def resample_future(self, t, seed):
        """Keep the same intervention on the latent-only engineering sampler."""
        return PairedWeather(self.__source.resample_future(t, seed), self.cells_enabled)


def make_paired_weather(seed, bbox, scale=1.0):
    """Construct one forced-storm draw, then return (clear, cells) interfaces."""
    source = WeatherDay(seed, bbox, mode="storm", scale=scale)
    return PairedWeather(source, False), PairedWeather(source, True)


def engineering_check():
    """Hand-written single-cell counterfactual; no map, solver or policy quality run."""
    import numpy as np
    from .weather import nowcast_hits
    source = WeatherDay(73, (0, 1000, 0, 1000), mode="storm")
    source._build_cells([dict(tb=0.0, L=600.0, cx0=450.0, cy0=0.0,
        vx=2.0, vy=0.0, a=100.0, b=50.0, ang=0.0, uo=6.0,
        ou=np.zeros((source.NT, 2)))])
    clear, cells = PairedWeather(source, False), PairedWeather(source, True)
    assert clear.pair_world_sha256 == cells.pair_world_sha256
    wind_queries, forecast_queries = 0, 0
    for t in (0.0, 12.5, 59.9, 60.0, 120.0, 300.0, 600.0, 900.0):
        for x, y in ((0.0, 0.0), (850.0, 0.0), (1100.0, 100.0)):
            assert clear.truth_wind(x, y, t) == cells.truth_wind(x, y, t) == source.truth_wind(x, y, t)
            wind_queries += 1
        for lead in (0.0, 10.0, 60.0):
            if t + lead <= T_MAX:
                assert clear.forecast_wind(t, t + lead) == cells.forecast_wind(t, t + lead)
                forecast_queries += 1
    # At t=300, centre=(1050,0) and the fully grown moving cell spans the route.
    assert not clear.truth_segment_hits(850, 0, 1250, 0, 300, 0.5)
    assert cells.truth_segment_hits(850, 0, 1250, 0, 300, 0.5)
    assert clear.nowcast(300) == [] and clear.ncell == 0
    assert cells.nowcast(300) and cells.ncell == 1
    assert not nowcast_hits(clear.nowcast(300), 850, 0, 1250, 0, 300, 0.5)
    assert nowcast_hits(cells.nowcast(300), 850, 0, 1250, 0, 300, 0.5)
    hidden = ("cells_meta", "c_a", "c_b", "c_ang", "c_cx", "c_cy", "_cell_list", "storm")
    assert not any(hasattr(clear, key) for key in hidden)
    # An outflow probe confirms the common weather retains the cell's effect.
    without = WeatherDay(73, (0, 1000, 0, 1000), mode="storm")
    without._build_cells([])
    outflow_probe = (1200.0, 0.0, 300.0)
    assert clear.truth_wind(*outflow_probe) != without.truth_wind(*outflow_probe)
    # Independent factory calls with the same seed preserve the same full draw.
    a, _ = make_paired_weather(74, (0, 1000, 0, 1000))
    _, b = make_paired_weather(74, (0, 1000, 0, 1000))
    assert a.pair_world_sha256 == b.pair_world_sha256
    a2, b2 = a.resample_future(12.5, 91), b.resample_future(12.5, 91)
    assert a2.pair_world_sha256 == b2.pair_world_sha256
    assert a2.truth_wind(17, 23, 40) == b2.truth_wind(17, 23, 40)
    assert not a2.public_future_sampler_verified and not b2.public_future_sampler_verified
    return dict(schema="rlv3-paired-weather-engineering-v1", status="PASS",
        engineering_only=True, scientific_run=False, pair_world_sha256=clear.pair_world_sha256,
        identical_truth_queries=wind_queries, identical_forecast_queries=forecast_queries,
        clear_collision=False, cells_collision=True, clear_cell_metadata_exposed=False,
        cell_outflow_retained_in_both=True, same_seed_reconstruction=True,
        paired_latent_resampling=True, causal_estimand=clear.causal_estimand)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engineering-check", action="store_true", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    receipt = engineering_check()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
