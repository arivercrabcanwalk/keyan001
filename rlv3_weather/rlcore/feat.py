"""State features (design 8.2: physics feature eta injected into the state).
The environment contract supplies only information observable at decision time: forecast (issued <= now), onboard measured wind at the drone
(flight-controller wind estimate), nowcast cells, task list, own/sibling drone status. Hidden gusts / true future
wind / future requests are never visible."""
import math
import numpy as np
from . import phys
from .common import VA_MS
from .env import T_DAY, ACT_RETURN, ACT_WAIT
from .weather import nowcast_min_gap

F_T = 34      # per-token features (32 = base-policy suggestion flag, 33 = reserved)
F_C = 24      # context features
SC = 5000.0


def _eta(w, x1, y1, x2, y2):
    d = math.hypot(x2 - x1, y2 - y1)
    if d < 1e-6:
        return 0.0, 0.0
    return phys.eta_xi(w[0], w[1], (x2 - x1) / d, (y2 - y1) / d)


def plan_next(env, d):
    """the author's next planned task for this drone (first undone task in its planned sequence)."""
    for tr in env.L["drones"][d["i"]]["trips"]:
        for tid in tr:
            j = env.tid2j[tid]
            if not env.tasks[j]["done"]:
                return j
    return None


def featurize(env, cur, suggest=None):
    """returns tok (n_tok, F_T), ctx (F_C,), mask (n_tok,) bool, actions list (task j / ACT_RETURN / ACT_WAIT)."""
    d, av, feas, infos, can_ret, can_wait = cur
    s = env.st[d["st"]]
    t = env.t
    cap = d["cap"]
    if not np.isfinite(cap) or cap <= 0:
        raise ValueError("drone energy capacity must be finite and positive")
    if env.calm:
        wf = wf30 = wf60 = wm = (0.0, 0.0)
        nc = []
    else:
        wf = env.wx.forecast_wind(t, t); wf30 = env.wx.forecast_wind(t, t + 30); wf60 = env.wx.forecast_wind(t, t + 60)
        wm = env.wx.truth_wind(d["x"], d["y"], t)       # onboard / station anemometer (instantaneous)
        nc = env._nc() if env.use_cells else []
    pn = plan_next(env, d)
    ids_av = [x["j"] for x in av]
    n = len(av)
    tok = np.zeros((n + 2, F_T), np.float32)
    mask = np.zeros(n + 2, bool)
    pos = {}
    for k, (x, f, inf) in enumerate(zip(av, feas, infos)):
        r = tok[k]
        r[0] = (x["x"] - d["x"]) / SC; r[1] = (x["y"] - d["y"]) / SC
        r[2] = (x["x"] - s["x"]) / SC; r[3] = (x["y"] - s["y"]) / SC
        r[4] = math.hypot(r[0], r[1]); r[5] = math.hypot(r[2], r[3])
        r[6] = inf["e1"] / cap; r[7] = inf["h"] / cap; r[8] = inf["e2"] / cap; r[9] = inf["need"] / cap
        r[10] = (cap - d["e"] - inf["need"]) / cap
        r[11] = inf["t1"] / 30.0; r[12] = inf["t2"] / 30.0
        e1, x1 = _eta(wf, d["x"], d["y"], x["x"], x["y"]); r[13] = e1; r[14] = x1
        e2, x2 = _eta(wf, x["x"], x["y"], s["x"], s["y"]); r[15] = e2; r[16] = x2
        r[17] = _eta(wf30, d["x"], d["y"], x["x"], x["y"])[0]
        r[18] = _eta(wm, d["x"], d["y"], x["x"], x["y"])[0]
        if nc:
            r[19] = min(nowcast_min_gap(nc, x["x"], x["y"], t), 10.0) / 10.0
            r[20] = min(nowcast_min_gap(nc, 0.5 * (x["x"] + d["x"]), 0.5 * (x["y"] + d["y"]), t), 10.0) / 10.0
        else:
            r[19] = r[20] = 1.0
        rk = env.rank.get(x["tid"]) if not x["urgent"] else None
        r[21] = 1.0 if (pn is not None and x["j"] == pn) else 0.0
        r[22] = (rk[1] / max(1, rk[2])) if rk else 1.0
        r[23] = 1.0 if (rk and rk[0] == d["i"]) else 0.0
        r[24] = float(x["urgent"]); r[25] = float(x["prio"])
        if x["urgent"]:
            r[26] = np.clip((x["dl"] - t - inf["t1"]) / 60.0, -3, 3)  # arrival SLA
            r[27] = min((t - x["rel"]) / 60.0, 3.0)
            r[28] = x["w"] / 5.0
        r[29] = sum(1 for y in av if (y["x"] - x["x"]) ** 2 + (y["y"] - x["y"]) ** 2 < 4e6) / 10.0
        r[30] = 1.0
        mask[k] = bool(f)
    # RETURN token
    r = tok[n]
    if can_ret:
        er, tr_, okr = env.leg_pred(d["x"], d["y"], s["x"], s["y"], t)
        r[6] = er / cap; r[11] = tr_ / 30.0; r[13] = _eta(wf, d["x"], d["y"], s["x"], s["y"])[0]
        r[10] = (cap - d["e"] - er) / cap
        r[31] = 1.0; mask[n] = True
    # WAIT token
    r = tok[n + 1]
    if can_wait:
        r[13] = math.hypot(*wf) / VA_MS; r[17] = math.hypot(*wf60) / VA_MS; r[18] = math.hypot(*wm) / VA_MS
        r[31] = -1.0; mask[n + 1] = True
    acts = ids_av + [ACT_RETURN, ACT_WAIT]
    if not mask.any():
        raise ValueError("environment exposed a state with no legal physical action")
    # Infeasible forecast legs can correctly have infinite cost/duration. Their
    # tokens are excluded from attention, and must not inject NaNs via projection.
    tok[~mask] = 0.0
    if suggest is not None and suggest in acts:
        tok[acts.index(suggest), 32] = 1.0
    # context
    c = np.zeros(F_C, np.float32)
    pool = [x for x in env.tasks if not x["done"] and ((not x["urgent"] and x["st"] == d["st"]))]
    urg = [x for x in env.tasks if x["urgent"] and not x["done"] and x["rel"] <= t and d["st"] in x["elig"]]
    sib = [env.dr[k] for k in s["drones"] if k != d["i"]]
    c[0] = t / T_DAY; c[1] = d["e"] / cap; c[2] = cap; c[3] = float(d["at_st"])
    c[4] = len(pool) / 20.0; c[5] = len(urg) / 10.0
    c[6] = float(sib[0]["at_st"]) if sib else -1.0; c[7] = (sib[0]["e"] / sib[0]["cap"]) if sib else 0.0
    c[8], c[9] = wf[0] / VA_MS, wf[1] / VA_MS; c[10], c[11] = wf60[0] / VA_MS, wf60[1] / VA_MS
    c[12] = math.hypot(*wf) / phys.W_LIMIT; c[13], c[14] = wm[0] / VA_MS, wm[1] / VA_MS
    c[15] = (math.hypot(*wm) - math.hypot(*wf)) / 5.0
    c[16] = len(nc) / 5.0
    c[17] = d["busy"] / d["limit"]
    work = sum(2 * math.hypot(x["x"] - s["x"], x["y"] - s["y"]) / 900.0 * 0.6 + x["svc"] for x in pool)
    c[18] = np.clip(work / max(1.0, len(s["drones"]) * (T_DAY - t)), 0, 5)
    c[19] = float(env.calm); c[20] = env.margin
    c[21] = float(t >= 480.0); c[22] = d["ntrip"] / 20.0; c[23] = len(av) / 20.0
    if not np.isfinite(tok).all() or not np.isfinite(c).all():
        raise ValueError("non-finite public observation")
    return tok, c, mask, acts
