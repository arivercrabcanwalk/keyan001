"""REINFORCE with POMO-style shared baseline (K rollouts of the same scenario) for the hold policy.
usage: train.py OUT [--iters N] [--B 16] [--K 8] [--lr 1e-3] [--bc 1] [--seed 0] [--algo pomo|a2c]"""
import dyn, sys, os, json, time, argparse, numpy as np, torch
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day, Sim
from dyn.rl import NPPolicy, init_params
from dyn.feat import NF
from dyn import pol as P
_C = {}
def load(path):
    if path not in _C: _C[path] = read_instance(path)
    return _C[path]
def rollouts(a):
    params, r, seed, K, greedy, base = a
    ins = load(r['path']); day = Day(ins, seed); out = []
    for k in range(K):
        rec = []
        if base: pol = {'static': P.make_static(120)}[base]; m = Sim(ins, r['solution'], day).run(pol); out.append((m, None)); continue
        pol = NPPolicy(params, greedy=greedy, rng=np.random.default_rng(seed * 100 + k), record=rec)
        m = Sim(ins, r['solution'], day).run(pol); out.append((m, rec))
    return out
def bc_states(a):
    """states visited by the static rule, labelled with its action (warm start)"""
    r, seed, T = a; ins = load(r['path']); day = Day(ins, seed); rec = []
    st = P.make_static(T)
    from dyn.feat import features
    def pol(sim, i):
        x = features(sim, i); y = st(sim, i); rec.append((x, int(y))); return y
    Sim(ins, r['solution'], day).run(pol); return rec
class Net(torch.nn.Module):
    def __init__(self, H=64):
        super().__init__(); self.l1 = torch.nn.Linear(NF, H); self.l2 = torch.nn.Linear(H, H); self.l3 = torch.nn.Linear(H, 1)
    def forward(self, x): return self.l3(torch.tanh(self.l2(torch.tanh(self.l1(x))))).squeeze(-1)
    def np_params(self):
        return [self.l1.weight.detach().numpy().T.copy(), self.l1.bias.detach().numpy().copy(), self.l2.weight.detach().numpy().T.copy(),
                self.l2.bias.detach().numpy().copy(), self.l3.weight.detach().numpy()[0].copy(), np.float32(self.l3.bias.item())]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--iters', type=int, default=400)
    ap.add_argument('--B', type=int, default=16); ap.add_argument('--K', type=int, default=8); ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--bc', type=int, default=1); ap.add_argument('--seed', type=int, default=0); ap.add_argument('--ent', type=float, default=0.01)
    ap.add_argument('--W', type=int, default=4); ap.add_argument('--train', default='plans/train_ours.jsonl'); ap.add_argument('--hours', type=float, default=3); ap.add_argument('--devseeds', type=int, default=2); ap.add_argument('--init', default=''); ap.add_argument('--bcT', type=float, default=120)
    A = ap.parse_args(); os.makedirs(A.out, exist_ok=True); torch.manual_seed(A.seed); torch.set_num_threads(1)
    rng = np.random.default_rng(A.seed)
    tr = [json.loads(l) for l in open(A.train)]
    dev = [json.loads(l) for l in open('plans/dev_ours.jsonl')]
    net = Net(); opt = torch.optim.Adam(net.parameters(), lr=A.lr)
    pool = get_context('fork').Pool(A.W); log = open(f'{A.out}/log.jsonl', 'a')
    devjobs = lambda prm: [(prm, r, 900 + s, 1, True, None) for r in dev for s in range(A.devseeds)]
    ref = [o[0][0]['J'] for o in pool.map(rollouts, [(None, r, 900 + s, 1, True, 'static') for r in dev for s in range(A.devseeds)])]
    if A.init: net.load_state_dict(torch.load(A.init))
    if A.bc and not A.init:
        recs = [x for rec in pool.map(bc_states, [(tr[rng.integers(len(tr))], int(rng.integers(1 << 30)), A.bcT) for _ in range(200)]) for x in rec]
        X = torch.tensor(np.stack([x for x, _ in recs])); Y = torch.tensor([y for _, y in recs], dtype=torch.float32)
        bopt = torch.optim.Adam(net.parameters(), lr=3e-3)
        for ep in range(300):
            idx = torch.randint(0, len(X), (1024,)); l = torch.nn.functional.binary_cross_entropy_with_logits(net(X[idx]), Y[idx] * 0.8 + 0.1)
            bopt.zero_grad(); l.backward(); bopt.step()
        acc = ((net(X) > 0).float() == Y).float().mean().item()
        print('bc', len(X), 'acc', acc, 'pos', Y.mean().item(), flush=True)
    best = 1e18; t0 = time.time()
    for it in range(A.iters + 1):
        if it % 20 == 0:
            res = pool.map(rollouts, devjobs(net.np_params())); J = [o[0][0]['J'] for o in res]
            gap = float(np.mean([(j - r) / r for j, r in zip(J, ref)]) * 100)
            ot = float(np.mean([o[0][0]['ontime'] for o in res])); mk = float(np.mean([o[0][0]['mk'] for o in res]))
            rec = dict(it=it, dev_J=float(np.mean(J)), dev_gap_vs_static=gap, ontime=ot, mk=mk, t=time.time() - t0)
            print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + '\n'); log.flush()
            torch.save(net.state_dict(), f'{A.out}/it{it}.pt')
            if gap < best: best = gap; torch.save(net.state_dict(), f'{A.out}/best.pt')
            if time.time() - t0 > A.hours * 3600: break
        prm = net.np_params()
        jobs = [(prm, tr[rng.integers(len(tr))], int(rng.integers(1 << 30)), A.K, False, None) for _ in range(A.B)]
        res = pool.map(rollouts, jobs)
        Xs, As, Ws = [], [], []
        for out in res:
            J = np.array([m['J'] for m, _ in out]); adv = (J - J.mean()) / J.mean() * 100
            for (m, rec), a in zip(out, adv):
                for x, act in rec: Xs.append(x); As.append(act); Ws.append(a)
        if not Xs: continue
        X = torch.tensor(np.stack(Xs)); Ac = torch.tensor(As, dtype=torch.float32); Wt = torch.tensor(Ws, dtype=torch.float32)
        z = net(X); logp = -torch.nn.functional.binary_cross_entropy_with_logits(z, Ac, reduction='none')
        p = torch.sigmoid(z); ent = -(p * torch.log(p + 1e-8) + (1 - p) * torch.log(1 - p + 1e-8))
        loss = (Wt * logp).sum() / (A.B * A.K) - A.ent * ent.mean()
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
if __name__ == '__main__': main()
