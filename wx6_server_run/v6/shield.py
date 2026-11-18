"""Shift shield (hard projection of the overtime constraint onto the action set), v6.

A HOLD of drone i at time t is removed from the action set when holding one more weather tick would make the
drone's conservative remaining planned work spill beyond the shift end H:
        t + DT + remaining_plan_time(i) > H - margin
(remaining_plan_time already inflates no-wind times by 1 + LD_MARGIN). Only HOLD is ever removed, so completion,
the latest-departure rule and the urgent guarantee of the shared feasibility layer are untouched.
The shield is a generic wrapper: it is offered to EVERY baseline rule as well ("S:" prefix, e.g. S:N6_90_0.25) and
the dev selection of the strongest baseline may pick shielded variants (PREREG_v6 sec. 4), so any gain of RL6 that
merely comes from the shield is available to the baselines too.
"""
from wx2 import const as C
from wx2.sim import HOLD, LAUNCH, SERVE0


def violates(sim, i, info, margin=0.0):
    if sim.t >= C.H:
        return False
    try:
        rem = sim.remaining_plan_time(i, info)
    except Exception:
        return False
    return sim.t + C.DT + rem > C.H - margin


def shielded(inner, margin=0.0):
    def pol(sim, i, mask, cands, info):
        if mask[HOLD] and violates(sim, i, info, margin):
            m2 = mask.copy(); m2[HOLD] = False
            sim.n_shield = getattr(sim, "n_shield", 0) + 1
            a = inner(sim, i, m2, cands, info)
            if a is None or a == HOLD or a < 0 or a >= len(m2) or not m2[a]:
                a = SERVE0 if m2[SERVE0] else LAUNCH
            return a
        return inner(sim, i, mask, cands, info)
    pol.inner = inner
    return pol
