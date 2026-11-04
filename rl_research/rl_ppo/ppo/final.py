"""Final test statistics on Liu-50.
Usage: final.py SEC REF_LABEL LABEL=file.jsonl[:spec] ... [TS]   (TS adds TSALNS_w at that budget from rlproj csvs)
Metrics per instance (mean over seeds): HV5 (front over lam in {0,.1,.5,1,2}, normalised by (C_ref,M1_ref),
ref point (1.10,1.50) as in pareto.py), HV7 (all 7 lams), MK@1% (min makespan/M1 over points with cost<=1.01 C_ref),
cost@lam0, F@lam (objective/init per lam). Paired Wilcoxon; Holm over all printed p-values."""
import sys, json, csv, collections, math, numpy as np
sys.path.insert(0, '/workspace/eval_kit'); import lrphsd_eval as E
from scipy.stats import wilcoxon
RP = (1.10, 1.50); L5 = (0.0, 0.1, 0.5, 1.0, 2.0)
def hv(pts):
    p = sorted({(c, m) for c, m in pts if c < RP[0] and m < RP[1]}); area = 0; best = RP[1]
    for c, m in p:
        if m < best: area += (RP[0] - c) * (best - m); best = m
    return area
sec = float(sys.argv[1]); reflab = sys.argv[2]; args = sys.argv[3:]
data = {}   # label -> inst -> seed -> lam -> (cost, mk, obj)
for a in args:
    if a == 'TS':
        d = collections.defaultdict(lambda: collections.defaultdict(dict))
        T = '0.3' if sec < 0.5 else '1'
        for l in L5:
            ls = ('%g' % l)
            for r in csv.DictReader(open(f'/workspace/rlproj/results/s2_json_T{T}/tsw_lam{ls}_r101.csv')):
                d[r['instance']][101][l] = (float(r['cost']), float(r['makespan_fixed']), None)
        data['TSALNS_w'] = d; continue
    lab, f = a.split('=', 1); spec = None
    if ':' in f and not f.endswith('.jsonl'): f, spec = f.split(':', 1)
    d = collections.defaultdict(lambda: collections.defaultdict(dict))
    for line in open(f):
        j = json.loads(line)
        if j['sec'] != sec or (spec and j['spec'] != spec): continue
        d[j['inst']][j['seed']][j['lam']] = (j['cost'], j['makespan'], j['objective'] / j['init_obj'])
    data[lab] = d
def metrics(d):
    out = {}
    for inst, S in d.items():
        c0, _, m1, _ = E.BASE[inst]; hv5 = []; hv7 = []; mk1 = []; cost0 = []; F = collections.defaultdict(list)
        for seed, L in S.items():
            pts = {l: (v[0] / c0, v[1] / m1) for l, v in L.items()}
            if all(l in pts for l in L5): hv5.append(hv([pts[l] for l in L5]))
            if len(pts) >= 7: hv7.append(hv(list(pts.values())))
            ok = [m for c, m in pts.values() if c <= 1.01]; mk1.append(min(ok) if ok else np.nan)
            if 0.0 in L: cost0.append(L[0.0][0])
            for l, v in L.items():
                if v[2] is not None: F[l].append(v[2])
        out[inst] = dict(HV5=np.mean(hv5) if hv5 else np.nan, HV7=np.mean(hv7) if hv7 else np.nan,
                         MK1=np.nanmean(mk1) if not all(np.isnan(mk1)) else np.nan, cost0=np.mean(cost0) if cost0 else np.nan,
                         **{f'F{l}': np.mean(v) for l, v in F.items()})
    return out
M = {lab: metrics(d) for lab, d in data.items()}
keys = ['HV5', 'HV7', 'MK1', 'cost0'] + [f'F{l}' for l in (0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0)]
higher = {'HV5', 'HV7'}
labs = list(M)
print(f'== budget {sec}s ; per-instance means over seeds; n = instances')
print('%-8s' % 'metric' + ''.join('%14s' % l for l in labs))
for k in keys:
    row = []
    for l in labs:
        v = [M[l][i][k] for i in M[l] if k in M[l][i] and not np.isnan(M[l][i][k])]
        row.append('%14.5f' % np.mean(v) if v else '%14s' % '-')
    print('%-8s' % k + ''.join(row))
tests = []
for l in labs:
    if l == reflab: continue
    for k in keys:
        ins = [i for i in M[l] if i in M[reflab] and k in M[l][i] and k in M[reflab][i]
               and not np.isnan(M[l][i][k]) and not np.isnan(M[reflab][i][k])]
        if len(ins) < 5: continue
        x = np.array([M[l][i][k] for i in ins]); y = np.array([M[reflab][i][k] for i in ins])
        better = int(((x > y) if k in higher else (x < y)).sum()); worse = int(((x < y) if k in higher else (x > y)).sum())
        try: p = wilcoxon(x, y).pvalue
        except ValueError: p = 1.0
        rel = (x.mean() / y.mean() - 1) * 100
        tests.append([l, k, rel, better, worse, len(ins), p])
# Holm
ps = sorted(range(len(tests)), key=lambda i: tests[i][-1]); m = len(tests); run = 0
for r, i in enumerate(ps):
    run = max(run, min(1, tests[i][-1] * (m - r))); tests[i].append(run)
print(f'\n-- vs {reflab} (rel% of mean; better/worse/n; Wilcoxon p; Holm p over {m} tests)')
for t in tests: print('%-12s %-6s %+7.3f%%  %2d/%2d/%2d  p=%.2g  pHolm=%.2g' % tuple(t))
