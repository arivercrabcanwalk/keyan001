import json, sys, numpy as np, collections
rows = [json.loads(l) for l in open(sys.argv[1])]
C = collections.defaultdict(dict)
for r in rows: C[r['case']][r['reserve']] = r
G = sorted({r['reserve'] for r in rows}); cases = sorted(C)
print('per reserve (mean over cases): cost, failed trips, P(any fail), undelivered')
for g in G:
    x = [C[c][g] for c in cases]
    print(f"r={g:.2f} cost {np.mean([y['cost'] for y in x]):8.2f} failed {np.mean([y['failed'] for y in x]):6.3f} Pany {np.mean([y['p_anyfail'] for y in x]):5.3f} undeliv {np.mean([y['undelivered'] for y in x]):6.3f} trips {np.mean([y['ntrips'] for y in x]):5.1f}")
for P in (25, 50, 100):
    J = np.array([[C[c][g]['cost'] + P * C[c][g]['failed'] for g in G] for c in cases])
    bf = J.mean(0).argmin(); orc = J.min(1)
    rel = 100 * (J[:, bf] - orc) / orc
    print(f"P={P}: best fixed r={G[bf]} J={J[:, bf].mean():.2f}; per-case oracle J={orc.mean():.2f}; headroom mean {rel.mean():.2f}% median {np.median(rel):.2f}% max {rel.max():.2f}%; oracle r distribution {collections.Counter(G[i] for i in J.argmin(1))}")
    # simple context rule baseline: r = argmin over grid of a*sigma_eff... (tuned on same set => optimistic)
    best = None
    feats = np.array([[C[c][0.0]['ctx']['sigma'], C[c][0.0]['ctx']['W'], C[c][0.0]['ctx']['gust']] for c in cases])
    for a in np.linspace(0, 0.2, 21):
        for b in np.linspace(0, 1.5, 16):
            rr = np.clip(a * feats[:, 0] + b * feats[:, 2], 0, 0.4)
            idx = [int(np.argmin(np.abs(np.array(G) - v))) for v in rr]
            val = np.mean([J[i, k] for i, k in enumerate(idx)])
            if best is None or val < best[0]: best = (val, a, b)
    print(f"      tuned rule r=a*sigma+b*gust (in-sample): J={best[0]:.2f} (a={best[1]:.2f}, b={best[2]:.2f}) -> {100*(best[0]-orc.mean())/orc.mean():.2f}% above oracle")
