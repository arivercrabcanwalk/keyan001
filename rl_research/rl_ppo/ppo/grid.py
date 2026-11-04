"""Run spec grid. Usage: grid.py OUT SPECS(;-sep) INSTSET LAMS SEEDS SECS [W]
INSTSET: tune4 (g*_1..4) | dev | test | tuneall"""
import sys, os, json, random
sys.path.insert(0, '/workspace/rl_ppo')
from multiprocessing import Pool
from ppo import common
SETS = dict(tune4=[f'g{s}_{i}' for s in common.SIZES for i in range(1, 5)], dev=common.DEV, test=common.TEST,
            tuneall=common.TUNE, tune5_10=[f'g{s}_{i}' for s in common.SIZES for i in range(5, 11)])
_CK = {}
def controller(spec, seed):
    from ppo import specs
    if spec.startswith('distill:'):
        _, f, key = spec.split(':', 2); sch = [tuple(c) for c in json.load(open(f))[key]]
        return lambda o, k, S: sch[min(k, len(sch) - 1)]
    if not spec.startswith('rl:'): return specs.make(spec)
    import numpy as np
    path = spec[3:]; greedy = True
    if path.endswith(':sample'): path = path[:-7]; greedy = False
    if path not in _CK:
        import torch; torch.set_num_threads(1)
        ck = torch.load(path, weights_only=False); sd = ck['net']
        P = dict(w1=sd['body.0.weight'].numpy(), b1=sd['body.0.bias'].numpy(), w2=sd['body.2.weight'].numpy(), b2=sd['body.2.bias'].numpy())
        for j in range(5): P[f'h{j}w'] = sd[f'heads.{j}.weight'].numpy(); P[f'h{j}b'] = sd[f'heads.{j}.bias'].numpy()
        _CK[path] = (P, ck['active'], ck['defaults'], ck['mu'], ck['sd'])
    from ppo.agent import NPPolicy, fam_default
    P, active, dfl, mu, sd = _CK[path]
    return NPPolicy(P, active, [dfl[0], dfl[1], fam_default, dfl[3], 0], mu, sd, greedy, np.random.default_rng(seed))
def resolve(spec, lam, sec):
    if spec.startswith('distill:'): return f'{spec}:{lam}_{sec}'
    if spec != 'tuned': return spec
    sel = json.load(open('/workspace/rl_ppo/results/norl_tuned.json'))
    lg = 0.0 if lam <= 0.05 else (0.2 if lam <= 0.5 else 1.0)
    sg = 0.3 if sec < 0.6 else 1.0
    return sel[f'{lg}_{sg}']
def run(t):
    spec, inst, lam, seed, sec = t
    from ppo import dac, specs
    ins = common.load(inst)
    r = dac.solve_dac(ins, controller(resolve(spec, lam, sec), seed), specs.units(sec, len(ins.targets)), seed=seed, lam=lam, record=spec.startswith('rl:'))
    if r['traj']: r['cfgs'] = [list(c) for _, c in r['traj']]
    r.pop('traj'); r.update(spec=spec, inst=inst, lam=lam, seed=seed, sec=sec)
    return r
if __name__ == '__main__':
    out = sys.argv[1]; specl = sys.argv[2].split(';'); insts = SETS[sys.argv[3]]
    lams = [float(x) for x in sys.argv[4].split(',')]; seeds = [int(x) for x in sys.argv[5].split(',')]
    secs = [float(x) for x in sys.argv[6].split(',')]; W = int(sys.argv[7]) if len(sys.argv) > 7 else 4
    tasks = [(sp, i, l, s, se) for sp in specl for i in insts for l in lams for s in seeds for se in secs]
    done = set()
    if os.path.exists(out):
        for line in open(out):
            j = json.loads(line); done.add((j['spec'], j['inst'], j['lam'], j['seed'], j['sec']))
    tasks = [t for t in tasks if t not in done]
    random.Random(0).shuffle(tasks); print(len(tasks), 'tasks', flush=True)
    with Pool(W, maxtasksperchild=50) as p, open(out, 'a') as f:
        for k, r in enumerate(p.imap_unordered(run, tasks, chunksize=4)):
            f.write(json.dumps(r) + '\n'); f.flush()
            if k % 200 == 0: print(k, flush=True)
