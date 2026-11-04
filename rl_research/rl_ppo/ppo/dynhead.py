"""Dynamic-vs-static headroom (CV over seeds): per (lam,sec) choose best spec on half the seeds among
STATIC set vs ALL (static+dynamic) set, evaluate on other half; values = % vs norl:4 paired."""
import sys, json, collections, numpy as np
from scipy.stats import wilcoxon
D = collections.defaultdict(dict)
for f in sys.argv[1:]:
    for l in open(f):
        j = json.loads(l); D[(j['inst'], j['lam'], j['seed'], j['sec'])][j['spec']] = j['objective']
specs = sorted(set.intersection(*[set(v) for v in D.values()]))
st = [s for s in specs if s.startswith(('s:', 'norl:'))]
seeds = sorted({k[2] for k in D}); h = len(seeds) // 2
R = {k: {s: (v[s] / v['norl:4'] - 1) * 100 for s in specs} for k, v in D.items()}
def cv(cands):
    out = {}
    for A, B in ((seeds[:h], seeds[h:]), (seeds[h:], seeds[:h])):
        for ctx in {(k[1], k[3]) for k in R}:
            m = {s: np.mean([R[k][s] for k in R if (k[1], k[3]) == ctx and k[2] in A]) for s in cands}
            c = min(m, key=m.get)
            for k in R:
                if (k[1], k[3]) == ctx and k[2] in B: out[k] = R[k][c]
    return out
a = cv(st); b = cv(specs)
ks = sorted(a); x = np.array([a[k] for k in ks]); y = np.array([b[k] for k in ks])
print('specs', len(specs), 'static', len(st), 'cells', len(ks))
print(f'best static (CV) vs norl:4: {x.mean():+.3f}%   best any (CV): {y.mean():+.3f}%   dyn-static: {(y-x).mean():+.3f}%  p={wilcoxon(y,x).pvalue:.3g}')
for ctx in sorted({(k[1], k[3]) for k in ks}):
    i = [n for n, k in enumerate(ks) if (k[1], k[3]) == ctx]
    print(ctx, f'static {x[i].mean():+.3f} any {y[i].mean():+.3f} diff {(y[i]-x[i]).mean():+.3f}')
