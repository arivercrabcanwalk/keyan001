"""Short-budget behaviour of cooled ALNS on wind instances (forecast planning, r=0.05): init gap and gaps at 10-300 ms vs 3 s M=4."""
import wind, sys, json, numpy as np
from multiprocessing import get_context
def job(t):
    path, cid, ctx, sec, M, seed = t
    from lrphsd.problem import read_instance
    from rlv3.search4 import solve4, FirstM
    from wind.model import make_planning_instance
    q = make_planning_instance(read_instance(path), ctx, 0.05)
    r = solve4(q, FirstM(), seed=seed, seconds=sec, M=M, G=M)
    return dict(case=cid, sec=sec, M=M, seed=seed, obj=r['objective'], init=r['init_obj'])
if __name__ == '__main__':
    from wind.cases import dev_cases
    jobs = [(p, c, x, s, 1, sd) for p, c, x in dev_cases() for s in (0.01, 0.05, 0.1, 0.3) for sd in (0, 1)] + [(p, c, x, 3.0, 4, 0) for p, c, x in dev_cases()]
    with get_context('forkserver').Pool(7) as pool, open(sys.argv[1], 'w') as f:
        for r in pool.imap_unordered(job, jobs): f.write(json.dumps(r) + '\n')
