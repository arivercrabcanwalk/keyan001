"""Strong min-max ALNS with exact closed-tour wind geometry.

Only the search cache uses effective coordinates. The original instance and
all eligibility checks stay in physical coordinates. Prefix service times are
recomputed by the independent heading-based scorer, not the symmetric metric.
"""
from time import perf_counter

from env.constant_wind import ConstantWind
from . import minmax_alns
from . import wind_scorer


class ConstantWindCtx(minmax_alns.Ctx):
    __slots__ = ("wind",)

    def __init__(self, instance, types, target_station, *, wind):
        super().__init__(instance, types, target_station)
        self.wind = ConstantWind(*wind, instance.params.speed)
        # T has units of minutes. Multiplication by a lets the unchanged
        # upstream distance/speed code continue to consume effective metres.
        def effective(node):
            x, y = self.wind.transform((node.x, node.y))
            return self.speed * x, self.speed * y
        target_xy = {node.id: effective(node) for node in instance.targets}
        self.X = {nid: xy[0] for nid, xy in target_xy.items()}
        self.Y = {nid: xy[1] for nid, xy in target_xy.items()}
        station_xy = [effective(node) for node in instance.stations]
        self.stx = [xy[0] for xy in station_xy]
        self.sty = [xy[1] for xy in station_xy]


def solve(instance, anchor, budget_s, *, started_at=None, seed=20261112):
    """Include wind setup, cache creation, search and independent certification.

    The caller must supply a wind-feasible immutable witness. This adapter
    makes no claim that the witness came from a wind-aware author solver.
    """
    t0 = perf_counter() if started_at is None else started_at
    anchor.verify(instance)
    wind = anchor.wind
    result = minmax_alns.solve(
        instance, anchor, budget_s, started_at=t0, seed=seed,
        context_factory=lambda ins, types, ownership: ConstantWindCtx(
            ins, types, ownership, wind=wind),
        candidate_validator=wind_scorer.validate_candidate)
    result.update({
        "schema": "constant_wind_strong_nonrl_adapter_v1",
        "method": "minmax_alns_constant_wind",
        "constant_wind": list(wind),
        "physics_sha256": wind_scorer.physics_identity(instance, wind),
        "certificate_space": "original_coordinates_independent_heading",
        "trip_cache_length_units": "effective_metres_not_physical_distance",
        "search_diagnostics_may_describe_raw_candidate": True,
        "anchor_source": "caller_supplied_wind_feasible_witness",
    })
    elapsed = perf_counter() - t0
    result["adapter_total_elapsed_s"] = elapsed
    result["output_ready_elapsed_s"] = elapsed
    result["over_budget"] = elapsed > budget_s
    if result["over_budget"]:
        result["status"] = "NO_ONTIME_VALID_OUTPUT"
    return result
