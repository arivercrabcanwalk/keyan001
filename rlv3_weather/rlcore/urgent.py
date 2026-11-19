"""Emergency (urgent) inspection request generator for rlv3-emergency (synthetic, documented assumptions).

Real-world grounding (DESIGN_ZH.md section 3):
 * Forced outages on 220 kV+ lines are rare (order 0.1-0.5 trips / 100 km / year; e.g. IEEE OAJPE 2020,
   doi:10.1109/OAJPE.2020.2975665), so per-day emergency load on a ~70-tower district does NOT come from trips alone;
   it comes from on-line-monitoring ALARMS that must be verified, defect re-checks and dispatcher requests
   (DL/T 741-2019 'fault / special patrol'; DL/T 1482-2023 UAV inspection guide; nest-based 'one-click dispatch of the
   nearest drone nest' deployments, e.g. Shenzhen 2024).  The daily rate is therefore a SCENARIO parameter swept over
   three levels, not a fitted statistic.
 * Arrivals: superposition of a homogeneous Poisson background and spatio-temporally clustered bursts
   (Neyman-Scott cluster process: one trigger -> several alarms on nearby towers within ~30 min), which mimics
   corridor events (wind-blown foreign objects, icing, wildfire smoke) that hit adjacent spans.
 * Location: always AT a tower of the instance (a fault/alarm is attributed to a tower / its adjacent span) ->
   always inside the author's coverage, so NO station has to be added (rule: no gains from more stations).
 * Two priorities: high (hazard / trip, deadline 20 min) and normal (defect verification, deadline 60 min).
 * Service: same inspection time/energy as the author (t_f = 10 min, p2 = 0.020/min).
"""
import numpy as np
from .common import stable_rng, T_SVC, P2

LEVELS = {"low": 0.05, "mid": 0.15, "high": 0.30}    # expected requests per tower per 8-h shift
H = 480.0
ARR_END = 450.0
P_HIGH = 0.30
DEADLINE = {1: 20.0, 0: 60.0}
W_LATE = {1: 10.0, 0: 2.0}           # RMB per late minute (pre-registered; sensitivity analysis in DESIGN)
CLUSTER_SHARE = 0.4
CLUSTER_MEAN_EXTRA = 2.0
CLUSTER_RADIUS = 3000.0
CLUSTER_TAU = 15.0


def make_requests(seed, targets, level="mid", rate=None):
    """targets: list of (tid, x, y).  Returns list of dict(rid, tid, x, y, t, prio, dl, svc, energy) sorted by t."""
    rho = LEVELS[level] if rate is None else float(rate)
    rng = stable_rng("rlv3-urgent", seed, level, rho)
    n_t = len(targets)
    lam = rho * n_t                                    # expected requests per shift
    xy = np.array([[x, y] for _, x, y in targets])
    reqs = []
    # background
    nb = rng.poisson(lam * (1 - CLUSTER_SHARE))
    for _ in range(nb):
        reqs.append((rng.uniform(0, ARR_END), int(rng.integers(n_t))))
    # clusters
    n_par = rng.poisson(lam * CLUSTER_SHARE / (1 + CLUSTER_MEAN_EXTRA))
    for _ in range(n_par):
        t0 = rng.uniform(0, ARR_END); j = int(rng.integers(n_t))
        reqs.append((t0, j))
        near = np.where(np.hypot(xy[:, 0] - xy[j, 0], xy[:, 1] - xy[j, 1]) <= CLUSTER_RADIUS)[0]
        for _ in range(rng.poisson(CLUSTER_MEAN_EXTRA)):
            tc = t0 + rng.exponential(CLUSTER_TAU)
            if tc < ARR_END:
                reqs.append((tc, int(rng.choice(near))))
    reqs.sort()
    out = []
    for r, (t, j) in enumerate(reqs):
        prio = int(rng.random() < P_HIGH)
        tid, x, y = targets[j]
        out.append(dict(rid=r, tid=int(tid), x=float(x), y=float(y), t=float(t), prio=prio,
                        dl=float(t + DEADLINE[prio]), svc=T_SVC, energy=P2 * T_SVC))
    return out
