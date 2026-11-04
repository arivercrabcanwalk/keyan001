"""Summarise grid file: mean % objective vs reference spec (paired on inst,lam,seed,sec)."""
import sys, json, collections, numpy as np
f = sys.argv[1]; ref = sys.argv[2] if len(sys.argv) > 2 else 'norl:4'
D = collections.defaultdict(dict)
for l in open(f):
    j = json.loads(l); D[(j['inst'], j['lam'], j['seed'], j['sec'])][j['spec']] = j['objective']
specs = sorted({s for v in D.values() for s in v})
secs = sorted({k[3] for k in D}); lams = sorted({k[1] for k in D})
rows = []
for sp in specs:
    out = [sp]
    for se in secs:
        for la in lams:
            d = [(v[sp] / v[ref] - 1) * 100 for k, v in D.items() if k[3] == se and k[1] == la and sp in v and ref in v]
            out.append(f'{np.mean(d):+.2f}({len(d)})' if d else '   -   ')
    rows.append(out)
print('spec', ' '.join(f's{se}/l{la}' for se in secs for la in lams))
for r in sorted(rows, key=lambda r: r[0]): print(' '.join(r))
