#!/usr/bin/env python3
"""P3 mechanism check, matching the pre-registered criteria.

P3 (PREREG):
  1) >=70% of the total J gain vs the strongest NoRL (N1_240) comes from storm days.
  2) After a uniform-spatial-fault retrain / eval, the advantage shrinks to half or less.

Share of total gain is computed as:
    delta_i = J_N1(i) - J_RL(i)          # positive = improvement
    storm_share = sum(delta on storm days) / sum(delta on all paired days)

This is the same quantity reported as "风暴日增益占 36.1%" for the oracle on dev.
"""
from __future__ import annotations
import os, sys, json, argparse
from collections import defaultdict
import numpy as np

ROOT = os.path.abspath(os.environ.get("WX_ROOT") or os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_jsonl(p):
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("error"):
            continue
        out.append(r)
    return out


def key(r):
    return (r.get("path"), int(r["day"]))


def is_storm(r):
    v = r.get("storm")
    if v is None:
        v = r.get("n_storm", 0)
        try:
            return int(v) > 0 and (r.get("mode", "storm") == "storm")
        except Exception:
            return False
    try:
        return int(v) != 0
    except Exception:
        return bool(v)


def index_by(rows, method=None):
    d = {}
    for r in rows:
        if method is not None and r.get("method") != method:
            continue
        d[key(r)] = r
    return d


def paired_share(rl_rows, n1_rows, rl_method=None):
    """Return storm-share of total J gain and related stats."""
    if rl_method:
        rl_rows = [r for r in rl_rows if r.get("method") == rl_method]
    n1 = index_by(n1_rows, "N1_240") if n1_rows and "method" in n1_rows[0] else index_by(n1_rows)
    # if n1 has method field use it; else assume they are all N1
    if n1_rows and any(r.get("method") == "N1_240" for r in n1_rows):
        n1 = index_by(n1_rows, "N1_240")
    storm_d, calm_d, all_d = [], [], []
    n_storm = n_calm = 0
    for r in rl_rows:
        k = key(r)
        if k not in n1:
            continue
        dlt = float(n1[k]["J"]) - float(r["J"])
        all_d.append(dlt)
        if is_storm(r) or is_storm(n1[k]):
            storm_d.append(dlt)
            n_storm += 1
        else:
            calm_d.append(dlt)
            n_calm += 1
    if not all_d:
        return dict(n=0, error="no paired rows")
    total = float(np.sum(all_d))
    ssum = float(np.sum(storm_d)) if storm_d else 0.0
    csum = float(np.sum(calm_d)) if calm_d else 0.0
    share = (ssum / total) if abs(total) > 1e-12 else float("nan")
    def md(xs):
        return float(np.mean(xs)) if xs else float("nan")
    return dict(
        n=len(all_d), n_storm=n_storm, n_calm=n_calm,
        mean_delta=md(all_d), mean_delta_storm=md(storm_d), mean_delta_calm=md(calm_d),
        sum_delta=total, sum_delta_storm=ssum, sum_delta_calm=csum,
        storm_share=share,
        J_rl=float(np.mean([r["J"] for r in rl_rows if key(r) in n1])),
        J_n1=float(np.mean([n1[key(r)]["J"] for r in rl_rows if key(r) in n1])),
        pass_70=bool(share >= 0.70) if share == share else False,
    )


def advantage(rl_rows, n1_rows, rl_method=None):
    if rl_method:
        rl_rows = [r for r in rl_rows if r.get("method") == rl_method]
    if n1_rows and any(r.get("method") == "N1_240" for r in n1_rows):
        n1 = index_by(n1_rows, "N1_240")
    else:
        n1 = index_by(n1_rows)
    js, jn = [], []
    for r in rl_rows:
        k = key(r)
        if k not in n1:
            continue
        js.append(float(r["J"]))
        jn.append(float(n1[k]["J"]))
    if not js:
        return dict(n=0)
    Jr, Jn = float(np.mean(js)), float(np.mean(jn))
    return dict(n=len(js), J_rl=Jr, J_n1=Jn,
                dJ_pct=(Jr - Jn) / (abs(Jn) + 1e-12) * 100.0,
                mean_delta=Jn - Jr)


def pick_rl_method(rows, prefer_substrings):
    meths = sorted({r.get("method") for r in rows if str(r.get("method", "")).startswith("RL")})
    for s in prefer_substrings:
        for m in meths:
            if s in m:
                return m
    return meths[0] if meths else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storm-rl", default="", help="jsonl of storm-trained RL + N1 on storm days (dev or test)")
    ap.add_argument("--uniform-eval", default="", help="jsonl of storm-trained RL + N1 on uniform faults")
    ap.add_argument("--uniform-retrain", default="", help="jsonl of uniform-retrained RL + N1 on uniform faults")
    ap.add_argument("--out", default=os.path.join(ROOT, "results_final", "P3_ANALYSIS.json"))
    args = ap.parse_args()

    report = dict(criterion_share=0.70, criterion_shrink=0.50, synthetic=True)
    md = ["# P3 分析（合成天气，预注册标准）\n",
          "增益份额 = 风暴日 Σ(J_N1 − J_RL) / 全部配对日 Σ(J_N1 − J_RL)。\n",
          "消融：均匀空间故障重训（或评估）后，优势应缩小到风暴条件优势的一半及以下。\n\n"]

    if args.storm_rl and os.path.exists(args.storm_rl):
        rows = load_jsonl(args.storm_rl)
        n1 = [r for r in rows if r.get("method") == "N1_240"]
        rl_m = pick_rl_method(rows, ("_pomo_v2", "RL_s0", "RL"))
        # also allow separate files? if no N1 in same file, look for sibling
        sh = paired_share([r for r in rows if r.get("method") == rl_m], n1, None)
        adv = advantage([r for r in rows if r.get("method") == rl_m], n1)
        report["storm_eval"] = dict(file=args.storm_rl, method=rl_m, share=sh, advantage=adv)
        md.append(f"## 风暴日评估（风暴训练策略，方法 `{rl_m}`）\n\n")
        md.append(f"- 配对 n={sh.get('n')}（风暴 {sh.get('n_storm')}，平静 {sh.get('n_calm')}）\n")
        md.append(f"- J_RL={sh.get('J_rl'):.4f}  J_N1={sh.get('J_n1'):.4f}\n" if sh.get("n") else "- 无配对\n")
        if sh.get("n"):
            md.append(f"- 总增益份额中风暴日占 **{sh['storm_share']*100:.1f}%**"
                      f"（门槛 70%，{'通过' if sh['pass_70'] else '未通过'}）\n")
            md.append(f"- 风暴日均 ΔJ={sh['mean_delta_storm']:.2f}，平静日均 ΔJ={sh['mean_delta_calm']:.2f}\n\n")
    else:
        md.append("风暴评估文件缺失，未计算份额。\n\n")

    if args.uniform_eval and os.path.exists(args.uniform_eval):
        rows = load_jsonl(args.uniform_eval)
        n1 = [r for r in rows if r.get("method") == "N1_240"]
        rl_m = pick_rl_method(rows, ("_pomo_v2", "RL_s0", "RL"))
        adv_u = advantage([r for r in rows if r.get("method") == rl_m], n1)
        report["uniform_eval_storm_trained"] = dict(file=args.uniform_eval, method=rl_m, advantage=adv_u)
        md.append(f"## 均匀故障评估（风暴训练策略，方法 `{rl_m}`）\n\n")
        if adv_u.get("n"):
            md.append(f"- n={adv_u['n']}  J_RL={adv_u['J_rl']:.4f}  J_N1={adv_u['J_n1']:.4f}  "
                      f"ΔJ={adv_u['dJ_pct']:.2f}%\n\n")

    if args.uniform_retrain and os.path.exists(args.uniform_retrain):
        rows = load_jsonl(args.uniform_retrain)
        n1 = [r for r in rows if r.get("method") == "N1_240"]
        rl_m = pick_rl_method(rows, ("uniform", "_pomo_v2", "RL"))
        adv_r = advantage([r for r in rows if r.get("method") == rl_m], n1)
        report["uniform_retrain"] = dict(file=args.uniform_retrain, method=rl_m, advantage=adv_r)
        md.append(f"## 均匀故障重训策略（方法 `{rl_m}`）\n\n")
        if adv_r.get("n"):
            md.append(f"- n={adv_r['n']}  J_RL={adv_r['J_rl']:.4f}  J_N1={adv_r['J_n1']:.4f}  "
                      f"ΔJ={adv_r['dJ_pct']:.2f}%\n\n")

    # shrink test: compare |advantage| of uniform-retrain (preferred) or uniform-eval vs storm
    storm_adv = (report.get("storm_eval") or {}).get("advantage") or {}
    uni_adv = (report.get("uniform_retrain") or {}).get("advantage") or \
              (report.get("uniform_eval_storm_trained") or {}).get("advantage") or {}
    if storm_adv.get("n") and uni_adv.get("n"):
        a_s = storm_adv["mean_delta"]  # J_N1 - J_RL, positive if RL better
        a_u = uni_adv["mean_delta"]
        ratio = a_u / a_s if abs(a_s) > 1e-12 else float("nan")
        # "优势缩小到一半以下": remaining advantage <= 50% of original
        shrink_ok = bool(ratio <= 0.50) if ratio == ratio else False
        report["shrink"] = dict(storm_mean_delta=a_s, uniform_mean_delta=a_u,
                                remaining_ratio=ratio, pass_half=shrink_ok,
                                used="uniform_retrain" if "uniform_retrain" in report else "uniform_eval")
        md.append("## 消融（优势是否缩小到一半及以下）\n\n")
        md.append(f"- 风暴条件优势（J_N1−J_RL 日均）={a_s:.2f}\n")
        md.append(f"- 均匀故障后优势={a_u:.2f}，剩余比例 **{ratio*100:.1f}%**"
                  f"（门槛 ≤50%，{'通过' if shrink_ok else '未通过'}）\n\n")

    share_ok = bool((report.get("storm_eval") or {}).get("share", {}).get("pass_70"))
    shrink_ok = bool((report.get("shrink") or {}).get("pass_half"))
    report["P3_pass"] = bool(share_ok and shrink_ok)
    report["P3_share_pass"] = share_ok
    report["P3_shrink_pass"] = shrink_ok
    md.append(f"## 总判定\n\n- 份额闸门：{'通过' if share_ok else '未通过'}\n"
              f"- 消融闸门：{'通过' if shrink_ok else '未通过'}\n"
              f"- **P3 整体：{'通过' if report['P3_pass'] else '未通过'}**（如实记录，不改门槛）。\n")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(report, open(args.out, "w"), indent=2, default=float)
    md_path = os.path.splitext(args.out)[0] + ".md"
    open(md_path, "w").write("".join(md))
    print(json.dumps(report, indent=2, default=float))
    print("wrote", args.out, md_path)
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
