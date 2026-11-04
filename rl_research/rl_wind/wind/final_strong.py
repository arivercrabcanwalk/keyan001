"""Design b' test tables. All methods evaluated on INDEPENDENT scenarios (seed B tables from resim.py).
usage: final_strong.py MODEL"""
import wind, sys, json, collections, numpy as np
from scipy.stats import wilcoxon
from wind.rl_reserve import GRID, load, act, feats
R = '/workspace/rl_wind/results/'
def tab(f):
    C = collections.defaultdict(dict)
    for l in open(f):
        r = json.loads(l); C[r['case']][r['reserve']] = r
    return C
def holm(ps):
    o = np.argsort(ps); m = len(ps); adj = np.empty(m); run = 0
    for k, i in enumerate(o): run = max(run, min(1, (m - k) * ps[i])); adj[i] = run
    return adj
def main(model):
    dA, dB = tab(R + 'hr_dev_strong.jsonl'), tab(R + 'hr_dev_strong_rs.jsonl')
    tA, tB = tab(R + 'hr_test_strong.jsonl'), tab(R + 'hr_test_strong_rs.jsonl')
    sdB, stB = tab(R + 'strong_dev_ts_fc_rs.jsonl'), tab(R + 'strong_test_ts_fc_rs.jsonl')
    snB = tab(R + 'strong_test_ts_nowind_rs.jsonl')
    trA = tab(R + 'hr_train_strong.jsonl'); cstr = [c for c in trA if len(trA[c]) == len(GRID) and not any(trA[c][g].get('infeasible') for g in GRID)]
    csd, Xd, _, _ = load(R + 'hr_dev_strong.jsonl'); cst, Xt, _, _ = load(R + 'hr_test_strong.jsonl')
    cst = [c for c in cst if c in stB and len(stB[c]) == len(GRID) and c in snB]
    Xt = np.stack([feats(c, None, None) for c in cst])
    def M(C, cs, g, k): return np.array([C[c][g][k] if not C[c][g].get('infeasible') else np.nan for c in cs])
    out = []
    for P in (25, 50, 100, 200):
        J = lambda C, cs, g: M(C, cs, g, 'cost') + P * M(C, cs, g, 'failed')
        # dev tuning (on dev seed-B tables is fine for NoRL; we use dev seed A to mimic "tune on dev sims")
        fr = min(GRID, key=lambda g: np.nanmean(J(dA, csd, g)))
        fr2 = min(GRID, key=lambda g: (np.nansum(J(dA, csd, g)) + np.nansum(J(trA, cstr, g))) / (len(csd) + len(cstr)))
        tr = min(GRID, key=lambda g: np.nanmean(J(sdB, csd, g)))
        Wd = np.array([dA[c][0.0]['ctx']['W'] for c in csd]); Wt = np.array([tA[c][0.0]['ctx']['W'] for c in cst])
        best = None
        for a in GRID:
            for b in (0.0, 0.025, 0.05, 0.1):
                for w0 in (6, 7, 8, 9):
                    ch = [min(GRID, key=lambda g: abs(g - min(0.5, a + b * max(0, w - w0)))) for w in Wd]
                    v = np.mean([J(dA, [c], g)[0] for c, g in zip(csd, ch)])
                    if best is None or v < best[0]: best = (v, a, b, w0)
        _, a, b, w0 = best
        rule = [min(GRID, key=lambda g: abs(g - min(0.5, a + b * max(0, w - w0)))) for w in Wt]
        rl = [GRID[i] for i in act(model, Xt, P)]
        sim = [min(GRID, key=lambda g: J(tA, [c], g)[0] if not tA[c][g].get('infeasible') else 1e18) for c in cst]
        def feas(C, c, g):
            while C[c][g].get('infeasible'): g = GRID[GRID.index(g) - 1]
            return g
        def pick(C, ch, k): return np.array([C[c][g][k] for c, g in zip(cst, ch)])
        meth = {'TSALNS (no wind, r=0, as published)': (snB, [0.0] * len(cst)),
                'TSALNS (forecast wind, r=0)': (stB, [0.0] * len(cst)),
                f'TSALNS (forecast wind, dev-tuned r={tr})': (stB, [feas(stB, c, tr) for c in cst]),
                f'NoRL fixed r={fr} (dev-tuned)': (tB, [feas(tB, c, fr) for c in cst]),
                f'NoRL fixed r={fr2} (tuned on train+dev, 639 cases)': (tB, [feas(tB, c, fr2) for c in cst]),
                f'NoRL rule r=a+b(W-w0) ({a},{b},{w0}) dev-tuned': (tB, [feas(tB, c, g) for c, g in zip(cst, rule)]),
                'RL adaptive reserve (1 plan)': (tB, [feas(tB, c, g) for c, g in zip(cst, rl)]),
                'ref: sim-select over 9 plans (9x compute)': (tB, sim)}
        print(f'\n=== P={P}  test n={len(cst)} (Liu-50 x 2 strong-wind contexts, 400 independent MC scenarios) ===')
        print(f'{"method":52s} {"J":>8s} {"cost":>8s} {"fail/day":>9s} {"P(any)":>7s} {"undeliv":>8s} {"mk":>7s}')
        V = {}
        for k, (C, ch) in meth.items():
            c, f = pick(C, ch, 'cost'), pick(C, ch, 'failed'); V[k] = dict(J=c + P * f, cost=c, failed=f, undeliv=pick(C, ch, 'undelivered'))
            print(f'{k:52s} {np.mean(c + P * f):8.2f} {c.mean():8.2f} {f.mean():9.3f} {pick(C, ch, "p_anyfail").mean():7.3f} {V[k]["undeliv"].mean():8.3f} {pick(C, ch, "makespan").mean():7.1f}')
        print('RL action histogram:', dict(collections.Counter(rl)))
        rlk = 'RL adaptive reserve (1 plan)'; tests = []
        for k in meth:
            if k == rlk or k.startswith('ref'): continue
            for m in ('J', 'cost', 'failed', 'undeliv'):
                d = V[rlk][m] - V[k][m]
                p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
                tests.append((k, m, d.mean(), 100 * d.mean() / np.mean(V[k][m]) if np.mean(V[k][m]) else 0, (d < 0).sum(), (d > 0).sum(), p))
        adj = holm(np.array([t[-1] for t in tests]))
        print(f'RL - baseline (negative = RL better), Holm over {len(tests)} tests')
        for t, pa in zip(tests, adj):
            print(f'  vs {t[0]:50s} {t[1]:8s} diff {t[2]:+9.3f} ({t[3]:+6.2f}%)  better/worse {t[4]}/{t[5]}  p={t[6]:.2e}  p_Holm={pa:.2e}')
        d = V[rlk]['J'] - V['ref: sim-select over 9 plans (9x compute)']['J']
        print(f'  [ref] RL - sim-select J diff {d.mean():+.2f} ({100*d.mean()/V["ref: sim-select over 9 plans (9x compute)"]["J"].mean():+.2f}%)')
if __name__ == '__main__':
    main(sys.argv[1])
