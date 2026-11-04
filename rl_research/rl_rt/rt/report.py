"""Summarise go/no-go: gaps (%) of each method vs reference = best of norl_8 10s (2 seeds) [and TSALNS 30s at lam 0]."""
import sys, json, collections, numpy as np
from scipy.stats import wilcoxon
rows = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
ref = {}; ts = {}
for r in rows:
    if r['method'] == 'norl_8':
        key = (r['inst'], r['lam']); ref[key] = min(ref.get(key, 1e18), r['objective'])
    if r['method'] == 'tsalns': ts[r['inst']] = r['cost']
G = collections.defaultdict(list)
for r in rows:
    if r['method'] in ('norl_8',): continue
    tag = r['method'] + (f"@{r['seconds']}" if 'seconds' in r and r['method'] != 'tsalns' else '')
    key = (r['inst'], r['lam'])
    if key not in ref: continue
    G[(tag, r['lam'])].append((r['inst'], r.get('seed', 0), 100 * (r['objective'] if 'objective' in r else r['cost']) / ref[key] - 100, r.get('wall', 0), r['feasible']))
print('reference = best norl_8 10s (2 seeds); TSALNS(py) 30s gap vs ref at lam0:',
      round(np.mean([100 * ts[i] / ref[(i, 0.0)] - 100 for i in ts if (i, 0.0) in ref]), 2) if ts else None)
sizes = ['5_35', '6_50', '7_65', '8_80', '10_110']
print(f"{'method':24s} lam   mean%  " + '  '.join(f'{s:>7s}' for s in sizes) + '   wall_ms  feas')
for (tag, lam) in sorted(G):
    v = G[(tag, lam)]
    per = [np.mean([g for i, s, g, w, fe in v if i[1:].startswith(sz + '_')]) for sz in sizes]
    print(f"{tag:24s} {lam:3.1f} {np.mean([x[2] for x in v]):7.2f}  " + '  '.join(f'{p:7.2f}' for p in per) +
          f"  {1000*np.mean([x[3] for x in v]):8.1f}  {sum(x[4] for x in v)}/{len(v)}")
