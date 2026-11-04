"""Pick best (reserve, policy) per family on DEV for a given failure price P. usage: tune.py P file..."""
import json, sys, numpy as np, collections
P = float(sys.argv[1]); rows = [json.loads(l) for f in sys.argv[2:] for l in open(f)]
G = collections.defaultdict(dict)
for r in rows: G[(r['reserve'], r['policy'])][r['case']] = r
cases = sorted(set.intersection(*[set(v) for v in G.values()]))
def fam(p):
    if p.startswith('rl:'): return 'rl:' + p.split(':')[1]
    return p.split(':')[0]
best = {}
for (res, pol), v in G.items():
    J = np.mean([v[c]['cost'] + P * v[c]['failed'] for c in cases])
    f = fam(pol)
    if pol.startswith('rl:') and abs(float(pol.split(':')[2]) - P) > 1e-6: continue
    if f not in best or J < best[f][0]: best[f] = (J, res, pol, np.mean([v[c]['cost'] for c in cases]), np.mean([v[c]['failed'] for c in cases]))
for f, (J, res, pol, c, fl) in sorted(best.items(), key=lambda x: x[1][0]):
    print(f"P={P:g} {f:28s} J={J:8.2f} cost={c:8.2f} failed/day={fl:.4f}  <- reserve={res} policy={pol}")
