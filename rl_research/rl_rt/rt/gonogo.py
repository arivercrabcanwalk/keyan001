"""Go/no-go on rl_rt dev instances: RL (fast numba path, 1 thread) vs references.
usage: gonogo.py CKPT OUT.jsonl"""
import sys, json, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine')
torch.set_num_threads(1)
from lrphsd.problem import read_instance
from rt.inst import from_lrphsd
from rt.model import Policy
from rt.fast import Fast
from rt.solution import decode, to_solution, makespan
from rt.ref_alns import DEV, DIR
ck, out = sys.argv[1], sys.argv[2]
nocond = 'nocond' in ck
from rt.model import load_policy; pol = load_policy(ck, cond=not nocond); pol.eval(); fs = Fast(pol)
kap = {}
for l in open('/workspace/rl_rt/results/dev_ref.jsonl'):
    r = json.loads(l)
    if r['method'] == 'norl_8': kap[(r['inst'], r['lam'])] = r['mk_w']
MODES = ['greedy', 'aug8', 'sample:16', 'aug8s:8', 'sample:64', 'aug8s:32', 'T10', 'T50', 'T100']
# warm-up compile
ins = read_instance(f'{DIR}/{DEV[0]}.txt'); tg, st, *_ = from_lrphsd(ins); fs.solve(tg, st, 0.0, 0.0, 'sample:2')
with open(out, 'w') as f:
    for inst in DEV:
        ins = read_instance(f'{DIR}/{inst}.txt'); tg, st, tid, sid = from_lrphsd(ins)
        for lam in (0.0, 0.5):
            if (inst, lam) in kap: k = kap[(inst, lam)]
            else:
                from lrphsd.greedy import build
                ev0, mk0 = makespan(ins, build(ins)); k = lam * ev0['cost'] / mk0
            for mode in MODES:
                t0 = time.perf_counter()
                if mode.startswith('T'):
                    ms = int(mode[1:]); r = fs.solve(tg, st, k, 0.0, 'aug8s:100000', deadline=t0 + ms / 1000 - 0.0005)
                else:
                    r = fs.solve(tg, st, k, 0.0, mode)
                ty, ro = decode(r[3], len(tg), len(st), tid); sol = to_solution(ins, ty, ro)
                wall = time.perf_counter() - t0
                ev, mk = makespan(ins, sol)
                rec = dict(method='rl_' + mode, inst=inst, lam=lam, kappa=k, objective=ev['cost'] + k * mk, cost=ev['cost'], makespan=mk,
                           feasible=ev['feasible'], wall=wall, rollouts=r[5])
                f.write(json.dumps(rec) + '\n'); f.flush()
            # warm start: RL aug8 then cooled ALNS (M=1) for the rest of the budget
            from rt.search_ws import solve4, FirstM
            for B in (0.05, 0.1, 0.3):
                for seed in (0, 1):
                    t0 = time.perf_counter()
                    r = fs.solve(tg, st, k, 0.0, 'aug8')
                    ty, ro = decode(r[3], len(tg), len(st), tid); sol = to_solution(ins, ty, ro)
                    rem = B - (time.perf_counter() - t0)
                    q = solve4(ins, FirstM(), seed=seed, seconds=rem, M=1, G=1, lam=lam, init_sol=sol, mk_w_override=k)
                    wall = time.perf_counter() - t0
                    f.write(json.dumps(dict(method='rlws_aug8_m1', seconds=B, seed=seed, inst=inst, lam=lam, objective=q['objective'],
                                            cost=q['cost'], makespan=q['makespan'], feasible=q['feasible'], wall=wall)) + '\n'); f.flush()
