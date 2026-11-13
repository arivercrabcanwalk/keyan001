#!/usr/bin/env python3
"""P4 robustness (PREREG): on test (or dev fallback), σ×1.5 and cell-speed +30%.

RL degradation must not exceed that of N1_240 (the strongest NoRL; PREREG text says N3,
which was superseded by the frozen N1_240).

degradation(m) = (J_perturbed(m) - J_baseline(m)) / |J_baseline(m)|
Pass if degradation(RL) <= degradation(N1)  (RL does not get worse *more* than N1).
"""
from __future__ import annotations
import os, sys, json, argparse
import numpy as np

ROOT = os.path.abspath(os.environ.get("WX_ROOT") or os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_jsonl(p):
    if not p or not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        if line.strip():
            r = json.loads(line)
            if not r.get("error"):
                out.append(r)
    return out


def key(r):
    return (r.get("path"), int(r["day"]))


def means(rows, method):
    xs = [r["J"] for r in rows if r.get("method") == method]
    return float(np.mean(xs)) if xs else float("nan")


def paired_deg(base_rows, p4_rows, method):
    b = {key(r): r for r in base_rows if r.get("method") == method}
    p = {key(r): r for r in p4_rows if r.get("method") == method}
    ks = sorted(set(b) & set(p))
    if not ks:
        return dict(n=0)
    Jb = np.array([b[k]["J"] for k in ks], float)
    Jp = np.array([p[k]["J"] for k in ks], float)
    deg = (Jp.mean() - Jb.mean()) / (abs(Jb.mean()) + 1e-12)
    return dict(n=len(ks), J_base=float(Jb.mean()), J_p4=float(Jp.mean()),
                deg=float(deg), deg_pct=float(deg * 100))


def pick_rl(rows):
    meths = sorted({r.get("method") for r in rows if str(r.get("method", "")).startswith("RL")})
    for s in ("_pomo_v2", "RL_s0", "RL"):
        for m in meths:
            if s in m or m == s:
                return m
    return meths[0] if meths else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, help="jsonl of baseline (Test-A or dev) with N1 and RL")
    ap.add_argument("--p4-sigma", default="", help="jsonl σ=1.5")
    ap.add_argument("--p4-speed", default="", help="jsonl speed +30%")
    ap.add_argument("--out", default=os.path.join(ROOT, "results_final", "P4_ANALYSIS.json"))
    args = ap.parse_args()

    base = load_jsonl(args.baseline)
    rl = pick_rl(base)
    report = dict(rule="N1_240", rl_method=rl, synthetic=True, cases={})
    md = ["# P4 分析（合成天气，预注册标准）\n",
          "退化 = (J_扰动 − J_基准) / |J_基准|。RL 退化不得超过 N1_240 的退化。\n\n"]
    all_ok = True
    any_case = False
    for name, path in (("sigma_x1.5", args.p4_sigma), ("speed_plus30", args.p4_speed)):
        if not path or not os.path.exists(path):
            md.append(f"## {name}\n\n文件缺失。\n\n")
            continue
        p4 = load_jsonl(path)
        d_n1 = paired_deg(base, p4, "N1_240")
        d_rl = paired_deg(base, p4, rl) if rl else dict(n=0)
        ok = False
        if d_n1.get("n") and d_rl.get("n"):
            ok = bool(d_rl["deg"] <= d_n1["deg"] + 1e-12)
            any_case = True
            all_ok = all_ok and ok
        report["cases"][name] = dict(file=path, N1=d_n1, RL=d_rl, pass_=ok)
        md.append(f"## {name}\n\n")
        md.append(f"- N1_240：n={d_n1.get('n')}  J_基={d_n1.get('J_base')}  J_扰={d_n1.get('J_p4')}  "
                  f"退化={d_n1.get('deg_pct')}%\n")
        md.append(f"- {rl}：n={d_rl.get('n')}  J_基={d_rl.get('J_base')}  J_扰={d_rl.get('J_p4')}  "
                  f"退化={d_rl.get('deg_pct')}%\n")
        md.append(f"- 判定：{'通过（RL 退化不超过 N1）' if ok else '未通过或数据不足'}\n\n")
    report["P4_pass"] = bool(any_case and all_ok)
    md.append(f"## 总判定\n\n**P4 整体：{'通过' if report['P4_pass'] else '未通过'}**（如实记录）。\n")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(report, open(args.out, "w"), indent=2, default=float)
    open(os.path.splitext(args.out)[0] + ".md", "w").write("".join(md))
    print(json.dumps(report, indent=2, default=float))
    print("wrote", args.out)
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
