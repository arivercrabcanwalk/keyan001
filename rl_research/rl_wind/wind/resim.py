"""Re-simulate stored plans with an independent scenario seed (removes oracle selection bias). usage: resim.py IN OUT S SEEDOFF W"""
import wind, sys, json, os, zlib
from multiprocessing import get_context
def job(t):
    line, S, off = t
    r = json.loads(line)
    if r.get('infeasible'): return r
    from lrphsd.problem import read_instance
    from wind.model import simulate
    from wind.cases import LIU, DEVDIR
    base = r['case'].split('#')[0]
    path = r.get('path') or (f'{DEVDIR}/{base}.txt' if base.startswith('d') else (f'/workspace/rl_wind/instances/train/{base}.txt' if base.startswith('w') else f'{LIU}/{base}.txt'))
    ins = read_instance(path)
    sim = simulate(ins, r['solution'], r['ctx'], S=S, seed=zlib.crc32(r['case'].encode()) + off)
    r.update(cost=float(sim['cost'].mean()), makespan=float(sim['makespan'].mean()), failed=float(sim['failed'].mean()),
             p_anyfail=float((sim['failed'] > 0).mean()), undelivered=float(sim['undelivered'].mean()))
    return r
if __name__ == '__main__':
    IN, OUT, S, off, W = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    lines = open(IN).read().splitlines()
    with get_context('forkserver').Pool(W) as p, open(OUT, 'w') as f:
        for r in p.imap(job, [(l, S, off) for l in lines], chunksize=4):
            f.write(json.dumps(r) + '\n')
