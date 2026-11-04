"""Demonstrations for BC warm start: generated Liu-style instances (seed range 10_000_000+, disjoint from dev/val)
solved by cooled ALNS (rl_v3 search4, M=1, 1 s), lam in {0,0.25,0.5,1,2}, reserve in {0,0.1,0.2}.
usage: gen_demo.py OUT.jsonl START COUNT WORKERS"""
import sys, os, json
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine'); sys.path.insert(0, '/workspace/rl_v3')
from multiprocessing import get_context
SIZES = [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]
def job(i):
    import numpy as np
    from rt.inst import gen
    from lrphsd.problem import read_instance
    from rt.search_ws import solve4, FirstM
    rng = np.random.default_rng(10_000_000 + i)
    ns, n = SIZES[i % 5]
    lam = [0.0, 0.0, 0.25, 0.5, 1.0, 2.0][rng.integers(6)]; r = [0.0, 0.0, 0.1, 0.2][rng.integers(4)]
    for _ in range(20):
        tg, st = gen(n, ns, rng)
        p = f'/workspace/rl_rt/instances/demo/x{i}.txt'
        rows = ['CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME']; k = 1
        for x, y in tg: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.2000\t10.0000'); k += 1
        for x, y in st: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000'); k += 1
        open(p, 'w').write('\n'.join(rows) + '\n')
        try:
            q = solve4(read_instance(p), FirstM(), seed=i, seconds=1.0, M=1, G=1, lam=lam, reserve=r)
        except Exception:
            continue
        finally:
            os.remove(p)
        if q['feasible']:
            tgr = [[float(f'{x:.4f}'), float(f'{y:.4f}')] for x, y in tg]; str_ = [[float(f'{x:.4f}'), float(f'{y:.4f}')] for x, y in st]
            return dict(i=i, tg=tgr, st=str_, lam=lam, reserve=r, kappa=q['mk_w'], objective=q['objective'],
                        types=q['solution']['station_types'], routes=q['solution']['routes'])
    return None
if __name__ == '__main__':
    out, s0, cnt, W = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    done = set()
    if os.path.exists(out): done = {json.loads(l)['i'] for l in open(out)}
    jobs = [i for i in range(s0, s0 + cnt) if i not in done]
    with get_context('forkserver').Pool(W, maxtasksperchild=100) as p, open(out, 'a') as f:
        for r in p.imap_unordered(job, jobs, chunksize=4):
            if r: f.write(json.dumps(r) + '\n'); f.flush()
    open(out + '.done', 'w').write('ok')
