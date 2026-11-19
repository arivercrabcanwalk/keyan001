"""Paired statistical analysis for CA-RL experiments (no SciPy dependency).

Implements the exact two-sided Wilcoxon signed-rank test for n <= 50 and a
normal approximation with tie/zero correction beyond that, paired bootstrap
confidence intervals for the mean difference, and Holm correction.
"""
import math
import random

import numpy as np


def wilcoxon_signed_rank(x, y):
    """Paired two-sided Wilcoxon signed-rank test, tie-aware."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    d = d[np.abs(d) > 1e-12]
    n = len(d)
    if n == 0:
        return {"n": 0, "statistic": 0.0, "p_value": 1.0, "method": "empty"}
    ranks = _rankdata(np.abs(d))
    w_plus = float(np.sum(ranks[d > 0]))
    w_minus = float(np.sum(ranks[d < 0]))
    w = min(w_plus, w_minus)
    if n <= 50:
        ranks2 = [int(round(2.0 * r)) for r in ranks]
        w_plus2 = int(round(2.0 * w_plus))
        p = _exact_two_sided_tied(ranks2, w_plus2)
        method = "exact_tie_aware"
    else:
        mean = float(np.sum(ranks)) / 2.0
        var = float(np.sum(ranks * ranks)) / 4.0
        z = max(0.0, abs(w_plus - mean) - 0.5) / math.sqrt(var) if var > 0 else 0.0
        p = 2.0 * _norm_cdf(-z)
        method = "normal_tie_corrected"
    rank_total = w_plus + w_minus
    rank_biserial = ((w_plus - w_minus) / rank_total) if rank_total else 0.0
    return {"n": n, "statistic": w, "p_value": min(1.0, p), "method": method,
            "w_plus": w_plus, "w_minus": w_minus,
            "rank_biserial": float(rank_biserial)}


def _exact_two_sided_tied(ranks2, observed_w_plus2):
    """Exact sign-permutation distribution for average ranks including ties."""
    counts = {0: 1}
    for rank in ranks2:
        nxt = dict(counts)
        for subtotal, count in counts.items():
            key = subtotal + rank
            nxt[key] = nxt.get(key, 0) + count
        counts = nxt
    total = 1 << len(ranks2)
    lower = sum(count for value, count in counts.items() if value <= observed_w_plus2)
    upper = sum(count for value, count in counts.items() if value >= observed_w_plus2)
    return min(1.0, 2.0 * min(lower, upper) / total)

def _rankdata(a):
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1, dtype=float)
    # average ties
    vals = a[order]
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and abs(vals[j + 1] - vals[i]) < 1e-12:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return ranks


def _exact_two_sided(n, w):
    # distribution of the signed-rank sum for n <= 50 via DP on counts
    maxsum = n * (n + 1) // 2
    counts = [0] * (maxsum + 1)
    counts[0] = 1
    for k in range(1, n + 1):
        for s in range(maxsum, k - 1, -1):
            counts[s] += counts[s - k]
    total = 1 << n
    tail = sum(counts[:w + 1])
    return min(1.0, 2.0 * tail / total)


def _norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def bootstrap_ci(x, y, n_boot=10000, alpha=0.05, seed=12345):
    """Paired bootstrap CI for mean(x) - mean(y)."""
    rng = np.random.default_rng(seed)
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    n = len(d)
    if n == 0:
        return {"mean": None, "lo": None, "hi": None}
    idx = rng.integers(0, n, size=(n_boot, n))
    means = d[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {"mean": float(d.mean()), "lo": float(lo), "hi": float(hi),
            "n_boot": n_boot}


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (m - rank) * p[i])
        running = max(running, val)
        adj[i] = running
    return adj.tolist()


def paired_summary(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d = x - y
    return {
        "n": int(len(d)),
        "mean_x": float(x.mean()) if len(x) else None,
        "mean_y": float(y.mean()) if len(y) else None,
        "mean_diff": float(d.mean()) if len(d) else None,
        "median_diff": float(np.median(d)) if len(d) else None,
        "pct_diff": float(100.0 * d.mean() / y.mean()) if len(d) and y.mean() else None,
        "wins": int(np.sum(d < -1e-9)),
        "losses": int(np.sum(d > 1e-9)),
        "ties": int(np.sum(np.abs(d) <= 1e-9)),
        "sd_diff": float(d.std(ddof=1)) if len(d) > 1 else 0.0,
        "cohen_dz": (float(d.mean() / d.std(ddof=1))
                     if len(d) > 1 and d.std(ddof=1) > 1e-12 else 0.0),
    }
