"""Rollout-based approximate policy iteration (API / 'learning from rollouts', Bertsekas 2019-2022) for the hold policy.
Each iteration: run the behaviour policy on training days, at sampled decision states estimate the advantage
Delta = E[J | hold] - E[J | launch] by M posterior-sampled futures (common random numbers) continued with the CURRENT
base policy, then fit the network with |Delta|-weighted logistic loss (cost-sensitive classification). Next iteration
uses the fitted network as both behaviour and base policy (policy improvement).
usage: api.py OUT [--iters 3] [--days 400] [--M 16] [--q 0.35] [--seed 0]"""
import dyn, sys, os, json, time, argparse, numpy as np, torch
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day, Sim
from dyn import pol as P
from dyn.feat import features
from dyn.rl import NPPolicy
from dyn.train import Net
_C = {}
def load(p):
    if p not in _C: _C[p] = read_instance(p)
    return _C[p]
def collect(a):
    r, seed, prm, M, q, eps = a
    ins = load(r['path']); day = Day(ins, seed); rng = np.random.default_rng(seed)
    base = P.make_static(120) if prm is None else NPPolicy(prm, greedy=True)
    post = P.Posterior(ins); data = []
    def beh(sim, i):
        x = features(sim, i); a0 = base(sim, i)
        if rng.random() < q:
            w = post.post(sim.seen); diff = 0.0; r2 = np.random.default_rng(int(rng.integers(1 << 30)))
            for m in range(M):
                fd = P.sample_future(sim, post, r2, None, w)
                diff += P._forced(sim, i, True, base, fd) - P._forced(sim, i, False, base, fd)
            data.append((x, diff / M))
        return (not a0) if rng.random() < eps else a0
    Sim(ins, r['solution'], day).run(beh)
    return data
def fit(net, X, D, epochs=40, lr=2e-3):
    """advantage regression (MSE) on standardised inputs; logits = -predicted Delta, so hold iff predicted Delta<0.
    Standardisation and the sign flip are folded into the network weights afterwards."""
    mu = X.mean(0); sd = X.std(0) + 1e-6; Xn = (X - mu) / sd
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4); n = len(X)
    for ep in range(epochs):
        perm = torch.randperm(n)
        for b in range(0, n, 256):
            idx = perm[b:b + 256]
            l = ((net(Xn[idx]) + D[idx]) ** 2).mean()
            opt.zero_grad(); l.backward(); opt.step()
    with torch.no_grad():
        pr = -net(Xn); r2 = float(1 - ((pr - D) ** 2).mean() / D.var())
        W = net.l1.weight; net.l1.bias.copy_(net.l1.bias - (W * (mu / sd)[None]).sum(1)); net.l1.weight.copy_(W / sd[None])
    return r2
def dev_eval(pool, prm, dev, ns=3):
    res = pool.map(devjob, [(prm, r, 2000 + s) for r in dev for s in range(ns)])
    return res
def devjob(a):
    prm, r, s = a; ins = load(r['path']); day = Day(ins, s)
    pol = P.make_static(120) if prm is None else NPPolicy(prm, greedy=True)
    return Sim(ins, r['solution'], day).run(pol)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--iters', type=int, default=3)
    ap.add_argument('--days', type=int, default=400); ap.add_argument('--M', type=int, default=16); ap.add_argument('--q', type=float, default=0.35)
    ap.add_argument('--eps', type=float, default=0.1); ap.add_argument('--seed', type=int, default=0); ap.add_argument('--W', type=int, default=4)
    ap.add_argument('--train', default='plans/train_ours.jsonl')
    A = ap.parse_args(); os.makedirs(A.out, exist_ok=True); torch.manual_seed(A.seed); torch.set_num_threads(1)
    rng = np.random.default_rng(A.seed); tr = [json.loads(l) for l in open(A.train)]
    dev = [json.loads(l) for l in open('plans/dev_ours.jsonl')]
    pool = get_context('fork').Pool(A.W); log = open(f'{A.out}/log.jsonl', 'a')
    ref = [m['J'] for m in dev_eval(pool, None, dev)]
    Xall, Dall = [], []; prm = None; net = None
    for it in range(A.iters):
        t0 = time.time()
        jobs = [(tr[rng.integers(len(tr))], int(rng.integers(1 << 30)), prm, A.M, A.q, A.eps) for _ in range(A.days)]
        fn = f'{A.out}/data_it{it}.npz'
        if os.path.exists(fn): z = np.load(fn); data = list(zip(z['X'], z['D']))
        else:
            data = [x for d in pool.map(collect, jobs, chunksize=4) for x in d]
            np.savez(fn, X=np.stack([x for x, _ in data]), D=np.array([d for _, d in data]))
        Xall += [x for x, _ in data]; Dall += [d for _, d in data]
        X = torch.tensor(np.stack(Xall)); D = torch.tensor(np.array(Dall), dtype=torch.float32)
        net = Net(); torch.manual_seed(A.seed + it); acc = fit(net, X, D)
        torch.save(net.state_dict(), f'{A.out}/it{it}.pt'); prm = net.np_params()
        res = dev_eval(pool, prm, dev); J = [m['J'] for m in res]
        rec = dict(it=it, n=len(Xall), frac_hold_better=float((D < 0).float().mean()), r2=acc,
                   dev_gap_vs_static=float(np.mean([(j - r) / r for j, r in zip(J, ref)]) * 100),
                   ontime=float(np.mean([m['ontime'] for m in res])), ontime_h=float(np.mean([m['ontime_h'] for m in res])),
                   mk=float(np.mean([m['mk'] for m in res])), sec=time.time() - t0)
        print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + '\n'); log.flush()
if __name__ == '__main__': main()
