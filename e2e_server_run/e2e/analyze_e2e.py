"""Pre-registered dynamic analysis (PREREG_E2E.md §5-6). Arms = (plan_set, method) pairs from dyn_eval rows.
Primary: J5, map-level paired Wilcoxon (per-map mean over days) of OURS vs each baseline, Holm over baselines,
crossed (map x day) bootstrap 95% CI of the relative difference. Gates G2-G6 per OURS seed; all seeds must pass.
Usage: python e2e/analyze_e2e.py --rows results/dyn_testA.jsonl --scenario base
          --ours OURS_s0=test_e2e:OURS_s0,OURS_s1=test_e2e:OURS_s1,OURS_s2=test_e2e:OURS_s2
          --base TS_A1=test_ts10:A1,TS_N6=test_ts10:N6_90_0.25,TS_Rfc=test_ts10:Rfc_N6_90_0.25,TS_RL5=test_ts10:RL5
          --primary TS_Rfc --ot_ref TS_N6 --out results/dyn_testA.md"""
import os, sys, json, argparse, collections, numpy as np
from scipy.stats import wilcoxon


def holm(ps):
    k = len(ps); order = np.argsort(ps); adj = np.zeros(k); run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (k - r) * ps[i])); adj[i] = run
    return adj


def crossed_boot(A, B, maps, days, reps=2000, seed=0):
    """A,B: dict (map,day)->value. relative difference of means, resampling maps and days independently."""
    rng = np.random.default_rng(seed); out = []
    M = np.array(maps); D = np.array(days)
    for _ in range(reps):
        mm = rng.choice(M, len(M)); dd = rng.choice(D, len(D))
        a = [A[(m, d)] for m in mm for d in dd if (m, d) in A and (m, d) in B]
        b = [B[(m, d)] for m in mm for d in dd if (m, d) in A and (m, d) in B]
        if b:
            out.append(np.mean(a) / np.mean(b) - 1)
    return np.percentile(out, [2.5, 97.5]) * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True); ap.add_argument("--scenario", default="base")
    ap.add_argument("--ours", required=True); ap.add_argument("--base", required=True)
    ap.add_argument("--primary", default="TS_Rfc"); ap.add_argument("--ot_ref", default="TS_N6")
    ap.add_argument("--extra", default="", help="ablation arms, same syntax (Holm family of their own)")
    ap.add_argument("--out", required=True); ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--g2", type=float, default=-15.0); ap.add_argument("--g4", type=float, default=-25.0); ap.add_argument("--g6", type=float, default=20.0)
    a = ap.parse_args()
    rows = collections.defaultdict(dict); nerr = 0
    for l in open(a.rows):
        r = json.loads(l)
        if "error" in r:
            nerr += 1; continue
        if r.get("scenario", "base") != a.scenario:
            continue
        rows[(r["plans"], r["method"])][(r["inst"], r["day"])] = r
    parse = lambda s: [tuple([x.split("=")[0]] + x.split("=")[1].split(":", 1)) for x in s.split(",") if x]
    ours = parse(a.ours); base = parse(a.base); extra = parse(a.extra)
    arms = {n: rows.get((p, m), {}) for n, p, m in ours + base + extra}
    for n, v in arms.items():
        if not v:
            print(f"[warn] arm {n} has no rows")
    common = set.intersection(*[set(v) for v in arms.values() if v]) if arms else set()
    maps = sorted({k[0] for k in common}); days = sorted({k[1] for k in common})
    L = [f"# Dynamic results — scenario `{a.scenario}` ({len(maps)} maps × {len(days)} days = {len(common)} paired runs; worker errors {nerr})\n"]
    METS = [("J", "J5"), ("cost", "cost"), ("fails", "fails"), ("ot_min", "overtime min"), ("late_min_h", "urgent late min"),
            ("ontime_h", "urgent on-time"), ("cvar_h", "CVaR90 late"), ("complete", "completion"), ("mk_last", "makespan (secondary)"), ("ms_p99", "decision p99 ms")]
    L.append("| arm | " + " | ".join(t for _, t in METS) + " |"); L.append("|---" * (len(METS) + 1) + "|")
    mean = lambda arm, k: float(np.mean([arms[arm][c][k] for c in common])) if common else float("nan")
    for n in arms:
        if arms[n]:
            L.append(f"| {n} | " + " | ".join(f"{mean(n, k):.3f}" if k in ("ontime_h", "complete") else f"{mean(n, k):.1f}" for k, _ in METS) + " |")
    def mapmean(arm, k):
        return np.array([np.mean([arms[arm][(m, d)][k] for d in days]) for m in maps])
    gates = {}
    for on, _, _ in ours:
        if not arms[on]:
            continue
        L.append(f"\n## {on} vs baselines (J5; map-level Wilcoxon, Holm over {len(base)} baselines)\n")
        L.append("| baseline | ΔJ5 % | 95% crossed-bootstrap CI | p | Holm p | Δfails % | Δot min | Δon-time_h |"); L.append("|---|---|---|---|---|---|---|---|")
        ps = []; rowsL = []
        for bn, _, _ in base:
            if not arms[bn]:
                continue
            x = mapmean(on, "J"); y = mapmean(bn, "J")
            p = wilcoxon(x, y).pvalue if len(maps) > 1 and np.any(x != y) else 1.0
            ps.append(p)
            A = {c: arms[on][c]["J"] for c in common}; B = {c: arms[bn][c]["J"] for c in common}
            ci = crossed_boot(A, B, maps, days, reps=a.boot)
            dj = (mean(on, "J") / mean(bn, "J") - 1) * 100
            df = (mean(on, "fails") / max(mean(bn, "fails"), 1e-9) - 1) * 100
            rowsL.append([bn, dj, ci, p, df, mean(on, "ot_min") - mean(bn, "ot_min"), mean(on, "ontime_h") - mean(bn, "ontime_h")])
        adj = holm(np.array(ps)) if ps else []
        for r, hp in zip(rowsL, adj):
            L.append(f"| {r[0]} | {r[1]:+.1f}% | [{r[2][0]:+.1f}, {r[2][1]:+.1f}] | {r[3]:.1e} | {hp:.1e} | {r[4]:+.1f}% | {r[5]:+.1f} | {r[6]:+.3f} |")
        prim = [(r, hp) for r, hp in zip(rowsL, adj) if r[0] == a.primary]
        g = {}
        if prim:
            r, hp = prim[0]
            g["G2_J5"] = bool(r[1] <= a.g2 and hp < 0.05)
            g["G4_fails"] = bool(r[4] <= a.g4)
        g["G3_completion"] = bool(all(arms[on][c]["complete"] == 1 for c in common))
        if arms.get(a.ot_ref):
            g["G5_overtime"] = bool(mean(on, "ot_min") <= mean(a.ot_ref, "ot_min"))
        g["G6_latency"] = bool(np.median([arms[on][c]["ms_p99"] for c in common]) <= a.g6)
        gates[on] = g
        L.append("\nGates: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in g.items()))
    if extra:
        L.append(f"\n## Ablations (J5 vs {ours[0][0]}, Holm over ablations)\n")
        L.append("| ablation | ΔJ5 vs full % | p | Holm p | fails | ot | p99 ms |"); L.append("|---|---|---|---|---|---|---|")
        ps = []; rr = []
        for en, _, _ in extra:
            if not arms[en]:
                continue
            x = mapmean(en, "J"); y = mapmean(ours[0][0], "J")
            p = wilcoxon(x, y).pvalue if np.any(x != y) else 1.0
            ps.append(p); rr.append((en, (mean(en, "J") / mean(ours[0][0], "J") - 1) * 100, p))
        for (en, d, p), hp in zip(rr, holm(np.array(ps)) if ps else []):
            L.append(f"| {en} | {d:+.1f}% | {p:.1e} | {hp:.1e} | {mean(en,'fails'):.2f} | {mean(en,'ot_min'):.1f} | {np.median([arms[en][c]['ms_p99'] for c in common]):.1f} |")
    allpass = bool(gates) and all(all(g.values()) for g in gates.values())
    L.append(f"\n**All pre-registered dynamic gates pass for all seeds: {allpass}**")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write("\n".join(L) + "\n"); json.dump(dict(gates=gates, all_pass=allpass, n=len(common)), open(a.out.replace(".md", ".json"), "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
