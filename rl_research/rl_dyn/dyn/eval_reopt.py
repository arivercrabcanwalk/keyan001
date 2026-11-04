"""Evaluate (A3) TS-reopt variants. usage: eval_reopt.py SET OUT METHODS nseeds seed0 workers
methods: reopt_ev_<sec> (re-opt at each urgent arrival) | reopt_p<delta>_<sec> (each arrival + every delta min)"""
import dyn, sys, os, json, time
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day
from dyn.simreopt import SimReopt
def job(a):
    pt, seed, nm = a
    ins = read_instance(pt['path']); day = Day(ins, seed)
    _, trig, sec = nm.split('_'); delta = None if trig == 'ev' else float(trig[1:])
    t = time.time(); m = SimReopt(ins, pt['solution'], day, sec=float(sec), delta=delta, seed=seed).run(); w = time.time() - t
    m['ms_per_dec'] = m['reopt_s'] * 1e3 / max(1, m['n_reopt']); m['wall_s'] = w
    return dict(path=pt['path'], seed=seed, method=nm, hot=bool(day.has_hot), **m)
if __name__ == '__main__':
    SET, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    ns, s0, W = int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
    PT = [json.loads(l) for l in open(f'plans/{SET}_ts.jsonl')]
    done = set()
    if os.path.exists(out): done = {(x['path'], x['seed'], x['method']) for x in map(json.loads, open(out))}
    jobs = [(pt, s0 + s, nm) for nm in names for s in range(ns) for pt in PT if (pt['path'], s0 + s, nm) not in done]
    print(len(jobs), 'jobs', flush=True)
    with get_context('fork').Pool(W) as p, open(out, 'a') as f:
        for k, x in enumerate(p.imap_unordered(job, jobs, chunksize=1)):
            f.write(json.dumps(x) + '\n'); f.flush()
            if k % 25 == 0: print(k, time.strftime('%H:%M'), flush=True)
