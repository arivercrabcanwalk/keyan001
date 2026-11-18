"""Dev-only freezes (PREREG_v6 sec. 4), written BEFORE any test evaluation.
  n6     : N6_best = argmin dev mean J5 over the 12-config N6 grid among arms with 100 % strict completion
  sb     : strongest fair baseline SB = argmin dev mean J5 over ALL non-RL arms that pass the strict gate
           (A1, A2, N1_240, N6 grid, shielded variants S:*, R_/Rfc_/Rfc600e15_ re-optimisation with N6_best)
  author : gate on the author-adapted arms (A1 / A2 on TSALNS-Cov plans): must be 100 % strict, else exit 3
Usage: python -m v6.freeze --rows results/dev_baselines.jsonl --what n6|sb|author --out results/N6_FREEZE.json"""
import json, sys, argparse
import numpy as np
from v6 import fairproto as FP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True); ap.add_argument("--what", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--plan-set", default="")
    ap.add_argument("--expected", type=int, default=0)
    a = ap.parse_args()
    rows = FP.load_rows(a.rows.split(","))
    t = FP.table(rows, plan_set=a.plan_set or None, scenario="base")
    allm = sorted(t)
    g = FP.gate(t, allm, a.expected or None)
    J = {m: float(np.mean([r["J"] for r in t[m].values()])) for m in allm}
    OT = {m: float(np.mean([r["ot_min"] for r in t[m].values()])) for m in allm}
    if a.what == "author":
        arms = [m for m in allm if m in ("A1", "A2")]
        ok = all(g[m]["passed"] for m in arms) and arms
        json.dump(dict(gate={m: g[m] for m in arms}, passed=bool(ok)), open(a.out, "w"), indent=1)
        print("[freeze] author-adaptation strict gate:", {m: g[m]["complete_strict"] for m in arms}, "PASS" if ok else "FAIL")
        return 0 if ok else 3
    if a.what == "n6":
        cand = [m for m in allm if m.startswith("N6_") and g[m]["passed"]] or [m for m in allm if m.startswith("N6_")]
        best = min(cand, key=lambda m: J[m])
        json.dump(dict(best=best, dev_J5={m: J[m] for m in allm if m.startswith("N6_")}, dev_ot=OT, gate=g,
                       rule="min dev mean J5 among 100%-strict N6 configs"), open(a.out, "w"), indent=1)
        print("[freeze] N6_best =", best, J[best]); return 0
    if a.what == "sb":
        nonrl = [m for m in allm if not m.startswith(("RL", "O"))]
        cand = [m for m in nonrl if g[m]["passed"]]
        if not cand:
            print("[freeze] no non-RL arm passes the strict gate"); return 3
        best = min(cand, key=lambda m: J[m])
        json.dump(dict(SB=best, dev_J5=J, dev_ot=OT, gate=g, candidates=cand,
                       rule="min dev mean J5 among ALL non-RL arms with 100% strict completion"), open(a.out, "w"), indent=1)
        print("[freeze] SB =", best, J[best], "ot", OT[best]); return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
