"""Preregistered dev selection of the RL6 checkpoint per (variant, seed) (PREREG_v6 sec. 5.4).
Candidates: distilled net (pre-ES), es_best (val), es_final. Each is evaluated on the dev set (dev maps x dev days,
TSALNS-Cov plans). Rule: among candidates with 100 % strict completion AND dev OT <= dev OT of the frozen SB, pick the
minimum dev mean J5; if none satisfies the OT condition, pick min (J5 + 5 * OT excess) and flag it.
The chosen file is copied to models6/final_<name>.npz; the decision is written to models6/select_<name>.json."""
import os, sys, json, argparse, shutil, subprocess
import numpy as np
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from v6 import fairproto as FP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--cands", required=True, help="comma list of npz")
    ap.add_argument("--plans", required=True); ap.add_argument("--days", required=True)
    ap.add_argument("--sb-freeze", required=True); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--models", default=os.path.join(ROOT, "models6")); ap.add_argument("--noshield", type=int, default=0)
    ap.add_argument("--limit-plans", type=int, default=0)
    a = ap.parse_args()
    sb = json.load(open(a.sb_freeze)); sb_ot = float(sb["dev_ot"][sb["SB"]])
    cands = [c for c in a.cands.split(",") if os.path.exists(c)]
    out = os.path.join(a.models, f"dev_select_{a.name}.jsonl")
    labs = []; extra = {}
    for k, c in enumerate(cands):
        lab = f"C{k}"; labs.append(f"{lab}=RL6"); extra[lab] = dict(ckpt=c, noshield=bool(a.noshield))
    cmd = [sys.executable, os.path.join(ROOT, "run_eval6.py"), "--out", out, "--plans", a.plans, "--methods", ",".join(labs),
           "--days", a.days, "--workers", str(a.workers), "--extra", json.dumps(extra)]
    if a.limit_plans:
        cmd += ["--limit-plans", str(a.limit_plans)]
    rc = subprocess.call(cmd)
    t = FP.table(FP.load_rows([out]), scenario="base")
    res = []
    for k, c in enumerate(cands):
        v = list(t.get(f"C{k}", {}).values())
        if not v:
            continue
        J = float(np.mean([r["J"] for r in v])); ot = float(np.mean([r["ot_min"] for r in v]))
        comp = float(np.mean([r["complete_strict"] for r in v]))
        res.append(dict(ckpt=c, J=J, ot=ot, complete_strict=comp, n=len(v), ot_ok=ot <= sb_ot + 1e-9))
    ok = [r for r in res if r["complete_strict"] >= 1 - 1e-12 and r["ot_ok"]]
    flag = ""
    if ok:
        best = min(ok, key=lambda r: r["J"])
    else:
        pool = [r for r in res if r["complete_strict"] >= 1 - 1e-12] or res
        best = min(pool, key=lambda r: r["J"] + 5.0 * max(0.0, r["ot"] - sb_ot)); flag = "OT_CONDITION_NOT_MET"
    shutil.copyfile(best["ckpt"], os.path.join(a.models, f"final_{a.name}.npz"))
    json.dump(dict(name=a.name, chosen=best, candidates=res, sb=sb["SB"], sb_dev_ot=sb_ot, flag=flag, rc=rc),
              open(os.path.join(a.models, f"select_{a.name}.json"), "w"), indent=1)
    print(f"[select6] {a.name}: chose {os.path.basename(best['ckpt'])} dev J5={best['J']:.1f} ot={best['ot']:.1f} (SB ot {sb_ot:.1f}) {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
