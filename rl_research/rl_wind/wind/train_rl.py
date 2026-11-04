"""POMO-style REINFORCE for the recourse policy. usage: train_rl.py OUT ITERS [--algo pomo|a2c] [--nocond]"""
import wind, sys, os, json, time, zlib, math, argparse, numpy as np, torch, torch.nn as nn
from multiprocessing import get_context
from wind.rlpol import NF, make_rl
class Pol(nn.Module):
    """MLP score + linear skip (initialised to prefer the full trip unless it is predicted infeasible under the nowcast)"""
    def __init__(self):
        super().__init__()
        self.l1 = nn.Linear(NF, 64); self.l2 = nn.Linear(64, 64); self.l3 = nn.Linear(64, 1); self.skip = nn.Linear(NF, 1)
        with torch.no_grad():
            self.l3.weight.mul_(0.1); self.skip.weight.zero_(); self.skip.bias.zero_()
            self.skip.weight[0, 17] = 3.0; self.skip.weight[0, 15] = -6.0
    def forward(self, x):
        return self.l3(torch.relu(self.l2(torch.relu(self.l1(x))))) + self.skip(x)
def build(): return Pol()
_PL = None
def _init(plans_file):
    global _PL
    from lrphsd.problem import read_instance
    _PL = []
    for l in open(plans_file):
        r = json.loads(l); _PL.append((read_instance(r['path']), r))
def episode(t):
    params, idx, seed, P, N, nocond = t
    from wind.online import Scenario, run
    ins, r = _PL[idx]
    sc = Scenario(r['ctx'], seed); rng = np.random.default_rng(seed + 7)
    out = []
    for j in range(N):
        rec = []
        pol = make_rl(params, P if not nocond else 100.0, r['reserve'], greedy=False, rng=rng, record=rec)
        m = run(ins, r['solution'], r['ctx'], sc, pol)
        if nocond:
            pass
        out.append((rec, -(m['cost'] + P * m['failed']), m))
    return idx, P, out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('iters', type=int)
    ap.add_argument('--algo', default='pomo'); ap.add_argument('--nocond', action='store_true')
    ap.add_argument('--B', type=int, default=28); ap.add_argument('--N', type=int, default=8); ap.add_argument('--W', type=int, default=7)
    ap.add_argument('--lr', type=float, default=1e-3); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(a.seed); rng = np.random.default_rng(a.seed)
    net = build(); opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    critic = nn.Sequential(nn.Linear(4, 64), nn.ReLU(), nn.Linear(64, 1)); copt = torch.optim.Adam(critic.parameters(), lr=1e-3)
    plans = '/workspace/rl_wind/results/plans_train.jsonl'; npl = sum(1 for _ in open(plans))
    log = open(f'{a.out}/log.jsonl', 'a'); t0 = time.time()
    with get_context('forkserver').Pool(a.W, initializer=_init, initargs=(plans,)) as pool:
        for it in range(a.iters):
            params = [p.detach().numpy().copy() for p in net.parameters()]
            jobs = []
            for b in range(a.B):
                P = float(np.exp(rng.uniform(math.log(20), math.log(500)))) if not a.nocond else 100.0
                N = a.N if a.algo == 'pomo' else 1
                jobs.append((params, int(rng.integers(npl)), int(rng.integers(1 << 30)), P, N, a.nocond))
            res = pool.map(episode, jobs)
            Fs, As, Adv, sizes = [], [], [], []
            closs = 0.0
            for idx, P, out in res:
                R = np.array([o[1] for o in out])
                if a.algo == 'pomo':
                    adv = (R - R.mean()) / 10.0
                else:
                    ctx = _ctxfeat(idx, P, plans)
                    v = critic(torch.tensor(ctx)[None])[0, 0]
                    cl = (v - torch.tensor(R.mean() / 100.0)) ** 2; copt.zero_grad(); cl.backward(); copt.step(); closs += cl.item()
                    adv = (R - 100.0 * v.item()) / 10.0
                for (rec, _, m), ad in zip(out, adv):
                    for F, act in rec:
                        Fs.append(F); As.append(act); Adv.append(ad); sizes.append(len(F))
            if not Fs: continue
            # batched log-prob over variable-size candidate sets
            L = max(sizes); X = np.zeros((len(Fs), L, Fs[0].shape[1]), np.float32); M = np.zeros((len(Fs), L), bool)
            for i, F in enumerate(Fs): X[i, :len(F)] = F; M[i, :len(F)] = True
            s = net(torch.tensor(X)).squeeze(-1).masked_fill(~torch.tensor(M), -1e9)
            lp = torch.log_softmax(s, -1).gather(1, torch.tensor(As)[:, None]).squeeze(1)
            ent = -(torch.softmax(s, -1) * torch.log_softmax(s, -1)).masked_fill(~torch.tensor(M), 0).sum(-1).mean()
            loss = -(torch.tensor(Adv, dtype=torch.float32) * lp).sum() / a.B - 0.01 * ent
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
            allm = [o[2] for _, _, out in res for o in out]
            rec = dict(it=it, min=round((time.time() - t0) / 60, 2), cost=float(np.mean([m['cost'] for m in allm])),
                       failed=float(np.mean([m['failed'] for m in allm])), trims=float(np.mean([m['trims'] for m in allm])), ent=float(ent.detach()), closs=closs)
            log.write(json.dumps(rec) + '\n'); log.flush()
            if it % 10 == 0: print(json.dumps(rec), flush=True); torch.save(net.state_dict(), f'{a.out}/last.pt')
            if it % 50 == 0: torch.save(net.state_dict(), f'{a.out}/it{it}.pt')
    torch.save(net.state_dict(), f'{a.out}/last.pt')
_CF = None
def _ctxfeat(idx, P, plans):
    global _CF
    if _CF is None: _CF = [json.loads(l) for l in open(plans)]
    r = _CF[idx]; c = r['ctx']
    return np.array([c['sigma'] / 2.5, c['gust'] * 5, math.log10(P) - 2, r['reserve'] * 10], np.float32)
if __name__ == '__main__': main()
