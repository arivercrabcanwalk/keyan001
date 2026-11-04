"""Final test tables: per P, methods (dev-tuned configs), mean metrics over the 100 test cases, paired Wilcoxon + Holm."""
import json, sys, numpy as np, collections
from scipy.stats import wilcoxon
def load(f): return [json.loads(l) for l in open(f)]
A = load('results/test_eval.jsonl'); TN = load('results/test_eval_ts_nowind.jsonl'); TF = load('results/test_eval_ts_fc.jsonl')
def get(rows, res, pol): return {r['case']: r for r in rows if r['reserve'] == res and r['policy'] == pol}
# dev-tuned configurations (wind/tune.py on dev_norl + dev_rl_f20)
CFG = {50: dict(norl=(0.05, 'margin:0.02'), look=(0.05, 'look:0.05'), rl=(0.05, 'rl:models/pomo_f20/last.pt:50'), plan_only=(0.05, 'none')),
       100: dict(norl=(0.05, 'margin:0.04'), look=(0.05, 'look:0.05'), rl=(0.1, 'rl:models/pomo_f20/last.pt:100'), plan_only=(0.1, 'none')),
       200: dict(norl=(0.1, 'margin:0.08'), look=(0.05, 'look:0.02'), rl=(0.1, 'rl:models/pomo_f20/last.pt:200'), plan_only=(0.1, 'none'))}
for P, cfg in CFG.items():
    M = {'TSALNS (no wind, as published)': get(TN, 0.0, 'none'), 'TSALNS (forecast wind)': get(TF, 0.0, 'none'),
         'TSALNS (forecast) + margin recourse': get(TF, 0.0, 'margin:0.04'),
         'ours plan only (dev-tuned r)': get(A, *cfg['plan_only']),
         'NoRL: plan + margin rule (dev-tuned)': get(A, *cfg['norl']), 'NoRL-model: MC look-ahead (dev-tuned)': get(A, *cfg['look']),
         'RL: plan + learned recourse': get(A, *cfg['rl'])}
    cases = sorted(set.intersection(*[set(v) for v in M.values()]))
    print(f'\n=== P={P}  (n={len(cases)} test cases = Liu-50 x 2 wind contexts, 100 MC scenarios each) ===')
    print(f"{'method':42s} {'J':>8s} {'cost':>8s} {'fail/day':>9s} {'P(any)':>7s} {'mk':>7s} {'undeliv':>8s}")
    for k, v in M.items():
        J = np.mean([v[c]['cost'] + P * v[c]['failed'] for c in cases])
        print(f"{k:42s} {J:8.2f} {np.mean([v[c]['cost'] for c in cases]):8.2f} {np.mean([v[c]['failed'] for c in cases]):9.4f} {np.mean([v[c]['p_anyfail'] for c in cases]):7.3f} {np.mean([v[c]['makespan'] for c in cases]):7.1f} {np.mean([v[c]['undelivered'] for c in cases]):8.4f}")
    rl = M['RL: plan + learned recourse']; tests = []
    for base in ['TSALNS (no wind, as published)', 'TSALNS (forecast wind)', 'NoRL: plan + margin rule (dev-tuned)']:
        for met in ('J', 'cost', 'failed'):
            f = (lambda r: r['cost'] + P * r['failed']) if met == 'J' else (lambda r, m=met: r[m])
            d = np.array([f(rl[c]) - f(M[base][c]) for c in cases])
            p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
            tests.append((base, met, d.mean(), int((d < 0).sum()), int((d > 0).sum()), p))
    ps = sorted(range(len(tests)), key=lambda i: tests[i][5]); m = len(tests); adj = [0] * m; run = 0
    for rank, i in enumerate(ps): run = max(run, min(1.0, (m - rank) * tests[i][5])); adj[i] = run
    print('RL vs baseline (diff = RL - base; negative = RL better), Holm-adjusted over', m, 'tests')
    for (b, met, md, w, l, p), pa in zip(tests, adj):
        print(f"  vs {b:38s} {met:6s} mean diff {md:+9.4f}  RL better/worse {w}/{l}  p={p:.2e}  p_Holm={pa:.2e}")
