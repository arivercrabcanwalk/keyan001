"""Design c' test tables: paired Wilcoxon + Holm over test cases (each = mean over S front scenarios)."""
import json, sys, numpy as np
from scipy.stats import wilcoxon
from wind.final_strong import holm
R = '/workspace/rl_wind/results/'
def load(f): return {json.loads(l)['case']: json.loads(l)['res'] for l in open(R + f)}
ours, tsn, tsf = load('front_test_ours.jsonl'), load('front_test_tsnw.jsonl'), load('front_test_tsfc.jsonl')
rlk = sys.argv[1]
cs = sorted(set(ours) & set(tsn) & set(tsf))
M = {'TSALNS (no wind, r=0, as published), plan order': (tsn, 'plan'), 'TSALNS (forecast wind, r=0), plan order': (tsf, 'plan'),
     'ours r=0.15, plan order': (ours, 'plan'), 'NoRL static reorder @ forecast T': (ours, 'static_fc'),
     'NoRL robust SAA reorder (16 scen.)': (ours, 'saa16'), 'NoRL online ratio rule': (ours, 'ratio1'),
     'NoRL-model rolling SAA (online, 16 scen.)': (ours, 'rsaa'), 'RL online next-trip policy': (ours, rlk),
     'ref: clairvoyant oracle order': (ours, 'oracle')}
V = {k: {m: np.array([C[c][key][m] for c in cs]) for m in ('J', 'cost', 'fail', 'mk')} for k, (C, key) in M.items()}
print(f'design c\' test: n={len(cs)} cases (Liu-50 x 2 strong-wind contexts, front scenarios per case), P=100')
print(f'{"method":48s} {"J":>8s} {"cost":>8s} {"fail/day":>9s} {"makespan":>9s}')
for k, v in V.items(): print(f'{k:48s} {v["J"].mean():8.2f} {v["cost"].mean():8.2f} {v["fail"].mean():9.4f} {v["mk"].mean():9.1f}')
rk = 'RL online next-trip policy'; tests = []
for k in M:
    if k == rk or k.startswith('ref'): continue
    for m in ('J', 'cost', 'fail', 'mk'):
        d = V[rk][m] - V[k][m]; p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
        tests.append((k, m, d.mean(), 100 * d.mean() / V[k][m].mean() if V[k][m].mean() else 0, (d < 0).sum(), (d > 0).sum(), p))
adj = holm(np.array([t[-1] for t in tests]))
print(f'RL - baseline (negative = RL better), Holm over {len(tests)} tests')
for t, pa in zip(tests, adj):
    print(f'  vs {t[0]:46s} {t[1]:5s} diff {t[2]:+9.3f} ({t[3]:+6.2f}%) better/worse {t[4]}/{t[5]}  p={t[6]:.2e}  p_Holm={pa:.2e}')
