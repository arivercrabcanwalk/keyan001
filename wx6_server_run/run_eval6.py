#!/usr/bin/env python3
"""v6 resumable evaluator: one jsonl row per (plan_set, map, method, day, scenario); skips done rows.
  --methods "LABEL=spec,LABEL=spec"   spec = any v6/registry.py policy name; per-label extras via --extra JSON
Every row carries the compact fields of PREREG_v6 sec. 7 (map, day, method, seed, J5, cost, ot, late_h, late_n, fails,
complete_strict, n_dabs, fixed_cost, latency) plus diagnostics. Scenarios (PREREG_v6 sec. 6):
  base | stress (lam 3.5, p_f 0.5) | sigma15 (OU + forecast residual x1.5, both components) |
  ncbias6 (nowcast bias 0.6 + cell speed +30 %) | uniform (spatially uniform faults)
"""
import argparse, json, os, sys, time, traceback
from multiprocessing import Pool
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wx2 import evaljob as E, sim as S, const as C
from v6 import registry as RG
from v6.common import parse_days, load_plans, fixed_cost

SCEN = {"base": dict(mode="storm"), "stress": dict(mode="storm", lam=3.5, p_f=0.5),
        "sigma15": dict(mode="storm", sigma_scale=1.5), "ncbias6": dict(mode="storm", nc_bias=0.6, speed_bias=0.3),
        "uniform": dict(mode="uniform")}
KEEP = ("J", "cost", "fixed", "busy", "ot_min", "late_min_h", "late_min_n", "fails", "complete", "complete_strict",
        "n_unservable", "n_unservable_all", "unserved", "unfinished", "n", "nh", "ontime_h", "ontime", "cvar_h", "mk",
        "mk_last", "n_backup", "n_forced", "n_urg_forced", "n_handover", "n_rebalance", "holds", "ndec", "n_launch",
        "n_hold", "n_serve", "ms_p50", "ms_p99", "ms_mean", "storm", "ncell", "n_storm_req", "n_bg", "n_dabs", "n_sabs", "J_v4")


def _job(j):
    t = time.time()
    base = dict(method=j["label"], spec=j["spec"], map=os.path.basename(j["path"])[:-4], day=j["day"],
                scenario=j["scenario"], plan_set=j["plan_set"], seed=j.get("seed", -1), win=C.T_OT)
    try:
        sc = SCEN[j["scenario"]]
        rec = E.materialize(j["path"], j["sol"], j["day"], sc.get("mode", "storm"), 0.08, sc.get("sigma_scale", 1.0),
                            sc.get("speed_bias", 0.0), sc.get("nc_bias", 0.0), sc.get("lam"), sc.get("p_f"))
        ins = E._ins(j["path"])
        pol = RG.get_policy(j["spec"], j.get("extra"))
        sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"])
        m = sim.run(pol, record_time=True)
        r = {k: m[k] for k in KEEP if k in m}
        r.update(base, n_shield=int(getattr(sim, "n_shield", 0)), fixed_cost_plan=j["fixed_cost"],
                 day_hash=rec["meta"]["day_hash"], wall_sec=time.time() - t)
        return r
    except Exception as e:
        base.update(error=repr(e), tb=traceback.format_exc()[-800:])
        return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--plans", required=True)
    ap.add_argument("--methods", required=True); ap.add_argument("--days", required=True)
    ap.add_argument("--scenario", default="base"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--extra", default="{}"); ap.add_argument("--limit-plans", type=int, default=0)
    a = ap.parse_args()
    plans = load_plans(os.path.join(ROOT, a.plans) if not os.path.isabs(a.plans) else a.plans)
    if a.limit_plans:
        k = max(1, len(plans) // a.limit_plans); plans = plans[::k][:a.limit_plans]
    pset = os.path.basename(a.plans).replace(".jsonl", "")
    days = parse_days(a.days); extra_all = json.loads(a.extra)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                r = json.loads(l)
                if "error" not in r:
                    done.add((r["plan_set"], r["method"], r["map"], r["day"], r["scenario"]))
            except Exception:
                pass
    jobs = []
    for item in a.methods.split(","):
        if not item:
            continue
        lab, spec = item.split("=", 1) if "=" in item else (item, item)
        ex = dict(extra_all.get(lab, {}))
        seed = int(lab.rsplit("_s", 1)[1]) if "_s" in lab and lab.rsplit("_s", 1)[1].isdigit() else -1
        for pl in plans:
            mp = os.path.basename(pl["path"])[:-4]
            for d in days:
                if (pset, lab, mp, d, a.scenario) in done:
                    continue
                jobs.append(dict(label=lab, spec=spec, extra=ex, path=pl["path"], sol=pl["solution"], day=d, seed=seed,
                                 scenario=a.scenario, plan_set=pset, fixed_cost=fixed_cost(pl["solution"]["station_types"])))
    heavy = ("Rfc", "R_", "N4", "RL6R", "S:Rfc", "S:R_", "O")
    jobs.sort(key=lambda j: (0 if j["spec"].startswith(heavy) else 1, -os.path.getsize(os.path.join(ROOT, j["path"]))))
    print(f"[run_eval6] {a.out}: todo {len(jobs)} done {len(done)} W={a.workers}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time(); n = 0; nerr = 0
    with Pool(a.workers, maxtasksperchild=100) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(_job, jobs, chunksize=1):
            f.write(json.dumps(r) + "\n"); f.flush()
            n += 1; nerr += "error" in r
            if "error" in r and nerr <= 3:
                print("[run_eval6] ERROR", r["method"], r["map"], r["day"], r["error"], r.get("tb", "")[-300:], flush=True)
            if n % 200 == 0 or n == len(jobs):
                print(f"[run_eval6] {n}/{len(jobs)} err={nerr} {time.time()-t0:.0f}s", flush=True)
    return 0 if nerr == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
