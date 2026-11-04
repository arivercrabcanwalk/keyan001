"""Coupling-aware state encoder.

The vector is deliberately fixed-length and cheap to compute so that the
controller can be called at every search step.  It keeps separate blocks for
global search status, station structure, assignment coupling, drone/trip
structure and per-operator search history instead of averaging everything into a
single scalar (the design note's "do not simply average" requirement).
"""
import math

import numpy as np

from .actions import (N_OPERATORS, N_ACTIONS, OPERATOR_NAMES,
                      OPERATOR_FAMILY, OPERATOR_INTENSITIES,
                      action_universe_mask)

STATE_SCHEMA = "carl-state-v6-pref-makespan-btl-84"
ACTION_SCHEMA = "carl-action-v5-20-operators-bottleneck-x-3-intensity-60"
REWARD_SCHEMA = "scalarized-cost-makespan-pref-v1"

FEATURE_NAMES = [
    # global search (13)
    "cost_ratio", "best_ratio", "gap_to_best", "budget_used", "temperature",
    "stagnation", "accept_rate", "improve_rate", "step_ratio", "budget_left",
    "log_targets", "station_scale", "dist_scale",
    # station structure (10)
    "open_share", "sabs_share", "dabs_share", "max_load", "mean_load",
    "std_load", "fixed_share", "min_slack", "mean_slack", "work_concentration",
    # assignment coupling (8)
    "alt_target_share", "mean_cover", "nearest_share", "detour_ratio",
    "max_count_share", "count_entropy", "transfer_opportunity", "load_range",
    # drone / route structure (10)
    "ld_work_share", "sd_work_share", "mean_station_trips", "max_station_trips",
    "mean_active_drone_energy_slack", "min_active_drone_energy_slack",
    "low_energy_slack_share", "mean_trip_size",
    "max_trip_size", "route_cost_share",
    # operator-specific history (34): preserve distinctions between the
    # five location, two assignment, five routing and five joint operators.
] + [f"succ_{name}" for name in OPERATOR_NAMES] + [
    f"impr_{name}" for name in OPERATOR_NAMES
] + ["pref_lambda", "makespan_ratio", "bottleneck_share"]

N_FEATURES = len(FEATURE_NAMES)


class History:
    """Recent per-operator feasibility / improvement statistics."""

    def __init__(self, window=200):
        self.window = window
        self.attempts = [0] * N_OPERATORS
        self.feasible = [0] * N_OPERATORS
        self.accepted = [0] * N_OPERATORS
        self.improved = [0] * N_OPERATORS
        self.best = [0] * N_OPERATORS

    def record(self, operator, feasible, accepted, improved, best):
        self.attempts[operator] += 1
        self.feasible[operator] += feasible
        self.accepted[operator] += accepted
        self.improved[operator] += improved
        self.best[operator] += best
        if sum(self.attempts) > self.window * N_OPERATORS:
            for arr in (self.attempts, self.feasible, self.accepted,
                        self.improved, self.best):
                for i in range(N_OPERATORS):
                    arr[i] = int(arr[i] * 0.5)

    def rates(self):
        succ, impr = [], []
        for i in range(N_OPERATORS):
            a = max(self.attempts[i], 1)
            succ.append(self.feasible[i] / a)
            impr.append(self.improved[i] / a)
        return succ, impr


GROUP_SLICES = {
    "global": (0, 13), "station": (13, 23), "assignment": (23, 31),
    "drone": (31, 41), "history": (41, 41 + 2 * N_OPERATORS),
    "pref": (41 + 2 * N_OPERATORS, 44 + 2 * N_OPERATORS),
}


def encode(ctx, history, initial_cost, elapsed, budget, temperature, stagnation,
           accept_rate, improve_rate, step, zero_groups=(), pref=(0.0, 1.0, 0.0)):
    ins = ctx.ins
    m = ctx.mirror
    nst = ctx.nst
    n = max(len(ins.targets), 1)
    types = m.types

    open_share = len(ctx.open_stations) / nst
    sabs = sum(1 for k in types if k == 1)
    dabs = sum(1 for k in types if k == 2)
    loads = [ctx.load[si] for si in ctx.open_stations]
    max_load = max(loads) if loads else 0.0
    mean_load = sum(loads) / len(loads) if loads else 0.0
    std_load = math.sqrt(sum((x - mean_load) ** 2 for x in loads) / len(loads)) if loads else 0.0
    total_fixed = sum(ctx.fixed)
    cost = getattr(ctx, "cost", initial_cost)
    fixed_share = total_fixed / cost if cost > 0 else 0.0
    slacks = [ctx.slack[si] for si in ctx.open_stations]
    min_slack = min(slacks) if slacks else 0.0
    mean_slack_s = sum(slacks) / len(slacks) if slacks else 0.0
    work_conc = (max((ctx.work[si] for si in ctx.open_stations), default=0.0)
                 / ctx.total_work) if ctx.total_work > 0 else 0.0

    # assignment coupling (cached coverage counts; no station loop per target)
    alt_counts = ctx.coverage.alt_counts(types)
    alt = 0
    detour = 0.0
    nearest = 0
    n_pos = len(m.pos)
    for nid, (si, di, ti, pi) in m.pos.items():
        d_assigned = ins.dist[ins.stations[si].id, nid]
        d_best = ctx.coverage.nearest[nid]
        if alt_counts[ctx.coverage.tidx[nid]] >= 2:
            alt += 1
        if d_best > 0:
            detour += d_assigned / d_best
        else:
            detour += 1.0
        if d_best >= d_assigned - 1e-9:
            nearest += 1
    nd = max(n_pos, 1)
    alt_share = alt / n
    detour_ratio = detour / nd
    nearest_share = nearest / nd
    mean_cover = sum(ctx.coverage.cnt_all) / max(len(ctx.coverage.cnt_all), 1)
    counts = [ctx.count[si] for si in ctx.open_stations]
    max_count = max(counts) if counts else 0
    max_count_share = max_count / n
    tot = sum(counts) or 1
    ent = 0.0
    for c in counts:
        if c:
            p = c / tot
            ent -= p * math.log(p + 1e-12)
    ent = ent / math.log(max(len(counts), 2))
    transfer_opp = alt / n
    load_range = (max(loads) - min(loads)) if loads else 0.0

    # drone structure
    ld = sum(ctx.dw0[si] for si in ctx.open_stations)
    sd = sum(ctx.dw1[si] for si in ctx.open_stations)
    total_work = ld + sd
    ld_share = ld / total_work if total_work > 0 else 0.0
    sd_share = sd / total_work if total_work > 0 else 0.0
    trip_counts = [ctx.trips[si] for si in ctx.open_stations]
    mean_trips = sum(trip_counts) / max(len(trip_counts), 1)
    max_trips = max(trip_counts) if trip_counts else 0
    slack_vals = []
    for si in ctx.open_stations:
        if m.types[si] == 2:
            slack_vals.extend((ctx.dslack0[si], ctx.dslack1[si]))
        else:
            # SABS has only the small drone, encoded in drone slot 1.
            slack_vals.append(ctx.dslack1[si])
    min_slack_d = min(slack_vals) if slack_vals else 0.0
    mean_slack_d = sum(slack_vals) / len(slack_vals) if slack_vals else 0.0
    low_slack = sum(1 for x in slack_vals if x < 0.1) / max(len(slack_vals), 1)
    sizes = [len(t) for si in ctx.open_stations for d in m.routes[si] for t in d]
    mean_trip = sum(sizes) / max(len(sizes), 1)
    max_trip = max(sizes) if sizes else 0
    route_cost = getattr(ctx, "route_cost", cost)
    route_share = route_cost / cost if cost > 0 else 0.0

    succ, impr = history.rates()

    vec = [
        cost / initial_cost if initial_cost else 1.0,
        getattr(ctx, "best_cost", initial_cost) / initial_cost if initial_cost else 1.0,
        (cost - getattr(ctx, "best_cost", cost)) / max(cost, 1e-9),
        min(elapsed / budget, 1.0) if budget else 0.0,
        min(temperature / (0.01 * initial_cost + 1e-12), 5.0),
        min(stagnation / 100.0, 3.0),
        accept_rate,
        improve_rate,
        min(step / 20000.0, 1.0),
        max(0.0, 1.0 - elapsed / budget) if budget else 0.0,
        math.log(1 + len(ins.targets)) / math.log(121.0),
        nst / 10.0,
        (sum(ctx.coverage.nearest.values()) / max(len(ctx.coverage.nearest), 1)) / 5000.0,
        open_share, sabs / nst, dabs / nst, max_load, mean_load,
        std_load, fixed_share, min_slack, mean_slack_s, work_conc,
        alt_share, mean_cover / nst, nearest_share, detour_ratio,
        max_count_share, ent, transfer_opp, load_range,
        ld_share, sd_share, mean_trips / 10.0, max_trips / 20.0,
        mean_slack_d, min_slack_d, low_slack, mean_trip / 10.0,
        max_trip / 20.0, route_share,
        *succ, *impr,
        pref[0] / 4.0, pref[1], pref[2],
    ]
    arr = np.asarray(vec, dtype=np.float32)
    if zero_groups:
        for g in zero_groups:
            lo, hi = GROUP_SLICES.get(g, (0, 0))
            arr[lo:hi] = 0.0
    return arr


def action_mask(ctx, families=(0, 1, 2, 3), intensities=(0, 1, 2),
                operators=None):
    """Operator-level dynamic mask (17 operators x supported intensities).

    Structural availability is cached on the immutable Context object. Full
    physical feasibility is still checked by the native guard and independent
    evaluator after candidate generation.
    """
    universe = action_universe_mask(families, intensities, operators)
    from .neighborhood import operator_available
    mask = np.zeros(N_ACTIONS, dtype=bool)
    # Lightweight structural mocks used by the protocol unit tests predate
    # the full Context object. Production contexts always expose station_targets.
    if not hasattr(ctx.mirror, "station_targets"):
        can_loc = (bool(ctx.closed_stations) or len(ctx.open_stations) > 1
                   or any(ctx.mirror.types[s] in (1, 2) for s in ctx.open_stations))
        can_asg = (len(ctx.open_stations) >= 2
                   and any(c >= 2 for c in ctx.coverage.alt_counts(ctx.mirror.types)))
        for op, family in enumerate(OPERATOR_FAMILY):
            enabled = (family == 0 and can_loc) or (family == 1 and can_asg) or (
                family == 3 and (can_loc or can_asg))
            if enabled:
                lo = op * 3
                for intensity in OPERATOR_INTENSITIES[op]:
                    if universe[lo + intensity]:
                        mask[lo + intensity] = True
        return mask
    for operator in range(N_OPERATORS):
        slots = slice(operator * 3, operator * 3 + 3)
        if not universe[slots].any():
            continue
        if operator_available(ctx, operator):
            mask[slots] = universe[slots]
    return mask
