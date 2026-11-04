"""Headroom diagnostic: myopic vs rules vs sampled rollout vs clairvoyant rollout. usage: headroom.py PLANFILE OUT [nseeds]"""
import dyn, sys, json, time, numpy as np
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day, Sim
from dyn import pol as P
import os
def policies():
    d = {'myopic': P.myopic, 'static120': P.make_static(120)}
    for T in (120, 240):
        for mg in (0, 10, 20):
            d[f'slack{T}_{mg}'] = P.make_slack(T, mg); d[f'slackA{T}_{mg}'] = P.make_slack(T, mg, need_station=False)
    d['clair_st'] = P.make_clairvoyant(P.make_static(120)); d['clair_sl'] = P.make_clairvoyant(P.make_slack(240, 0))
    st = P.make_static(120)
    for M in (2, 8, 32): d[f'roll{M}_st'] = P.make_rollout(M, base=st)
    sel = os.environ.get('POLS')
    if sel: d = {k: v for k, v in d.items() if k in sel.split(',')} | {'myopic': P.myopic}
    return d
def job(a):
    r, seed, names = a
    ins = read_instance(r['path']); day = Day(ins, seed); out = []
    pols = policies()
    for nm in names:
        t = time.time(); m = Sim(ins, r['solution'], day).run(pols[nm]); m['ms'] = (time.time() - t) * 1e3
        out.append(dict(path=r['path'], seed=seed, pol=nm, hot=bool(day.has_hot), **m))
    return out
if __name__ == '__main__':
    plans = [json.loads(l) for l in open(sys.argv[1])]; out = sys.argv[2]; ns = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    names = list(policies().keys())
    jobs = [(r, 1000 + s, names) for r in plans for s in range(ns)]
    with get_context('fork').Pool(4) as p, open(out, 'w') as f:
        for res in p.imap_unordered(job, jobs):
            for x in res: f.write(json.dumps(x) + '\n')
            f.flush()
