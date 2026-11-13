#!/usr/bin/env python3
"""WX-H: value-guided lookahead at 1/10/100 ms vs plain sampling rollout,
plus random-value-net ablation. Dev only (20×10) unless --plans/--days given.
Requires a trained policy (optional prior) and a fitted ValueNet.
"""
from __future__ import annotations

import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.dirname(_os_paths.path.abspath(__file__)))
WX_ROOT = _wx_root()
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)

import os, sys, json, time, argparse, traceback, math
from collections import defaultdict
from multiprocessing import get_context
import numpy as np

sys.path.insert(0, WX_ROOT)
from wx2 import const as C, inst as I, evaljob as E, sim as S, feat as F, learn as L, policies as P
from wx2.policies import (N_ACT, LAUNCH, HOLD, SERVE0, urgent_first_then,
                           _sample_future, inject_future_safe, make_N1, make_rollout)

OUT = os.path.join(WX_ROOT, "wx_h")
RES = os.path.join(OUT, "results")
os.makedirs(RES, exist_ok=True)

def log(*a):
    print(*a, flush=True)

def apply_action(s, i, act):
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
    return s

def state_feat(s):
    """Features at a remaining decision, or drone 0 fallback."""
    for i, d in enumerate(s.drones):
        if d.get("state") in ("idle", "hold"):
            try:
                m, cands, info = s.mask(i)
                return F.features(s, i, m, cands, info)
            except Exception:
                continue
    try:
        m, cands, info = s.mask(0)
        return F.features(s, 0, m, cands, info)
    except Exception:
        return np.zeros(F.NIN, np.float32)

def make_vg(V, mu, sd, deadline_ms, prior=None, Mmax=128, base=None, seed=0):
    """Value-backed one-step lookahead. Score(a) = E[V(s' after a)] under sampled futures.
    Completing the day with the base rule is avoided — that is the speed gain vs N4.
    """
    if base is None:
        base = make_N1(240.0)

    def pol(sim, i, mask, cands, info):
        legal = [a for a in range(N_ACT) if mask[a]]
        if not legal:
            return HOLD
        if len(legal) == 1:
            return legal[0]
        t0 = time.perf_counter()
        x0 = F.features(sim, i, mask, cands, info)
        if prior is not None:
            _, p = prior.act(x0, mask.astype(np.float64), greedy=False)
            order = sorted(legal, key=lambda a: -float(p[a]))
        else:
            order = list(legal)
        rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed + 17) % (2 ** 31))
        acc = {a: 0.0 for a in legal}
        cnt = {a: 0 for a in legal}
        n = 0
        while n < Mmax and (time.perf_counter() - t0) * 1000.0 < deadline_ms:
            fut = _sample_future(sim, rng)
            for a in order:
                if (time.perf_counter() - t0) * 1000.0 >= deadline_ms:
                    break
                s = sim.clone()
                inject_future_safe(s, fut)
                apply_action(s, i, a)
                x2 = state_feat(s)
                v = float(V.predict(x2)[0]) * sd + mu
                acc[a] += v
                cnt[a] += 1
            n += 1
        scored = [a for a in legal if cnt[a] > 0]
        if not scored:
            return order[0]
        return min(scored, key=lambda a: acc[a] / cnt[a])
    return pol

# registry used by workers
_CACHE_POL = {}

def get_wxh_pol(name, ckpt, vpath, rpath, mu, sd):
    k = (name, ckpt, vpath, rpath)
    if k in _CACHE_POL:
        return _CACHE_POL[k]
    prior = L.load_net(ckpt) if ckpt and os.path.exists(ckpt) else None
    if name.startswith("N4d_"):
        # N4d_32_1ms
        parts = name.split("_")
        M = int(parts[1])
        dms = float(parts[2].replace("ms", ""))
        pol = make_rollout(M=M, base=make_N1(240.0), deadline_ms=dms)
    elif name.startswith("VG_"):
        dms = float(name.split("_")[1].replace("ms", ""))
        V = L.load_value(vpath)
        pol = make_vg(V, mu, sd, dms, prior=prior)
    elif name.startswith("RV_"):
        dms = float(name.split("_")[1].replace("ms", ""))
        V = L.load_value(rpath)
        # random net: use SAME mu/sd so scores are in J-ish units (shift doesn't change argmin
        # if mu/sd are affine; random outputs are N(0,1)-ish uncalibrated — still a fair ablation)
        pol = make_vg(V, mu, sd, dms, prior=prior)
    elif name.startswith("RL"):
        net = L.load_net(ckpt)
        pol = L.make_policy(net, greedy=True, rng=np.random.default_rng(0))
    elif name == "N1_240":
        pol = make_N1(240.0)
    else:
        pol = P.name_policy(name)
    _CACHE_POL[k] = pol
    return pol

def eval_job(j):
    try:
        rec = E.materialize(j["path"], j["sol"], j["day"], "storm", 0.08)
        ins = E._ins(j["path"])
        pol = get_wxh_pol(j["method"], j.get("ckpt"), j.get("vpath"), j.get("rpath"),
                          j.get("mu", 0.0), j.get("sd", 1.0))
        t0 = time.perf_counter()
        sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=100)
        m = sim.run(pol, record_time=True)
        m = dict(m)
        m.update(path=j["path"], day=j["day"], method=j["method"],
                 wall_sec=time.perf_counter() - t0,
                 inst=os.path.basename(j["path"]), storm=int(rec["wx"].storm))
        return m
    except Exception as e:
        return dict(path=j["path"], day=j["day"], method=j["method"], error=str(e),
                    traceback=traceback.format_exc())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=str, default="")
    ap.add_argument("--value", type=str, default=os.path.join(WX_ROOT, "models", "value_s0.npz"))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WX_WORKERS", "3")))
    ap.add_argument("--plans", type=str, default="dev_ours")
    ap.add_argument("--days", type=str, default="")
    ap.add_argument("--limit-plans", type=int, default=0)
    ap.add_argument("--methods", type=str, default="")

    args = ap.parse_args()
    if not args.ckpt:
        for s in (0, 1, 2):
            p = os.path.join(WX_ROOT, "models", f"rl_s{s}_best_pomo_v2.npz")
            if os.path.exists(p):
                args.ckpt = p; break
    meta = json.load(open(args.value + ".meta.json")) if os.path.exists(args.value + ".meta.json") else dict(mu=0, sd=1)
    mu, sd = float(meta.get("mu", 0)), float(meta.get("sd", 1))
    rpath = os.path.join(os.path.dirname(args.value), "value_random.npz")
    methods = ["N1_240", "N4d_32_1ms", "N4d_32_10ms", "N4d_32_100ms",
               "VG_1ms", "VG_10ms", "VG_100ms",
               "RV_1ms", "RV_10ms", "RV_100ms"]
    if args.ckpt:
        methods = ["RL"] + methods
    plans = I.load_plans(args.plans)
    days = list(C.DEV_DAYS)
    if args.days:
        days = [int(x) for x in args.days.split(",") if x.strip()]
    plans = plans[: int(args.limit_plans)] if args.limit_plans else plans
    if args.methods:
        methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    outp = os.path.join(RES, "wxh_dev.jsonl")
    done = set()
    if os.path.exists(outp):
        for l in open(outp):
            r = json.loads(l)
            if not r.get("error"):
                done.add((r["path"], r["day"], r["method"]))
    jobs = []
    for r in plans:
        for d in days:
            for m in methods:
                if (r["path"], d, m) not in done:
                    jobs.append(dict(path=r["path"], sol=r["solution"], day=d, method=m,
                                     ckpt=args.ckpt, vpath=args.value, rpath=rpath, mu=mu, sd=sd))
    log(f"WX-H todo {len(jobs)} done {len(done)} ckpt={args.ckpt} V={args.value} W={args.workers}")
    t0 = time.time()
    ok = fail = 0
    if jobs:
        with get_context("fork").Pool(args.workers, maxtasksperchild=10) as pool, open(outp, "a") as f:
            for r in pool.imap_unordered(eval_job, jobs, chunksize=1):
                if r.get("error"):
                    fail += 1
                    if fail <= 6:
                        log("FAIL", r.get("method"), r.get("error"), str(r.get("traceback", ""))[:400])
                    continue
                f.write(json.dumps(r, default=float) + "\n"); f.flush()
                ok += 1
                if ok % 20 == 0 or ok == len(jobs):
                    log(f"WXH {ok}/{len(jobs)} fail={fail} elapsed={time.time()-t0:.1f}s "
                        f"last {r['method']} J={r['J']:.1f} ms99={r.get('ms_p99',0):.2f}")
    rows = [json.loads(l) for l in open(outp) if l.strip() and not json.loads(l).get("error")]
    by = defaultdict(list)
    for r in rows:
        by[r["method"]].append(r)
    def mean(rs, k):
        return float(np.mean([r[k] for r in rs])) if rs and k in rs[0] else float("nan")
    lines = [f"{'method':16} {'n':>4} {'J':>9} {'ot':>7} {'fails':>6} {'ms99':>8} {'ms50':>8} {'sec':>7}"]
    for m in methods:
        if m not in by:
            continue
        v = by[m]
        lines.append(f"{m:16} {len(v):4d} {mean(v,'J'):9.2f} {mean(v,'ontime_h'):7.4f} "
                     f"{mean(v,'fails'):6.2f} {mean(v,'ms_p99'):8.2f} {mean(v,'ms_p50'):8.2f} {mean(v,'wall_sec'):7.2f}")
    table = "\n".join(lines)
    log("\n" + table)
    open(os.path.join(OUT, "WXH.md"), "w").write("# WX-H dev results\n\n```\n" + table + "\n```\n")
    # Pareto vs plain N4d at same deadline
    report = {}
    for dms in (1, 10, 100):
        a, b, c = f"N4d_32_{dms}ms", f"VG_{dms}ms", f"RV_{dms}ms"
        report[dms] = {}
        for name, key in (("plain", a), ("vg", b), ("randomV", c)):
            if key in by:
                report[dms][name] = dict(J=mean(by[key], "J"), ms99=mean(by[key], "ms_p99"),
                                         ot=mean(by[key], "ontime_h"), fails=mean(by[key], "fails"), n=len(by[key]))
        if "plain" in report[dms] and "vg" in report[dms]:
            dJ = (report[dms]["vg"]["J"] - report[dms]["plain"]["J"]) / max(abs(report[dms]["plain"]["J"]), 1e-9) * 100
            report[dms]["vg_vs_plain_dJ"] = dJ
        if "plain" in report[dms] and "randomV" in report[dms]:
            dJ = (report[dms]["randomV"]["J"] - report[dms]["plain"]["J"]) / max(abs(report[dms]["plain"]["J"]), 1e-9) * 100
            report[dms]["rv_vs_plain_dJ"] = dJ
    json.dump(report, open(os.path.join(OUT, "WXH_SUMMARY.json"), "w"), indent=2)
    log("WXH summary", json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        traceback.print_exc(); sys.exit(2)
