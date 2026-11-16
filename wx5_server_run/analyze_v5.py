#!/usr/bin/env python3
"""WX5 final analysis (pre-registered in wx_e/PREREG_v5.md).
Order (PREREG_v5 §6):
 ① COMPLETION GATE: per method share of (map, day) units with 100% completion (all planned targets + every physically
    reachable urgent request) INSIDE the operational window T_END = H + 240 min. <100% -> FLAG, other metrics conditional (†).
 ② H1 (primary): RL5 (seed mean) vs EVERY realisable baseline on J5 (Holm family over baselines).
    J5 = cost(fixed + 0.5*busy + backup) + C_OT*overtime + 30*late_h + 10*late_n + 100*fails   (no makespan term).
 ③ H2 (constraint): RL5 overtime NON-INFERIOR to the frozen N6_best (trained constraint E[ot_RL - ot_N6] <= 0):
    crossed map x day bootstrap 95% upper bound of the relative difference < +5%.
 ④ secondary (Holm): cost, fails, ontime_h, cvar_h.
 ⑤ ablations (own Holm family): RL5 vs no-forecast, no-emergency-features, unconstrained (no OT budget), no-ES (pomo_v2), no-RL (A1).
 ⑥ sensitivity: re-scored J5 with C_OT in {0,0.5,2,4}, fail weight x0.5/x2, late_h x0.5/x2, backup cost x0.5/x2.
 ⑦ APPENDIX (honest, descriptive + Holm): makespan (mk), last-crew-end (mk_last) and v4's J (J_v4 with 0.5*mk).
Statistics: map-level Wilcoxon + Holm, day-cluster Wilcoxon, crossed map x day bootstrap, rank-biserial r.
"Confirmed" = Holm<.05 & p_day<.05 & crossed CI excludes 0."""
import json, os, glob, datetime, zoneinfo
from collections import defaultdict
import numpy as np
import analyze_v3 as A3
from analyze_v3 import paired, holm, fmt, HDR

ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "wx_e", "results")
OUT = os.path.join(ROOT, "results_final")
OT_DELTA = float(os.environ.get("OT_DELTA", "5"))   # H2 non-inferiority margin (%) for overtime vs N6_best
METRICS = [("J", -1), ("cost", -1), ("fails", -1), ("ontime", 1), ("ontime_h", 1), ("cvar_h", -1), ("ot_min", -1),
           ("n_backup", -1), ("mk", -1), ("J_v4", -1)]
SECONDARY = [("cost", -1), ("fails", -1), ("ontime_h", 1), ("cvar_h", -1)]
W0 = dict(ot=1.0, lh=30.0, ln=10.0, P=100.0, bk=200.0)
WVARS = {"C_OT=0": dict(ot=0.0), "C_OT=0.5": dict(ot=0.5), "C_OT=2": dict(ot=2.0), "C_OT=4": dict(ot=4.0),
         "P×0.5": dict(P=50.0), "P×2": dict(P=200.0), "lateH×0.5": dict(lh=15.0), "lateH×2": dict(lh=60.0),
         "backup×0.5": dict(bk=100.0), "backup×2": dict(bk=400.0)}
REAL_BASES = ["A1", "A2", "N1_240", "N6_best", "R_N6best", "Rfc_N6best", "POMO_mean"]
GROUPS = {"RL5_s": "RL5_mean", "RL5nf_s": "RL5nf_mean", "RL5ne_s": "RL5ne_mean", "RL5uc_s": "RL5uc_mean", "POMO_s": "POMO_mean"}
ABL = [("RL5nf_mean", "无天气预报特征"), ("RL5ne_mean", "无紧急任务特征"), ("RL5uc_mean", "无加班约束（仅 C_OT 计价）"),
       ("POMO_mean", "无 ES（pomo_v2 初始化）"), ("A1", "无 RL（计划 + 共享可行性掩码）")]
RL = "RL5_mean"


def enrich(r):
    r["urg_miss"] = max(0.0, float(r.get("unserved", 0)) - float(r.get("n_unservable", 0)))
    r["inc"] = float(r.get("unfinished", 0)) + r["urg_miss"]
    r["complete"] = float(r.get("complete", 1.0 if r["inc"] == 0 else 0.0))
    nb = float(r.get("n_backup", 0))
    for name, w in WVARS.items():
        ww = dict(W0, **w)
        r["Jw_" + name] = (r["cost"] + (ww["bk"] - W0["bk"]) * nb + ww["ot"] * r.get("ot_min", 0) + ww["lh"] * r["late_min_h"]
                           + ww["ln"] * r["late_min_n"] + ww["P"] * r["fails"])
    return r


def table(rows):
    t = defaultdict(dict)
    for r in rows:
        t[r["method"]][(r["inst"], r["day"])] = enrich(r)
    seeds = {}
    for pref, mean_name in GROUPS.items():
        ss = sorted(m for m in t if m.startswith(pref))
        if not ss:
            continue
        seeds[mean_name] = ss
        keys = set.intersection(*[set(t[s]) for s in ss])
        num = [k for k, v in next(iter(t[ss[0]].values())).items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        t[mean_name] = {k: {m: float(np.mean([t[s][k][m] for s in ss])) for m in num} for k in keys}
        for k in keys:
            t[mean_name][k]["complete"] = float(min(t[s][k]["complete"] for s in ss))
    return t, seeds


def gate(t):
    g = {}
    for m, v in t.items():
        rr = list(v.values())
        g[m] = dict(n=len(rr), complete=float(np.mean([r["complete"] for r in rr])),
                    unfinished=float(np.mean([r.get("unfinished", 0) for r in rr])),
                    urg_miss=float(np.mean([r["urg_miss"] for r in rr])),
                    unreach=float(np.mean([r.get("n_unservable", 0) for r in rr])),
                    backup=float(np.mean([r.get("n_backup", 0) for r in rr])),
                    ot=float(np.mean([r.get("ot_min", 0) for r in rr])))
        g[m]["pass"] = bool(g[m]["complete"] >= 1.0 - 1e-12)
    return g


def ot_bound(t, m):
    keys = sorted(t[m]); ins = sorted({k[0] for k in keys}); dys = sorted({k[1] for k in keys})
    X = np.full((len(ins), len(dys)), np.nan); im = {a: i for i, a in enumerate(ins)}; idd = {a: i for i, a in enumerate(dys)}
    for k in keys:
        X[im[k[0]], idd[k[1]]] = t[m][k].get("ot_min", 0)
    rng = np.random.default_rng(1); bs = []
    for _ in range(2000):
        bs.append(np.nanmean(X[np.ix_(rng.integers(0, len(ins), len(ins)), rng.integers(0, len(dys), len(dys)))]))
    return float(np.nanmean(X)), float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))


def suite(name, f, primary=True, extra=()):
    rows = A3.load(os.path.join(RES, f))
    if not rows:
        return None, f"\n### {name}\n\n（无结果文件 `{f}`）\n"
    t, seeds = table(rows)
    g = gate(t)
    out = {"file": f, "n_rows": len(rows), "gate": g, "seeds": seeds}
    L = [f"\n### {name}（`{f}`，{len(rows)} 行）\n",
         f"**① 完成率门槛**（作业窗口 T_END=H+240 min 内，计划目标 100% + 所有物理可达紧急请求）",
         "| 方法 | n | complete | 未完成/天 | 漏紧急/天 | 物理不可达紧急/天 | 备用机/天 | 加班(站·分)/天 | 门槛 |", "|---|---|---|---|---|---|---|---|---|"]
    for m in sorted(g):
        x = g[m]
        L.append(f"| {m} | {x['n']} | {x['complete']:.4f} | {x['unfinished']:.3f} | {x['urg_miss']:.3f} | {x['unreach']:.2f} | "
                 f"{x['backup']:.3f} | {x['ot']:.1f} | {'✓' if x['pass'] else '✗ FLAG'} |")
    L.append("\n**均值表**（† = 未过门槛；mk/J_v4 仅附录参考）\n")
    L.append("| 方法 | " + " | ".join(m for m, _ in METRICS) + " | ms_p99 |\n|---|" + "---|" * (len(METRICS) + 1))
    for m in sorted(t):
        v = list(t[m].values())
        L.append(f"| {m}{'' if g[m]['pass'] else ' †'} | " + " | ".join(f"{np.mean([r.get(k, np.nan) for r in v]):.4g}" for k, _ in METRICS)
                 + f" | {np.mean([r.get('ms_p99', np.nan) for r in v]):.3g} |")
    bases = [b for b in REAL_BASES if b in t]
    if RL in t and primary:
        rl_pass = all(g[s]["pass"] for s in seeds.get(RL, []))
        passing = [b for b in bases if g[b]["pass"]]
        strongest = min(passing or bases, key=lambda b: np.mean([r["J"] for r in t[b].values()])) if bases else None
        out.update(rl_pass=rl_pass, passing_bases=passing, strongest=strongest)
        L.append(f"\nRL5 所有种子过门槛：**{rl_pass}**；最强基线（过门槛中 J5 最小）：**{strongest}**")
        famJ = holm([paired(t, RL, b, "J", -1) for b in bases])
        out["H1_J5"] = famJ
        L.append(f"\n**② H1：RL5（种子均值）对每个可实现基线的 J5（Holm {len(famJ)}）**\n\n" + HDR)
        L += [fmt(x) for x in famJ]
        mu, lo, hi = ot_bound(t, RL)
        x2 = paired(t, RL, "N6_best", "ot_min", -1) if "N6_best" in t else None
        h2 = dict(mean=mu, ci=[lo, hi], vs_N6=x2, delta_pct=OT_DELTA,
                  pass_=bool(x2 is not None and x2["ci_cross"][1] < OT_DELTA),
                  ot_bases={b: float(np.mean([r.get("ot_min", 0) for r in t[b].values()])) for b in bases})
        out["H2_ot"] = h2
        L.append(f"\n**③ H2 加班非劣（对冻结 N6_best，δ=+{OT_DELTA:.0f}%）**：RL5 平均加班 {mu:.1f} 站·分/天 [{lo:.1f}, {hi:.1f}]"
                 + (f"；相对 N6_best {x2['rel_pct']:+.1f}%，交叉 CI [{x2['ci_cross'][0]:+.1f}, {x2['ci_cross'][1]:+.1f}]" if x2 else "")
                 + f" → {'✓ 非劣' if h2['pass_'] else '✗ 未通过'}；基线加班 " + ", ".join(f"{b} {v:.0f}" for b, v in h2["ot_bases"].items()))
        sec = holm([paired(t, RL, b, met, bd) for b in bases for met, bd in SECONDARY])
        out["secondary"] = sec
        L.append(f"\n**④ 次要指标（Holm {len(sec)}）**\n\n" + HDR)
        L += [fmt(x) for x in sec]
        ab = holm([paired(t, RL, b, "J", -1) for b, _ in ABL if b in t])
        out["ablation"] = ab
        if ab:
            L.append("\n**⑤ 消融（J5，单独 Holm）**：" + "；".join(f"{b} = {d}" for b, d in ABL if b in t) + "\n\n" + HDR)
            L += [fmt(x) for x in ab]
            L.append("\n消融的加班 / 失败 / 成本均值：\n\n| 变体 | J5 | ot | fails | cost | ontime_h |\n|---|---|---|---|---|---|")
            for b in [RL] + [b for b, _ in ABL if b in t]:
                v = list(t[b].values())
                L.append(f"| {b} | {np.mean([r['J'] for r in v]):.0f} | {np.mean([r.get('ot_min', 0) for r in v]):.0f} | "
                         f"{np.mean([r['fails'] for r in v]):.2f} | {np.mean([r['cost'] for r in v]):.0f} | {np.mean([r['ontime_h'] for r in v]):.4f} |")
        ws = []
        for wn in WVARS:
            for b in bases:
                x = paired(t, RL, b, "Jw_" + wn, -1)
                if x:
                    ws.append(dict(variant=wn, b=b, rel_pct=x["rel_pct"], ci_cross=x["ci_cross"], p=x["p"]))
        out["weight_sensitivity"] = ws
        L.append("\n**⑥ 权重敏感性（用记录分量重新计分，不重训）**\n\n| 变体 | B | 相对差 | 交叉 CI | p |\n|---|---|---|---|---|")
        L += [f"| {x['variant']} | {x['b']} | {x['rel_pct']:+.2f}% | [{x['ci_cross'][0]:+.2f}, {x['ci_cross'][1]:+.2f}] | {x['p']:.2e} |" for x in ws]
        per = holm([paired(t, s, strongest, "J", -1) for s in seeds.get(RL, [])]) if strongest else []
        out["per_seed"] = per
        L.append(f"\n逐种子对最强基线 {strongest}（J5）\n\n" + HDR)
        L += [fmt(x) for x in per]
        app = holm([paired(t, RL, b, met, -1) for b in bases for met in ("mk", "J_v4")])
        out["appendix_mk"] = app
        L.append("\n**⑦ 附录：完工时间（makespan，次要，如实报告）与 v4 口径 J_v4（含 0.5·mk）**\n\n" + HDR)
        L += [fmt(x) for x in app]
        for em in extra:
            ex = holm([paired(t, RL, em, met, bd) for met, bd in (("J", -1), ("fails", -1), ("ot_min", -1))])
            if ex:
                out["vs_" + em] = ex
                L.append(f"\n对 {em}（参照/时延匹配，单独 Holm）\n\n" + HDR)
                L += [fmt(x) for x in ex]
    return out, "\n".join(L) + "\n"


SPECS = [("Test-A（ours 计划 × 新天 7700–7799，主测试集）", "testA_v5.jsonl", True, ("O", "N4fd_32_100ms", "RLR_100ms")),
         ("Test-B（作者 TSALNS 计划 × 8700–8799，结构分布外）", "testB_v5.jsonl", True, ()),
         ("Test-C（压力 λ=3.5, p_f=0.5 × 8800–8899）", "testC_v5.jsonl", True, ()),
         ("Test-L（较大实例 12×150、15×200 × 9700–9799）", "testL_v5.jsonl", True, ()),
         ("P4a σ×1.5", "p4_sigma15_v5.jsonl", True, ()),
         ("P4b 临近预报速度偏差 ×1.3", "p4_ncbias_v5.jsonl", True, ()),
         ("P3 探索性：均匀故障", "p3_uniform_v5.jsonl", True, ()),
         ("窗口敏感性：作业窗口 H+180（WX_OT=180，更紧，Test-A 20 天子集）", "scale_ot180_v5.jsonl", True, ()),
         ("窗口敏感性：作业窗口 H+300（WX_OT=300，更松，Test-A 20 天子集）", "scale_ot300_v5.jsonl", True, ())]


def main():
    os.makedirs(OUT, exist_ok=True)
    now = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
    md = [f"# WX5 结果汇总（自动生成，{now} JST）\n",
          "合成天气。预注册：wx_e/PREREG_v5.md。**完成率是第一门槛**（12 h 作业日窗口内 100%）；主指标 J5（不含 makespan 项，加班按站·分计价），",
          f"并要求 RL 的加班不多于冻结的 N6_best（训练约束 E[ot_RL−ot_N6]≤0，检验非劣 δ=+{OT_DELTA:.0f}%），从而 RL 不能靠拖延到收工后取胜。makespan 降为次要，在 ⑦ 附录如实报告。\n"]
    res = {}
    for name, f, prim, extra in SPECS:
        o, txt = suite(name, f, prim, extra)
        res[f] = o
        md.append(txt)
    md.append("\n## 训练与选择记录（PREREG_v5 §5）\n")
    for f in sorted(glob.glob(os.path.join(ROOT, "models5", "select_*.json"))):
        z = json.load(open(f))
        md.append(f"- {z['name']}：选中 {z['picked']['kind']}，可行={z['feasible']}；dev " +
                  json.dumps({k: round(z['picked']['dev'].get(k, float('nan')), 3) for k in ('J', 'ot_min', 'mk', 'complete', 'fails', 'cost')}))
    for f in sorted(glob.glob(os.path.join(ROOT, "models5", "DONE_*"))):
        md.append(f"- {os.path.basename(f)}: {open(f).read().strip()}")
    json.dump(res, open(os.path.join(OUT, "ANALYSIS_V5.json"), "w"), indent=1, default=float)
    open(os.path.join(OUT, "SUMMARY_ZH.md"), "w").write("\n".join(md))
    print("wrote", os.path.join(OUT, "SUMMARY_ZH.md"))


if __name__ == "__main__":
    main()
