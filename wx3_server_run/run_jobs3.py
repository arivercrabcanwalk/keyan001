#!/usr/bin/env python3
"""WX3 resumable evaluator: one jsonl row per (method, plan, day, scenario); skips done rows.
Usage: run_jobs3.py --out F --methods A,B --plans dev_ours --days 6000-6009 [--limit-plans N]
       [--scenario base|sigma15|ncbias|stress|uniform] [--workers W] [--extra JSON]
"""
import argparse, json, os, sys, time, traceback
from multiprocessing import Pool
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wx2 import evaljob as E

SCEN = {
    "base": dict(mode="storm"),
    "uniform": dict(mode="uniform"),
    "sigma15": dict(mode="storm", sigma_scale=1.5),
    "ncbias": dict(mode="storm", nc_bias=0.3),
    "stress": dict(mode="storm", lam=3.5, p_f=0.5),
}


def parse_days(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def _job(j):
    t = time.time()
    try:
        r = E.eval_one(j)
        r.update(method=j["method"], inst=os.path.basename(j["path"]), day=j["day"],
                 scenario=j["scenario"], plans=j["plans"], wall_sec=time.time() - t)
        for k in list(r):
            if isinstance(r[k], (list, dict)) and k not in ("extra",):
                r.pop(k)
        return r
    except Exception as e:
        return dict(method=j["method"], inst=os.path.basename(j["path"]), day=j["day"],
                    scenario=j["scenario"], plans=j["plans"], error=repr(e), tb=traceback.format_exc()[-800:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--methods", required=True)
    ap.add_argument("--plans", default="dev_ours")
    ap.add_argument("--days", default="6000-6009")
    ap.add_argument("--limit-plans", type=int, default=0)
    ap.add_argument("--scenario", default="base")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--extra", default="{}")
    ap.add_argument("--P", type=float, default=100.0)
    a = ap.parse_args()
    plans = [json.loads(l) for l in open(os.path.join(ROOT, "data", "plans", a.plans + ".jsonl"))]
    if a.limit_plans:
        # stratified: keep order (families interleaved by file order) -> take every k-th
        k = max(1, len(plans) // a.limit_plans)
        plans = plans[::k][:a.limit_plans]
    days = parse_days(a.days)
    extra_all = json.loads(a.extra)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                r = json.loads(l)
                if "error" not in r:
                    done.add((r["method"], r["inst"], r["day"], r["scenario"]))
            except Exception:
                pass
    sc = SCEN[a.scenario]
    jobs = []
    for m in a.methods.split(","):
        extra = dict(extra_all.get(m, extra_all.get("*", {})))
        for pl in plans:
            for d in days:
                key = (m, os.path.basename(pl["path"]), d, a.scenario)
                if key in done:
                    continue
                j = dict(path=pl["path"], sol=pl["solution"], day=d, method=m, P=a.P,
                         extra=extra, scenario=a.scenario, plans=a.plans, **sc)
                jobs.append(j)
    # expensive methods first for better packing
    jobs.sort(key=lambda j: (0 if j["method"].startswith(("N4", "VG", "RV")) else 1, -os.path.getsize(os.path.join(ROOT, j["path"]))))
    print(f"[run_jobs3] {a.out}: todo {len(jobs)} done {len(done)} W={a.workers}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time(); n = 0; nerr = 0
    with Pool(a.workers, maxtasksperchild=50) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(_job, jobs, chunksize=1):
            f.write(json.dumps(r) + "\n"); f.flush()
            n += 1; nerr += "error" in r
            if n % 20 == 0 or n == len(jobs):
                print(f"[run_jobs3] {n}/{len(jobs)} err={nerr} {time.time()-t0:.0f}s", flush=True)
    return 0 if nerr == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
