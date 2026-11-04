"""Scenario 2: dynamic re-planning events. usage: dynamic.py CKPT SET(dev|test) OUT.jsonl
Events (per instance, lam in {0, 0.5}):
  surge10/surge20 : energy consumption +10/20% -> nominal plan audited under surge (fraction of failing trips),
                    then re-plan with reserve r = 0.1/0.2 (RL conditioned on r; ALNS run on the de-rated instance)
  newtgt          : +10% new targets (uniform, within 4750 m of a station), re-plan from scratch
  outage          : the open station serving most targets in the nominal plan fails (removed); targets only it
                    could reach are dropped (same instance for every method)
Methods: RL greedy / aug8 / T50 (anytime sampling) ; ALNS (cooled NoRL M=1) at 10/50/100 ms ; RL warm start + ALNS at 50/100 ms.
All wall-clock includes everything after the event is known (instance build, encode/prepare, decode, conversion)."""
import sys, os, json, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine'); sys.path.insert(0, '/workspace/rl_v3')
torch.set_num_threads(1)
from dataclasses import replace
from lrphsd.problem import read_instance, Instance
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build
from rt.inst import from_lrphsd, gen
from rt.model import Policy
from rt.fast import Fast
from rt.solution import decode, to_solution, makespan
from rt.search_ws import solve4, FirstM
ck, SET, out = sys.argv[1], sys.argv[2], sys.argv[3]
if SET == 'dev':
    from rt.ref_alns import DEV as NAMES, DIR
else:
    DIR = '/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg'
    NAMES = [f'{s}_{i}' for s in ['5_35', '6_50', '7_65', '8_80', '10_110'] for i in range(1, 11)]
if os.environ.get('ONLY'): NAMES = os.environ['ONLY'].split(',')
EDIR = f'/workspace/rl_rt/instances/dyn_{SET}'; os.makedirs(EDIR, exist_ok=True)
from rt.model import load_policy; pol = load_policy(ck); pol.eval(); fs = Fast(pol)
def write(path, tg, st):
    rows = ['CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME']; k = 1
    for x, y in tg: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.2000\t10.0000'); k += 1
    for x, y in st: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000'); k += 1
    open(path, 'w').write('\n'.join(rows) + '\n')
def derate(ins, r):
    p = ins.params
    return Instance(ins.name, ins.targets, ins.stations, ins.sha256, replace(p, small_battery=p.small_battery / (1 + r), large_battery=p.large_battery / (1 + r)))
def kappa_of(ins, lam):
    ev, mk = makespan(ins, build(ins)); return lam * ev['cost'] / mk
def F_of(ins_eval, sol, k):
    ev, mk = makespan(ins_eval, sol); return ev['cost'] + k * mk, ev['feasible'], ev['cost'], mk
f = open(out, 'a')
def emit(**kw): f.write(json.dumps(kw) + '\n'); f.flush()
fs.solve(*from_lrphsd(read_instance(f'{DIR}/{NAMES[0]}.txt'))[:2], 0.0, 0.0, 'sample:2')
for name in NAMES:
    ins0 = read_instance(f'{DIR}/{name}.txt'); tg0, st0, tid0, sid0 = from_lrphsd(ins0)
    import zlib; rng = np.random.default_rng(zlib.crc32(name.encode()))
    for lam in (0.0, 0.5):
        k0 = kappa_of(ins0, lam)
        nom = solve4(ins0, FirstM(), seed=0, seconds=1.0, M=1, G=1, lam=lam, mk_w_override=k0)['solution']
        events = []
        for s in (0.1, 0.2):
            ev_s = evaluate(derate(ins0, s), nom)
            ntrip = sum(len(tr) for stn in nom['routes'] for tr in stn)
            events.append((f'surge{int(s*100)}', ins0, s, dict(nominal_feasible_under_surge=ev_s['feasible'], issues=len(ev_s['issues']), trips=ntrip)))
        # new targets
        n_new = max(2, int(round(0.1 * len(tg0))))
        new = []
        while len(new) < n_new:
            c = rng.uniform(0, 15000, 2)
            if np.sqrt(((st0 - c) ** 2).sum(1)).min() <= 4750: new.append(c)
        p = f'{EDIR}/{name}_new.txt'; write(p, np.concatenate([tg0, np.array(new)]), st0)
        events.append(('newtgt', read_instance(p), 0.0, dict(n_new=n_new)))
        # outage: open station serving most targets
        load = [sum(len(t) for dr in nom['routes'][i] for t in dr) for i in range(len(st0))]
        j = int(np.argmax(load)); keep_st = np.delete(st0, j, 0)
        dd = np.sqrt(((tg0[:, None] - keep_st[None]) ** 2).sum(-1)).min(1)
        tg_k = tg0[dd <= 5000 - 1e-6]
        p = f'{EDIR}/{name}_out.txt'; write(p, tg_k, keep_st)
        events.append(('outage', read_instance(p), 0.0, dict(dropped=int(len(tg0) - len(tg_k)), station=j)))
        for ev_name, ins, r, info in events:
            k = k0 if ev_name.startswith('surge') else None
            insr = derate(ins, r) if r else ins
            if k is None:
                k = kappa_of(ins, lam)   # problem parameter of the new instance (not timed: it is the decision-maker's price)
            base = dict(inst=name, lam=lam, event=ev_name, **info)
            tg, st, tid, sid = from_lrphsd(ins)
            for mode in ('greedy', 'aug8', 'T50'):
                t0 = time.perf_counter()
                if mode == 'T50': q = fs.solve(tg, st, k, r, 'aug8s:100000', deadline=t0 + 0.0495)
                else: q = fs.solve(tg, st, k, r, mode)
                ty, ro = decode(q[3], len(tg), len(st), tid); sol = to_solution(ins, ty, ro)
                wall = time.perf_counter() - t0
                F, feas, c, mk = F_of(insr, sol, k)
                emit(method='rl_' + mode, objective=F, feasible=feas, cost=c, makespan=mk, wall=wall, **base)
            for B in (0.01, 0.05, 0.1):
                for seed in (0, 1):
                    t0 = time.perf_counter()
                    try:
                        q = solve4(ins, FirstM(), seed=seed, seconds=B, M=1, G=1, lam=lam, reserve=r, mk_w_override=k)
                        wall = time.perf_counter() - t0
                        F, feas, c, mk = F_of(insr, q['solution'], k)
                        emit(method='alns_m1', seconds=B, seed=seed, objective=F, feasible=feas, cost=c, makespan=mk, wall=wall, **base)
                    except Exception as e:
                        emit(method='alns_m1', seconds=B, seed=seed, objective=None, feasible=False, err=str(e)[:80], wall=time.perf_counter() - t0, **base)
            for B in (0.05, 0.1):
                for seed in (0, 1):
                    t0 = time.perf_counter()
                    q = fs.solve(tg, st, k, r, 'aug8')
                    ty, ro = decode(q[3], len(tg), len(st), tid); sol = to_solution(ins, ty, ro)
                    q = solve4(ins, FirstM(), seed=seed, seconds=B - (time.perf_counter() - t0), M=1, G=1, lam=lam, reserve=r, init_sol=sol, mk_w_override=k)
                    wall = time.perf_counter() - t0
                    F, feas, c, mk = F_of(insr, q['solution'], k)
                    emit(method='rlws_m1', seconds=B, seed=seed, objective=F, feasible=feas, cost=c, makespan=mk, wall=wall, **base)
            # long reference for this event (gap denominator)
            q = solve4(ins, FirstM(), seed=0, seconds=3.0, M=4, G=4, lam=lam, reserve=r, mk_w_override=k)
            F, feas, c, mk = F_of(insr, q['solution'], k)
            emit(method='ref_m4_3s', objective=F, feasible=feas, cost=c, makespan=mk, wall=3.0, **base)
