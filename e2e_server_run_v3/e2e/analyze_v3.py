"""v3 analysis: compact raw CSV, tables, pre-registered gates (PREREG_E2E_V3.md) with Holm families and bootstrap.

Arms are '<plans>|<method>' (dyn rows) and may contain '{s}' = seed placeholder (expanded over --seeds; a seeded arm's
per-(map,day) value is the mean over seeds, and per-seed results are reported for the >=4/5-seed rule).
Usage: python e2e/analyze_v3.py --dyn 'results/dyn/*.jsonl' --plans_dir results/plans --gates gates_v3.json --out results/analysis
"""
import os, sys, json, glob, argparse, re, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COLS = ["map", "day", "scenario", "plans", "method", "seed", "J5", "cost", "ot", "late_h", "late_n", "fails", "complete_strict",
        "n_dabs", "fixed_cost", "latency_p99_ms", "n_offload"]


def load(dyn_glob, plans_dir):
    rows = []; errs = 0
    plan_meta = {}
    for f in sorted(glob.glob(os.path.join(plans_dir, "*.jsonl"))) if plans_dir else []:
        nm = os.path.basename(f)[:-6]
        for l in open(f):
            r = json.loads(l); t = r["solution"]["station_types"]
            plan_meta[(nm, os.path.basename(r["path"]).replace(".txt", ""))] = (sum(1 for x in t if x == 2), 27.8 * sum(1 for x in t if x == 1) + 43.4 * sum(1 for x in t if x == 2))
    for f in sorted(glob.glob(dyn_glob)):
        for l in open(f):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if "error" in r:
                errs += 1; continue
            m = re.search(r"_s(\d+)$", r["plans"]); seed = int(m.group(1)) if m else -1
            ms = re.search(r"_s(\d+)$", r["method"]); seed = int(ms.group(1)) if ms and seed < 0 else seed
            nd, fx = plan_meta.get((r["plans"], r["inst"]), (None, r.get("fixed")))
            rows.append(dict(map=r["inst"], day=r["day"], scenario=r["scenario"], plans=r["plans"], method=r["method"], seed=seed,
                             J5=r["J"], cost=r["cost"], ot=r["ot_min"], late_h=r["late_min_h"], late_n=r["late_min_n"], fails=r["fails"],
                             complete_strict=r["complete_strict"], n_dabs=nd, fixed_cost=fx, latency_p99_ms=r.get("ms_p99"), n_offload=r.get("n_offload", 0)))
    return rows, errs


def index(rows):
    D = {}
    for r in rows:
        D.setdefault((r["scenario"], f"{r['plans']}|{r['method']}"), {})[(r["map"], r["day"])] = r
    return D


def arm_vals(D, scen, arm, seeds, key="J5"):
    """{(map,day): value}  (seed-mean for seeded arms) and per-seed dicts."""
    if "{s}" not in arm:
        d = D.get((scen, arm), {}); return {k: v[key] for k, v in d.items()}, None
    per = {}
    for s in seeds:
        d = D.get((scen, arm.replace("{s}", str(s))))
        if d:
            per[s] = {k: v[key] for k, v in d.items()}
    if not per:
        return {}, {}
    keys = set.intersection(*[set(v) for v in per.values()])
    return {k: float(np.mean([per[s][k] for s in per])) for k in keys}, per


def boot_ci(diff_by_map, B=5000, seed=0):
    """two-level bootstrap (maps, then days within map) of the mean relative difference."""
    rng = np.random.default_rng(seed); maps = list(diff_by_map); out = np.zeros(B)
    arr = [np.asarray(diff_by_map[m]) for m in maps]
    for b in range(B):
        idx = rng.integers(len(maps), size=len(maps))
        out[b] = np.mean([arr[i][rng.integers(len(arr[i]), size=len(arr[i]))].mean() for i in idx])
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def compare(D, scen, a, b, seeds, key="J5"):
    from scipy.stats import wilcoxon
    va, pa = arm_vals(D, scen, a, seeds, key); vb, _ = arm_vals(D, scen, b, seeds, key)
    ks = sorted(set(va) & set(vb))
    if len(ks) < 5:
        return None
    A = np.array([va[k] for k in ks]); Bv = np.array([vb[k] for k in ks])
    rel = (A.mean() - Bv.mean()) / Bv.mean() * 100
    bym = {}
    for k, x, y in zip(ks, A, Bv):
        bym.setdefault(k[0], []).append(x - y)
    mm = np.array([np.mean(v) for v in bym.values()])
    p_less = float(wilcoxon(mm, alternative="less").pvalue) if np.any(mm != 0) else 1.0
    p_greater = float(wilcoxon(mm, alternative="greater").pvalue) if np.any(mm != 0) else 1.0
    lo, hi = boot_ci({m: np.asarray(v) / Bv.mean() * 100 for m, v in bym.items()})
    seed_wins = None
    if pa:
        seed_wins = []
        for s, d in pa.items():
            kk = [k for k in ks if k in d]
            seed_wins.append(int(np.mean([d[k] for k in kk]) < np.mean([vb[k] for k in kk])))
    return dict(a=a, b=b, scenario=scen, n=len(ks), n_maps=len(bym), mean_a=float(A.mean()), mean_b=float(Bv.mean()), rel_pct=float(rel),
                ci95_pct=[lo, hi], p_less=p_less, p_greater=p_greater, seed_wins=seed_wins)


_PC = {}


def plan_costs(plans_dir, name):
    if name not in _PC:
        f = os.path.join(plans_dir, name + ".jsonl")
        _PC[name] = {os.path.basename(json.loads(l)["path"]).replace(".txt", ""): json.loads(l)["cost"] for l in open(f)} if os.path.exists(f) else {}
    return _PC[name]


def compare_static(plans_dir, a, b, seeds):
    from scipy.stats import wilcoxon
    vb = plan_costs(plans_dir, b)
    per = {s: plan_costs(plans_dir, a.replace("{s}", str(s))) for s in (seeds if "{s}" in a else [None])}
    per = {s: d for s, d in per.items() if d}
    if not per or not vb:
        return None
    ks = sorted(set.intersection(*[set(d) for d in per.values()]) & set(vb))
    if len(ks) < 5:
        return None
    A = np.array([np.mean([d[k] for d in per.values()]) for k in ks]); B = np.array([vb[k] for k in ks])
    dif = A - B
    p_less = float(wilcoxon(dif, alternative="less").pvalue) if np.any(dif != 0) else 1.0
    rng = np.random.default_rng(0); bs = [np.mean((dif / B)[rng.integers(len(ks), size=len(ks))]) * 100 for _ in range(5000)]
    sw = [int(np.mean([d[k] for k in ks]) < np.mean([vb[k] for k in ks])) for d in per.values()] if "{s}" in a else None
    return dict(a=a, b=b, scenario="static", n=len(ks), n_maps=len(ks), mean_a=float(A.mean()), mean_b=float(B.mean()),
                rel_pct=float((A / B - 1).mean() * 100), ci95_pct=[float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
                p_less=p_less, p_greater=1.0 - p_less, seed_wins=sw)


def holm(ps):
    order = np.argsort(ps); m = len(ps); adj = np.zeros(m); run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i])); adj[i] = run
    return adj.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dyn", required=True); ap.add_argument("--plans_dir", default="")
    ap.add_argument("--static", default="", help="glob of static summary jsonl (plan rows) for static tables")
    ap.add_argument("--gates", default=""); ap.add_argument("--seeds", default="0 1 2 3 4"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); seeds = [int(x) for x in a.seeds.split()]
    rows, errs = load(a.dyn, a.plans_dir)
    import csv
    with open(os.path.join(a.out, "raw_per_instance.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    D = index(rows)
    md = [f"# E2E v3 analysis\n\nrows={len(rows)} error_rows={errs}\n", "## Arms (mean over map x day)\n",
          "| scenario | arm | n | strict % | J5 | cost | ot | late_h | late_n | fails | #DABS | fixed | p99 ms | offl |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    summ = {}
    for (sc, arm), d in sorted(D.items()):
        v = list(d.values()); g = lambda k: np.mean([x[k] for x in v if x[k] is not None]) if any(x[k] is not None for x in v) else float("nan")
        s = dict(n=len(v), strict=100 * g("complete_strict"), J5=g("J5"), cost=g("cost"), ot=g("ot"), late_h=g("late_h"), late_n=g("late_n"),
                 fails=g("fails"), n_dabs=g("n_dabs"), fixed=g("fixed_cost"), p99=float(np.quantile([x["latency_p99_ms"] or 0 for x in v], 0.99)), off=g("n_offload"))
        summ[f"{sc}|{arm}"] = s
        md.append(f"| {sc} | {arm} | {s['n']} | {s['strict']:.2f} | {s['J5']:.1f} | {s['cost']:.1f} | {s['ot']:.1f} | {s['late_h']:.2f} | {s['late_n']:.2f} | {s['fails']:.2f} | {s['n_dabs']:.2f} | {s['fixed']:.1f} | {s['p99']:.2f} | {s['off']:.2f} |")
    gates_out = {}
    if a.gates and os.path.exists(a.gates):
        G = json.load(open(a.gates))
        md.append("\n## Pre-registered comparisons (Holm within family; Wilcoxon on per-map means; 2-level bootstrap 95% CI)\n")
        for fam, comps in G.get("families", {}).items():
            res = [compare_static(a.plans_dir, c["a"], c["b"], seeds) if c.get("kind") == "static" else
                   compare(D, c.get("scenario", "base"), c["a"], c["b"], seeds, c.get("key", "J5")) for c in comps]
            ok_idx = [i for i, r in enumerate(res) if r]
            kind = [comps[i].get("type", "sup") for i in ok_idx]
            ps = [res[i]["p_less"] if k == "sup" else res[i]["p_greater"] for i, k in zip(ok_idx, kind)]
            adj = holm(ps) if ps else []
            md.append(f"### {fam}\n\n| a | b | scen | n | rel % | 95% CI | p_holm | seeds a<b | pass |\n|---|---|---|---|---|---|---|---|---|")
            for j, i in enumerate(ok_idx):
                r = res[i]; c = comps[i]; r["p_holm"] = adj[j]
                if c.get("type", "sup") == "sup":
                    ok = adj[j] < 0.05 and r["rel_pct"] < 0 and (r["seed_wins"] is None or sum(r["seed_wins"]) >= min(4, len(r["seed_wins"])))
                else:                                 # non-inferiority: upper CI below margin (absolute key units or %)
                    marg = c.get("margin_pct", 2.0); ok = r["ci95_pct"][1] < marg
                r["pass"] = bool(ok)
                md.append(f"| {r['a']} | {r['b']} | {r['scenario']} | {r['n']} | {r['rel_pct']:+.2f} | [{r['ci95_pct'][0]:+.2f}, {r['ci95_pct'][1]:+.2f}] | {adj[j]:.2g} | {r['seed_wins']} | {'PASS' if ok else 'fail'} |")
            for i, c in enumerate(comps):
                if not res[i]:
                    md.append(f"| {c['a']} | {c['b']} | {c.get('scenario','base')} | - | missing | | | | n/a |")
            gates_out[fam] = [r for r in res if r]
        # strict-completion gate G3: every listed arm must be 100 % strict in every scenario it was run
        g3 = G.get("strict_arms", [])
        bad = {k: v["strict"] for k, v in summ.items() if any(re.fullmatch(p.replace("{s}", r"\d+").replace("|", r"\|"), k.split("|", 1)[1]) for p in g3) and v["strict"] < 100.0}
        gates_out["G3_strict"] = dict(pass_=not bad, violations=bad)
        md.append(f"\n### G3 strict completion (100 % required)\n\n{'PASS' if not bad else 'FAIL: ' + json.dumps(bad)}\n")
        fac = G.get("factorial")
        if fac:
            md.append(f"\n## Factorial (scenario {fac.get('scenario','base')}, mean J5; rows = plans, cols = exec)\n")
            md.append("| plans \\ exec | " + " | ".join(fac["cols"]) + " |"); md.append("|---" * (len(fac["cols"]) + 1) + "|")
            for rp in fac["rows"]:
                cells = []
                for cm in fac["cols"]:
                    v, _ = arm_vals(D, fac.get("scenario", "base"), f"{rp}|{cm}", seeds)
                    cells.append(f"{np.mean(list(v.values())):.1f}" if v else "-")
                md.append(f"| {rp} | " + " | ".join(cells) + " |")
    if a.static:
        md.append("\n## Static plans (official evaluator cost)\n\n| plan set | n | mean cost | feasible | cov_feasible | #DABS | fixed | wall s |\n|---|---|---|---|---|---|---|---|")
        for f in sorted(glob.glob(a.static)):
            P = [json.loads(l) for l in open(f)]
            P = [r for r in P if "cost" in r and "solution" in r]
            if not P:
                continue
            t = [r["solution"]["station_types"] for r in P]
            md.append(f"| {os.path.basename(f)[:-6]} | {len(P)} | {np.mean([r['cost'] for r in P]):.2f} | {np.mean([bool(r.get('feasible')) for r in P]):.3f} | "
                      f"{np.mean([bool(r.get('cov_feasible', True)) for r in P]):.3f} | {np.mean([sum(x == 2 for x in tt) for tt in t]):.2f} | "
                      f"{np.mean([27.8 * sum(x == 1 for x in tt) + 43.4 * sum(x == 2 for x in tt) for tt in t]):.1f} | {np.mean([r.get('wall', r.get('sec', 0)) for r in P]):.2f} |")
    open(os.path.join(a.out, "ANALYSIS_V3.md"), "w").write("\n".join(md) + "\n")
    json.dump(dict(summary=summ, gates=gates_out), open(os.path.join(a.out, "analysis_v3.json"), "w"), indent=1, default=float)
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
