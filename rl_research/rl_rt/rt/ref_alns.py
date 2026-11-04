"""ALNS / TSALNS references on rl_rt dev instances.
usage: ref_alns.py OUT WORKERS  (job list built in-file)"""
import sys, os, json, time
sys.path.insert(0, '/workspace/rl_v3'); sys.path.insert(0, '/workspace/rl_v3/engine')
from multiprocessing import get_context
DEV = [f'd{s}_{i}' for s in ['5_35', '6_50', '7_65', '8_80', '10_110'] for i in (1, 2, 3, 4)]
DIR = '/workspace/rl_rt/instances/dev'
def run(t):
    meth, inst, lam, seed, sec = t
    from lrphsd.problem import read_instance
    ins = read_instance(f'{DIR}/{inst}.txt')
    if meth == 'tsalns':
        from lrphsd.tsalns import solve
        from lrphsd.evaluator import evaluate
        t0 = time.perf_counter(); sol, info = solve(ins, seed=seed, seconds=sec)
        ev = evaluate(ins, sol)
        return dict(method=meth, inst=inst, lam=lam, seed=seed, seconds=sec, cost=ev['cost'], feasible=ev['feasible'],
                    wall=time.perf_counter() - t0, outer=info.get('outer_iterations_attempted'))
    from rlv3.search4 import solve4, FirstM
    M = {'norl_m1': 1, 'norl_m4': 4, 'norl_8': 8}[meth]
    t0 = time.perf_counter()
    r = solve4(ins, FirstM(), seed=seed, seconds=sec, M=M, G=M, lam=lam, reserve=0.0)
    wall = time.perf_counter() - t0
    return dict(method=meth, inst=inst, lam=lam, seed=seed, seconds=sec, objective=r['objective'], cost=r['cost'],
                makespan=r['makespan'], mk_w=r['mk_w'], feasible=r['feasible'], init_obj=r['init_obj'], steps=r['steps'], wall=wall)
if __name__ == '__main__':
    out, W, phase = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    jobs = []
    if phase == 'budget':
        for sec in (0.01, 0.05, 0.1, 0.3, 1.0):
            for meth in ('norl_m1', 'norl_m4'):
                for lam in (0.0, 0.5):
                    for seed in (0, 1):
                        for inst in DEV: jobs.append((meth, inst, lam, seed, sec))
    else:  # long references
        for inst in DEV:
            for lam in (0.0, 0.5):
                for seed in (0, 1): jobs.append(('norl_8', inst, lam, seed, 10.0))
            jobs.append(('tsalns', inst, 0.0, 0, 30.0))
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l); done.add((r['method'], r['inst'], r['lam'], r['seed'], r['seconds']))
    jobs = [j for j in jobs if j not in done]
    with get_context('forkserver').Pool(W, maxtasksperchild=50) as p, open(out, 'a') as f:
        for r in p.imap_unordered(run, jobs):
            f.write(json.dumps(r) + '\n'); f.flush()
    open(out + '.done', 'w').write('ok')
