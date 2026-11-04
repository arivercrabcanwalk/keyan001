import json, collections, numpy as np, sys
from scipy.stats import wilcoxon
L = [json.loads(l) for f in ['/tmp/m30.jsonl', 'results/test_rollb30.jsonl'] for l in open(f)]
idx = collections.defaultdict(dict)
for x in L: idx[x['method']][(x['path'], x['seed'])] = x
MET = [('J', -1), ('ontime', 1), ('ontime_h', 1), ('resp', -1), ('mk', -1), ('cost', -1)]
rows = []; tests = []
for rm in ['rollb30_1', 'rollb30_8', 'rollb30_32']:
    keys = sorted(idx[rm]); n = len(keys)
    for meth in ['RL3', 'static30', rm]:
        v = [idx[meth][k] for k in keys]
        rows.append((rm, meth, n, *[np.mean([x[m] for x in v]) for m, _ in MET], np.mean([x['ms_per_dec'] for x in v])))
    paths = sorted({k[0] for k in keys})
    for m, b in MET:
        a = np.array([np.mean([idx['RL3'][k][m] for k in keys if k[0] == p]) for p in paths]); c = np.array([np.mean([idx[rm][k][m] for k in keys if k[0] == p]) for p in paths])
        d = a - c; p = wilcoxon(a, c).pvalue if np.any(d) else 1
        tests.append([rm, m, d.mean(), d.mean() / abs(c.mean()) * 100, int((d * b > 0).sum()), int((d * b < 0).sum()), p])
ps = np.array([t[-1] for t in tests]); o = np.argsort(ps); adj = np.zeros(len(ps)); run = 0
for r, i in enumerate(o): run = max(run, min(1, (len(ps) - r) * ps[i])); adj[i] = run
print('%-11s %-9s %5s' % ('subset', 'method', 'days') + ''.join('%10s' % m for m, _ in MET) + '  ms/dec')
for r in rows: print('%-11s %-9s %5d' % r[:3] + ''.join('%10.3f' % x for x in r[3:-1]) + '  %.3f' % r[-1])
print('\nRL3 - rollout (instance-level, Holm over %d)' % len(ps))
for t, a in zip(tests, adj): print('%-11s %-9s %9.3f %7.2f%% win %2d lose %2d p=%.2g p_holm=%.2g' % (*t, a))
