"""G0 (v3, pre-registered, run BEFORE any dynamic evaluation): for every plan set and every (map, day, scenario)
count emergency requests that are reachable from SOME candidate DABS but not from the stations the plan opens
(plan-only, policy-independent). Any such request makes complete_strict impossible, so a plan set passes G0 only
with ZERO gaps on all test days. Also checks the CFL support-set property and evaluator feasibility.
Writes results/G0_coverage.json + .md; exit 1 if any plan set fails (the arm is then excluded and reported)."""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, read_instance, evaluate
os.environ.setdefault("WX_ROOT", ROOT)
from wx2 import sim as S                       # noqa: E402
from e2e import coverage as CV                 # noqa: E402
from e2e.dyn_eval import SCEN, parse_days      # noqa: E402

_DAY = {}


def reqs_of(ins, day, sc):
    k = (ins.name, day, sc)
    if k not in _DAY:
        wx, reqs, meta = S.make_day(ins, day, **SCEN[sc]); _DAY[k] = reqs
    return _DAY[k]


def check(job):
    path, types, days, sc = job
    ins = read_instance(os.path.join(ROOT, path))
    P, cS, cD = CV.for_instance(ins, ROOT)
    gaps = [CV.request_gap(ins, types, S.make_day(ins, d, **SCEN[sc])[1]) for d in days]
    return dict(path=path, cfl=CV.feasible(types, cS, cD), gap_days=int(sum(g > 0 for g in gaps)), gap_reqs=int(sum(gaps)), n_days=len(days))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", required=True, help="name=plans.jsonl,... ")
    ap.add_argument("--days", required=True, help="scenario:days;scenario:days e.g. base:21700-21799;stress:22700-22749")
    ap.add_argument("--out", default="results/G0_coverage")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--allow_fail", default="", help="comma list of set names that are EXPECTED to fail (e.g. TS orig)")
    a = ap.parse_args()
    from multiprocessing import get_context
    res = {}; fail = []
    allow = set(x for x in a.allow_fail.split(",") if x)
    with get_context("spawn").Pool(a.workers) as pool:
        for spec in a.sets.split(","):
            name, f = spec.split("=", 1)
            f = f if os.path.isabs(f) else os.path.join(ROOT, f)
            if not os.path.exists(f):
                res[name] = dict(missing=True); continue
            rows = [json.loads(l) for l in open(f)]
            out = dict(n_plans=len(rows))
            for sd in a.days.split(";"):
                sc, ds = sd.split(":"); days = parse_days(ds)
                rr = pool.map(check, [(r["path"], r["solution"]["station_types"], days, sc) for r in rows])
                out[sc] = dict(days=sum(x["n_days"] for x in rr), gap_days=sum(x["gap_days"] for x in rr), gap_reqs=sum(x["gap_reqs"] for x in rr),
                               cfl_infeasible_maps=[x["path"] for x in rr if not x["cfl"]],
                               max_strict_bound=1 - sum(x["gap_days"] for x in rr) / max(1, sum(x["n_days"] for x in rr)))
            nd = [sum(1 for t in r["solution"]["station_types"] if t == 2) for r in rows]
            out["mean_n_dabs"] = float(np.mean(nd)); out["mean_fixed_cost"] = float(np.mean([CV.fixed_cost(r["solution"]["station_types"]) for r in rows]))
            out["evaluator_infeasible"] = int(sum(1 for r in rows if not evaluate(read_instance(os.path.join(ROOT, r["path"])), r["solution"])["feasible"]))
            ok = all(v.get("gap_days", 0) == 0 for k, v in out.items() if isinstance(v, dict)) and out["evaluator_infeasible"] == 0
            out["G0_pass"] = bool(ok)
            res[name] = out
            if not ok and name not in allow:
                fail.append(name)
            print(f"[G0] {name}: {json.dumps(out)[:400]}", flush=True)
    os.makedirs(os.path.dirname(os.path.join(ROOT, a.out)) or ".", exist_ok=True)
    json.dump(dict(sets=res, failed=fail, rho=CV.RHO, step=CV.STEP), open(os.path.join(ROOT, a.out + ".json"), "w"), indent=1)
    with open(os.path.join(ROOT, a.out + ".md"), "w") as f:
        f.write(f"# G0 coverage-feasibility check (rho={CV.RHO:.0f} m, step={CV.STEP:.0f} m)\n\n| plan set | G0 | mean #DABS | mean fixed cost | scenario: max strict-completion bound (gap days / days) |\n|---|---|---|---|---|\n")
        for k, v in res.items():
            if v.get("missing"):
                f.write(f"| {k} | missing | | | |\n"); continue
            sc = "; ".join(f"{s}: {x['max_strict_bound']:.4f} ({x['gap_days']}/{x['days']})" for s, x in v.items() if isinstance(x, dict))
            f.write(f"| {k} | {'PASS' if v['G0_pass'] else 'FAIL'} | {v['mean_n_dabs']:.2f} | {v['mean_fixed_cost']:.1f} | {sc} |\n")
    print("[G0] failed (not allowed):", fail, flush=True)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
