"""Design b' v2 test tables + Pareto. usage: final_type.py MODEL1,MODEL2,...   (all eval on seed-B tables)"""
import wind, sys, json, collections, numpy as np
from scipy.stats import wilcoxon
from sklearn.tree import DecisionTreeRegressor
from wind.rl_type import load, act
from wind.final_strong import holm
R = '/workspace/rl_wind/results/'
PS = [25, 50, 100, 200]; METR = ['J', 'cost', 'failed', 'undeliv', 'mk']
def tabg(f):
    C = collections.defaultdict(dict)
    for l in open(R + f):
        r = json.loads(l); C[r['case']][r['reserve']] = r
    return C
def main(models):
    _, A, Xtr, ctr, ftr, _, _ = load(R + 'hr_train_type.jsonl')
    csd, _, Xd, cdA, fdA, _, _ = load(R + 'hr_dev_type.jsonl', A)
    cst, _, Xt, ctA, ftA, _, _ = load(R + 'hr_test_type.jsonl', A)
    cstB, _, _, cB, fB, uB, mB = load(R + 'hr_test_type_rs.jsonl', A); assert cstB == cst
    tsn, tsf, sdB = tabg('strong_test_ts_nowind_rs.jsonl'), tabg('strong_test_ts_fc_rs.jsonl'), tabg('strong_dev_ts_fc_rs.jsonl')
    G9 = sorted({r for c in sdB for r in sdB[c]})
    feasT = ~np.isnan(ctA); n = len(cst); ar = np.arange(n)
    diag = [i for i, a in enumerate(A) if a[0] == a[1]]
    def pickB(k):  # k: action index per case (fallback to feasible if needed)
        k = np.array([ki if feasT[i, ki] else np.nanargmin(np.where(feasT[i], 0, np.nan) + np.arange(len(A))) for i, ki in enumerate(k)])
        return dict(cost=cB[ar, k], failed=fB[ar, k], undeliv=uB[ar, k], mk=mB[ar, k]), k
    def ts(C, chooser):
        out = collections.defaultdict(list)
        for c in cst:
            g = chooser(c)
            while C[c][g].get('infeasible'): g = G9[G9.index(g) - 1]
            r = C[c][g]; out['cost'].append(r['cost']); out['failed'].append(r['failed']); out['undeliv'].append(r['undelivered']); out['mk'].append(r['makespan'])
        return {k: np.array(v) for k, v in out.items()}
    allres = {}; lines = []
    trd_c = np.vstack([ctr, cdA]); trd_f = np.vstack([ftr, fdA])
    for P in PS:
        Jtd = trd_c + P * trd_f
        okc = ~np.isnan(Jtd).any(0)
        fpair = min([i for i in range(len(A)) if okc[i]] or range(len(A)), key=lambda i: np.nanmean(Jtd[:, i]))
        fglob = min(diag, key=lambda i: np.nanmean(Jtd[:, i]))
        # supervised rule: multi-output regression tree on per-case normalised J, depth tuned on dev
        def norm(Cc, Ff):
            J = Cc + P * Ff; m = np.nanmean(J, 1, keepdims=True); return np.nan_to_num(J / m, nan=3.0)
        Ytr = norm(ctr, ftr); best = None
        for d in (1, 2, 3, 4, 6, 8):
            for leaf in (5, 20, 50):
                tr = DecisionTreeRegressor(max_depth=d, min_samples_leaf=leaf, random_state=0).fit(Xtr, Ytr)
                kd = tr.predict(Xd).argmin(1); v = np.nanmean((cdA + P * fdA)[np.arange(len(csd)), kd])
                if best is None or v < best[0]: best = (v, d, leaf, tr)
        _, dd, leaf, tree = best
        # refit on train+dev
        tree = DecisionTreeRegressor(max_depth=dd, min_samples_leaf=leaf, random_state=0).fit(np.vstack([Xtr, Xd]), np.vstack([Ytr, norm(cdA, fdA)]))
        ksup = np.where(feasT, tree.predict(Xt), 9e9).argmin(1)
        ksim = np.nanargmin(ctA + P * ftA, 1)
        tr_r = min(G9, key=lambda g: np.nanmean([sdB[c][g]['cost'] + P * sdB[c][g]['failed'] if not sdB[c][g].get('infeasible') else np.nan for c in sdB]))
        M = {'TSALNS (no wind, r=0, as published)': ts(tsn, lambda c: 0.0), 'TSALNS (forecast wind, r=0)': ts(tsf, lambda c: 0.0),
             f'TSALNS (forecast wind, dev-tuned r={tr_r})': ts(tsf, lambda c: tr_r),
             f'NoRL best fixed r={A[fglob][0]} (train+dev)': pickB(np.full(n, fglob))[0],
             f'NoRL best fixed (r_s,r_l)={A[fpair]} (train+dev) [main]': pickB(np.full(n, fpair))[0],
             f'NoRL supervised tree rule (depth {dd}, leaf {leaf})': pickB(ksup)[0],
             'ref: sim-select over 36 plans (36x compute)': pickB(ksim)[0]}
        for mi, m in enumerate(models):
            M[f'RL seed{mi}'] = pickB(act(m, Xt, P, feasT))[0]
        for v in M.values(): v['J'] = v['cost'] + P * v['failed']
        allres[P] = M
    # tables
    rlk = [k for k in allres[PS[0]] if k.startswith('RL seed')]
    for P in PS:
        M = allres[P]
        print(f'\n=== P={P}  test n={n} (Liu-50 x 2 strong-wind contexts, 400 independent MC scenarios) ===')
        print(f'{"method":58s} {"J":>8s} {"cost":>8s} {"fail/day":>9s} {"undeliv":>8s} {"mk":>7s}')
        for k, v in M.items():
            if k.startswith('RL seed'): continue
            print(f'{k:58s} {v["J"].mean():8.2f} {v["cost"].mean():8.2f} {v["failed"].mean():9.3f} {v["undeliv"].mean():8.3f} {v["mk"].mean():7.1f}')
        for m in METR:
            vals = [M[k][m].mean() for k in rlk]
        print(f'{"RL (mean +- std over %d seeds)" % len(rlk):58s} ' + ' '.join(f'{np.mean([M[k][m].mean() for k in rlk]):7.2f}±{np.std([M[k][m].mean() for k in rlk]):.2f}' for m in ['J', 'cost', 'failed', 'undeliv', 'mk']))
    # tests: per seed, Holm over P x baselines x metrics
    base = lambda M: [k for k in M if not k.startswith('RL seed') and not k.startswith('ref')]
    summary = collections.defaultdict(list)
    for rk in rlk:
        tests = []
        for P in PS:
            M = allres[P]
            for b in base(M):
                for m in METR:
                    d = M[rk][m] - M[b][m]; p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
                    tests.append((P, b, m, d.mean(), 100 * d.mean() / M[b][m].mean() if M[b][m].mean() else 0, (d < 0).sum(), (d > 0).sum(), p))
        adj = holm(np.array([t[-1] for t in tests]))
        print(f'\n--- {rk}: RL - baseline (negative = RL better), Holm over {len(tests)} tests ---')
        for t, pa in zip(tests, adj):
            if 'TSALNS (no wind' in t[1] or 'TSALNS (forecast wind, r=0)' in t[1]:
                if t[2] not in ('J', 'failed'): continue
            print(f'  P={t[0]:3d} vs {t[1]:56s} {t[2]:7s} {t[3]:+9.3f} ({t[4]:+6.2f}%) b/w {t[5]}/{t[6]} p_Holm={pa:.1e}{" *" if pa < 0.05 else ""}')
            summary[(t[0], t[1], t[2])].append((t[4], pa))
    print('\n=== robustness summary across seeds: mean rel. diff, #seeds RL significantly better / worse (Holm<0.05) ===')
    for (P, b, m), v in summary.items():
        if 'TSALNS (no wind' in b or 'TSALNS (forecast wind, r=0)' in b: continue
        rel = [x[0] for x in v]
        print(f'  P={P:3d} {b:56s} {m:7s} {np.mean(rel):+6.2f}%±{np.std(rel):.2f}  better {sum(1 for x in v if x[1] < .05 and x[0] < 0)}/{len(v)}  worse {sum(1 for x in v if x[1] < .05 and x[0] > 0)}/{len(v)}')
    return allres
if __name__ == '__main__':
    main(sys.argv[1].split(','))
