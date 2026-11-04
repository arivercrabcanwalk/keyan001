"""Cost-failure Pareto on the test set (seed B). Fronts: NoRL fixed actions (each fixed (r_s,r_l) = one point),
NoRL fixed global r, TSALNS(forecast) fixed r, RL swept over P, supervised tree rule swept over P, sim-select swept.
HV computed in normalised (cost, fail) space with a common reference point. usage: pareto.py MODELS OUTPNG"""
import wind, sys, json, collections, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from sklearn.tree import DecisionTreeRegressor
from wind.rl_type import load, act
R = '/workspace/rl_wind/results/'
def nd(pts):
    pts = sorted(set(map(tuple, pts))); out = []; best = np.inf
    for c, f in pts:
        if f < best - 1e-12: out.append((c, f)); best = f
    return np.array(out)
def hv(front, ref, lo):
    F = (np.array(front) - lo) / (ref - lo); F = nd(F); h = 0.0; prev_f = 1.0
    for c, f in F:
        if c >= 1 or f >= 1: continue
        h += (1 - c) * (prev_f - f); prev_f = f
    return h
def main(models, png):
    _, A, Xtr, ctr, ftr, _, _ = load(R + 'hr_train_type.jsonl')
    _, _, Xd, cdA, fdA, _, _ = load(R + 'hr_dev_type.jsonl', A)
    cst, _, Xt, ctA, ftA, _, _ = load(R + 'hr_test_type.jsonl', A)
    _, _, _, cB, fB, _, _ = load(R + 'hr_test_type_rs.jsonl', A)
    feas = ~np.isnan(ctA); n = len(cst); ar = np.arange(n)
    def fb(k):
        k = np.array([ki if feas[i, ki] else int(np.flatnonzero(feas[i])[0]) for i, ki in enumerate(k)]); return cB[ar, k].mean(), fB[ar, k].mean()
    fixed = [fb(np.full(n, i)) for i in range(len(A)) if feas[:, i].all()]
    glob = [fb(np.full(n, i)) for i, a in enumerate(A) if a[0] == a[1] and feas[:, i].all()]
    C = collections.defaultdict(dict)
    for l in open(R + 'strong_test_ts_fc_rs.jsonl'):
        r = json.loads(l); C[r['case']][r['reserve']] = r
    G9 = sorted({g for c in C for g in C[c]})
    tsf = []
    for g in G9:
        ok = [C[c][g] for c in cst if not C[c][g].get('infeasible')]
        if len(ok) == len(cst): tsf.append((np.mean([r['cost'] for r in ok]), np.mean([r['failed'] for r in ok])))
    PS = np.exp(np.linspace(np.log(15), np.log(400), 14))
    rl = {m: [fb(act(m, Xt, P, feas)) for P in PS] for m in models}
    sim = [fb(np.nanargmin(ctA + P * ftA, 1)) for P in PS]
    sup = []
    for P in PS:
        Y = lambda Cc, Ff: np.nan_to_num((Cc + P * Ff) / np.nanmean(Cc + P * Ff, 1, keepdims=True), nan=3.0)
        tr = DecisionTreeRegressor(max_depth=3, min_samples_leaf=20, random_state=0).fit(np.vstack([Xtr, Xd]), np.vstack([Y(ctr, ftr), Y(cdA, fdA)]))
        sup.append(fb(np.where(feas, tr.predict(Xt), 9e9).argmin(1)))
    allp = np.array(fixed + glob + tsf + sim + sup + [p for v in rl.values() for p in v])
    lo = allp.min(0) * np.array([0.995, 0.95]); ref = np.array([allp[:, 0].max() * 1.005, allp[:, 1].max() * 1.05])
    out = {'NoRL fixed (r_s,r_l) front': hv(fixed, ref, lo), 'NoRL fixed global r front': hv(glob, ref, lo),
           'TSALNS(forecast) fixed r front': hv(tsf, ref, lo), 'supervised tree rule (P sweep)': hv(sup, ref, lo),
           'ref sim-select 36x (P sweep)': hv(sim, ref, lo)}
    for i, m in enumerate(models): out[f'RL seed{i} (P sweep)'] = hv(rl[m], ref, lo)
    plt.figure(figsize=(7, 5))
    for pts, lab, st in [(tsf, 'TSALNS (forecast wind) fixed r', 'k^--'), (glob, 'NoRL fixed global r', 'bs--'), ([tuple(x) for x in nd(fixed)], 'NoRL fixed (r_s,r_l), nondominated', 'go-'),
                         (sup, 'NoRL supervised tree rule (P sweep)', 'c.-'), (sim, 'ref: sim-select 36x compute', 'm:')]:
        p = np.array(sorted(pts)); plt.plot(p[:, 0], p[:, 1], st, label=lab, ms=4)
    for i, m in enumerate(models):
        p = np.array(rl[m]); plt.plot(p[:, 0], p[:, 1], 'r.-', alpha=0.5, label='RL (P sweep), %d seeds' % len(models) if i == 0 else None)
    plt.xlabel('expected cost per day'); plt.ylabel('expected failed trips per day'); plt.title('Strong wind, Liu-50 test (400 indep. MC scen.)')
    plt.legend(fontsize=7); plt.grid(alpha=.3); plt.tight_layout(); plt.savefig(png, dpi=150)
    for k, v in out.items(): print(f'HV {k:40s} {v:.4f}')
    print('RL HV mean±std', np.mean([out[k] for k in out if k.startswith('RL')]), np.std([out[k] for k in out if k.startswith('RL')]))
if __name__ == '__main__':
    main(sys.argv[1].split(','), sys.argv[2])
