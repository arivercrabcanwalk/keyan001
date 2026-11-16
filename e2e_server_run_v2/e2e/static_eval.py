"""Static comparison (author's objective = plan cost) of plan files vs the author's TSALNS (compute-matched).
Usage: python e2e/static_eval.py --ref data/plans/test_ts10.jsonl --arms OURS_full=runs/plans/test_full.jsonl,... --out results/static_test.md"""
import os, sys, json, argparse, numpy as np
from scipy.stats import wilcoxon
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(p):
    """REVIEW FIX (R-static-surv): infeasible rows are kept and flagged (previously silently dropped)."""
    out = {}
    for l in open(p):
        r = json.loads(l)
        out[os.path.basename(r["path"]).replace(".txt", "")] = (r.get("cost", r.get("plan_obj")), r.get("wall", r.get("sec")),
                                                                 r.get("feasible", True) is not False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True); ap.add_argument("--arms", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--gate", type=float, default=1.0); ap.add_argument("--gate_arm", default="")
    ap.add_argument("--inst", default="", help="glob of the instance set; missing plans count as failures")
    a = ap.parse_args()
    ref = load(a.ref)
    import glob as _g
    ROOT = os.environ.get("E2E_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    expected = sorted(os.path.basename(x).replace(".txt", "") for x in _g.glob(os.path.join(ROOT, a.inst))) if a.inst else sorted(ref)
    bad_ref = [k for k in expected if k not in ref or not ref[k][2]]
    L = [f"# Static plan cost vs TSALNS ({os.path.basename(a.ref)})\n", "| arm | n | mean gap | median | max | wins | Wilcoxon p | mean wall s |", "|---|---|---|---|---|---|---|---|"]
    res = {}
    for spec in a.arms.split(","):
        name, p = spec.split("=", 1)
        if not os.path.exists(p):
            L.append(f"| {name} | missing | | | | | | |"); continue
        arm = load(p)
        miss = [k for k in expected if k not in arm or not arm[k][2]]
        keys = sorted(k for k in expected if k in arm and arm[k][2] and k in ref and ref[k][2])
        if not keys:
            continue
        g = np.array([arm[k][0] / ref[k][0] - 1 for k in keys]) * 100
        try:
            pv = wilcoxon([arm[k][0] for k in keys], [ref[k][0] for k in keys]).pvalue
        except Exception:
            pv = float("nan")
        w = np.mean([arm[k][1] or 0 for k in keys])
        wmax = max(arm[k][1] or 0 for k in keys)
        res[name] = dict(n=len(keys), n_expected=len(expected), missing_or_infeasible=miss, mean=float(g.mean()), median=float(np.median(g)),
                         wins=int((g < 0).sum()), p=float(pv), wall_mean=float(w), wall_max=float(wmax))
        L.append(f"| {name} | {len(keys)}/{len(expected)} (fail {len(miss)}) | {g.mean():+.2f}% | {np.median(g):+.2f}% | {g.max():+.2f}% | {(g<0).sum()}/{len(keys)} | {pv:.2e} | {w:.2f} (max {wmax:.1f}) |")
    if bad_ref:
        L.append(f"\nWARNING: reference missing/infeasible on {len(bad_ref)} instances: {bad_ref[:10]}")
    if a.gate_arm and a.gate_arm in res:
        # G1 requires a feasible plan on EVERY expected instance (no survivorship)
        ok = res[a.gate_arm]["mean"] <= a.gate and not res[a.gate_arm]["missing_or_infeasible"]
        L.append(f"\n**G1 static gate** ({a.gate_arm} mean gap <= +{a.gate}%): {'PASS' if ok else 'FAIL'} ({res[a.gate_arm]['mean']:+.2f}%)")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write("\n".join(L) + "\n"); json.dump(res, open(a.out.replace(".md", ".json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
