#!/usr/bin/env python3
"""Shared evaluation for Test-A, P3 (uniform faults), P4 (robustness).

Usage:
  run_eval_suite.py --suite testa --methods N1_240,A1,A2,RL
  run_eval_suite.py --suite p3 --methods N1_240,A1,RL --mode uniform
  run_eval_suite.py --suite p4 --sigma 1.5 --speed 0.30 --methods N1_240,A1,RL

Does not invent results; resumes from jsonl. Official Test-A requires G-b/G-c
unless --force. Test seeds 7000-7029, test_ours (Liu-50).
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

import os, sys, json, time, argparse, traceback
from collections import defaultdict
from multiprocessing import get_context
import numpy as np

sys.path.insert(0, WX_ROOT)
from wx2 import const as C, inst as I, evaljob as E, statsutil as ST

OUT = os.path.join(WX_ROOT, "wx_e", "results")
os.makedirs(OUT, exist_ok=True)

def log(*a):
    print(*a, flush=True)

def load_jsonl(p):
    if not os.path.exists(p):
        return []
    out = []
    for l in open(p):
        if l.strip():
            r = json.loads(l)
            if not r.get("error"):
                out.append(r)
    return out

def mean(rs, k):
    xs = [r[k] for r in rs if k in r and r[k] is not None]
    return float(np.mean(xs)) if xs else float("nan")


def _run_job(j):
    """Module-level so multiprocessing can pickle it (do not nest inside main)."""
    meth = j.pop("_meth_out", j["method"])
    official = j.pop("_official", False)
    try:
        r = E.eval_one(j)
    except Exception as e:
        return dict(error=str(e), traceback=traceback.format_exc(),
                    path=j.get("path"), day=j.get("day"), method=meth)
    if r is None:
        return dict(error="none", path=j.get("path"), day=j.get("day"), method=meth)
    r["method"] = meth
    r["sigma_scale"] = j.get("sigma_scale", 1.0)
    r["speed_bias"] = j.get("speed_bias", 0.0)
    r["official"] = official
    return r


def latest_rl_ckpts(tag=""):
    """Map seed -> best ckpt path if it exists."""
    found = {}
    for s in (0, 1, 2):
        p = os.path.join(WX_ROOT, "models", f"rl_s{s}_best{tag}.npz")
        if os.path.exists(p):
            found[s] = p
    return found

def gates_ok(tag=""):
    oks = []
    for s in (0, 1, 2):
        p = os.path.join(WX_ROOT, "wx_e", f"GB_s{s}{tag}.json")
        if os.path.exists(p):
            d = json.load(open(p))
            oks.append(bool(d.get("G_b")) and bool(d.get("G_c")))
    return dict(n=len(oks), n_pass=sum(oks), all_ok=(sum(oks) >= 2 and len(oks) >= 3), raw=oks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=["testa", "p3", "p4", "dev_rl"])
    ap.add_argument("--methods", type=str, default="N1_240,A1,A2")
    ap.add_argument("--mode", type=str, default="storm")
    ap.add_argument("--sigma", type=float, default=1.0)
    ap.add_argument("--speed", type=float, default=0.0, help="cell speed bias, 0.30 = +30%")
    ap.add_argument("--plans", type=str, default="")
    ap.add_argument("--days", type=str, default="")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WX_WORKERS", "3")))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--rl-tag", type=str, default="", help="ckpt tag, e.g. _uniform")
    ap.add_argument("--subset-slow", action="store_true", help="for N4 use TEST_SUBSET")
    ap.add_argument("--limit-plans", type=int, default=0, help="use first N plans (smoke)")

    args = ap.parse_args()

    if args.suite == "testa":
        plans_name = args.plans or "test_ours"
        days = list(C.TEST_DAYS) if not args.days else [int(x) for x in args.days.split(",")]
        tag_out = "testA"
        g = gates_ok(args.rl_tag)
        log("Test-A gate check", g)
        if not g["all_ok"] and not args.force:
            log("REFUSE official Test-A: need G-b and G-c on >=2 of 3 seeds (pass --force to run unofficial)")
            return 3
        official = g["all_ok"]
    elif args.suite == "p3":
        plans_name = args.plans or "test_ours"
        days = list(C.TEST_DAYS) if not args.days else [int(x) for x in args.days.split(",")]
        # if test not yet official, allow dev with --plans dev_ours --days 6000..
        args.mode = args.mode or "uniform"
        if args.mode == "storm" and "--mode" not in sys.argv:
            args.mode = "uniform"
        tag_out = f"p3_{args.mode}"
        official = True
    elif args.suite == "p4":
        plans_name = args.plans or "test_ours"
        days = list(C.TEST_DAYS) if not args.days else [int(x) for x in args.days.split(",")]
        tag_out = f"p4_s{args.sigma}_v{args.speed}"
        official = True
    else:
        plans_name = args.plans or "dev_ours"
        days = list(C.DEV_DAYS)
        tag_out = "dev_rl"
        official = False

    outp = os.path.join(OUT, f"{tag_out}.jsonl")
    plans = I.load_plans(plans_name)
    if getattr(args, "limit_plans", 0):
        plans = plans[: int(args.limit_plans)]
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    ckpts = latest_rl_ckpts(args.rl_tag)
    log(f"{args.suite} plans={plans_name} n={len(plans)} days={days[0]}..{days[-1]} "
        f"mode={args.mode} sigma={args.sigma} speed={args.speed} methods={methods} ckpts={ckpts}")

    done = set()
    if os.path.exists(outp):
        for r in load_jsonl(outp):
            done.add((r["path"], r["day"], r["method"], r.get("mode", "storm"),
                      round(r.get("sigma_scale", 1.0), 4), round(r.get("speed_bias", 0.0), 4)))

    jobs = []
    for r in plans:
        for d in days:
            for m in methods:
                if m == "RL" or m.startswith("RL_s"):
                    seeds = [int(m.split("s")[-1])] if m.startswith("RL_s") else list(ckpts)
                    for s in seeds:
                        if s not in ckpts:
                            log(f"skip RL seed {s}, no ckpt")
                            continue
                        meth = f"RL_s{s}{args.rl_tag}"
                        key = (r["path"], d, meth, args.mode, args.sigma, args.speed)
                        if key in done:
                            continue
                        jobs.append(dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                                         method="RL", P=100, margin=0.08, plan_method="ours",
                                         sigma_scale=args.sigma, speed_bias=args.speed,
                                         extra=dict(ckpt=ckpts[s], greedy=True, seed=s),
                                         _meth_out=meth))
                elif m.startswith("N4"):
                    ds = list(C.TEST_SUBSET) if (args.subset_slow or args.suite == "testa") else days
                    if d not in ds:
                        continue
                    key = (r["path"], d, m, args.mode, args.sigma, args.speed)
                    if key in done:
                        continue
                    jobs.append(dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                                     method=m, P=100, margin=0.08, plan_method="ours",
                                     sigma_scale=args.sigma, speed_bias=args.speed,
                                     _meth_out=m))
                else:
                    key = (r["path"], d, m, args.mode, args.sigma, args.speed)
                    if key in done:
                        continue
                    extra = None
                    if m == "N5":
                        tabp = os.path.join(WX_ROOT, "wx_e", "N5_TABLE.json")
                        if not os.path.exists(tabp):
                            log("N5 table missing, skip")
                            continue
                        raw = json.load(open(tabp))
                        table = {}
                        for k, v in raw.items():
                            a, b = k.split(",")
                            table[(int(a), int(b))] = v["policy"] if isinstance(v, dict) else v
                        extra = {"n5_table": table}
                    jobs.append(dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                                     method=m, P=100, margin=0.08, plan_method="ours",
                                     sigma_scale=args.sigma, speed_bias=args.speed,
                                     extra=extra, _meth_out=m))
    log(f"todo {len(jobs)} done {len(done)} W={args.workers}")
    t0 = time.time()
    ok = fail = 0

    for j in jobs:
        j["_official"] = official

    if jobs:
        with get_context("fork").Pool(args.workers, maxtasksperchild=15) as pool, open(outp, "a") as f:
            for r in pool.imap_unordered(_run_job, jobs, chunksize=1):
                if r.get("error"):
                    fail += 1
                    if fail <= 8:
                        log("FAIL", r.get("method"), r.get("error"), str(r.get("traceback", ""))[:400])
                    continue
                f.write(json.dumps(r, default=float) + "\n"); f.flush()
                ok += 1
                if ok % 50 == 0 or ok == len(jobs):
                    log(f"{tag_out} {ok}/{len(jobs)} fail={fail} elapsed={time.time()-t0:.1f}s last J={r['J']:.1f} {r['method']}")
    log(f"done ok={ok} fail={fail} in {time.time()-t0:.1f}s")

    rows = load_jsonl(outp)
    # filter this suite's knobs
    rows = [r for r in rows if r.get("mode", "storm") == args.mode
            and abs(r.get("sigma_scale", 1.0) - args.sigma) < 1e-9
            and abs(r.get("speed_bias", 0.0) - args.speed) < 1e-9]
    by = defaultdict(list)
    for r in rows:
        by[r["method"]].append(r)
    log(f"{'method':16} {'n':>5} {'J':>9} {'cost':>8} {'ot_h':>7} {'cvar':>7} {'fails':>6} {'mk':>7}")
    for m, v in sorted(by.items(), key=lambda kv: mean(kv[1], "J")):
        log(f"{m:16} {len(v):5d} {mean(v,'J'):9.2f} {mean(v,'cost'):8.2f} "
            f"{mean(v,'ontime_h'):7.4f} {mean(v,'cvar_h'):7.2f} {mean(v,'fails'):6.2f} {mean(v,'mk'):7.1f}")

    # stats vs N1_240 and A1 if present
    if "N1_240" in by:
        # unify RL seeds as RL_mean by averaging per (path,day) if multiple
        # for tests, compare each RL_s* and also a virtual mean if 3 seeds
        metrics = [("J", -1), ("ontime_h", +1), ("cvar_h", -1), ("cost", -1),
                   ("fails", -1), ("mk", -1)]
        methods_for = [m for m in by if m != "N1_240"]
        # family_tests needs all methods in one list; inst_means uses method field
        tests_n1 = ST.family_tests(rows, [m for m in by if m.startswith("RL") or m=="O"][0] if any(m.startswith("RL") or m=="O" for m in by) else methods_for[0],
                                   ["N1_240"] + (["A1"] if "A1" in by else []),
                                   metrics)
        # do per RL seed vs N1 and A1
        summary = []
        refs = ["N1_240"] + (["A1"] if "A1" in by else [])
        rl_meths = [m for m in by if m.startswith("RL")]
        for rm in rl_meths + [m for m in methods_for if not m.startswith("RL")]:
            for ref in refs:
                for metric, better in metrics:
                    t = ST.paired(rows, rm, ref, metric, better=better)
                    summary.append(t)
                    if t.get("n"):
                        log(f"  {rm} vs {ref} {metric}: mean {t['mean_a']:.4f} vs {t['mean_b']:.4f} "
                            f"rel={t['rel']:.2f}% win={t['win']}/{t['n']} p={t['p']:.4g}")
        # Holm within this family
        ps = [t.get("p", 1.0) for t in summary]
        if ps:
            adj = ST.holm(ps)
            for t, a in zip(summary, adj):
                t["p_holm"] = float(a)
        sump = os.path.join(OUT, f"{tag_out}_STATS.json")
        # jsonify
        def conv(t):
            o = dict(t)
            for k, v in list(o.items()):
                if isinstance(v, tuple):
                    o[k] = list(v)
            return o
        json.dump(dict(suite=args.suite, official=official, mode=args.mode,
                       sigma=args.sigma, speed=args.speed, plans=plans_name,
                       n_days=len(days), n_maps=len(plans),
                       means={m: {k: mean(v, k) for k in ("J","cost","ontime_h","cvar_h","fails","mk","resp_h")
                                  if k in (v[0] if v else {})}
                              for m, v in by.items()},
                       tests=[conv(t) for t in summary]),
                  open(sump, "w"), indent=2)
        log("wrote", sump)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        traceback.print_exc(); sys.exit(2)
