"""Analysis + pre-registered gates.  Only numbers present in the result files are reported (never imputed).
Usage: python rlcore/analyze.py --res results/test_weather.jsonl --scen weather --tuned results/tuned_weather.json --out results/report_weather"""
import os, sys, json, argparse, math
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

COLS = [("cost", "总成本"), ("fixed", "固定成本"), ("n_open", "开站数"), ("n_dabs", "DABS"), ("n_drones", "无人机"),
        ("dist_km", "飞行距离(km)"), ("launches", "架次"), ("op_min", "飞行+巡检(min)"), ("completion", "完成率"),
        ("aborts", "中止"), ("inc", "安全事件"), ("ot", "超时(min)"), ("J", "J")]
COLS_U = [("n_urgent", "紧急任务"), ("ontime_high", "高优先准时率"), ("ontime_norm", "普通准时率"),
          ("resp_mean", "平均响应(min)"), ("late_pen", "迟到惩罚")]


def load(paths):
    rows, errs = [], []
    for p in paths:
        if not os.path.exists(p):
            continue
        for l in open(p):
            try:
                r = json.loads(l)
            except Exception:
                continue
            (errs if "error" in r else rows).append(r)
    for r in rows:
        r["inc"] = r.get("inc_cell", 0) + r.get("inc_land", 0)
        r["ot"] = r.get("busy_ot", 0) + r.get("clock_ot", 0)
    return rows, errs


def wilcoxon_p(d):
    d = np.asarray(d, float)
    d = d[np.abs(d) > 1e-12]
    if len(d) < 5:
        return 1.0
    try:
        from scipy.stats import wilcoxon
        return float(wilcoxon(d).pvalue)
    except Exception:
        n = len(d); r = np.argsort(np.argsort(np.abs(d))) + 1
        W = r[d > 0].sum(); mu = n * (n + 1) / 4; sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
        z = (W - mu) / sd
        return float(math.erfc(abs(z) / math.sqrt(2)))


def cluster_boot(diff_by_map, B=2000, seed=0):
    rng = np.random.default_rng(seed)
    keys = list(diff_by_map); arr = [np.asarray(diff_by_map[k]) for k in keys]
    ms = []
    for _ in range(B):
        idx = rng.integers(len(arr), size=len(arr))
        v = np.concatenate([arr[i][rng.integers(len(arr[i]), size=len(arr[i]))] for i in idx])
        ms.append(v.mean())
    return float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", required=True, help="comma list of jsonl"); ap.add_argument("--scen", required=True)
    ap.add_argument("--tuned", default=""); ap.add_argument("--out", required=True)
    ap.add_argument("--rl_prefix", default="RL_s"); ap.add_argument("--ref", default="A1")
    a = ap.parse_args()
    rows, errs = load(a.res.split(","))
    rows = [r for r in rows if r["scen"] == a.scen]
    os.makedirs(a.out, exist_ok=True)
    meths = sorted(set(r["method"] for r in rows), key=lambda m: (m.startswith(a.rl_prefix), m))
    by = {m: {(r["path"], r["day"]): r for r in rows if r["method"] == m} for m in meths}
    common = set.intersection(*[set(v) for v in by.values()]) if by else set()
    urg = a.scen.startswith("emerg")
    cols = COLS + (COLS_U if urg else [])
    tuned = json.load(open(a.tuned)) if a.tuned and os.path.exists(a.tuned) else None
    best_non_rl = None
    if tuned:
        cands = [k for k in tuned["best"] if k in by]
        if cands:
            best_non_rl = min(cands, key=lambda k: tuned["grid"][tuned["best"][k]]["J"])   # chosen on DEV, not test
    ref = a.ref if a.ref in by else None
    summ = {}
    for m in meths:
        rr = [by[m][k] for k in common]
        s = {}
        for c, _ in cols:
            v = [r[c] for r in rr if r.get(c) is not None]
            s[c] = float(np.mean(v)) if v else None
        s["strict_all"] = bool(all(r["complete_strict"] for r in rr)) if rr else False
        s["n"] = len(rr)
        s["fallback"] = float(np.mean([r["fallback"] for r in rr])) if rr else None
        summ[m] = s
    # gates
    gates = dict(scen=a.scen, n_episodes=len(common), errors=len(errs), best_non_rl_dev=best_non_rl, ref=ref)
    gates["G0_completion_100"] = all(summ[m]["strict_all"] for m in meths)
    fx = {}
    okfix = True
    for m in meths:
        for k, r in by[m].items():
            key = k[0]
            v = (r["fixed"], r["n_open"], r["n_dabs"], r["n_drones"])
            if key in fx and fx[key] != v:
                okfix = False
            fx[key] = v
    gates["G1_same_stations_fixed_cost"] = okfix
    comps = []
    rls = [m for m in meths if m.startswith(a.rl_prefix)]
    for m in rls:
        for base in [b for b in (ref, best_non_rl) if b]:
            d = [by[m][k]["J"] - by[base][k]["J"] for k in common]
            dm = {}
            for k in common:
                dm.setdefault(k[0], []).append(by[m][k]["J"] - by[base][k]["J"])
            lo, hi = cluster_boot(dm) if dm else (None, None)
            comps.append(dict(rl=m, base=base, meanJ_rl=summ[m]["J"], meanJ_base=summ[base]["J"],
                              diff=float(np.mean(d)) if d else None,
                              rel=float(np.mean(d) / summ[base]["J"] * 100) if d else None,
                              p=wilcoxon_p(d), ci95=(lo, hi), win_rate=float(np.mean([x < 0 for x in d])) if d else None))
    # Holm within each RL seed
    for m in rls:
        cs = sorted([c for c in comps if c["rl"] == m], key=lambda c: c["p"])
        for i, c in enumerate(cs):
            c["p_holm"] = min(1.0, max(c["p"] * (len(cs) - i), cs[i - 1]["p_holm"] if i else 0.0))
    gates["comparisons"] = comps
    def sup(base):
        cs = [c for c in comps if c["base"] == base]
        return bool(cs) and sum(1 for c in cs if c["diff"] < 0 and c["p_holm"] < 0.05) >= max(1, math.ceil(0.67 * len(cs)))
    gates["G2_RL_beats_A1"] = sup(ref) if ref else None
    gates["G3_RL_beats_best_nonRL"] = sup(best_non_rl) if best_non_rl else None
    if best_non_rl:
        gates["G4_safety_noninferior"] = all(summ[m]["inc"] <= summ[best_non_rl]["inc"] + 0.01 for m in rls) if rls else None
    json.dump(dict(summary=summ, gates=gates), open(os.path.join(a.out, "gates.json"), "w"), indent=1)
    # markdown + latex
    def fmt(v, c):
        if v is None:
            return "-"
        if c in ("completion", "ontime_high", "ontime_norm"):
            return f"{100 * v:.1f}%"
        if c in ("n_open", "n_dabs", "n_drones", "launches", "aborts", "inc", "n_urgent"):
            return f"{v:.2f}"
        return f"{v:.1f}"
    hdr = ["方法"] + [h for _, h in cols] + ["ΔJ vs A1"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    tex = ["\\begin{tabular}{l" + "r" * (len(hdr) - 1) + "}", "\\toprule", " & ".join(hdr) + " \\\\", "\\midrule"]
    for m in meths:
        s = summ[m]
        rel = (f"{(s['J'] - summ[ref]['J']) / summ[ref]['J'] * 100:+.2f}%" if ref and s["J"] is not None else "-")
        cells = [m] + [fmt(s[c], c) for c, _ in cols] + [rel]
        lines.append("| " + " | ".join(cells) + " |")
        tex.append(" & ".join(x.replace("%", "\\%") for x in cells) + " \\\\")
    tex += ["\\bottomrule", "\\end{tabular}"]
    md = [f"# 结果 {a.scen}", "", f"episodes (map×day 配对) = {len(common)}; error rows = {len(errs)}", ""] + lines + ["", "## 预注册闸门", ""]
    for k, v in gates.items():
        if k != "comparisons":
            md.append(f"- {k}: {v}")
    md += ["", "## 配对比较 (J, Wilcoxon + Holm, map 聚类 bootstrap 95% CI)", "",
           "| RL | 对照 | RL 均值 | 对照均值 | 差 | 相对 | p_holm | CI95 | 胜率 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in comps:
        md.append(f"| {c['rl']} | {c['base']} | {c['meanJ_rl']:.2f} | {c['meanJ_base']:.2f} | {c['diff']:+.2f} | {c['rel']:+.2f}% | "
                  f"{c['p_holm']:.3g} | [{c['ci95'][0]:+.2f}, {c['ci95'][1]:+.2f}] | {100 * c['win_rate']:.1f}% |")
    open(os.path.join(a.out, "REPORT.md"), "w").write("\n".join(md) + "\n")
    open(os.path.join(a.out, "table.tex"), "w").write("\n".join(tex) + "\n")
    with open(os.path.join(a.out, "per_episode.csv"), "w") as f:
        keys = ["path", "day", "method", "J", "cost", "fixed", "n_open", "n_dabs", "op_min", "dist_km", "launches", "aborts",
                "inc", "ot", "complete_strict", "fallback"] + ([c for c, _ in COLS_U] if urg else [])
        f.write(",".join(keys) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(k, "")) for k in keys) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
