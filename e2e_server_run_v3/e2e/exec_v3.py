"""pi_exec v3 -- learned execution / dynamic re-routing layer (paper 2, pure RL; no ALNS anywhere).

Actions (per drone decision, offered by the shared WX5 feasibility layer):
  0 LAUNCH next planned trip | 1 HOLD 5 min | 2..4 SERVE urgent candidate k | 5 OFFLOAD (v3, replaces v2 REROUTE)
  OFFLOAD = cross-station dynamic re-routing: hand the drone's LAST unstarted planned trip to the drone of ANOTHER
  station whose projected finish time is earliest (all trip targets in its radius, calm energy <= 0.9 cap, duty
  slack, and the receiver finishes >= 5 min before the donor would), then launch the next trip. It is legal only
  when it shortens the donor's projected finish -> it targets crew overtime and frees loaded stations for urgents.
  (v2 REROUTE rebuilt routes inside one station and was never useful: ABL_noRR = 0.0 %.)
Network: RL5-compatible MLP (global 48 + 6 x per-action 10 features) + value head; numpy forward in workers.
Training (exec_train_v3.py):
  stage X  Expert Iteration (Anthony et al. 2017; Silver et al. 2017): fair-twin rollout search (wx2/twin.py, only
           information observable at t) with the CURRENT policy as base improves decisions; the improved decisions
           are distilled into the policy (soft-Q targets). Round 0 base = N6 rule (no RL5 / no ALNS-derived weights).
  stage P  PPO fine-tune with common-random-number paired baselines and a PID-Lagrangian overtime constraint
           (Stooke et al. 2020): E[ot(pi)] <= E[ot(pi_X)] + eps ("do no harm on overtime").
Test time: OURS (greedy policy, ~1 ms) and OURS+S (policy-prior fair rollout search under a 100 ms deadline).
"""
import math, time
import numpy as np
from .exec_policy import ExecNet, np_forward, NIN, NACT, NG, NA, N5, sim_j_running   # noqa: F401  (NACT = 6)
import sys, os
from .common import ROOT
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from wx2 import feat as FT, const as C, sim as S, policies as PL   # noqa: E402

OFFLOAD = 5
OFF_MARGIN = 5.0


def offload_target(sim, i, info):
    """Return (fin_j, j, need_j, donor_fin, trip_min) for the best receiver of drone i's last planned trip, else None."""
    d = sim.drones[i]
    if d.get("backup") or d.get("handed") or len(d["trips"]) < 2:
        return None
    tr = d["trips"][-1]
    if tuple(tr) in getattr(sim, "_off_moved", ()):      # each trip is handed over at most once -> no ping-pong,
        return None                                       # the number of OFFLOADs per day is bounded by #trips
    fl_i, sv_i, _ = sim._trip_nw(d, tr)
    fin_i = sim.t + sim.remaining_plan_time(i, info)
    best = None
    for j, e in enumerate(sim.drones):
        if e["sid"] == d["sid"] or e.get("handed") or e["state"] == "down":
            continue
        st = sim._station(e)
        if any(math.hypot(sim.nodes[n].x - st["x"], sim.nodes[n].y - st["y"]) > e["R"] + 1e-6 for n in tr):
            continue
        fl, sv, sve = sim._trip_nw(e, tr)
        if fl * sim.p.flight_energy + sve > 0.9 * e["cap"]:
            continue
        need = (fl + sv) * (1 + C.LD_MARGIN)
        if e["duty"] + sim._committed_min(j) * (1 + C.LD_MARGIN) + need > e["duty_max"] - 1e-6:
            continue
        fin_j = sim.t + sim._time_need(j) + need
        if fin_j < fin_i - OFF_MARGIN and fin_j <= C.T_END - C.LD_RESERVE and (best is None or fin_j < best[0]):
            best = (fin_j, j, need, fin_i, (fl_i + sv_i))
    return best


def do_offload(sim, i, j):
    d = sim.drones[i]; e = sim.drones[j]
    if len(d["trips"]) < 2:
        return False
    tr = d["trips"].pop()
    e["trips"].append(list(tr))
    if not hasattr(sim, "_off_moved"):
        sim._off_moved = set()
    sim._off_moved.add(tuple(tr))
    sim.n_offload = getattr(sim, "n_offload", 0) + 1
    if e["state"] in ("idle", "hold"):
        sim._push(sim.t, 0, j)
    return True


def legal6(sim, i, m5, info, allow_off=True):
    mask = np.zeros(NACT, dtype=bool); mask[:N5] = m5
    off = None
    if allow_off and m5[S.LAUNCH] and info is not None:
        off = offload_target(sim, i, info)
        mask[OFFLOAD] = off is not None
    return mask, off


def features6(sim, i, m5, cands, info, off):
    x5 = FT.features(sim, i, m5, cands, info)
    x = np.zeros(NIN, dtype=np.float32); x[:NG + N5 * NA] = x5
    if off is not None:
        fin_j, j, need, fin_i, trip = off
        af = x[NG + OFFLOAD * NA: NG + (OFFLOAD + 1) * NA]
        af[0] = 1.0; af[1] = (fin_i - sim.t) / C.H; af[2] = (fin_j - sim.t) / C.H; af[3] = trip / 60.0
        af[4] = (fin_i - fin_j) / 60.0; af[5] = max(0.0, fin_i - C.H) / 60.0; af[6] = max(0.0, fin_j - C.H) / 60.0
        af[7] = float(sim.drones[j]["state"] in ("idle", "hold")); af[8] = min(len(sim.drones[i]["trips"]), 10) / 10.0
        af[9] = sim.t / C.H
    return x


def apply_action(sim, i, a, off):
    """Policy-side effect of the 6th action; returns the 5-action code the simulator executes."""
    if a == OFFLOAD:
        if off is not None:
            do_offload(sim, i, off[1])
        return S.LAUNCH
    return a


def make_policy(P, greedy=True, rng=None, record=None, allow_off=True):
    rng = rng or np.random.default_rng(0)

    def pol(sim, i, m5, cands, info):
        mask, off = legal6(sim, i, m5, info, allow_off)
        x = features6(sim, i, m5, cands, info, off)
        p, v = np_forward(P, x, mask)
        a = int(np.argmax(p)) if greedy else int(rng.choice(NACT, p=p))
        if record is not None:
            record.append([x, mask, a, float(np.log(p[a] + 1e-12)), v, sim_j_running(sim)])
        return apply_action(sim, i, a, off)
    pol.P = P
    return pol


def make_rule_off(inner):
    """Non-RL counterpart (ablation/baseline 'N6+OFF'): offload whenever legal, then the inner rule decides."""
    def pol(sim, i, m5, cands, info):
        if m5[S.LAUNCH] and info is not None and not m5[S.SERVE0:].any():
            off = offload_target(sim, i, info)
            if off is not None:
                do_offload(sim, i, off[1])
                info = sim.next_trip_info(i)
        return inner(sim, i, m5, cands, info)
    return pol


# ---------------- fair rollout Q-estimation (shared by ExIt data generation and OURS+S) ----------------
def q_values(sim, i, legal, off, base, M, rng, deadline_ms=None):
    from wx2 import twin as TW
    t0 = time.perf_counter()
    sums = np.zeros(len(legal)); nfull = 0
    for _ in range(M):
        if deadline_ms is not None and (time.perf_counter() - t0) * 1000.0 >= deadline_ms:
            break
        tw, fut = TW.sample_future_fair(sim, rng)
        row = np.zeros(len(legal)); ok = True
        for k, a in enumerate(legal):
            if deadline_ms is not None and (time.perf_counter() - t0) * 1000.0 >= deadline_ms:
                ok = False; break
            s = sim.clone(); s.wx = tw
            PL.inject_future_safe(s, fut)
            if deadline_ms is not None:
                s.abort_at = t0 + deadline_ms / 1000.0
            try:
                a5 = a
                if a == OFFLOAD:
                    do_offload(s, i, off[1]); a5 = S.LAUNCH
                s = PL._apply_and_run(s, i, a5, base)
            except S.RolloutAbort:
                ok = False; break
            row[k] = s.metrics()["J"]
        if not ok:
            break
        sums += row; nfull += 1
    return (sums / nfull if nfull else None), nfull


def make_search_policy(P, M=32, deadline_ms=100.0, topk=3, pmin=0.02, seed=0, allow_off=True):
    """OURS+S: AlphaZero-style use of the learned policy -- prior-pruned candidate actions (top-k with prob>=pmin),
    each scored by fair-twin rollouts with the greedy policy as base (common random numbers), under a hard
    per-decision deadline; honest fallback to the policy's action if no complete round fits."""
    base = make_policy(P, greedy=True, allow_off=allow_off)

    def pol(sim, i, m5, cands, info):
        mask, off = legal6(sim, i, m5, info, allow_off)
        x = features6(sim, i, m5, cands, info, off)
        p, v = np_forward(P, x, mask)
        a0 = int(np.argmax(p))
        order = [a for a in np.argsort(-p) if mask[a] and (p[a] >= pmin or a == a0)][:topk]
        if len(order) <= 1:
            return apply_action(sim, i, a0, off)
        rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed + 17) % (2 ** 31))
        Q, nf = q_values(sim, i, order, off, base, M, rng, deadline_ms)
        a = a0 if Q is None else int(order[int(np.argmin(Q))])
        return apply_action(sim, i, a, off)
    return pol


def load_policy_params(path):
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    return ck["P"]
