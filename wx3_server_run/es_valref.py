"""Reference policies on the ES validation pool (training distribution; NOT dev/test)."""
import os, sys, json
import numpy as np
from multiprocessing import Pool
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from wx2 import evaljob as E, const as C, inst as I
from run_es import VAL_DAY0
def main():
    meths = sys.argv[1].split(","); n = int(sys.argv[2]); W = int(sys.argv[3]); out = sys.argv[4]
    train = I.load_plans("train_ours"); rv = np.random.default_rng(777)
    val = [(train[int(rv.integers(len(train)))], VAL_DAY0 + j) for j in range(n)]
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", method=m, P=C.P_MAIN, record_time=False)
            for m in meths for r, d in val]
    with Pool(W) as p:
        rows = p.map(E.eval_one, jobs, chunksize=1)
    res = {}
    for m in meths:
        rr = [r for r in rows if r["method"] == m]
        res[m] = {k: float(np.mean([r[k] for r in rr])) for k in ("J", "cost", "mk", "ontime_h", "fails", "cvar_h", "late_min_h")}
        print(m, {k: round(v, 3) for k, v in res[m].items()})
    json.dump(res, open(out, "w"), indent=1)
if __name__ == "__main__":
    main()
