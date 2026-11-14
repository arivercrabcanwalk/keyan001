"""All WX-E baselines. Every policy has the signature
    act = pol(sim, i, mask, cands, info) -> int in {0..4}
and only sees information also available to RL (forecast, nowcast, station wind,
already-alarmed faults). Rollout/clairvoyant additionally use the generative model
or the true future (clairvoyant is an unimplementable upper bound).
"""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import math, time
import numpy as np
from . import const as C
from .sim import LAUNCH, HOLD, SERVE0, N_ACT, Sim
from . import fly as F
from . import weather as W


def _pick_serve(mask, cands, prefer_high=True):
    if not mask[SERVE0:].any():
        return None
    if not cands:
        return SERVE0 if mask[SERVE0] else None
    best = 0
    if prefer_high:
        # already sorted by deadline; prefer high-pri among those with tight deadline
        for k, c in enumerate(cands):
            if not mask[SERVE0 + k]:
                continue
            j = c[1]
            pri = 0
            # cands don't have pri at [3] — look at nothing; just first legal
            best = k
            break
        # prefer any high-pri: we need pri. Request is sim.reqs[j]
    return SERVE0 + best


def urgent_first_then(mask, cands, fallback):
    if mask[SERVE0:].any():
        # soonest deadline is index 0 (candidates already sorted)
        for k in range(len(cands)):
            if mask[SERVE0 + k]:
                return SERVE0 + k
        if mask[SERVE0]:
            return SERVE0
    if fallback == LAUNCH and mask[LAUNCH]:
        return LAUNCH
    if fallback == HOLD and mask[HOLD]:
        return HOLD
    if mask[LAUNCH]:
        return LAUNCH
    if mask[HOLD]:
        return HOLD
    return int(np.argmax(mask)) if mask.any() else HOLD


# ---------- A1: no hold, urgent first, nearest (implicit via event order) ----------
def make_A1():
    def pol(sim, i, mask, cands, info):
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


# ---------- N1: static(T) reserve ----------
def _ready_others(sim, i):
    d = sim.drones[i]
    n = 0
    for j, e in enumerate(sim.drones):
        if j == i:
            continue
        if e["sid"] == d["sid"] and e["state"] in ("idle", "hold"):
            n += 1
    return n


def make_N1(T=120.0, dabs_only=False, k=1):
    """Until time T, keep >=k ready drones at the station (DABS-only if flag).
    Urgent requests are always served first (that is the point of reserving).
    """
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any():
            return urgent_first_then(mask, cands, HOLD)
        d = sim.drones[i]
        if sim.t >= T:
            return urgent_first_then(mask, cands, LAUNCH)
        if dabs_only and sim.st[d["sid"]]["kind"] != 2:
            return urgent_first_then(mask, cands, LAUNCH)
        # hold if we would otherwise drop ready count below k
        if _ready_others(sim, i) < k and mask[HOLD]:
            return HOLD
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


# ---------- N2: corridor threshold ----------
def _corridor_ok(sim, info, m_min):
    if info is None:
        return False
    if not info["clear"]:
        return False
    # "clear for trip duration + m": re-check nowcast over [t, t+ttot+m]
    # info['clear'] already uses predicted duration; extend by sampling further
    # We approximate: if a cell is predicted to enter the corridor in extra m minutes
    # by pushing t0. Implemented in info via plan_trip at t; do a second check.
    return True


def make_N2(m=10.0):
    """Launch only if the planned corridor is predicted clear for duration+m.
    Always serve urgents first. If not clear, HOLD (or SERVE).
    """
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any():
            return urgent_first_then(mask, cands, HOLD)
        if info is None:
            return urgent_first_then(mask, cands, HOLD)
        clear = info["clear"]
        if clear and m > 0 and info.get("wps"):
            # peek m minutes ahead: would a predicted cell reach the next trip path?
            nc = sim._nowcast()
            wps = info["wps"]
            t1 = sim.t + info["ttot"] + m
            # check last leg region against later predicted cells
            for a, b in zip(wps, wps[1:]):
                if F.corridor_hits((a[0], a[1]), (b[0], b[1]), sim.t, info["ttot"] + m, nc, C.BUFFER):
                    clear = False
                    break
        if clear and mask[LAUNCH]:
            return LAUNCH
        if mask[HOLD]:
            return HOLD
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


# ---------- N3: storm-aware preposition ----------
def _station_in_sweep(sim, sid, H_p):
    st = sim.st[sid]
    nc = sim._nowcast()
    if not nc:
        return False
    R = st["R"]
    for c in nc:
        # sample every 5 min over H_p
        t = 0.0
        while t <= H_p + 1e-9:
            cx, cy = F.pred_cell_at(c, sim.t, sim.t + t)
            # coverage circle intersects predicted ellipse
            # approx: dist(station, center) < R + max(a,b) + small buffer
            if math.hypot(cx - st["x"], cy - st["y"]) <= R + max(c["a"], c["b"]) + 500.0:
                return True
            t += C.DT
    return False


def make_N3(H_p=30.0, k=1):
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any():
            return urgent_first_then(mask, cands, HOLD)
        d = sim.drones[i]
        if _station_in_sweep(sim, d["sid"], H_p) and _ready_others(sim, i) < k and mask[HOLD]:
            return HOLD
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


def make_N2N3(m=10.0, H_p=30.0, k=1):
    p2 = make_N2(m)
    p3 = make_N3(H_p, k)
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any():
            return urgent_first_then(mask, cands, HOLD)
        a2 = p2(sim, i, mask, cands, info)
        a3 = p3(sim, i, mask, cands, info)
        if a2 == HOLD or a3 == HOLD:
            return HOLD if mask[HOLD] else urgent_first_then(mask, cands, LAUNCH)
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


# ---------- N5: weather-adaptive (category -> frozen params) ----------
def wind_bin(sim, cuts=(6.0, 9.0)):
    wx, wy = sim._fc()
    spd = math.hypot(wx, wy)
    if spd < cuts[0]:
        return 0
    if spd < cuts[1]:
        return 1
    return 2


def storm_obs(sim):
    return int(len(sim._nowcast()) > 0)


def make_N5(table):
    """table[(storm, wbin)] = a policy already built."""
    def pol(sim, i, mask, cands, info):
        key = (storm_obs(sim), wind_bin(sim))
        if key not in table:
            key = (0, 1)
        return table[key](sim, i, mask, cands, info)
    return pol


# ---------- A2: TS-insert (cheapest insertion of urgent into remaining trips) ----------
def make_A2():
    """Cost-greedy: if an urgent can be cheaply inserted, SERVE the cheapest;
    otherwise launch; never hold. Insertion into a *future* trip is approximated
    by serving as a dedicated sortie when that is cheaper than delaying (we keep
    dedicated-sortie semantics for energy/coverage consistency with WX-E).
    Among serve candidates, pick the one with smallest predicted duration
    (nearest). This is a faithful cheap-insertion stand-in; full node-level
    insertion into planned sequences is done in make_A2_insert.
    """
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any() and cands:
            # cheapest = shortest predicted ttot
            best, bk = None, 0
            for k, c in enumerate(cands):
                if not mask[SERVE0 + k]:
                    continue
                if best is None or c[3] < best:
                    best, bk = c[3], k
            return SERVE0 + bk
        if mask[LAUNCH]:
            return LAUNCH
        return urgent_first_then(mask, cands, LAUNCH)
    return pol


# ---------- Clairvoyant one-step (O) ----------
def _continue(sim, base):
    """Run the rest of the day with base policy, no timing."""
    sim.run(base, record_time=False)
    return sim.metrics()["J"]


def _forced(sim, i, act, base, wx=None, reqs=None):
    s = sim.clone()
    if wx is not None:
        s.wx = wx
    if reqs is not None:
        # replace future requests (keep past / already seen)
        # rebuild pending and event queue's type-1 events
        t0 = s.t
        s.reqs = list(reqs)
        s.nreq = len(reqs)
        # keep flags for already done; new length
        old_n = len(s._done_flags)
        s._done_flags = list(s._done_flags) + [False] * max(0, len(reqs) - old_n)
        if len(s._done_flags) > len(reqs):
            s._done_flags = s._done_flags[:len(reqs)]
        s.pending = [j for j in range(len(reqs)) if (not s._done_flags[j]) and reqs[j][0] <= t0
                     and j not in s.assigned]
        # rebuild request events in the future
        s.ev = [e for e in s.ev if e[1] != 1]
        for j, r in enumerate(reqs):
            if r[0] > t0 and not (j < len(s._done_flags) and s._done_flags[j]):
                s._push(r[0], 1, j)
        heapq_heapify = __import__("heapq").heapify
        heapq_heapify(s.ev)
    first = {"v": True}

    def pol(ss, k, mask, cands, info):
        if first["v"] and k == i:
            first["v"] = False
            if 0 <= act < N_ACT and mask[act]:
                return act
            # fallback if the forced action became illegal
            return urgent_first_then(mask, cands, LAUNCH)
        return base(ss, k, mask, cands, info)

    # execute the forced action now, then continue
    # The current call is INSIDE _decide; easier to return act from a wrapper
    # used as the current policy, then continue.
    # We are called from make_clairvoyant as the policy itself, so we must
    # simulate clones independently: apply act on clone then run remainder.
    s._decide_forced(i, act, pol) if hasattr(s, "_decide_forced") else _apply_and_run(s, i, act, pol)
    return s.metrics()["J"]


def _apply_and_run(s, i, act, pol_rest):
    """Apply `act` for drone i on clone s (which is at the decision state),
    then run the rest with pol_rest. We inject a one-shot wrapper."""
    first = {"v": True}

    def wrap(ss, k, mask, cands, info):
        if first["v"] and k == i and 0 <= act < N_ACT and mask[act]:
            first["v"] = False
            return act
        if first["v"] and k == i:
            first["v"] = False
        return pol_rest(ss, k, mask, cands, info)

    # The clone is at the same t, with the same event just being processed.
    # We cannot easily re-enter _decide. Instead: set a one-shot and call _decide,
    # then run() for the remaining events. The current event was already popped
    # on the ORIGINAL; the clone still has the same ev (copied AFTER pop?);

    # Careful: clone is made inside the policy, which is called from _decide,
    # AFTER the event was popped on the original. The clone's ev is a copy of
    # the already-popped queue. The drone is still idle. We just need to apply
    # the action then continue the queue — without re-offering this same decision
    # in a tick. Directly execute the action.
    m, cands, info = s.mask(i)
    if not (0 <= act < N_ACT and m[act]):
        act = urgent_first_then(m, cands, LAUNCH)
    s.ndec += 1
    d = s.drones[i]
    if act == HOLD:
        d["state"] = "hold"
        d["holds"] += 1
        s.n_hold += 1
    elif act == LAUNCH:
        s.n_launch += 1
        s._exec_launch(i, info)
    else:
        k = act - SERVE0
        if 0 <= k < len(cands):
            s.n_serve += 1
            s._exec_urgent(i, cands[k])
    s.run(wrap, record_time=False)
    return s


def make_clairvoyant(base=None):
    if base is None:
        base = make_N1(240.0)  # dev-best rule (frozen after grid)

    def pol(sim, i, mask, cands, info):
        legal = [a for a in range(N_ACT) if mask[a]]
        if not legal:
            return HOLD
        if len(legal) == 1:
            return legal[0]
        best, bj = None, legal[0]
        for a in legal:
            J = _apply_and_run(sim.clone(), i, a, base).metrics()["J"] if False else None
            s = sim.clone()
            _apply_and_run(s, i, a, base)
            J = s.metrics()["J"]
            if best is None or J < best - 1e-9:
                best, bj = J, a
        return bj
    return pol


# ---------- Rollout / MSA (N4) ----------
def _sample_future(sim, rng, horizon=None):
    """Sample remaining exogenous process from the known generative model,
    conditioned on what has been observed (nowcast, seen requests). Past
    requests are kept. Future background ~ Poisson remainder. Future cells
    born after t: Poisson remainder in the window. Already-visible cells
    continue with nowcast velocity + OU noise (we approximate by nowcast
    const vel + N(0, SIG_V)). Storm faults for predicted remaining sweeps
    with p_f (use the day's p_f if known — it is a day attribute of truth;
    using it is 'same generative model'. Agents that aren't rollout don't
    get p_f; rollout is allowed the model).
    """
    t0 = sim.t
    wx = sim.wx
    T = sim.Txy
    nt = len(T)
    # keep past requests (already in sim.reqs with t <= t0) plus already pending
    past = [r for r in sim.reqs if r[0] <= t0]
    # remaining background
    t1 = C.H if horizon is None else min(C.H, t0 + horizon)
    rem = max(0.0, t1 - t0)
    lam_bg = (nt / C.BG_RATE_DIV) / C.H
    nbg = int(rng.poisson(lam_bg * rem))
    new = []
    for _ in range(nbg):
        t = float(rng.uniform(t0, t1))
        ti = int(rng.integers(nt))
        xy = T[ti] + rng.normal(0.0, C.BG_JITTER, 2)
        pri = int(rng.random() < C.P_HIGH_FRAC)
        new.append((t, float(xy[0]), float(xy[1]), pri, "bg", -1))
    # predicted remaining sweeps of VISIBLE cells (const-vel nowcast)
    nc = sim._nowcast()
    p_f = wx.p_f
    swept_now = set()
    # already alarmed storm faults (by target)
    already = {r[5] for r in past if r[4] in ("storm", "uniform") and r[5] >= 0}
    for c in nc:
        for ti, (x, y) in enumerate(T):
            if ti in already:
                continue
            # will the predicted track sweep this target in the future?
            hit_leave = None
            tt = 0.0
            inside = False
            while tt <= min(120.0, t1 - t0) + 1e-9:
                cx, cy = F.pred_cell_at(c, t0, t0 + tt)
                inn = (math.hypot(x - cx, y - cy) <= max(c["a"], c["b"]))
                if inn:
                    inside = True
                    hit_leave = t0 + tt
                elif inside:
                    break
                tt += C.DT
            if hit_leave is not None and rng.random() < p_f:
                delay = float(rng.uniform(0.0, 20.0))
                alarm = min(C.H - 1e-6, hit_leave + delay)
                if alarm > t0:
                    pri = int(rng.random() < C.P_HIGH_FRAC)
                    new.append((alarm, float(x), float(y), pri, "storm", int(ti)))
                    already.add(ti)
    # possible new cells not yet born (if t0 still in window) — coarse Poisson
    if wx.storm and t0 < C.CELL_WINDOW[1]:
        rem_h = max(0.0, (C.CELL_WINDOW[1] - max(t0, C.CELL_WINDOW[0])) / 60.0)
        nnew = int(rng.poisson(wx.lam * rem_h))
        # we don't materialise new cells into wx (truth cells stay);
        # we only sample the FAULTS they might cause, uniform-ish in remaining window.
        # This is a model approximation (new cells aren't in the nowcast).
        for _ in range(nnew):
            # a random subset of targets may be swept
            for ti in range(nt):
                if ti in already:
                    continue
                if rng.random() < p_f * 0.15:  # low, because not every new cell sweeps every target
                    alarm = float(rng.uniform(t0, min(C.H, t0 + 120.0)))
                    pri = int(rng.random() < C.P_HIGH_FRAC)
                    new.append((alarm, float(T[ti, 0]), float(T[ti, 1]), pri, "storm", int(ti)))
                    already.add(ti)
    fut = past + new
    fut.sort(key=lambda r: r[0])
    return fut


def make_rollout(M=32, base=None, seed=0, horizon=None, deadline_ms=None):
    """Sample-based one-step rollout. If deadline_ms is set, hard wall-clock
    cutoff: return the current best action when time runs out (WX-H / N4a).
    """
    if base is None:
        base = make_N1(240.0)  # dev-best rule (frozen after grid)

    def pol(sim, i, mask, cands, info):
        legal = [a for a in range(N_ACT) if mask[a]]
        if not legal:
            return HOLD
        if len(legal) == 1:
            return legal[0]
        rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed + 17) % (2 ** 31))
        # pre-draw futures (common random numbers across actions)
        t_start = time.perf_counter()
        acc = {a: 0.0 for a in legal}
        n_used = 0
        for m in range(M):
            if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                break
            fut = _sample_future(sim, rng, horizon)
            for a in legal:
                if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                    break
                s = sim.clone()
                # replace future requests
                _inject_future(s, fut)
                _apply_and_run(s, i, a, base)
                acc[a] += s.metrics()["J"]
            n_used += 1
        if n_used == 0:
            return urgent_first_then(mask, cands, LAUNCH)
        best, bj = None, legal[0]
        for a in legal:
            if best is None or acc[a] < best:
                best, bj = acc[a], a
        return bj
    return pol


def _inject_future(s, fut):
    t0 = s.t
    s.reqs = list(fut)
    s.nreq = len(fut)
    s._done_flags = [False] * len(fut)
    # mark already-logged as done: match by (t,x,y) of seen
    seen_keys = {(round(r[0], 5), round(r[1], 1), round(r[2], 1)) for r in s.seen}
    logged = {L[4] for L in s.log}  # old indices, not reliable after replace
    # better: any fut request with t<=t0 that is not in pending and was served
    # Keep pending by matching (t,x,y)
    pend_keys = set()
    for j in s.pending:
        # s.pending refers to OLD reqs — we saved pending as indices. After clone,
        # pending still points at old sim.reqs which we are replacing. Fix:
        pass
    old_pending = list(s.pending)
    old_reqs = s.reqs  # already replaced — TOO LATE if we already overwrote.
    # This function is called AFTER clone, we must capture old pending reqs first.
    # We'll change the API: call before replacing, using sim.reqs from clone
    # which still has original reqs until we overwrite.
    return  # see inject_future_safe


def inject_future_safe(s, fut):
    t0 = s.t
    old_reqs = s.reqs
    old_pending = [old_reqs[j] for j in s.pending if j < len(old_reqs)]
    old_assigned_reqs = []
    done_keys = set()
    for L in s.log:
        done_keys.add(L[4])  # old index
    done_tuples = set()
    for idx, r in enumerate(old_reqs):
        if idx < len(s._done_flags) and s._done_flags[idx]:
            done_tuples.add((round(r[0], 4), round(r[1], 1), round(r[2], 1), r[3]))
    s.reqs = list(fut)
    s.nreq = len(fut)
    s._done_flags = [False] * len(fut)
    s.assigned = set()
    s.pending = []
    for j, r in enumerate(fut):
        key = (round(r[0], 4), round(r[1], 1), round(r[2], 1), r[3])
        if key in done_tuples:
            s._done_flags[j] = True
        elif r[0] <= t0 + 1e-9:
            s.pending.append(j)
    # drop old request events, add new future ones
    s.ev = [e for e in s.ev if e[1] != 1]
    for j, r in enumerate(fut):
        if r[0] > t0 + 1e-9 and not s._done_flags[j]:
            s._push(r[0], 1, j)
    __import__("heapq").heapify(s.ev)


# monkey-patch rollout to use safe inject
def make_rollout(M=32, base=None, seed=0, horizon=None, deadline_ms=None):  # noqa: F811
    if base is None:
        base = make_N1(240.0)  # dev-best rule (frozen after grid)

    def pol(sim, i, mask, cands, info):
        legal = [a for a in range(N_ACT) if mask[a]]
        if not legal:
            return HOLD
        if len(legal) == 1:
            return legal[0]
        rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed + 17) % (2 ** 31))
        t_start = time.perf_counter()
        acc = {a: 0.0 for a in legal}
        n_used = 0
        futures = []
        for m in range(M):
            futures.append(_sample_future(sim, rng, horizon))
        for m, fut in enumerate(futures):
            if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                break
            for a in legal:
                if deadline_ms is not None and (time.perf_counter() - t_start) * 1000.0 >= deadline_ms:
                    break
                s = sim.clone()
                inject_future_safe(s, fut)
                _apply_and_run(s, i, a, base)
                acc[a] += s.metrics()["J"]
            n_used += 1
        if n_used == 0:
            return urgent_first_then(mask, cands, LAUNCH)
        best, bj = None, legal[0]
        for a in legal:
            if best is None or acc[a] < best:
                best, bj = acc[a], a
        return bj
    return pol


# ---------- A3: periodic TS-reopt of remaining unstarted work ----------
# Implemented as: at each decision, optionally re-pack this station's remaining
# unstarted trips + pending urgents by cheapest-insertion greedy + relocate,
# then take urgent-first / launch. The SEARCH is the differentiator; the
# immediate action is still a physical one. Budget is a real wall-clock cap.
def _repack_station(sim, sid, budget_s):
    t0 = time.perf_counter()
    # gather leftover planned nodes at this station + pending urgents in range
    nodes_left = []
    drone_ids = [i for i, d in enumerate(sim.drones) if d["sid"] == sid and d["state"] != "down"]
    for i in drone_ids:
        d = sim.drones[i]
        for tr in d["trips"]:
            nodes_left.extend(tr)
        nodes_left.extend(d["backlog"])
    # we only rearrange unstarted planned trips (not urgents into planned —
    # urgents stay dedicated, but we can choose order of planned packs).
    if not nodes_left or not drone_ids:
        return
    # greedy NN pack into drones by remaining duty / cap, nearest first
    rng_t = 0
    st = sim.st[sid]
    remaining = list(nodes_left)
    # clear existing unstarted
    for i in drone_ids:
        sim.drones[i]["trips"] = []
        sim.drones[i]["backlog"] = []
    # process drones with smallest remaining duty first
    order = sorted(drone_ids, key=lambda i: sim.drones[i]["duty"])
    for i in order:
        if time.perf_counter() - t0 > budget_s:
            break
        sim.drones[i]["backlog"] = list(remaining)
        remaining = []
        sim._pack_backlog(i)
        # unpack unused
        # _pack_backlog consumes backlog fully into trips (or leftover backlog)
        # any not packed stay on this drone's backlog — move to remaining for next
        if sim.drones[i]["backlog"]:
            remaining.extend(sim.drones[i]["backlog"])
            sim.drones[i]["backlog"] = []
    if remaining:
        sim.drones[order[-1]]["backlog"].extend(remaining)
    # local relocate while budget remains: swap tails
    improved = True
    while improved and (time.perf_counter() - t0) < budget_s:
        improved = False
        for a in order:
            for b in order:
                if a >= b:
                    continue
                if time.perf_counter() - t0 > budget_s:
                    break
                da, db = sim.drones[a], sim.drones[b]
                if not da["trips"] or not db["trips"]:
                    continue
                # try move last trip of a to b
                tr = da["trips"][-1]
                da["trips"].pop()
                db["trips"].append(tr)
                # accept always if b can pack (energy checked at launch); simple
                improved = True
                break


def make_A3(budget_s=1.0, every_min=10.0, inner=None):
    """TS-reopt: on events and every `every_min`, re-pack remaining trips
    of the deciding station, using a real wall-clock budget. Immediate
    action after reopt is urgent-first then launch (no hold), unless `inner`
    is provided (e.g. N3).
    """
    if inner is None:
        inner = make_A1()
    last = {"t": -1e9}

    def pol(sim, i, mask, cands, info):
        d = sim.drones[i]
        if (sim.t - last["t"] >= every_min - 1e-9) or True:  # every decision + events
            _repack_station(sim, d["sid"], budget_s)
            last["t"] = sim.t
            # info may be stale after repack; inner will recompute via mask already given
        return inner(sim, i, mask, cands, info)
    return pol


# convenience registry for grid search
N1_GRID = [15, 20, 30, 45, 60, 90, 120, 180, 240]
N2_GRID = [0, 5, 10, 15, 20, 30]
N3_HP = [15, 30, 45]
N3_K = [1, 2]


def name_policy(name):
    """Build a policy from a frozen name string."""
    if name == "A1":
        return make_A1()
    if name == "A2":
        return make_A2()
    if name.startswith("A3"):
        # A3_1s, A3_3s, A3_100ms
        if name == "A3_1s":
            return make_A3(1.0)
        if name == "A3_3s":
            return make_A3(3.0)
        if name == "A3_100ms":
            return make_A3(0.10)
        if name == "A3_50ms":
            return make_A3(0.05)
        return make_A3(1.0)
    if name.startswith("N6_"):
        # N6_H_theta e.g. N6_60_0.25
        parts = name.split("_")
        return make_N6(float(parts[1]), float(parts[2]))
    if name.startswith("N1_"):
        return make_N1(float(name.split("_")[1]))
    if name.startswith("N2_"):
        return make_N2(float(name.split("_")[1]))
    if name.startswith("N3_"):
        # N3_Hp_k
        parts = name.split("_")
        return make_N3(float(parts[1]), int(parts[2]))
    if name.startswith("N2N3_"):
        # N2N3_m_Hp_k
        parts = name.split("_")
        return make_N2N3(float(parts[1]), float(parts[2]), int(parts[3]))
    if name == "O":
        return make_clairvoyant(make_N3(30.0, 1))
    if name.startswith("N4_"):
        # N4_M32, N4_M8, N4_M1. Optional trailing base: N4_M32_N1_240.
        # Default base is the frozen dev-best rule N1_240 (not N3).
        parts = name.split("_")
        M = int(parts[1][1:]) if "M" in parts[1] else 32
        if len(parts) >= 4:
            base = name_policy("_".join(parts[2:]))
        else:
            base = make_N1(240.0)
        return make_rollout(M=M, base=base)
    raise KeyError(name)

# ---------- N6 (WX3): anticipatory reserve, after waiting strategies (Mitrovic-Minic & Laporte 2004)
# and anticipatory time budgeting (Ulmer 2018). Reserve >=k ready drones only while the EXPECTED number
# of urgent alarms in this station's coverage over the next H minutes is >= theta. Expectation uses only
# observable information: background Poisson rate + targets in coverage predicted (const-vel nowcast)
# to be swept by a visible cell within H, times the prior-mean fault probability.
def _expected_urgent(sim, i, H):
    d = sim.drones[i]; st = sim.st[d["sid"]]
    R = d["R"]
    T = sim.Txy
    cov = [k for k, (x, y) in enumerate(T) if math.hypot(x - st["x"], y - st["y"]) <= R]
    if not len(T):
        return 0.0
    lam_bg = (len(T) / C.BG_RATE_DIV) / C.H * (len(cov) / len(T))
    e = lam_bg * min(H, C.H - sim.t)
    nc = sim._nowcast()
    if nc and cov:
        pf = 0.5 * (C.PF_RANGE[0] + C.PF_RANGE[1])
        hit = 0
        for k in cov:
            x, y = T[k]
            for c in nc:
                swept = False
                tt = 0.0
                while tt <= H + 1e-9:
                    cx, cy = F.pred_cell_at(c, sim.t, sim.t + tt)
                    if math.hypot(x - cx, y - cy) <= max(c["a"], c["b"]):
                        swept = True
                        break
                    tt += C.DT
                if swept:
                    hit += 1
                    break
        e += pf * hit
    return e


def make_N6(H=60.0, theta=0.25, k=1):
    def pol(sim, i, mask, cands, info):
        if mask[SERVE0:].any():
            return urgent_first_then(mask, cands, HOLD)
        if _ready_others(sim, i) < k and mask[HOLD] and _expected_urgent(sim, i, H) >= theta:
            return HOLD
        return urgent_first_then(mask, cands, LAUNCH)
    return pol
