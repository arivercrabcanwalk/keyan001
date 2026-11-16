#!/usr/bin/env python3
"""WX4 final analysis (pre-registered in wx_e/PREREG_v4.md).

Order of evaluation (PREREG_v4 §5):
  1. COMPLETION GATE (primary, checked first): per method, share of (map, day) instances with 100% completion
     (all planned targets + every non-structurally-unservable urgent request). A method < 100% is FLAGGED and
     all its other metrics are reported only as CONDITIONAL (marked †).
  2. Only if RL (every seed) passes the gate: RL (seed mean) vs EVERY realisable baseline on J (Holm family);
     H2 makespan NON-INFERIORITY vs the STRONGEST gate-passing baseline (lowest mean J; margin +2%; one-sided);
     then secondary metrics.
  3. Guards: J' = J + pi*(unfinished + urgent_missed) for pi in {0,100,200,500,1000}; weight sensitivity
     (re-scoring J with alternative weights from logged components).
Statistics: map level (mean over days) Wilcoxon + Holm, day-cluster Wilcoxon, crossed map x day bootstrap,
rank-biserial r (reused from analyze_v3). "Confirmed" = Holm<.05 & p_day<.05 & crossed CI excludes 0.
"""
import json, os, glob, datetime, zoneinfo
from collections import defaultdict
import numpy as np
from scipy.stats import wilcoxon
import analyze_v3 as A3
from analyze_v3 import paired, holm, fmt, HDR

ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "wx_e", "results")
OUT = os.path.join(ROOT, "results_final")
METRICS = [("J", -1), ("cost", -1), ("mk", -1), ("ontime", 1), ("ontime_h", 1), ("fails", -1), ("cvar_h", -1)]
SECONDARY = ["fails", "cost", "ontime_h", "cvar_h"]
PIS = [0, 100, 200, 500, 1000]
MK_DELTA = 0.02
W0 = dict(mk=0.5, lh=30.0, ln=10.0, P=100.0)
WVARS = {"mk×0.5": dict(mk=0.25), "mk×2": dict(mk=1.0), "mk×4": dict(mk=2.0),
         "P×0.5": dict(P=50.0), "P×2": dict(P=200.0), "lateH×0.5": dict(lh=15.0), "lateH×2": dict(lh=60.0),
         "lateN×2": dict(ln=20.0)}
REAL_BASES = ["N1_240", "A1", "A2", "N6_best", "POMO_mean"]
RL_PREFIX = "RL4_s"


def urg_miss(r):
    return max(0.0, float(r.get("unserved", 0)) - float(r.get("n_unservable", 0)))


def enrich(r):
    r["urg_miss"] = urg_miss(r)
    r["inc"] = float(r.get("unfinished", 0)) + r["urg_miss"]
    r["complete"] = float(r.get("complete", 1.0 if r["inc"] == 0 else 0.0))
    for pi in PIS:
        r[f"Jp{pi}"] = r["J"] + pi * r["inc"]
    for name, w in WVARS.items():
        ww = dict(W0, **w)
        r["Jw_" + name] = (r["cost"] + ww["mk"] * r["mk"] + ww["lh"] * r["late_min_h"] + ww["ln"] * r["late_min_n"]
                           + ww["P"] * r["fails"])
    return r


KEYS_MEAN = None


def table(rows):
    t = defaultdict(dict)
    for r in rows:
        t[r["method"]][(r["inst"], r["day"])] = enrich(r)
    seeds = sorted(m for m in t if m.startswith(RL_PREFIX))
    for pref, mean_name in ((RL_PREFIX, "RL4_mean"), ("POMO_s", "POMO_mean")):
        ss = sorted(m for m in t if m.startswith(pref))
        if ss:
            keys = set.intersection(*[set(t[s]) for s in ss])
            num = [k for k, v in next(iter(t[ss[0]].values())).items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            t[mean_name] = {k: {m: float(np.mean([t[s][k][m] for s in ss])) for m in num} for k in keys}
            for k in keys:   # the mean policy is complete only if EVERY seed is complete
                t[mean_name][k]["complete"] = float(min(t[s][k]["complete"] for s in ss))
    return t, seeds


def gate(t):
    g = {}
    for m, v in t.items():
        rr = list(v.values())
        g[m] = dict(n=len(rr), complete=float(np.mean([r["complete"] for r in rr])),
                    comp_plan=float(np.mean([r.get("comp_plan", 1) for r in rr])),
                    comp_urg=float(np.mean([r.get("comp_urg", 1) for r in rr])),
                    unfinished=float(np.mean([r.get("unfinished", 0) for r in rr])),
                    urg_miss=float(np.mean([r["urg_miss"] for r in rr])),
                    n_unservable_struct=float(np.mean([r.get("n_unservable", 0) for r in rr])),
                    forced=float(np.mean([r.get("n_forced", 0) for r in rr])))
        g[m]["pass"] = bool(g[m]["complete"] >= 1.0 - 1e-12)
    return g


def noninf(t, a, b, metric="mk", delta=MK_DELTA):
    """One-sided non-inferiority: H0 mean_a >= (1+delta) mean_b (maps); also crossed-bootstrap upper bound."""
    x = paired(t, a, b, metric, -1)
    if not x:
        return None
    keys = sorted(set(t[a]) & set(t[b]))
    A = defaultdict(list); B = defaultdict(list)
    for k in keys:
        A[k[0]].append(t[a][k][metric]); B[k[0]].append(t[b][k][metric])
    ins = sorted(A)
    xa = np.array([np.mean(A[i]) for i in ins]); xb = np.array([np.mean(B[i]) for i in ins])
    d = xa - (1 + delta) * xb
    p = float(wilcoxon(d, alternative="less").pvalue) if np.any(np.abs(d) > 1e-12) and len(ins) > 5 else 1.0
    x.update(delta_pct=delta * 100, p_noninf=p,
             noninferior=bool(p < 0.05 and x["ci_cross"][1] < delta * 100))
    return x


def suite(name, f, primary=True, extra=()):
    rows = A3.load(os.path.join(RES, f))
    if not rows:
        return None, f"\n### {name}\n\n（无结果文件 `{f}`）\n"
    t, seeds = table(rows)
    g = gate(t)
    out = {"file": f, "n_rows": len(rows), "gate": g, "seeds": seeds}
    L = [f"\n### {name}（`{f}`，{len(rows)} 行）\n",
         "**① 完成率门槛（先于一切指标）**：complete = 计划目标 100% 完成且所有非结构性不可达的紧急请求均被服务。",
         "| 方法 | n | complete | 计划完成率 | 紧急完成率 | 未完成/天 | 漏紧急/天 | 结构性不可达/天 | 强制出发/天 | 门槛 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for m in sorted(g):
        x = g[m]
        L.append(f"| {m} | {x['n']} | {x['complete']:.4f} | {x['comp_plan']:.4f} | {x['comp_urg']:.4f} | {x['unfinished']:.3f} | "
                 f"{x['urg_miss']:.3f} | {x['n_unservable_struct']:.2f} | {x['forced']:.1f} | {'✓' if x['pass'] else '✗ FLAG'} |")
    L.append("\n**② 条件指标**（† = 该方法未过门槛，指标仅供参考）\n")
    L.append("| 方法 | " + " | ".join(m for m, _ in METRICS) + " | ms_p99 |\n|---|" + "---|" * (len(METRICS) + 1))
    for m in sorted(t):
        v = list(t[m].values())
        ms = np.mean([r.get("ms_p99", np.nan) for r in v])
        L.append(f"| {m}{'' if g[m]['pass'] else ' †'} | " + " | ".join(f"{np.mean([r[k] for r in v]):.4g}" for k, _ in METRICS) + f" | {ms:.3g} |")
    rl = "RL4_mean"
    bases = [b for b in REAL_BASES if b in t]
    if rl in t and primary:
        rl_pass = all(g[s]["pass"] for s in seeds)
        passing = [b for b in bases if g[b]["pass"]]
        strongest = min(passing or bases, key=lambda b: np.mean([r["J"] for r in t[b].values()])) if bases else None
        out.update(rl_pass=rl_pass, passing_bases=passing, strongest=strongest)
        L.append(f"\nRL 所有种子过门槛：**{rl_pass}**；过门槛基线：{passing}；最强基线（过门槛中均值 J 最小）：**{strongest}**")
        famJ = holm([paired(t, rl, b, "J", -1) for b in bases])
        out["primary_J"] = famJ
        L.append(f"\n**③ 主要假设 H1：RL（种子均值）对每个可实现基线的 J（Holm {len(famJ)} 检验）**" + ("" if rl_pass else "（RL 未过门槛 → 结论无效，仅条件参考）") + "\n\n" + HDR)
        L += [fmt(x) for x in famJ]
        ni = [noninf(t, rl, b) for b in bases]
        out["mk_noninf"] = ni
        out["H2_primary"] = next((x for x in ni if x and x["b"] == strongest), None)
        L.append(f"\n**④ H2 makespan 非劣（δ=+{MK_DELTA*100:.0f}%，单侧 Wilcoxon(地图) p<.05 且交叉 bootstrap 上界 < δ）；预注册主检验 = 对最强基线 {strongest}，其余行仅描述**\n")
        L.append("| B | RL mk | B mk | 相对差 | 交叉 CI | p_noninf | 非劣 |\n|---|---|---|---|---|---|---|")
        for x in ni:
            if x:
                L.append(f"| {x['b']}{' (主)' if x['b'] == strongest else ''} | {x['mean_a']:.1f} | {x['mean_b']:.1f} | {x['rel_pct']:+.2f}% | [{x['ci_cross'][0]:+.2f}, {x['ci_cross'][1]:+.2f}] | {x['p_noninf']:.2e} | {'✓' if x['noninferior'] else '✗'} |")
        sec = holm([paired(t, rl, b, met, bd) for b in bases for met, bd in METRICS if met in SECONDARY])
        out["secondary"] = sec
        L.append(f"\n**⑤ 次要指标（Holm {len(sec)} 检验）**\n\n" + HDR)
        L += [fmt(x) for x in sec]
        pis = []
        for pi in PIS:
            for b in bases:
                x = paired(t, rl, b, f"Jp{pi}", -1)
                if x:
                    pis.append(dict(pi=pi, b=b, rel_pct=x["rel_pct"], ci_cross=x["ci_cross"], p=x["p"]))
        out["pi_sensitivity"] = pis
        L.append("\n**⑥ J' = J + π·(未完成+漏紧急) 敏感性**（门槛通过时 J'≡J）\n\n| π | B | 相对差 | 交叉 CI | p |\n|---|---|---|---|---|")
        L += [f"| {x['pi']} | {x['b']} | {x['rel_pct']:+.2f}% | [{x['ci_cross'][0]:+.2f}, {x['ci_cross'][1]:+.2f}] | {x['p']:.2e} |" for x in pis]
        ws = []
        for wn in WVARS:
            for b in bases:
                x = paired(t, rl, b, "Jw_" + wn, -1)
                if x:
                    ws.append(dict(variant=wn, b=b, rel_pct=x["rel_pct"], ci_cross=x["ci_cross"], p=x["p"]))
        out["weight_sensitivity"] = ws
        L.append("\n**⑦ 权重敏感性（用记录的分量重新计分；策略不重训）**\n\n| 权重变体 | B | 相对差 | 交叉 CI | p |\n|---|---|---|---|---|")
        L += [f"| {x['variant']} | {x['b']} | {x['rel_pct']:+.2f}% | [{x['ci_cross'][0]:+.2f}, {x['ci_cross'][1]:+.2f}] | {x['p']:.2e} |" for x in ws]
        per = holm([paired(t, s, b, met, bd) for s in seeds for b in bases[:1] for met, bd in METRICS if met in ["J", "mk"]])
        out["per_seed"] = per
        L.append(f"\n逐种子对 {bases[:1]}（J、mk）\n\n" + HDR)
        L += [fmt(x) for x in per]
        for em in extra:
            ex = holm([paired(t, rl, em, met, bd) for met, bd in METRICS if met in ["J", "mk", "fails"]])
            if ex:
                out["vs_" + em] = ex
                L.append(f"\n对 {em}（参照/时延匹配，单独 Holm）\n\n" + HDR)
                L += [fmt(x) for x in ex]
    return out, "\n".join(L) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    now = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")
    md = [f"# WX4 结果汇总（自动生成，{now} JST）\n",
          "合成天气。**完成率是第一门槛**（PREREG_v4 §5）：共享可行性层（最晚出发/强制出发掩码 + 不放弃重试 + 收工后风场衰减的完成窗口）下，",
          "任一方法 complete<100% 即被标记，其余指标仅作条件参考。主张：在 100% 完成下 RL 的 J 显著优于所有可实现基线（含最强基线），且 makespan 非劣（δ=2%）。\n"]
    res = {}
    specs = [("Test-A（ours 计划 × 7200–7299）", "testA_v4.jsonl", True, ("O", "N4fd_32_100ms", "N4fd_32_1000ms", "N4f_M32", "N4p_M32")),
             ("Test-B（作者 TSALNS 计划 × 8200–8299，计划结构分布外）", "testB_v4.jsonl", True, ()),
             ("Test-C（压力：λ=3.5, p_f=0.5 × 8300–8399）", "testC_v4.jsonl", True, ()),
             ("Test-L（较大实例 12×150、15×200 × 9200–9299）", "testL_v4.jsonl", True, ()),
             ("P4a σ×1.5", "p4_sigma15_v4.jsonl", True, ()),
             ("P4b 临近预报速度偏差 ×1.3", "p4_ncbias_v4.jsonl", True, ()),
             ("WX-H 时延（dev）", "wxh_v4.jsonl", False, ()),
             ("P3 探索性：均匀故障", "p3_uniform_v4.jsonl", True, ())]
    for name, f, prim, extra in specs:
        o, txt = suite(name, f, prim, extra)
        res[f] = o
        md.append(txt)
    md.append("\n## 训练记录（dev 选择，PREREG_v4 §4）\n")
    for f in sorted(glob.glob(os.path.join(ROOT, "models4", "select_es_s*.json"))):
        z = json.load(open(f))
        md.append(f"- seed {z['seed']}：选中 λ={z['picked']['lam']}，可行={z['feasible']}；dev " +
                  json.dumps({k: round(z['picked']['dev'].get(k, float('nan')), 4) for k in ('J', 'mk', 'complete', 'ontime_h', 'fails', 'cvar_h')}) +
                  "；N1 dev " + json.dumps({k: round(z['N1_dev'].get(k, float('nan')), 4) for k in ('J', 'mk', 'complete')}))
    json.dump(res, open(os.path.join(OUT, "ANALYSIS_V4.json"), "w"), indent=1, default=float)
    open(os.path.join(OUT, "SUMMARY_ZH.md"), "w").write("\n".join(md))
    print("wrote", os.path.join(OUT, "SUMMARY_ZH.md"))


if __name__ == "__main__":
    main()
