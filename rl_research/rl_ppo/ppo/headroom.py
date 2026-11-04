"""Cross-validated headroom of selection granularities over a grid file.
Score of config c on cell (inst,lam,seed,sec) = obj_c / mean_over_specs_obj(cell) (relative, %).
CV: select with seed set A, evaluate on seed set B (and swap). Granularity: global / per-lam / per-sec /
per-(lam,sec) / per-(inst,lam,sec)."""
import sys, json, collections, numpy as np, itertools
f = sys.argv[1]; only = sys.argv[2].split(';') if len(sys.argv) > 2 and sys.argv[2] else None
D = collections.defaultdict(dict)
for l in open(f):
    j = json.loads(l)
    if only and j['spec'] not in only: continue
    D[(j['inst'], j['lam'], j['seed'], j['sec'])][j['spec']] = j['objective']
specs = sorted({s for v in D.values() for s in v})
cells = {k: v for k, v in D.items() if len(v) == len(specs)}
print(len(specs), 'specs', len(cells), 'complete cells of', len(D))
seeds = sorted({k[2] for k in cells}); insts = sorted({k[0] for k in cells})
lams = sorted({k[1] for k in cells}); secs = sorted({k[3] for k in cells})
# normalise per (inst,lam,sec) by mean over all specs & seeds
norm = collections.defaultdict(list)
for k, v in cells.items(): norm[(k[0], k[1], k[3])] += list(v.values())
norm = {k: np.mean(x) for k, x in norm.items()}
S = {k: {s: (v[s] / norm[(k[0], k[1], k[3])] - 1) * 100 for s in specs} for k, v in cells.items()}
def score(sel_keyfn, A, B):
    # choose per group on seeds A, evaluate on seeds B
    grp = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, v in S.items():
        if k[2] in A:
            for s in specs: grp[sel_keyfn(k)][s].append(v[s])
    choice = {g: min(d, key=lambda s: np.mean(d[s])) for g, d in grp.items()}
    out = collections.defaultdict(list)
    for k, v in S.items():
        if k[2] in B and sel_keyfn(k) in choice: out[(k[1], k[3])].append(v[choice[sel_keyfn(k)]])
    return out, choice
half = len(seeds) // 2
A, B = set(seeds[:half]), set(seeds[half:])
gran = dict(glob=lambda k: 0, lam=lambda k: k[1], sec=lambda k: k[3], lamsec=lambda k: (k[1], k[3]),
            inst=lambda k: (k[0], k[1], k[3]))
res = {}
for name, fn in gran.items():
    o1, c1 = score(fn, A, B); o2, c2 = score(fn, B, A)
    tot = collections.defaultdict(list)
    for o in (o1, o2):
        for g, x in o.items(): tot[g] += x
    res[name] = tot
    allv = [x for v in tot.values() for x in v]
    print(f'{name:7s} all {np.mean(allv):+.3f}  ' + '  '.join(f'l{g[0]}/s{g[1]}:{np.mean(v):+.2f}' for g, v in sorted(tot.items())))
    if name in ('glob', 'lamsec'): print('   choices A:', dict(list(c1.items())[:14]))
# per-spec mean per lam/sec (in-sample)
print('\nin-sample per (lam,sec) top-3:')
for la in lams:
    for se in secs:
        m = {s: np.mean([v[s] for k, v in S.items() if k[1] == la and k[3] == se]) for s in specs}
        top = sorted(m.items(), key=lambda x: x[1])[:3]
        print(f' l{la} s{se}: ' + ', '.join(f'{s} {x:+.2f}' for s, x in top), f' norl:4 {m.get("norl:4", float("nan")):+.2f}' if 'norl:4' in m else '')
