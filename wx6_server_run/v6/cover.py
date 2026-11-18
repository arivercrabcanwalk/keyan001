"""Coverage of the v6 emergency-demand support Omega (wx2/omega.py) by a plan's opened stations.

  check   : number of Omega points not covered (must be 0 for every plan that enters the dynamic evaluation)
  repair  : EXACT minimum-added-fixed-cost repair (MILP, scipy/HiGHS): stations already opened keep at least their
            type; closed stations may be opened as SABS/DABS and SABS may be upgraded to DABS; new/upgraded stations
            get no planned trips (pure emergency responders). Used (a) as the post-hoc author adaptation "TSR"
            (TSALNS unchanged + repair) and (b) as a safety net after TSALNS-Cov (counted and reported).
  pad     : PAD baseline (every candidate station opened as DABS, routes unchanged) - mandatory reviewer control.
CLI: python -m v6.cover --mode repair|pad|check --inp plans.jsonl --out plans_out.jsonl --tag TSR
"""
import os, sys, json, argparse
import numpy as np
from .common import ROOT, read_instance, fixed_cost, SABS_FIX, DABS_FIX
from wx2 import omega as OM


def cover_matrix(ins):
    pts = OM.omega(ins)["points"]; p = ins.params
    S = np.array([[s.x, s.y] for s in ins.stations])
    D = np.sqrt(((pts[:, None, :] - S[None]) ** 2).sum(-1))
    return (D <= p.small_radius + 1e-6), (D <= p.large_radius + 1e-6)


def n_uncovered(ins, types):
    return int(len(OM.uncovered(ins, types)))


def min_cost_types(ins, lower):
    """Exact MILP: minimise total fixed cost of station types t_s in {0,1,2}, t_s >= lower_s, covering all Omega."""
    from scipy.optimize import milp, LinearConstraint, Bounds
    A1, A2 = cover_matrix(ins); ns = A1.shape[1]
    # x = [y1_0..y1_{ns-1}, y2_0..y2_{ns-1}]
    c = np.concatenate([np.full(ns, SABS_FIX), np.full(ns, DABS_FIX)])
    rows = [np.concatenate([A1[k].astype(float), A2[k].astype(float)]) for k in range(A1.shape[0])]
    cons = [LinearConstraint(np.array(rows), lb=1.0, ub=np.inf)]
    one = np.concatenate([np.eye(ns), np.eye(ns)], axis=1)
    cons.append(LinearConstraint(one, lb=np.array([1.0 if l > 0 else 0.0 for l in lower]), ub=1.0))
    lb = np.zeros(2 * ns); ub = np.ones(2 * ns)
    for s, l in enumerate(lower):
        if l == 2:
            lb[ns + s] = 1.0; ub[s] = 0.0
    res = milp(c, constraints=cons, integrality=np.ones(2 * ns), bounds=Bounds(lb, ub))
    if not res.success:
        raise RuntimeError(f"cover MILP failed: {res.message}")
    x = np.round(res.x).astype(int)
    return [2 if x[ns + s] else (1 if x[s] else 0) for s in range(ns)]


def repair(ins, sol):
    t0 = list(sol["station_types"])
    if n_uncovered(ins, t0) == 0:
        return sol, dict(repaired=0, added_fixed=0.0, changed=[])
    t1 = min_cost_types(ins, t0)
    new = json.loads(json.dumps(sol)); new["station_types"] = t1
    for s, (a, b) in enumerate(zip(t0, t1)):
        if a == 0 and b > 0:
            new["routes"][s] = [[], []]
    assert n_uncovered(ins, t1) == 0
    return new, dict(repaired=1, added_fixed=fixed_cost(t1) - fixed_cost(t0),
                     changed=[(s, a, b) for s, (a, b) in enumerate(zip(t0, t1)) if a != b])


def pad(ins, sol):
    new = json.loads(json.dumps(sol)); n = len(new["station_types"])
    new["station_types"] = [2] * n
    new["routes"] = [rt if rt else [[], []] for rt in new["routes"]]
    return new, dict(added_fixed=fixed_cost([2] * n) - fixed_cost(sol["station_types"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["repair", "pad", "check"])
    ap.add_argument("--inp", required=True); ap.add_argument("--out", default="")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.inp) if l.strip()]
    out = []; nrep = 0; nbad = 0
    for r in rows:
        ins = read_instance(os.path.join(ROOT, r["path"]))
        if a.mode == "check":
            u = n_uncovered(ins, r["solution"]["station_types"]); nbad += u > 0
            print(f"{r['path']} uncovered={u}"); continue
        f = repair if a.mode == "repair" else pad
        sol, info = f(ins, r["solution"])
        r2 = dict(r); r2["solution"] = sol; r2["cover_info"] = info
        r2["method"] = (a.tag or r.get("method", "") + "_" + a.mode)
        r2["n_dabs"] = sum(1 for t in sol["station_types"] if t == 2)
        r2["n_open"] = sum(1 for t in sol["station_types"] if t > 0)
        r2["fixed_cost"] = fixed_cost(sol["station_types"])
        assert n_uncovered(ins, sol["station_types"]) == 0
        nrep += int(info.get("repaired", 1)); out.append(r2)
    if a.mode == "check":
        print(f"[cover] {nbad}/{len(rows)} plans leave Omega points uncovered"); return 1 if nbad else 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"[cover] {a.mode}: {len(out)} plans written to {a.out}; repaired {nrep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
