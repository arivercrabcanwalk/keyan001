"""Headroom diagnostic for an adaptive (context-dependent) battery reserve.
For each case and reserve r in GRID: plan with cooled ALNS (search4, M=1, 1 s) on the forecast-wind instance derated by (1+r);
execute the plan in S=200 realized-wind scenarios (common random numbers across r). usage: headroom.py SET OUT WORKERS"""
import wind, sys, os, json, numpy as np
from multiprocessing import get_context
GRID = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
def job(t):
    path, cid, ctx, r, sec, M = t
    import zlib
    from lrphsd.problem import read_instance
    from rlv3.search4 import solve4, FirstM
    from wind.model import make_planning_instance, simulate
    ins = read_instance(path)
    try:
        q = make_planning_instance(ins, ctx, r)
        res = solve4(q, FirstM(), seed=0, seconds=sec, M=M, G=M)
    except ValueError as e:
        return dict(case=cid, reserve=r, sec=sec, M=M, infeasible=True, ctx=ctx, err=str(e)[:60])
    sim = simulate(ins, res['solution'], ctx, S=200, seed=zlib.crc32(cid.encode()))
    return dict(case=cid, path=path, reserve=r, sec=sec, M=M, plan_obj=res['objective'], ctx=ctx,
                cost=float(sim['cost'].mean()), makespan=float(sim['makespan'].mean()), failed=float(sim['failed'].mean()),
                p_anyfail=float((sim['failed'] > 0).mean()), undelivered=float(sim['undelivered'].mean()),
                overtime=float(sim['overtime'].mean()), ntrips=sum(len([t for t in d if t]) for s in res['solution']['routes'] for d in s),
                solution=res['solution'])
if __name__ == '__main__':
    import os, wind.model as wm
    wm.STRONG = bool(os.environ.get('STRONG'))
    from wind.cases import dev_cases, test_cases, train_cases
    SET, out, W = sys.argv[1], sys.argv[2], int(sys.argv[3])
    cases = {'dev': dev_cases, 'test': test_cases, 'train': lambda: train_cases(int(os.environ.get('NTRAIN', 150)))}[SET]()
    grid = GRID if not os.environ.get('TYPEGRID') else [(a, b) for a in (0.1, 0.2, 0.3, 0.4, 0.5) for b in (0.05, 0.1, 0.2, 0.3)] if os.environ.get('TYPEGRID') == '2' else [(a, b) for a in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5) for b in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5)]
    jobs = [(p, c, x, r, float(os.environ.get('SEC', 1.0)), 1) for p, c, x in cases for r in grid]
    done = set()
    if os.path.exists(out): done = {(json.loads(l)['case'], str(json.loads(l)['reserve'])) for l in open(out)}
    jobs = [j for j in jobs if (j[1], str(list(j[3]) if isinstance(j[3], tuple) else j[3])) not in done]
    with get_context('forkserver').Pool(W, maxtasksperchild=20) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, jobs):
            f.write(json.dumps(r) + '\n'); f.flush()
    open(out + '.done', 'w').write('ok')
