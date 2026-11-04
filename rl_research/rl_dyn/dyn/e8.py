"""E8 table: author group (A1/A2/A3) vs our NoRL vs RL3, paired Wilcoxon + Holm. usage: e8.py [seeds e.g. 5000-5002]"""
import dyn, sys, json, collections, numpy as np
from scipy.stats import wilcoxon
lo, hi = map(int, (sys.argv[1] if len(sys.argv) > 1 else '5000-5002').split('-'))
F = ['results/test30.jsonl', 'results/test_rollb30.jsonl', 'results/test_reopt.jsonl', 'results/test_reopt30.jsonl']
L = [json.loads(l) for f in F for l in open(f)]
L = [x for x in L if lo <= x['seed'] <= hi]
RL = ['rl=models/pg_r10/best.pt', 'rl=models/pg_r11/best.pt', 'rl=models/pg_r12/best.pt']
g = collections.defaultdict(list)
for x in L:
    if x['method'] in RL: g[(x['path'], x['seed'])].append(x)
for k, v in g.items():
    if len(v) == 3:
        y = dict(v[0]); y['method'] = 'RL3'
        for key in v[0]:
            if isinstance(v[0][key], (int, float)) and not isinstance(v[0][key], bool) and key != 'seed': y[key] = sum(z[key] for z in v) / 3
        L.append(y)
for x in L:  # decision time per decision (ms)
    if x['method'] == 'ts_ins': x['dec_ms'] = x['ms_per_dec'] / max(1, x['n'])     # whole-day sim time / #urgent (upper bound)
    elif x['method'].startswith('reopt'): x['dec_ms'] = x['ms_per_dec']             # mean wall-clock per re-opt
    else: x['dec_ms'] = x['ms_per_dec']
GROUPS = [('作者方法组 (TSALNS 计划)', [('A1 TSALNS+最近空闲机派单', 'ts_myo'), ('A2 TS-insert', 'ts_ins'),
          ('A3 TS-reopt 事件触发 1s', 'reopt_ev_1'), ('A3 TS-reopt 事件触发 3s', 'reopt_ev_3'), ('A3 TS-reopt 事件+Δ10min 1s', 'reopt_p10_1')]),
          ('我们的 NoRL 消融组', [('myopic（不保留）', 'myo'), ('static30（dev 调参最优）', 'static30'),
          ('rollout M=1', 'rollb30_1'), ('rollout M=8', 'rollb30_8'), ('rollout M=32', 'rollb30_32')]),
          ('我们的 RL', [('RL3（REINFORCE-POMO，3 种子均值）', 'RL3')] + [(f'RL seed {s}', m) for s, m in zip((10, 11, 12), RL)])]
by = collections.defaultdict(lambda: collections.defaultdict(list))
for x in L: by[x['method']][x['path']].append(x)
MET = [('J', 'J', -1), ('ontime', '准时率', 1), ('ontime_h', '高优先准时率', 1), ('resp', '响应(min)', -1), ('mk', 'makespan', -1), ('cost', '成本', -1), ('dec_ms', '决策ms', -1)]
print(f'seeds {lo}-{hi}; instances = #paths; cells = mean over (instance, day)')
print('| 组 | 方法 | n天 | ' + ' | '.join(m[1] for m in MET) + ' |'); print('|' + '---|' * (3 + len(MET)))
for gname, ms in GROUPS:
    for lab, m in ms:
        v = [x for vv in by[m].values() for x in vv]
        if not v: print(f'| {gname} | {lab} | 0 |' + ' – |' * len(MET)); continue
        cells = []
        for k, _, _ in MET:
            a = np.mean([x[k] for x in v])
            cells.append(f'{a*100:.1f}%' if k in ('ontime', 'ontime_h') else (f'{a:.2f}' if k in ('resp', 'dec_ms') else f'{a:.1f}'))
        print(f'| {gname} | {lab} | {len(v)} | ' + ' | '.join(cells) + ' |')
def pinst(r, b, m):  # instance means over the (path, seed) pairs both methods have -> properly paired
    A = {(x['path'], x['seed']): x[m] for v in by[r].values() for x in v}; B = {(x['path'], x['seed']): x[m] for v in by[b].values() for x in v}
    ks = set(A) & set(B); ga = collections.defaultdict(list); gb = collections.defaultdict(list)
    for k in ks: ga[k[0]].append(A[k]); gb[k[0]].append(B[k])
    return {p: np.mean(v) for p, v in ga.items()}, {p: np.mean(v) for p, v in gb.items()}
def inst(meth, m): return {p: np.mean([x[m] for x in v]) for p, v in by[meth].items()}
def block(ref, bls, mets):
    tests = []
    for b in bls:
        if b not in by: continue
        for m, lab, better in mets:
            a, c = pinst(ref, b, m); ks = sorted(set(a) & set(c))
            x = np.array([a[k] for k in ks]); y = np.array([c[k] for k in ks]); d = x - y
            p = wilcoxon(x, y).pvalue if np.any(d != 0) else 1.0
            tests.append([b, lab, d.mean(), d.mean() / abs(y.mean()) * 100, int(((d * better) > 1e-12).sum()), int(((d * better) < -1e-12).sum()), p, len(ks)])
    ps = np.array([t[6] for t in tests]); o = np.argsort(ps); n = len(ps); adj = np.zeros(n); run = 0
    for r, i in enumerate(o): run = max(run, min(1, (n - r) * ps[i])); adj[i] = run
    print(f'\n{ref} − baseline（每个对照只在双方共有的 (算例,天) 上配对）（算例级配对，Holm 校正共 {n} 个检验）')
    print('| 对照 | 指标 | 差值 | 相对% | 赢 | 输 | p | p_Holm |'); print('|---|---|---|---|---|---|---|---|')
    for t, a in zip(tests, adj): print(f'| {t[0]} | {t[1]} | {t[2]:+.3f} | {t[3]:+.2f} | {t[4]} | {t[5]} | {t[6]:.2g} | {a:.2g} |')
M6 = MET[:6]
block('RL3', ['ts_myo', 'ts_ins', 'reopt_ev_1', 'reopt_ev_3', 'reopt_p10_1', 'myo', 'static30', 'rollb30_1', 'rollb30_8', 'rollb30_32'], M6)
best = 'reopt_ev_1' or min([m for m in ('reopt_ev_1', 'reopt_ev_3', 'reopt_p10_1') if m in by], key=lambda m: np.mean([x['J'] for v in by[m].values() for x in v]), default=None)
if best: block(best, ['ts_ins', 'ts_myo'], M6)
for m in ('reopt_ev_1', 'reopt_ev_3', 'reopt_p10_1'):
    v = [x for vv in by[m].values() for x in vv]
    if v: print(f'{m}: n_reopt/天 {np.mean([x["n_reopt"] for x in v]):.1f}, 每次 re-opt 墙钟 均值 {np.mean([x["ms_per_dec"] for x in v]):.0f} ms, 最大 {max(x["reopt_max_s"] for x in v):.2f} s, 每天总重优化 {np.mean([x["reopt_s"] for x in v]):.1f} s, 每次评估数 {np.mean([x["evals"]/max(1,x["n_reopt"]) for x in v]):.0f}')
