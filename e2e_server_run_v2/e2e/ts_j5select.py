"""REVIEW FIX (R-info): information-matched non-RL baseline. Our j5 planning mode re-ranks candidate sitings by
simulated J5 on TRAINING weather days (5e6+k). The fair analogue for TSALNS: per instance, choose among the TSALNS
plans with battery reserve 0/10/20 % the one with the lowest simulated J5 on the SAME training days with the
baseline execution rule. Output = plan jsonl usable by dyn_eval (arm names TSj5_*)."""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, read_instance


def _job(j):
    from e2e import dyn_eval as D
    ins = read_instance(os.path.join(ROOT, j["path"]))
    return j["k"], j["path"], float(np.mean([D.run_day(ins, j["sol"], 5_000_000 + d, j["exec"])["J"] for d in range(j["K"])]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", required=True, help="comma list of TSALNS plan files (same instance set)")
    ap.add_argument("--exec", default="N6_90_0.25"); ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    files = a.plans.split(","); P = [{json.loads(l)["path"]: json.loads(l) for l in open(f)} for f in files]
    paths = sorted(set.intersection(*[set(p) for p in P]))
    jobs = [dict(k=k, path=p, sol=P[k][p]["solution"], exec=a.exec, K=a.K) for p in paths for k in range(len(P))]
    from multiprocessing import get_context
    with get_context("spawn").Pool(a.workers) as pool:
        res = pool.map(_job, jobs, chunksize=1)
    best = {}
    for k, p, J in res:
        if p not in best or J < best[p][1]:
            best[p] = (k, J)
    with open(a.out, "w") as f:
        for p in paths:
            k, J = best[p]; row = dict(P[k][p]); row.update(method="tsalns_j5sel", j5sel_from=os.path.basename(files[k]), j5sel_J=J)
            f.write(json.dumps(row) + "\n")
    print("[ts_j5select] picks:", {os.path.basename(files[k]): sum(1 for v in best.values() if v[0] == k) for k in range(len(files))})


if __name__ == "__main__":
    main()
