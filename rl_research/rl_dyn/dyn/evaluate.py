"""Evaluate methods on a set. usage: evaluate.py SET OUT METHODS(comma) [nseeds] [seed0] [workers]
methods: ts_ins | ts_myo | ts_static<T> | myo | static<T>[a] | slack<T>_<m> | adapt<th> | roll<M> | clair | rl=<ckpt>[@ts]"""
import dyn, sys, os, json, time, numpy as np, torch
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day, Sim
from dyn.simts import SimTS
from dyn import pol as P
_RL = {}
def rlpol(ck):
    if ck not in _RL:
        from dyn.train import Net
        from dyn.rl import NPPolicy
        n = Net(); n.load_state_dict(torch.load(ck)); _RL[ck] = n.np_params()
    from dyn.rl import NPPolicy
    return NPPolicy(_RL[ck], greedy=True)
def make(name):
    if name in ('myo', 'ts_myo'): return P.myopic
    if name.startswith('ts_static'): return P.make_static(float(name[9:]))
    if name.startswith('static'):
        a = name.endswith('a'); return P.make_static(float(name[6:].rstrip('a')), dabs_only=not a)
    if name.startswith('slack'): T, m = name[5:].split('_'); return P.make_slack(float(T), float(m))
    if name.startswith('adapt'): return P.make_adaptive(float(name[5:]))
    if name.startswith('rollb30_'): return P.make_rollout(int(name[8:]), base=P.make_static(30))
    if name.startswith('roll'): return P.make_rollout(int(name[4:]), base=P.make_static(120))
    if name == 'clair': return P.make_clairvoyant(P.make_static(120))
    if name.startswith('rl='): return rlpol(name[3:].split('@')[0])
    if name.startswith('ac='):
        from dyn.ppo import ACNet, TorchPol
        ck = name[3:].split('@')[0]
        if ck not in _RL:
            sd = torch.load(ck); net = ACNet(any(k.startswith('ed.') for k in sd)); net.load_state_dict(sd); net.eval(); _RL[ck] = net
        return TorchPol(_RL[ck], True, None)
    raise ValueError(name)
def job(a):
    po, pt, seed, names = a
    ins = read_instance(po['path']); day = Day(ins, seed); out = []
    for nm in names:
        t = time.time()
        if nm == 'ts_ins': m = SimTS(ins, pt['solution'], day).run(None)
        else:
            sol = pt['solution'] if (nm.startswith('ts_') or nm.endswith('@ts')) else po['solution']
            m = Sim(ins, sol, day).run(make(nm))
        m['ms_per_dec'] = (time.time() - t) * 1e3 / max(1, m['ndec'])
        out.append(dict(path=po['path'], seed=seed, method=nm, hot=bool(day.has_hot), **m))
    return out
if __name__ == '__main__':
    SET, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    ns = int(sys.argv[4]) if len(sys.argv) > 4 else 10; s0 = int(sys.argv[5]) if len(sys.argv) > 5 else {'dev': 2000, 'test': 5000}[SET]
    W = int(sys.argv[6]) if len(sys.argv) > 6 else 4
    PO = [json.loads(l) for l in open(f'plans/{SET}_ours.jsonl')]; PT = {json.loads(l)['path']: json.loads(l) for l in open(f'plans/{SET}_ts.jsonl')}
    done = set()
    if os.path.exists(out): done = {(x['path'], x['seed'], x['method']) for x in map(json.loads, open(out))}
    jobs = []
    for po in PO:
        for s in range(ns):
            nm = [n for n in names if (po['path'], s0 + s, n) not in done]
            if nm: jobs.append((po, PT[po['path']], s0 + s, nm))
    torch.set_num_threads(1)
    with get_context('fork').Pool(W) as p, open(out, 'a') as f:
        for res in p.imap_unordered(job, jobs):
            for x in res: f.write(json.dumps(x) + '\n')
            f.flush()
