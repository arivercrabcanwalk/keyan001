"""RL6 state/action-token features (all observable; same information the baselines use).

Global vector g (NG6 = 56) = the 48 v5 features (wx2/feat.py) + 8 anticipatory/coordination features:
  48 expected urgent alarms in this station's coverage within 30 min (N6's anticipatory estimator, observable)
  49 same within 90 min
  50 shift slack of this drone (H - t - conservative remaining planned work) / 120
  51 pending requests that ONLY this drone's station can reach / 4
  52 fleet-wide pending high-priority requests / 6
  53 other idle/holding drones whose station covers the most urgent pending request / 4
  54 overtime phase flag (t >= H)
  55 shield active for this decision (HOLD removed by the shift shield)
Per-action token a (NA6 = 16) = the 10 v5 per-action features + 6 new:
  LAUNCH: 10 overtime impact of launching now, 11 expected urgent (60 min) / 3, 12 ready others / 4
  HOLD  : 10 shift slack after one hold tick / 60, 11 expected urgent 30 min / 3, 12 expected urgent 90 min / 3,
          13 min slack of pending requests this station can reach / 30
  SERVE : 10 competitor advantage (fastest OTHER idle/holding coverer's outbound minutes - own outbound) / 20,
          11 number of other idle/holding coverers / 4, 12 deadline slack at predicted arrival / 20,
          13 overtime impact of serving / 60, 14 already-late flag, 15 high-priority AND already-late flag
Feature groups for the preregistered ablations: FORECAST (weather information) and EMERG (urgent-request information).
"""
import math
import numpy as np
from wx2 import const as C, feat as F5, policies as P
from wx2.sim import LAUNCH, HOLD, SERVE0, N_ACT, N_SERVE

NG5, NA5 = F5.NG, F5.NA
NG6 = NG5 + 8
NA6 = NA5 + 6
NTOK = NG6 + NA6 + 3   # + one-hot action type (LAUNCH / HOLD / SERVE)

# ablation groups (indices into g and into the per-action block)
G_FORECAST = [1, 2, 3, 4, 5, 6, 7, 8, 10, 31, 42, 43, 44, 48, 49]
A_FORECAST = {LAUNCH: [2, 5, 11], HOLD: [2, 3, 11, 12], "SERVE": [2]}
G_EMERG = [11, 12, 13, 14, 15, 16, 28, 29, 48, 49, 51, 52, 53]
A_EMERG = {LAUNCH: [11], HOLD: [4, 6, 11, 12, 13], "SERVE": [1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 14, 15]}


def _clip(x, lo=-3.0, hi=3.0):
    return lo if x < lo else hi if x > hi else x


def _idle_others(sim, i):
    return [j for j, e in enumerate(sim.drones) if j != i and e["state"] in ("idle", "hold")]


def features(sim, i, mask, cands, info, shield_on=False):
    v = F5.features(sim, i, mask, cands, info)
    g5 = v[:NG5]; a5 = v[NG5:].reshape(N_ACT, NA5)
    g = np.zeros(NG6, dtype=np.float32); g[:NG5] = g5
    A = np.zeros((N_ACT, NA6), dtype=np.float32); A[:, :NA5] = a5
    d = sim.drones[i]; st = sim.st[d["sid"]]; t = sim.t
    e30 = P._expected_urgent(sim, i, 30.0)
    e90 = P._expected_urgent(sim, i, 90.0) if e30 < 3.0 else e30 * 2.0
    try:
        rem = sim.remaining_plan_time(i, info)
    except Exception:
        rem = 0.0
    others = _idle_others(sim, i)
    pend = [j for j in sim.pending if not sim._done_flags[j] and j not in sim.assigned]
    only = 0; urg = None
    for j in pend:
        r = sim.reqs[j]
        mine = math.hypot(r[1] - st["x"], r[2] - st["y"]) <= d["R"] + 1e-6
        if mine and not any(math.hypot(r[1] - sim.st[sim.drones[k]["sid"]]["x"], r[2] - sim.st[sim.drones[k]["sid"]]["y"])
                            <= sim.drones[k]["R"] + 1e-6 for k in range(len(sim.drones)) if k != i):
            only += 1
        dl = r[0] + C.DL[r[3]]
        if urg is None or dl < urg[0]:
            urg = (dl, r)
    g[48] = min(e30, 3.0) / 3.0
    g[49] = min(e90, 6.0) / 3.0
    g[50] = _clip((C.H - t - rem) / 120.0, -2, 3)
    g[51] = min(only, 4) / 4.0
    g[52] = min(sum(1 for j in pend if sim.reqs[j][3] == 1), 6) / 6.0
    if urg is not None:
        r = urg[1]
        g[53] = min(sum(1 for k in others if math.hypot(r[1] - sim.st[sim.drones[k]["sid"]]["x"],
                                                      r[2] - sim.st[sim.drones[k]["sid"]]["y"]) <= sim.drones[k]["R"]), 4) / 4.0
    g[54] = float(t >= C.H)
    g[55] = float(shield_on)
    if info is not None:
        A[LAUNCH, 10] = _clip((t + rem - C.H) / 60.0, -3, 3)
    A[LAUNCH, 11] = g[48] * 0 + min(P._expected_urgent(sim, i, 60.0) if e30 > 0 else 0.0, 3.0) / 3.0
    A[LAUNCH, 12] = min(len(others), 4) / 4.0
    A[HOLD, 10] = _clip((C.H - t - C.DT - rem) / 60.0, -3, 3)
    A[HOLD, 11] = g[48]
    A[HOLD, 12] = g[49]
    mine_sl = [sim.reqs[j][0] + C.DL[sim.reqs[j][3]] - t for j in pend
               if math.hypot(sim.reqs[j][1] - st["x"], sim.reqs[j][2] - st["y"]) <= d["R"] + 1e-6]
    A[HOLD, 13] = _clip(min(mine_sl) / 30.0, -2, 2) if mine_sl else 2.0
    for k, c in enumerate(cands[:N_SERVE]):
        dl, j, wps, ttot, e, clear = c[0], c[1], c[2], c[3], c[4], c[5]
        r = sim.reqs[j]
        own_out = math.hypot(r[1] - st["x"], r[2] - st["y"]) / C.VA
        best_o = None; n_o = 0
        for q in others:
            so = sim.st[sim.drones[q]["sid"]]
            dd = math.hypot(r[1] - so["x"], r[2] - so["y"])
            if dd <= sim.drones[q]["R"] + 1e-6:
                n_o += 1
                tt = dd / C.VA
                best_o = tt if best_o is None else min(best_o, tt)
        A[SERVE0 + k, 10] = _clip(((best_o if best_o is not None else 60.0) - own_out) / 20.0, -3, 3)
        A[SERVE0 + k, 11] = min(n_o, 4) / 4.0
        A[SERVE0 + k, 12] = _clip((dl - (t + own_out)) / 20.0, -3, 3)
        A[SERVE0 + k, 13] = _clip((t + ttot + rem - C.H) / 60.0, -3, 3)
        A[SERVE0 + k, 14] = float(t > dl)
        A[SERVE0 + k, 15] = float(t > dl and r[3] == 1)
    return g, A


def tokens(g, A):
    """[N_ACT, NTOK] token matrix: [g, A_a, onehot(type)]."""
    X = np.zeros((N_ACT, NTOK), dtype=np.float32)
    X[:, :NG6] = g[None]
    X[:, NG6:NG6 + NA6] = A
    X[LAUNCH, NG6 + NA6 + 0] = 1.0
    X[HOLD, NG6 + NA6 + 1] = 1.0
    X[SERVE0:, NG6 + NA6 + 2] = 1.0
    return X


def ablation_mask(name):
    """Length-NTOK 0/1 mask per action token -> array [N_ACT, NTOK] (None = no ablation)."""
    if not name or name == "none":
        return None
    gi, ai = {"noforecast": (G_FORECAST, A_FORECAST), "noemerg": (G_EMERG, A_EMERG)}[name]
    M = np.ones((N_ACT, NTOK), dtype=np.float32)
    M[:, gi] = 0.0
    for act, idx in ai.items():
        acts = range(SERVE0, N_ACT) if act == "SERVE" else [act]
        for a in acts:
            for k in idx:
                M[a, NG6 + k] = 0.0
    return M
