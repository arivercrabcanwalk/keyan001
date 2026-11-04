"""Evaluate recourse policies on a plans file with common random wind scenarios.
usage: evalpol.py PLANS OUT S WORKERS RESERVES POLICY [POLICY ...]
POLICY: none | margin:m | look:eps | oracle | rl:CKPT:P
Each output row = mean over S scenarios for one (case, reserve, policy) + per-decision wall-clock."""
import wind, sys, os, json, zlib, time, numpy as np
from multiprocessing import get_context
_ins = {}
def mkpol(spec, r):
    from wind.online import pol_none, make_margin, make_lookahead, pol_oracle
    k = spec.split(':')
    if k[0] == 'none': return pol_none
    if k[0] == 'margin': return make_margin(float(k[1]))
    if k[0] == 'look': return make_lookahead(float(k[1]), M=64)
    if k[0] == 'oracle': return pol_oracle
    if k[0] == 'rl':
        import torch
        from wind.rlpol import make_rl
        sd = torch.load(k[1]); params = [sd[x].numpy() for x in ('l1.weight', 'l1.bias', 'l2.weight', 'l2.bias', 'l3.weight', 'l3.bias', 'skip.weight', 'skip.bias')]
        return make_rl(params, float(k[2]), r['reserve'])
    raise ValueError(spec)
def job(t):
    r, specs, S = t
    from lrphsd.problem import read_instance
    from wind.online import Scenario, run
    ins = read_instance(r['path']); out = []
    scs = [Scenario(r['ctx'], zlib.crc32(f"{r['case']}#{s}".encode())) for s in range(S)]
    for spec in specs:
        pol = mkpol(spec, r); calls = [0, 0.0]
        def timed(obs, pol=pol):
            t0 = time.perf_counter(); k = pol(obs); calls[0] += 1; calls[1] += time.perf_counter() - t0; return k
        ms = [run(ins, r['solution'], r['ctx'], sc, timed) for sc in scs]
        out.append(dict(case=r['case'], method=r.get('method', 'alns'), reserve=r['reserve'], policy=spec, S=S,
                        **{m: float(np.mean([x[m] for x in ms])) for m in ('cost', 'makespan', 'failed', 'undelivered', 'trims', 'overtime')},
                        p_anyfail=float(np.mean([x['failed'] > 0 for x in ms])), ms_per_decision=1000 * calls[1] / max(calls[0], 1)))
    return out
if __name__ == '__main__':
    plans, out, S, W, R = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), [float(x) for x in sys.argv[5].split(',')]
    specs = sys.argv[6:]
    rows = [json.loads(l) for l in open(plans)]; rows = [r for r in rows if r['reserve'] in R]
    done = set()
    if os.path.exists(out):
        for l in open(out): x = json.loads(l); done.add((x['case'], x['reserve'], x['policy']))
    jobs = []
    for r in rows:
        todo = [s for s in specs if (r['case'], r['reserve'], s) not in done]
        if todo: jobs.append((r, todo, S))
    with get_context('forkserver').Pool(W, maxtasksperchild=10) as p, open(out, 'a') as f:
        for res in p.imap_unordered(job, jobs):
            for x in res: f.write(json.dumps(x) + '\n')
            f.flush()
    open(out + '.done', 'w').write('ok')
