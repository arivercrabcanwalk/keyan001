"""Cheap oracle headroom for design (c'): time-varying wind (front passage at time T; wind switches w1 -> w2).
Decision = order of each drone's trips (and so which trips fly before/after the front). Deterministic mean wind
(no OU/gusts) to measure the structural value. Compares plan order vs oracle best order (knows T) vs rule
(sort trips by pre-front advantage, using forecast T). Reports J = cost + P*failed (battery w/o reserve)."""
import wind, sys, json, math, itertools, numpy as np
from wind.model import ground_speed, MS
def trip_eval(ins, st, trip, t0, T, w1, w2, cap):
    p = ins.params; seq = [st] + [ins.nodes[n] for n in trip] + [st]; t = t0; e = 0.0; ok = True
    for li, (u, v) in enumerate(zip(seq, seq[1:])):
        w = w1 if t < T else w2
        vg = float(ground_speed(v.x - u.x, v.y - u.y, w[0], w[1])); d = math.hypot(v.x - u.x, v.y - u.y)
        if math.isnan(vg): vg = 0.3 * 900; ok = False
        t += d / vg; e += d / vg * p.flight_energy
        if li < len(seq) - 2: e += v.energy; t += v.service
    return t, (e <= cap + 1e-9) and ok
def drone_eval(ins, st, trips, T, w1, w2, cap, P):
    t = 0.0; fail = 0
    for tr in trips:
        t1, ok = trip_eval(ins, st, tr, t, T, w1, w2, cap); t = t1; fail += (not ok)
    return t * ins.params.time_cost + P * fail, t, fail
def best_order(ins, st, trips, T, w1, w2, cap, P):
    if len(trips) <= 1: return drone_eval(ins, st, trips, T, w1, w2, cap, P)
    if len(trips) <= 7:
        return min((drone_eval(ins, st, list(pm), T, w1, w2, cap, P) for pm in itertools.permutations(trips)), key=lambda x: x[0])
    # greedy pairwise improvement
    cur = list(trips); bv = drone_eval(ins, st, cur, T, w1, w2, cap, P)
    imp = True
    while imp:
        imp = False
        for i in range(len(cur)):
            for j in range(i + 1, len(cur)):
                c2 = cur[:]; c2[i], c2[j] = c2[j], c2[i]; v = drone_eval(ins, st, c2, T, w1, w2, cap, P)
                if v[0] < bv[0] - 1e-9: cur, bv, imp = c2, v, True
    return bv
def main(table, P=100.0, seed=0):
    from lrphsd.problem import read_instance
    rng = np.random.default_rng(seed); rows = [json.loads(l) for l in open(table)]
    rows = [r for r in rows if not r.get('infeasible') and abs(r['reserve'] - 0.15) < 1e-9]
    tot = dict(plan=0.0, rule=0.0, oracle=0.0, fixed=0.0); fl = dict(plan=0, rule=0, oracle=0)
    for r in rows:
        from wind.cases import LIU, DEVDIR
        b = r['case'].split('#')[0]; ins = read_instance(r.get('path') or (f'{DEVDIR}/{b}.txt' if b.startswith('d') else f'{LIU}/{b}.txt'))
        p = ins.params; ctx = r['ctx']; sol = r['solution']
        w1 = (ctx['W'] * MS * math.cos(ctx['theta']), ctx['W'] * MS * math.sin(ctx['theta']))
        W2 = rng.uniform(4, 10); th2 = ctx['theta'] + rng.choice([-1, 1]) * rng.uniform(math.pi / 2, math.pi)
        w2 = (W2 * MS * math.cos(th2), W2 * MS * math.sin(th2)); T = rng.uniform(30, 150); That = T + rng.normal(0, 30)
        fixed = 0.0
        for si, kind in enumerate(sol['station_types']):
            if not kind: continue
            fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
            st = ins.stations[si]
            for di, trips in enumerate(sol['routes'][si]):
                trips = [t for t in trips if t]
                if not trips: continue
                cap = p.large_battery if di == 0 else p.small_battery
                a = drone_eval(ins, st, trips, T, w1, w2, cap, P)
                o = best_order(ins, st, trips, T, w1, w2, cap, P)
                # rule: order chosen with forecast front time That (then evaluated with true T)
                ro = trips
                if len(trips) <= 7:
                    ro = list(min(itertools.permutations(trips), key=lambda pm: drone_eval(ins, st, list(pm), That, w1, w2, cap, P)[0]))
                rr = drone_eval(ins, st, ro, T, w1, w2, cap, P)
                def score(tr):
                    a1, ok1 = trip_eval(ins, st, tr, 0.0, 1e9, w1, w2, cap); a2, ok2 = trip_eval(ins, st, tr, 0.0, -1.0, w1, w2, cap)
                    return (a2 - a1) * p.time_cost + P * ((not ok2) - (not ok1))
                rem = list(trips); seqo = []; tt = 0.0
                while rem:
                    nx = max(rem, key=score) if tt < T else rem[0]
                    rem.remove(nx); seqo.append(nx); tt, _ = trip_eval(ins, st, nx, tt, T, w1, w2, cap)
                mo = drone_eval(ins, st, seqo, T, w1, w2, cap, P)
                tot['myopic'] = tot.get('myopic', 0.0) + mo[0]; fl['myopic'] = fl.get('myopic', 0) + mo[2]
                tot['plan'] += a[0]; tot['oracle'] += o[0]; tot['rule'] += rr[0]
                fl['plan'] += a[2]; fl['oracle'] += o[2]; fl['rule'] += rr[2]
        tot['fixed'] += fixed
    n = len(rows); F = tot['fixed']
    print(f'cases {n}  P={P}  fixed cost/case {F/n:.1f}')
    for k in ('plan', 'rule', 'myopic', 'oracle'):
        print(f'  {k:7s} J/case {(F + tot[k]) / n:.2f}  failed/case {fl[k] / n:.3f}')
    print(f'  oracle reorder headroom vs plan order: {100 * (tot["plan"] - tot["oracle"]) / (F + tot["plan"]):.2f}%  vs forecast-rule: {100 * (tot["rule"] - tot["oracle"]) / (F + tot["rule"]):.2f}%  vs online-myopic: {100 * (tot["myopic"] - tot["oracle"]) / (F + tot["myopic"]):.2f}%')
if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 100.0)
