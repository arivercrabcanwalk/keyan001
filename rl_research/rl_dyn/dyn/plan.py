"""Static LRPHSD plans. usage: plan.py SET METHOD OUT WORKERS [sec] [lam]
SET: train|dev|test ; METHOD: alns (our cooled NoRL engine, F=cost+lam*mk) | tsalns (Python TSALNS = authors, cost only)"""
import dyn, sys, os, json, glob
from multiprocessing import get_context
LIU = '/workspace/rl_dyn/engine/external/LRPHSD/data/Instances_Alg'
SIZES = ['5_35', '6_50', '7_65', '8_80', '10_110']
def cases(SET):
    if SET == 'test': return [f'{LIU}/{s}_{i}.txt' for s in SIZES for i in range(1, 11)]
    if SET == 'dev': return [f'/workspace/rl_rt/instances/dev/d{s}_{i}.txt' for s in SIZES for i in (1, 2, 3, 4)]
    if SET == 'train':
        fs = sorted(glob.glob('/workspace/rl_wind/instances/train/w*.txt'), key=lambda p: int(p.split('_')[-1][:-4]))
        return fs[:200]
def job(t):
    path, method, sec, lam = t
    from lrphsd.problem import read_instance
    ins = read_instance(path)
    if method == 'alns':
        from rlv3.search4 import solve4, FirstM
        res = solve4(ins, FirstM(), seed=0, seconds=sec, M=1, G=1, lam=lam); sol = res['solution']; obj = res['objective']
    else:
        from lrphsd.tsalns import solve
        sol, info = solve(ins, seed=0, seconds=sec); obj = info['objective']
    return dict(path=path, method=method, sec=sec, lam=lam, plan_obj=obj, solution=sol)
if __name__ == '__main__':
    SET, method, out, W = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    sec = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
    lam = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
    done = set()
    if os.path.exists(out): done = {json.loads(l)['path'] for l in open(out)}
    jobs = [(p, method, sec, lam) for p in cases(SET) if p not in done]
    with get_context('forkserver').Pool(W, maxtasksperchild=20) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, jobs):
            f.write(json.dumps(r) + '\n'); f.flush()
    open(out + '.done', 'w').write('ok')
