"""Headroom for design c' with fair NoRL baselines. usage: hr_front2.py TABLE OUT S W [reserve]"""
import wind, sys, json, zlib, numpy as np
from multiprocessing import get_context
def job(t):
    line, S, methods = t
    from wind.front import front_ctx, sample_scen, load_case, run_order, run_policy, best_order, make_ratio, make_rollout, make_rsaa, J
    row = json.loads(line); ins, fixed, drones = load_case(row); fc = front_ctx(row['case'], row['ctx'])
    rng = np.random.default_rng(zlib.crc32(row['case'].encode()) + 99)
    Ts, W2 = sample_scen(fc, rng, S)
    frng = np.random.default_rng(5); fT, fW = sample_scen(fc, frng, 16); fsc = list(zip(fT, fW))
    out = {m: np.zeros((S, 3)) for m in methods}; nT = []
    for dr in drones:
        n = len(dr.trips)
        st = {}
        if 'static_fc' in methods: st['static_fc'] = best_order(dr, [(fc['That'], np.array(fc['w2fc']))], fc['w1'])
        if 'saa16' in methods: st['saa16'] = best_order(dr, fsc, fc['w1'])
        st['plan'] = list(range(n))
        for s in range(S):
            T, w2 = Ts[s], W2[s]
            for m in methods:
                if m in st: r = run_order(dr, st[m], T, fc['w1'], w2)
                elif m == 'oracle': r = run_order(dr, best_order(dr, [(T, w2)], fc['w1']), T, fc['w1'], w2)
                elif m.startswith('ratio'): r = run_policy(dr, make_ratio(float(m[5:])), T, fc['w1'], w2, fc)
                elif m.startswith('rl:'):
                    from wind.front_rl import make_rl
                    r = run_policy(dr, make_rl(m[3:]), T, fc['w1'], w2, fc)
                elif m == 'rsaa': r = run_policy(dr, make_rsaa(16), T, fc['w1'], w2, fc)
                elif m.startswith('roll'): r = run_policy(dr, make_rollout(16, float(m[4:])), T, fc['w1'], w2, fc)
                out[m][s, :2] += (r['cost'], r['fail']); out[m][s, 2] = max(out[m][s, 2], r['end'])
    res = {m: dict(cost=float(fixed + v[:, 0].mean()), fail=float(v[:, 1].mean()), J=float(fixed + v[:, 0].mean() + 100 * v[:, 1].mean()), mk=float(v[:, 2].mean()), Jv=list(map(float, fixed + v[:, 0] + 100 * v[:, 1]))) for m, v in out.items()}
    return dict(case=row['case'], res=res)
if __name__ == '__main__':
    TABLE, OUT, S, W = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); r0 = float(sys.argv[5]) if len(sys.argv) > 5 else 0.15
    methods = sys.argv[6].split(',') if len(sys.argv) > 6 else ['plan', 'static_fc', 'saa16', 'ratio0', 'ratio0.5', 'ratio1', 'roll1', 'rsaa', 'oracle']
    lines = [l for l in open(TABLE) if not json.loads(l).get('infeasible') and abs(json.loads(l)['reserve'] - r0) < 1e-9]
    with get_context('forkserver').Pool(W) as p, open(OUT, 'w') as f:
        for r in p.imap_unordered(job, [(l, S, methods) for l in lines]):
            f.write(json.dumps(r) + '\n'); f.flush()
