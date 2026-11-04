"""Tables + paired Wilcoxon (instance-level means over seeds) + Holm. usage: stats.py FILE REF_METHOD BASELINES(comma) [all methods for table]"""
import sys, json, collections, numpy as np
from scipy.stats import wilcoxon
F = sys.argv[1]; REF = sys.argv[2]; BL = sys.argv[3].split(',')
L = [json.loads(l) for l in open(F)]
by = collections.defaultdict(lambda: collections.defaultdict(list))
for x in L: by[x['method']][x['path']].append(x)
MET = ['J', 'cost', 'mk', 'pen', 'ontime', 'ontime_h', 'resp', 'late_h', 'unc', 'ms_per_dec']
print('%-26s' % 'method' + ''.join('%10s' % m for m in MET) + '   n')
for k in sorted(by, key=lambda k: np.mean([x['J'] for v in by[k].values() for x in v])):
    v = [x for vv in by[k].values() for x in vv]
    print('%-26s' % k[:26] + ''.join('%10.3f' % np.mean([x[m] for x in v]) for m in MET) + '  %d' % len(v))
def inst(meth, m): return {p: np.mean([x[m] for x in v]) for p, v in by[meth].items()}
tests = []
for b in BL:
    for m, better in [('J', -1), ('ontime_h', 1), ('ontime', 1), ('mk', -1), ('resp', -1), ('cost', -1), ('pen', -1)]:
        a = inst(REF, m); c = inst(b, m); ks = sorted(set(a) & set(c))
        x = np.array([a[k] for k in ks]); y = np.array([c[k] for k in ks]); d = x - y
        p = wilcoxon(x, y).pvalue if np.any(d != 0) else 1.0
        win = int(((d * better) > 1e-12).sum()); lose = int(((d * better) < -1e-12).sum())
        rel = d.mean() / abs(y.mean()) * 100 if y.mean() != 0 else 0
        tests.append([b, m, d.mean(), rel, win, lose, p])
ps = np.array([t[-1] for t in tests]); o = np.argsort(ps); n = len(ps); adj = np.zeros(n); run = 0
for r, i in enumerate(o): run = max(run, min(1, (n - r) * ps[i])); adj[i] = run
print(f'\n{REF} minus baseline (instance-level, n=#instances), Holm over {n} tests')
print('%-22s %-9s %10s %8s %5s %5s %10s %10s' % ('baseline', 'metric', 'diff', 'rel%', 'win', 'lose', 'p', 'p_holm'))
for t, a in zip(tests, adj): print('%-22s %-9s %10.3f %8.2f %5d %5d %10.2g %10.2g' % (t[0][:22], t[1], t[2], t[3], t[4], t[5], t[6], a))
