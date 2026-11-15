#!/usr/bin/env python3
"""WX3 final analysis (pre-registered families, see wx_e/PREREG_v3.md).
Instance level = mean over days per (map); paired two-sided Wilcoxon signed-rank; Holm within family;
effect size = matched-pairs rank-biserial r; 95% bootstrap CI of the relative difference (maps resampled).
Writes results_final/ANALYSIS_V3.json and results_final/SUMMARY_ZH.md.
"""
import json, os, sys, glob, math, time
from collections import defaultdict
import numpy as np
from scipy.stats import wilcoxon, rankdata
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "wx_e", "results")
OUT = os.path.join(ROOT, "results_final")
METRICS = [("J", -1), ("cost", -1), ("mk", -1), ("ontime", 1), ("ontime_h", 1), ("fails", -1), ("cvar_h", -1)]
PRIMARY = ["J", "fails", "cost", "mk", "ontime_h", "cvar_h"]


def load(f):
    rows = []
    if not os.path.exists(f):
        return rows
    for l in open(f):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if "error" not in r:
            rows.append(r)
    return rows


def table(rows, rl_prefix="RL3_s"):
    t = defaultdict(dict)
    for r in rows:
        t[r["method"]][(r["inst"], r["day"])] = r
    seeds = sorted(m for m in t if m.startswith(rl_prefix))
    for pref, mean_name in ((rl_prefix, "RL3_mean"), ("POMO_s", "POMO_mean")):
        ss = sorted(m for m in t if m.startswith(pref))
        if ss:
            keys = set.intersection(*[set(t[s]) for s in ss])
            t[mean_name] = {k: {m: float(np.mean([t[s][k][m] for s in ss])) for m, _ in METRICS} for k in keys}
    return t, seeds


def rank_biserial(d):
    d = d[np.abs(d) > 1e-12]
    if len(d) == 0:
        return 0.0
    r = rankdata(np.abs(d))
    return float((r[d > 0].sum() - r[d < 0].sum()) / r.sum())


def paired(t, a, b, metric, better):
    keys = sorted(set(t.get(a, {})) & set(t.get(b, {})))
    if not keys:
        return None
    A = defaultdict(list); Bm = defaultdict(list)
    for k in keys:
        A[k[0]].append(t[a][k][metric]); Bm[k[0]].append(t[b][k][metric])
    ins = sorted(A)
    x = np.array([np.mean(A[i]) for i in ins]); y = np.array([np.mean(Bm[i]) for i in ins])
    d = x - y
    p = float(wilcoxon(x, y).pvalue) if np.any(np.abs(d) > 1e-12) and len(ins) > 5 else 1.0
    rng = np.random.default_rng(0)
    den = abs(y.mean()) if abs(y.mean()) > 1e-12 else 1.0
    bs = []
    for _ in range(4000):
        ix = rng.integers(0, len(ins), len(ins))
        dd = abs(y[ix].mean()) if abs(y[ix].mean()) > 1e-12 else 1.0
        bs.append(d[ix].mean() / dd * 100)
    # weather is seeded by DAY only (shared across maps) -> day-cluster test (unit = day, mean over maps)
    Ad = defaultdict(list); Bd = defaultdict(list)
    for k in keys:
        Ad[k[1]].append(t[a][k][metric]); Bd[k[1]].append(t[b][k][metric])
    dys = sorted(Ad)
    xd = np.array([np.mean(Ad[q]) for q in dys]); yd = np.array([np.mean(Bd[q]) for q in dys])
    p_day = float(wilcoxon(xd, yd).pvalue) if np.any(np.abs(xd - yd) > 1e-12) and len(dys) > 5 else 1.0
    # crossed (map x day) bootstrap of the relative difference
    M2 = {k: (t[a][k][metric], t[b][k][metric]) for k in keys}
    im = {m: j for j, m in enumerate(ins)}; idd = {q: j for j, q in enumerate(dys)}
    XA = np.full((len(ins), len(dys)), np.nan); XB = np.full((len(ins), len(dys)), np.nan)
    for (m_, q_), (va, vb) in M2.items():
        XA[im[m_], idd[q_]] = va; XB[im[m_], idd[q_]] = vb
    bsx = []
    for _ in range(2000):
        ii = rng.integers(0, len(ins), len(ins)); jj = rng.integers(0, len(dys), len(dys))
        sa = np.nanmean(XA[np.ix_(ii, jj)]); sb = np.nanmean(XB[np.ix_(ii, jj)])
        bsx.append((sa - sb) / (abs(sb) if abs(sb) > 1e-12 else 1.0) * 100)
    return dict(a=a, b=b, metric=metric, n_inst=len(ins), n_days=len(keys), n_wx_days=len(dys), p_day=p_day,
                ci_cross=[float(np.nanpercentile(bsx, 2.5)), float(np.nanpercentile(bsx, 97.5))],
                mean_a=float(x.mean()),
                mean_b=float(y.mean()), diff=float(d.mean()), rel_pct=float(d.mean() / den * 100),
                ci_rel=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                win=int(((d * better) > 1e-12).sum()), loss=int(((d * better) < -1e-12).sum()),
                r_rb=float(rank_biserial(d) * better), p=p, better_dir=better)


def holm(ts):
    ts = [x for x in ts if x]
    ps = np.array([x["p"] for x in ts]); o = np.argsort(ps); run = 0.0; n = len(ps)
    for r, i in enumerate(o):
        run = max(run, min(1.0, (n - r) * ps[i])); ts[i]["p_holm"] = float(run)
    for x in ts:
        good = (x["diff"] * x["better_dir"]) > 0
        x["sig_better"] = bool(good and x["p_holm"] < 0.05)
        x["sig_worse"] = bool((not good) and x["p_holm"] < 0.05)
        # PREREG_v3 §5: "confirmed" needs map-level Holm AND day-cluster p<0.05 AND crossed-bootstrap CI excluding 0
        ci = x.get("ci_cross", [0, 0])
        x["confirmed"] = bool(x["sig_better"] and x.get("p_day", 1) < 0.05 and (ci[0] > 0 or ci[1] < 0))
    return ts


def fmt(x):
    return (f"| {x['a']} | {x['b']} | {x['metric']} | {x['mean_a']:.4g} | {x['mean_b']:.4g} | {x['rel_pct']:+.2f}% "
            f"[{x['ci_rel'][0]:+.2f}, {x['ci_rel'][1]:+.2f}] | {x['win']}/{x['n_inst']} | {x['r_rb']:+.2f} | "
            f"{x['p']:.2e} | {x['p_holm']:.2e} | {x.get('p_day', float('nan')):.2e} | [{x.get('ci_cross', [0, 0])[0]:+.2f}, {x.get('ci_cross', [0, 0])[1]:+.2f}] | "
            f"{'✓' if x['sig_better'] else ('✗' if x['sig_worse'] else '–')} | {'✓✓' if x.get('confirmed') else ''} |")


HDR = ("| A | B | 指标 | A | B | 相对差 [地图 bootstrap 95% CI] | 胜/图 | r_rb | p(地图) | p_Holm | p(天聚类) | 交叉 bootstrap CI | 显著更好 | 确认 |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def suite(name, f, refs, extra_methods=()):
    rows = load(os.path.join(RES, f))
    if not rows:
        return None, f"\n### {name}\n\n（无结果文件 `{f}`）\n"
    t, seeds = table(rows)
    out = {"file": f, "n_rows": len(rows), "methods": {m: len(v) for m, v in t.items()}, "seeds": seeds}
    lines = [f"\n### {name}（`{f}`，{len(rows)} 行）\n"]
    # means
    lines.append("| 方法 | n | " + " | ".join(m for m, _ in METRICS) + " | ms_p99 |\n|---|---|" + "---|" * (len(METRICS) + 1))
    for m in sorted(t):
        v = list(t[m].values())
        ms = np.mean([r.get("ms_p99", float("nan")) for r in v]) if v and "ms_p99" in v[0] else float("nan")
        lines.append(f"| {m} | {len(v)} | " + " | ".join(f"{np.mean([r[k] for r in v]):.4g}" for k, _ in METRICS) + f" | {ms:.3g} |")
    fam = []
    if "RL3_mean" in t:
        for ref in refs:
            if ref in t:
                fam += [paired(t, "RL3_mean", ref, met, b) for met, b in METRICS if met in PRIMARY]
    fam = holm(fam)
    out["family_mean"] = fam
    lines.append(f"\n预注册族（RL 种子均值 × {refs} × {PRIMARY}，Holm 共 {len(fam)} 检验）\n\n" + HDR)
    lines += [fmt(x) for x in fam]
    per = []
    for s in seeds:
        for ref in refs[:1]:
            per += [paired(t, s, ref, met, b) for met, b in METRICS if met in PRIMARY]
    per = holm(per)
    out["per_seed_vs_" + refs[0]] = per
    lines.append(f"\n逐种子对 {refs[0]}（Holm 跨种子×指标）\n\n" + HDR)
    lines += [fmt(x) for x in per]
    if "RL3_mean" in t and "POMO_mean" in t:   # ablation: does ES add value over its own pomo_v2 init?
        ab = holm([paired(t, "RL3_mean", "POMO_mean", met, b) for met, b in METRICS if met in PRIMARY])
        out["vs_POMO_mean"] = ab
        lines.append("\n消融：ES-RL（种子均值）对其初始化 pomo_v2（种子均值），单独 Holm\n\n" + HDR)
        lines += [fmt(x) for x in ab]
    for em in extra_methods:
        ex = holm([paired(t, "RL3_mean", em, met, b) for met, b in METRICS if met in PRIMARY])
        if ex:
            out["vs_" + em] = ex
            lines.append(f"\n对 {em}（参照/匹配时延，单独 Holm）\n\n" + HDR)
            lines += [fmt(x) for x in ex]
    return out, "\n".join(lines) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {}
    md = [f"# WX3 结果汇总（自动生成，{__import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S')} JST）\n",
          "合成天气（σ0=1，κ=0.5，非 ERA5）。实例层（每图对日取均值）配对 Wilcoxon，Holm；r_rb=匹配秩二列相关（正=RL 更好）。",
          "N4p = 使用真实未来天气的 rollout（特权参照，**不是**可实现基线）；N4f = 无特权 twin rollout。O = 一步千里眼上界。\n"]
    tA = os.environ.get("WX3_TESTA_REFS", "N1_240,A1,A2,N6_best").split(",")
    specs = [
        ("Test-A（Liu-50 × 7000–7029，ours 计划）", "testA_v3.jsonl", tA, ("O", "N4p_M32", "N4f_M32", "N4fd_32_10ms", "N4fd_32_100ms")),
        ("Test-B（Liu-50 × 8000–8029，作者 TSALNS 计划，计划结构分布外）", "testB_v3.jsonl", tA, ()),
        ("Test-C（压力：λ=3.5, p_f=0.5，ours 计划 × 8100–8129）", "testC_v3.jsonl", tA, ()),
        ("P4a σ×1.5（Test-A 日）", "p4_sigma15_v3.jsonl", tA[:2], ()),
        ("P4b 临近预报速度偏差 ×1.3（只扰动信息，不改真实天气；Test-A 日）", "p4_ncbias_v3.jsonl", tA[:2], ()),
        ("WX-H（dev，时延帕累托）", "wxh_v3.jsonl", ["N1_240"], ("N4fd_32_10ms", "N4fd_32_100ms", "N4fd_32_1000ms", "RLR_100ms", "RLR_1000ms")),
        ("P3 探索性：均匀故障（Test-A 日，uniform）", "p3_uniform_v3.jsonl", tA[:1], ()),
    ]
    for name, f, refs, extra in specs:
        o, txt = suite(name, f, refs, extra)
        res[f] = o
        md.append(txt)
    # training logs
    md.append("\n## 训练记录（dev 选择）\n")
    for f in sorted(glob.glob(os.path.join(ROOT, "models3", "select_es_s*.json"))):
        z = json.load(open(f))
        md.append(f"- seed {z['seed']}：选中 λ={z['picked']['lam']}，可行={z['feasible']}；dev " +
                  json.dumps({k: round(z['picked']['dev'][k], 4) for k in ('J', 'cost', 'mk', 'ontime_h', 'fails', 'cvar_h')}) +
                  "；N1 dev " + json.dumps({k: round(z['N1_dev'][k], 4) for k in ('J', 'ontime_h', 'cvar_h')}))
    json.dump(res, open(os.path.join(OUT, "ANALYSIS_V3.json"), "w"), indent=1, default=float)
    open(os.path.join(OUT, "SUMMARY_ZH.md"), "w").write("\n".join(md))
    print("wrote", os.path.join(OUT, "SUMMARY_ZH.md"))


if __name__ == "__main__":
    main()
