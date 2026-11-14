"""WX3: non-privileged ("fair") future sampling for rollouts + corrected rollout policy.

Background (found 2026-11-14): `policies.make_rollout` (N4) clones the simulator,
and `Sim.clone` SHARES the true WeatherDay. Rollouts therefore fly on the realised
future wind / gusts / storm-cell tracks and only the request stream is sampled.
N4 is thus weather-clairvoyant. This module builds a *twin* of the weather that
keeps the past (t <= t0) and resamples everything after t0 from the generative
model, conditioned only on what an agent can observe at t0:
  * large-scale OU error and Fourier spatial modes: Markov continuation from the
    state at t0 (fresh noise);
  * hidden gust: two-state Markov continuation from the state at t0;
  * visible storm cells: current position kept, future motion = nowcast velocity
    (estimated from the last observations) + fresh velocity OU; remaining lifetime
    resampled from the prior conditioned on the observed age;
  * cells not yet born: removed and re-spawned from the prior; whether the day is
    a storm day is resampled from its posterior given "no cell seen yet";
  * day-level parameters an agent cannot see (p_f, lam): resampled from the prior;
  * future urgent requests: storm faults from the twin's own sweeps (alarm > t0,
    target not yet alarmed) + Poisson background remainder.
Day-level wind hyper-parameters (ou_tau, ou_sig, gust amplitude/dwell) are kept,
i.e. the twin knows the day's climatology but not its realisation (documented).
"""
from __future__ import annotations
import copy
import math
import time
import numpy as np
from . import const as C
from .sim import LAUNCH, HOLD, SERVE0, N_ACT
from . import policies as P

LABEL_KEYS = ("J", "cost", "mk", "fails", "late_min_h", "late_min_n", "nh", "n_late_h",
              "n", "n_late", "cvar_h")


def _ou_continue(x0, n, a, s, rng):
    out = np.empty((n,) + np.shape(x0))
    x = np.array(x0, dtype=float)
    for k in range(n):
        x = a * x + s * rng.normal(0.0, 1.0, x.shape)
        out[k] = x
    return out


def _spawn(tw, rng, birth):
    xmin, xmax, ymin, ymax = tw.bbox
    pad = 8000.0
    life = float(rng.uniform(*C.LIFE_RANGE))
    death = min(C.H, birth + life)
    a = float(rng.uniform(*C.AXIS_RANGE)); b = float(rng.uniform(*C.AXIS_RANGE))
    ang = float(rng.uniform(0, 2 * math.pi))
    spd = float(rng.uniform(*C.CELL_SPEED_RANGE))
    cx0 = float(rng.uniform(xmin - pad, xmax + pad)); cy0 = float(rng.uniform(ymin - pad, ymax + pad))
    front = float(rng.uniform(*C.FRONT_ADD))
    from .weather import ou_path
    vu = ou_path(rng, tw.NT, C.DT, C.TAU_V, C.SIG_V, 2)
    vx = spd * math.cos(tw.cell_dir) + vu[:, 0]
    vy = spd * math.sin(tw.cell_dir) + vu[:, 1]
    return _track(tw, birth, death, cx0, cy0, vx, vy, a, b, ang, front, spd, life)


def _track(tw, birth, death, cxb, cyb, vx, vy, a, b, ang, front, spd, life, ib=None, cx_hist=None, cy_hist=None):
    NT = tw.NT
    cx = np.zeros(NT); cy = np.zeros(NT)
    if ib is None:
        ib = tw._idx(birth)
        cx[ib], cy[ib] = cxb, cyb
        for k in range(ib - 1, -1, -1):
            cx[k] = cx[k + 1] - vx[k] * 60.0 * C.DT
            cy[k] = cy[k + 1] - vy[k] * 60.0 * C.DT
    else:  # keep observed history up to ib
        cx[:ib + 1] = cx_hist[:ib + 1]; cy[:ib + 1] = cy_hist[:ib + 1]
    for k in range(ib + 1, NT):
        cx[k] = cx[k - 1] + vx[k - 1] * 60.0 * C.DT
        cy[k] = cy[k - 1] + vy[k - 1] * 60.0 * C.DT
    mid = 0.5 * (birth + death)
    tg = tw.tgrid
    inten = np.where((tg < birth) | (tg > death), 0.0,
                     np.where(tg <= mid, (tg - birth) / max(1e-6, mid - birth),
                              (death - tg) / max(1e-6, death - mid)))
    return dict(birth=birth, death=death, life=life, a=a, b=b, ang=ang, cx=cx, cy=cy,
                vx=vx, vy=vy, inten=inten, front=front, spd=spd)


def twin_future(wx, t0, rng):
    """Return a WeatherDay twin: identical up to t0, resampled afterwards."""
    tw = copy.copy(wx)
    if wx.mode == "nowind" or wx.NT == 0:
        return tw
    j0 = wx._idx(t0)
    n = wx.NT - j0 - 1
    a = math.exp(-C.DT / wx.ou_tau)
    if n > 0:
        s = wx.ou_sig * math.sqrt(max(0.0, 1 - a * a))
        tw.ou = wx.ou.copy()
        tw.ou[j0 + 1:] = _ou_continue(wx.ou[j0], n, a, s, rng)
        tw.kxi = wx.kxi.copy()
        s1 = math.sqrt(max(0.0, 1 - a * a))
        tw.kxi[j0 + 1:] = _ou_continue(wx.kxi[j0], n, a, s1, rng)
        # gust Markov continuation
        tw.gust = wx.gust.copy()
        on = bool(np.abs(wx.gust[j0]).sum() > 0)
        vec = wx.gust[j0].copy()
        p_switch = 1.0 - math.exp(-C.DT / wx.gust_dwell)
        for k in range(j0 + 1, wx.NT):
            if rng.random() < p_switch:
                on = not on
                if on:
                    ang = wx.dir0 + rng.uniform(-0.4, 0.4)
                    vec = wx.gust_amp * np.array([math.cos(ang), math.sin(ang)])
                else:
                    vec = np.zeros(2)
            tw.gust[k] = vec
        tw.wtx = wx.F0x + tw.ou[:, 0] + tw.gust[:, 0]
        tw.wty = wx.F0y + tw.ou[:, 1] + tw.gust[:, 1]
    # unobservable day parameters -> prior
    tw.p_f = float(rng.uniform(*C.PF_RANGE))
    tw.lam = float(rng.uniform(*C.LAM_RANGE))
    # cells
    tg = wx.tgrid[j0]
    nc = {c["i"]: c for c in wx.nowcast_cells(t0)}
    cells = []
    seen_any = False
    for i, c in enumerate(wx.cells):
        if c["birth"] > tg + 1e-9:
            continue  # unborn: unknown to the agent -> resample below
        seen_any = True
        if i not in nc:
            cells.append(c)  # already dead & observed; future irrelevant
            continue
        o = nc[i]
        age = max(0.0, tg - c["birth"])
        lo = max(C.LIFE_RANGE[0], age + C.DT)
        hi = max(lo, C.LIFE_RANGE[1])
        life = float(rng.uniform(lo, hi))
        death = min(C.H, c["birth"] + life)
        from .weather import ou_path
        vu = ou_path(rng, wx.NT, C.DT, C.TAU_V, C.SIG_V, 2, x0=np.zeros(2))
        vx = c["vx"].copy(); vy = c["vy"].copy()
        vx[j0:] = o["vx"] + vu[j0:, 0]
        vy[j0:] = o["vy"] + vu[j0:, 1]
        cells.append(_track(tw, c["birth"], death, None, None, vx, vy, c["a"], c["b"], c["ang"],
                            c["front"], c["spd"], life, ib=j0, cx_hist=c["cx"], cy_hist=c["cy"]))
    w0, w1 = C.CELL_WINDOW
    if wx.mode != "nowind" and tg < w1:
        if seen_any:
            storm = True
        else:
            tau_h = max(0.0, (tg - w0) / 60.0)
            lams = np.linspace(C.LAM_RANGE[0], C.LAM_RANGE[1], 21)
            p_none = float(np.mean(np.exp(-lams * tau_h)))
            ps = C.STORM_PROB * p_none / (C.STORM_PROB * p_none + (1 - C.STORM_PROB))
            storm = bool(rng.random() < ps)
        if storm:
            lo = max(tg, w0)
            for _ in range(int(rng.poisson(tw.lam * (w1 - lo) / 60.0))):
                cells.append(_spawn(tw, rng, float(rng.uniform(lo, w1))))
        tw.storm = storm or seen_any
    tw.cells = cells
    tw._pack_cells()
    return tw


def sample_future_fair(sim, rng):
    """Return (twin_wx, request list) for a fair rollout from sim.t."""
    t0 = sim.t
    tw = twin_future(sim.wx, t0, rng)
    T = sim.Txy
    nt = len(T)
    past = [r for r in sim.reqs if r[0] <= t0]
    already = {r[5] for r in past if r[4] in ("storm", "uniform") and r[5] >= 0}
    new = []
    if sim.wx.mode == "storm" and tw.ncell:
        first = {}
        for ti, ci, ent, lev in tw.swept_targets(T):
            if ti in already:
                continue
            if ti not in first or lev < first[ti]:
                first[ti] = lev
        for ti, lev in first.items():
            if rng.random() < tw.p_f:
                alarm = min(C.H - 1e-6, lev + float(rng.uniform(0.0, 20.0)))
                if alarm > t0:
                    pri = int(rng.random() < C.P_HIGH_FRAC)
                    new.append((alarm, float(T[ti][0]), float(T[ti][1]), pri, "storm", int(ti)))
    elif sim.wx.mode == "uniform" and t0 < 400.0:
        # uniform-fault days: faults independent of cells; Poisson with matched mean
        lam_u = 0.5 * nt * 0.3 * 0.25 / 370.0
        for _ in range(int(rng.poisson(lam_u * (400.0 - t0)))):
            ti = int(rng.integers(nt))
            if ti in already:
                continue
            new.append((float(rng.uniform(t0, 400.0)), float(T[ti][0]), float(T[ti][1]),
                        int(rng.random() < C.P_HIGH_FRAC), "uniform", ti))
    rem = max(0.0, C.H - t0)
    lam_bg = (nt / C.BG_RATE_DIV) / C.H
    for _ in range(int(rng.poisson(lam_bg * rem))):
        t = float(rng.uniform(t0, C.H))
        ti = int(rng.integers(nt))
        xy = np.asarray(T[ti]) + rng.normal(0.0, C.BG_JITTER, 2)
        new.append((t, float(xy[0]), float(xy[1]), int(rng.random() < C.P_HIGH_FRAC), "bg", -1))
    fut = past + new
    fut.sort(key=lambda r: r[0])
    return tw, fut


def label_metrics(m):
    nh = m["nh"]
    n_late_h = int(round(nh * (1.0 - m["ontime_h"]))) if nh else 0
    n_late = int(round(m["n"] * (1.0 - m["ontime"]))) if m["n"] else 0
    return np.array([m["J"], m["cost"], m["mk"], m["fails"] if "fails" in m else 0.0,
                     m["late_min_h"], m["late_min_n"], nh, n_late_h, m["n"], n_late, m["cvar_h"]],
                    dtype=np.float64)


def make_rollout_v3(M=32, base=None, seed=0, deadline_ms=None, fair=True, record=None,
                    score=None):
    """Corrected rollout (N4f if fair else N4p).

    * common random numbers: one sampled future per round, all legal actions on it;
    * only COMPLETE rounds are used, actions compared by the MEAN (fixes the
      sum-with-unequal-counts bug of make_rollout under a deadline);
    * deadline: checked before every rollout; an incomplete round is discarded;
      if no round completes, the base policy's action is returned (honest fallback);
    * record: optional list; per decision appends (legal, Qmat[n_legal, len(LABEL_KEYS)]).
    * score: optional fn(Qvec)->scalar (default J).
    """
    if base is None:
        base = P.make_N1(240.0)

    def pol(sim, i, mask, cands, info):
        legal = [a for a in range(N_ACT) if mask[a]]
        if not legal:
            return HOLD
        if len(legal) == 1:
            return legal[0]
        rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed + 17) % (2 ** 31))
        t_start = time.perf_counter()
        sums = np.zeros((len(legal), len(LABEL_KEYS)))
        nfull = 0
        for m in range(M):
            if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                break
            if fair:
                tw, fut = sample_future_fair(sim, rng)
            else:
                tw, fut = None, P._sample_future(sim, rng, None)
            row = np.zeros_like(sums)
            ok = True
            for k, a in enumerate(legal):
                if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                    ok = False
                    break
                s = sim.clone()
                if tw is not None:
                    s.wx = tw
                P.inject_future_safe(s, fut)
                s = P._apply_and_run(s, i, a, base)
                mm = s.metrics()
                mm["fails"] = len(s.fail_log)
                row[k] = label_metrics(mm)
            if not ok:
                break
            sums += row
            nfull += 1
        pol.last_nfull = nfull
        if nfull == 0:
            return base(sim, i, mask, cands, info)
        Q = sums / nfull
        if record is not None:
            record.append((list(legal), Q.copy(), nfull))
        sc = Q[:, 0] if score is None else np.array([score(q) for q in Q])
        return legal[int(np.argmin(sc))]
    pol.last_nfull = 0
    return pol
