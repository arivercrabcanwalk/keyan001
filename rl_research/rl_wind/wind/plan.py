"""Plans for a case set. usage: plan.py SET METHOD OUT WORKERS [reserves comma] [seconds]
METHOD: alns (cooled NoRL engine, forecast wind) | tsalns_nowind | tsalns_fc (Python TSALNS = authors' algorithm; Java unavailable)"""
import wind, sys, os, json
from multiprocessing import get_context
def job(t):
    path, cid, ctx, method, r, sec = t
    from lrphsd.problem import read_instance
    from wind.model import make_planning_instance
    ins = read_instance(path)
    if method == 'alns':
        from rlv3.search4 import solve4, FirstM
        q = make_planning_instance(ins, ctx, r)
        res = solve4(q, FirstM(), seed=0, seconds=sec, M=1, G=1); sol = res['solution']; obj = res['objective']
    else:
        from lrphsd.tsalns import solve
        q = make_planning_instance(ins, ctx, r, use_wind=(method == 'tsalns_fc'))
        try:
            sol, info = solve(q, seed=0, seconds=sec); obj = info['objective']
        except ValueError as e:
            return dict(case=cid, path=path, ctx=ctx, method=method, reserve=r, sec=sec, infeasible=True, err=str(e)[:60])
    return dict(case=cid, path=path, ctx=ctx, method=method, reserve=r, sec=sec, plan_obj=obj, solution=sol)
if __name__ == '__main__':
    import wind.model as wm
    wm.STRONG = bool(os.environ.get('STRONG'))
    from wind.cases import dev_cases, test_cases, train_cases
    SET, method, out, W = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    R = [float(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 else [0.0, 0.05, 0.1]
    sec = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
    cases = {'dev': dev_cases, 'test': test_cases, 'train': train_cases}[SET]()
    jobs = [(p, c, x, method, r, sec) for p, c, x in cases for r in R]
    done = set()
    if os.path.exists(out): done = {(json.loads(l)['case'], json.loads(l)['reserve']) for l in open(out)}
    jobs = [j for j in jobs if (j[1], j[4]) not in done]
    with get_context('forkserver').Pool(W, maxtasksperchild=20) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, jobs):
            f.write(json.dumps(r) + '\n'); f.flush()
    open(out + '.done', 'w').write('ok')
