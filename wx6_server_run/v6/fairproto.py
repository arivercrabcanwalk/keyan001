"""Fair-comparison protocol, v6 (paper 1). Reusable module; mirrored in docs/PROTOCOL_FAIR_V6_ZH.md.

P0  Data contract. One row per (plan_set, map, method, day, scenario). Compact fields (CSV export):
    map, day, scenario, plan_set, method, seed, J5, cost, ot, late_h, late_n, fails, complete_strict, n_dabs,
    fixed_cost, latency_p99_ms (+ latency_mean_ms, n_backup, ontime_h).
P1  Completion first. complete_strict = all planned targets done AND every urgent request served inside the
    operational window, denominator independent of siting (only requests not coverable by ANY candidate station as
    DABS are excluded; 0 by construction in WX-E6). An arm with < 100 % strict completion on any (map, day) FAILS
    the gate; no other metric of that arm is interpreted (reported with a dagger).
P2  Siting parity. Every hypothesis compares arms that execute the IDENTICAL plan (same station types, same routes,
    hence same n_dabs and fixed cost); check_parity() verifies it row by row. Siting variants (author-adapted
    TSALNS-Cov, post-hoc repair TSR, PAD = all stations DABS) are separate plan sets on which EVERY execution method
    is run, so a gain can never come from opening more stations.
P3  Strongest fair baseline (SB) chosen BEFORE testing, on dev only, among all non-RL arms (incl. shielded variants
    and tuned re-optimisation budgets) by min dev J5 subject to 100 % strict completion; frozen in SB_FREEZE.json.
P4  Equal information: every policy sees the same observable state (forecast, nowcast, alarms, fleet state); fair
    rollouts sample futures only from observable information; the clairvoyant O is reported but never tested/bolded.
P5  Equal compute / latency classes: real-time class (<= 100 ms / decision, p99 reported) and look-ahead class
    (100 ms in-sim deadline rollouts). RL is compared within its class and against everything slower.
P6  Statistics. Unit = map (day-averaged) Wilcoxon signed-rank (two-sided) + Holm within each preregistered family;
    day-cluster Wilcoxon (weather is shared across maps on a day); crossed map x day bootstrap (2000) for the 95 % CI
    of the relative difference. CONFIRMED = p_Holm < .05 AND p_day < .05 AND crossed CI excludes 0.
    Per-seed confirmation is reported for every seed (no seed may be dropped); the main claim uses the seed mean
    and additionally requires >= 4 of 5 seeds individually confirmed.
P7  Fresh test days never used for training/tuning; maps of Test-G/Test-L generated after the preregistration.
"""
import json, os, csv
from collections import defaultdict
import numpy as np

COMPACT = [("map", "map"), ("day", "day"), ("scenario", "scenario"), ("plan_set", "plan_set"), ("method", "method"),
           ("seed", "seed"), ("J5", "J"), ("cost", "cost"), ("ot", "ot_min"), ("late_h", "late_min_h"),
           ("late_n", "late_min_n"), ("fails", "fails"), ("complete_strict", "complete_strict"), ("n_dabs", "n_dabs"),
           ("fixed_cost", "fixed"), ("latency_p99_ms", "ms_p99"), ("latency_mean_ms", "ms_mean"),
           ("n_backup", "n_backup"), ("ontime_h", "ontime_h"), ("n_urgent", "n")]


def load_rows(paths):
    rows = []
    for p in paths:
        if not os.path.exists(p):
            continue
        for l in open(p):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if "error" in r:
                r["complete_strict"] = 0      # P1: a crash counts as incomplete
            rows.append(r)
    return rows


def export_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow([c for c, _ in COMPACT])
        for r in rows:
            w.writerow([r.get(k, "") for _, k in COMPACT])


def table(rows, plan_set=None, scenario=None):
    """-> {method: {(map, day): row}}"""
    t = defaultdict(dict)
    for r in rows:
        if plan_set and r.get("plan_set") != plan_set:
            continue
        if scenario and r.get("scenario") != scenario:
            continue
        t[r["method"]][(r["map"], r["day"])] = r
    return t


def seed_mean(t, prefix, name):
    ss = sorted(m for m in t if m.startswith(prefix) and m[len(prefix):].isdigit())
    if not ss:
        return []
    keys = set.intersection(*[set(t[s]) for s in ss])
    num = ["J", "cost", "ot_min", "late_min_h", "late_min_n", "fails", "ms_p99", "ms_mean", "n_backup", "ontime_h",
           "mk", "fixed", "n_dabs", "cvar_h"]
    t[name] = {}
    for k in keys:
        r = {m: float(np.mean([t[s][k].get(m, 0.0) for s in ss])) for m in num}
        r["complete_strict"] = int(min(t[s][k].get("complete_strict", 0) for s in ss))
        r["map"], r["day"] = k
        t[name][k] = r
    return ss


def gate(t, methods, expected_n=None):
    g = {}
    for m in methods:
        v = list(t.get(m, {}).values())
        n = len(v); c = float(np.mean([r.get("complete_strict", 0) for r in v])) if v else 0.0
        g[m] = dict(n=n, complete_strict=c, n_incomplete=int(sum(1 for r in v if not r.get("complete_strict", 0))),
                    n_unservable_all=int(sum(r.get("n_unservable_all", 0) for r in v)),
                    passed=bool(v and c >= 1.0 - 1e-12 and (expected_n is None or n == expected_n)))
    return g


def check_parity(t, a, b):
    """Siting parity: same n_dabs and fixed cost on every common unit."""
    bad = 0; n = 0
    for k in set(t.get(a, {})) & set(t.get(b, {})):
        n += 1
        ra, rb = t[a][k], t[b][k]
        if abs(ra.get("fixed", 0) - rb.get("fixed", 0)) > 1e-6 or ra.get("n_dabs") != rb.get("n_dabs"):
            bad += 1
    return dict(n=n, mismatches=bad, ok=bad == 0)


def holm(ps):
    ps = np.asarray(ps, dtype=float); n = len(ps); o = np.argsort(ps); adj = np.zeros(n); run = 0.0
    for r, i in enumerate(o):
        run = max(run, min(1.0, (n - r) * ps[i])); adj[i] = run
    return adj


def _wil(x, y):
    from scipy.stats import wilcoxon
    d = np.asarray(x) - np.asarray(y)
    if len(d) < 2 or not np.any(np.abs(d) > 1e-12):
        return 1.0
    try:
        return float(wilcoxon(x, y, zero_method="wilcox").pvalue)
    except ValueError:
        return 1.0


def compare(t, a, b, metric="J", better=-1, B=2000, seed=0):
    """a vs b on common (map, day) units. rel = (mean_a - mean_b) / mean_b * 100."""
    keys = sorted(set(t.get(a, {})) & set(t.get(b, {})))
    if not keys:
        return dict(n=0, a=a, b=b, metric=metric)
    maps = sorted({k[0] for k in keys}); days = sorted({k[1] for k in keys})
    mi = {m: i for i, m in enumerate(maps)}; di = {d: i for i, d in enumerate(days)}
    XA = np.full((len(maps), len(days)), np.nan); XB = np.full_like(XA, np.nan)
    for k in keys:
        XA[mi[k[0]], di[k[1]]] = float(t[a][k].get(metric, 0.0)); XB[mi[k[0]], di[k[1]]] = float(t[b][k].get(metric, 0.0))
    ma, mb = np.nanmean(XA, 1), np.nanmean(XB, 1)
    da, db = np.nanmean(XA, 0), np.nanmean(XB, 0)
    p_map = _wil(ma, mb); p_day = _wil(da, db)
    mean_a, mean_b = float(np.nanmean(XA)), float(np.nanmean(XB))
    rel = (mean_a - mean_b) / (abs(mean_b) + 1e-12) * 100
    rng = np.random.default_rng(seed); bs = []
    for _ in range(B):
        im = rng.integers(0, len(maps), len(maps)); idd = rng.integers(0, len(days), len(days))
        sa = np.nanmean(XA[np.ix_(im, idd)]); sb = np.nanmean(XB[np.ix_(im, idd)])
        bs.append((sa - sb) / (abs(sb) + 1e-12) * 100)
    lo, hi = float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    dm = (ma - mb) * better
    return dict(n=len(keys), n_maps=len(maps), n_days=len(days), a=a, b=b, metric=metric, better=better,
                mean_a=mean_a, mean_b=mean_b, rel=rel, ci=(lo, hi), p=p_map, p_day=p_day,
                map_win=int((dm > 1e-12).sum()), map_lose=int((dm < -1e-12).sum()))


def family(t, a, bases, metric="J", better=-1, B=2000):
    res = [compare(t, a, b, metric, better, B) for b in bases]
    res = [r for r in res if r.get("n")]
    adj = holm([r["p"] for r in res]) if res else []
    for r, pa in zip(res, adj):
        r["p_holm"] = float(pa)
        good = (r["rel"] * r["better"] > 0)
        r["confirmed"] = bool(pa < 0.05 and r["p_day"] < 0.05 and (r["ci"][0] > 0 or r["ci"][1] < 0) and good)
        r["confirmed_worse"] = bool(pa < 0.05 and r["p_day"] < 0.05 and (r["ci"][0] > 0 or r["ci"][1] < 0) and not good)
    return res
