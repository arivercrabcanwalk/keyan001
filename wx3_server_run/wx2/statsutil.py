"""Paired Wilcoxon signed-rank + Holm, bootstrap CI. Instance-level means."""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import math
import numpy as np
from scipy.stats import wilcoxon


def holm(ps):
    ps = np.asarray(ps, dtype=float)
    n = len(ps)
    o = np.argsort(ps)
    adj = np.zeros(n)
    run = 0.0
    for r, i in enumerate(o):
        run = max(run, min(1.0, (n - r) * ps[i]))
        adj[i] = run
    return adj


def inst_means(rows, method, metric, inst_key="path"):
    from collections import defaultdict
    by = defaultdict(list)
    for r in rows:
        if r["method"] == method:
            by[r[inst_key]].append(r[metric])
    return {k: float(np.mean(v)) for k, v in by.items()}


def paired(rows, meth_a, meth_b, metric, inst_key="path", better=-1):
    """a minus b, instance-level. better=-1 means smaller is better."""
    A = inst_means(rows, meth_a, metric, inst_key)
    B = inst_means(rows, meth_b, metric, inst_key)
    ks = sorted(set(A) & set(B))
    if not ks:
        return dict(n=0)
    x = np.array([A[k] for k in ks])
    y = np.array([B[k] for k in ks])
    d = x - y
    try:
        p = float(wilcoxon(x, y, zero_method="wilcox").pvalue) if np.any(np.abs(d) > 1e-15) else 1.0
    except ValueError:
        p = 1.0
    win = int(((d * better) > 1e-12).sum())
    lose = int(((d * better) < -1e-12).sum())
    rel = float(d.mean() / (abs(y.mean()) + 1e-12) * 100)
    # bootstrap CI on mean relative and absolute, resample instances
    rng = np.random.default_rng(0)
    boots = []
    boots_rel = []
    ratio = []
    N = 10000
    for _ in range(N):
        idx = rng.integers(0, len(ks), len(ks))
        boots.append(d[idx].mean())
        ym = y[idx].mean()
        boots_rel.append(d[idx].mean() / (abs(ym) + 1e-12) * 100)
        ratio.append(x[idx].mean() / (y[idx].mean() + 1e-12))
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    ci_rel = (float(np.percentile(boots_rel, 2.5)), float(np.percentile(boots_rel, 97.5)))
    ci_ratio = (float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5)))
    return dict(n=len(ks), mean_a=float(x.mean()), mean_b=float(y.mean()),
                diff=float(d.mean()), rel=rel, win=win, lose=lose, p=p,
                ci=ci, ci_rel=ci_rel, ci_ratio=ci_ratio,
                better=better, metric=metric, a=meth_a, b=meth_b)


def family_tests(rows, ref, baselines, metrics, inst_key="path"):
    tests = []
    for b in baselines:
        for m, better in metrics:
            t = paired(rows, ref, b, m, inst_key, better)
            tests.append(t)
    ps = [t.get("p", 1.0) for t in tests]
    adj = holm(ps) if tests else []
    for t, a in zip(tests, adj):
        t["p_holm"] = float(a)
    return tests
