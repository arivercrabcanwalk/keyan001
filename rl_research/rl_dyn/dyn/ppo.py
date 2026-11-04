"""Actor-critic training for the hold/launch policy: PPO (GAE, clipped objective) or A2C (GAE, single update),
with an MLP encoder or an attention/set encoder over drone tokens and recent-request tokens.
Rewards: telescoping decomposition of J between consecutive decisions (realised cost so far), so sum = -J/100.
usage: ppo.py OUT --algo ppo|a2c --enc mlp|attn [--init bc|api|none] [--hours 0.75] [--W 2] [--seed 0]"""
import dyn, sys, os, json, time, math, argparse, numpy as np, torch, torch.nn as nn
from multiprocessing import get_context
from lrphsd.problem import read_instance
from dyn.sim import Day, Sim
from dyn import pol as P, sim as S
from dyn.feat import features, NF
ND, NR, FD, FR = 20, 10, 8, 5
RS = 100.0
_C = {}
def load(p):
    if p not in _C: _C[p] = read_instance(p)
    return _C[p]
def set_feats(sim, i):
    d = sim.drones[i]; D = np.zeros((ND, FD), np.float32); md = np.zeros(ND, np.float32)
    for k, e in enumerate(sim.drones[:ND]):
        st = e['state']
        D[k] = [float(k == i), float(st == 'busy'), float(st == 'idle'), float(st == 'hold'),
                (max(0.0, e['free'] - sim.t) if st == 'busy' else 0.0) / 30.0, sum(e['q']) / 100.0,
                math.hypot(e['x'] - d['x'], e['y'] - d['y']) / 5000.0, float(e['large'])]
        md[k] = 1
    R = np.zeros((NR, FR), np.float32); mr = np.zeros(NR, np.float32)
    rec = [s for s in sim.seen if sim.t - s[0] <= 60][-NR:]
    for k, (t, x, y, p) in enumerate(rec):
        R[k] = [(x - d['x']) / 5000.0, (y - d['y']) / 5000.0, (sim.t - t) / 60.0, float(p),
                float(math.hypot(x - d['x'], y - d['y']) <= d['R'])]; mr[k] = 1
    return D, md, R, mr
class ACNet(nn.Module):
    def __init__(self, attn, mu=None, sd=None, H=64):
        super().__init__(); self.attn = attn
        self.register_buffer('mu', torch.zeros(NF) if mu is None else torch.tensor(mu, dtype=torch.float32))
        self.register_buffer('sd', torch.ones(NF) if sd is None else torch.tensor(sd, dtype=torch.float32))
        self.ex = nn.Sequential(nn.Linear(NF, H), nn.Tanh(), nn.Linear(H, H), nn.Tanh())
        if attn:
            self.ed = nn.Sequential(nn.Linear(FD, H), nn.Tanh(), nn.Linear(H, H)); self.er = nn.Sequential(nn.Linear(FR, H), nn.Tanh(), nn.Linear(H, H))
            self.qd = nn.Linear(H, H); self.qr = nn.Linear(H, H)
            self.trunk = nn.Sequential(nn.Linear(3 * H, H), nn.Tanh())
        self.pi = nn.Linear(H, 1); self.v = nn.Sequential(nn.Linear(H, H), nn.Tanh(), nn.Linear(H, 1))
    def _att(self, q, tok, m):
        s = (q[:, None, :] * tok).sum(-1) / math.sqrt(tok.shape[-1]); s = s.masked_fill(m < 0.5, -1e9)
        w = torch.softmax(s, -1) * (m.sum(-1, keepdim=True) > 0)
        return (w[..., None] * tok).sum(1)
    def forward(self, x, D=None, md=None, R=None, mr=None):
        h = self.ex((x - self.mu) / self.sd)
        if self.attn:
            h = self.trunk(torch.cat([h, self._att(self.qd(h), self.ed(D), md), self._att(self.qr(h), self.er(R), mr)], -1))
        return self.pi(h).squeeze(-1), self.v(h).squeeze(-1)
def cost_so_far(sim):
    pen = sum((S.P_HIGH if p == 1 else S.P_NORM) for (p, r, _) in sim.log if r is None or r > S.DL[p])
    # policy-dependent parts only: urgent sortie time + projected planned makespan (immediately reflects a hold on a critical drone)
    ub = sum(d['busy'] + sum(d['q']) for d in sim.drones) - sim.__dict__.setdefault('_pt0', sum(d['busy'] + sum(d['q']) for d in sim.drones))
    pm = max([d['planned_end'] for d in sim.drones] + [P.proj_end(sim, j) for j, d in enumerate(sim.drones) if d['q']] + [0.0])
    return sim.p.time_cost * ub + S.LAM_MK * pm + pen
class TorchPol:
    def __init__(self, net, greedy, rng, record=None, base=None):
        self.net, self.greedy, self.rng, self.rec, self.base = net, greedy, rng, record, base
    def __call__(self, sim, i):
        x = features(sim, i)
        if self.base is not None:
            a = bool(self.base(sim, i)); self.rec.append(dict(x=x, sf=set_feats(sim, i) if self.net is None or self.net.attn else None, a=int(a))); return a
        sf = set_feats(sim, i) if self.net.attn else None
        with torch.no_grad():
            if sf is not None:
                D, md, R, mr = [torch.from_numpy(z)[None] for z in sf]; z, v = self.net(torch.from_numpy(x)[None], D, md, R, mr)
            else: z, v = self.net(torch.from_numpy(x)[None])
        p = float(torch.sigmoid(z)); a = (p > 0.5) if self.greedy else (self.rng.random() < p)
        if self.rec is not None:
            self.rec.append(dict(x=x, sf=sf, a=int(a), logp=math.log(p if a else 1 - p + 1e-12) if p not in (0.0, 1.0) else math.log(max(1e-12, p if a else 1 - p)),
                                 v=float(v), c=cost_so_far(sim)))
        return bool(a)
_NET = {}
def episode(a):
    sd, attn, mu, sdv, r, seed, greedy, mode = a
    torch.set_num_threads(1)
    key = (attn,)
    if key not in _NET: _NET[key] = ACNet(attn, mu, sdv)
    net = _NET[key]; net.load_state_dict(sd); net.eval()
    ins = load(r['path']); day = Day(ins, seed); rec = []
    if mode == 'bc': pol = TorchPol(net, True, None, rec, base=P.make_static(120))
    else: pol = TorchPol(net, greedy, np.random.default_rng(seed + (int(mode[5:]) * 7777 if mode.startswith('train') and len(mode) > 5 else 0)), rec if not greedy else None)
    sim = Sim(ins, r['solution'], day); m = sim.run(pol)
    if mode == 'bc' or greedy: return m, rec
    # rewards: telescoping realised cost
    cs = [s['c'] for s in rec] + [m['pen'] + S.LAM_MK * m['mk'] + sim.p.time_cost * (sum(d['busy'] for d in sim.drones) - sim.__dict__.get('_pt0', 0.0) - (0 if '_pt0' in sim.__dict__ else 0))]
    for k, s in enumerate(rec): s['r'] = -(cs[k + 1] - cs[k]) / RS
    return m, rec
def batchify(recs, attn):
    X = torch.tensor(np.stack([s['x'] for s in recs]))
    if not attn: return X, None, None, None, None
    D = torch.tensor(np.stack([s['sf'][0] for s in recs])); md = torch.tensor(np.stack([s['sf'][1] for s in recs]))
    R = torch.tensor(np.stack([s['sf'][2] for s in recs])); mr = torch.tensor(np.stack([s['sf'][3] for s in recs]))
    return X, D, md, R, mr
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--algo', default='ppo'); ap.add_argument('--enc', default='mlp')
    ap.add_argument('--init', default='bc'); ap.add_argument('--hours', type=float, default=0.75); ap.add_argument('--W', type=int, default=2)
    ap.add_argument('--seed', type=int, default=0); ap.add_argument('--E', type=int, default=48); ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--gae', type=float, default=0.95); ap.add_argument('--epochs', type=int, default=4); ap.add_argument('--clip', type=float, default=0.2)
    ap.add_argument('--ent', type=float, default=0.005); ap.add_argument('--devseeds', type=int, default=5)
    A = ap.parse_args(); os.makedirs(A.out, exist_ok=True); torch.manual_seed(A.seed); torch.set_num_threads(2)
    rng = np.random.default_rng(A.seed); attn = A.enc == 'attn'
    tr = [json.loads(l) for l in open('plans/train_ours.jsonl')]; dev = [json.loads(l) for l in open('plans/dev_ours.jsonl')]
    api = np.load('models/api_s0/data_it0.npz'); mu = api['X'].mean(0); sdv = api['X'].std(0) + 1e-3
    net = ACNet(attn, mu, sdv); pool = get_context('fork').Pool(A.W); log = open(f'{A.out}/log.jsonl', 'a')
    sdict = lambda: {k: v.clone() for k, v in net.state_dict().items()}
    ref = [m['J'] for m, _ in pool.map(episode, [(sdict(), attn, mu, sdv, r, 900 + s, True, 'static_ref') for r in dev for s in range(A.devseeds)])] if False else None
    st_ref = []
    for r in dev:
        ins = load(r['path'])
        for s in range(A.devseeds): st_ref.append(Sim(ins, r['solution'], Day(ins, 900 + s)).run(P.make_static(30))['J'])
    if A.init in ('bc', 'api'):
        if A.init == 'bc':
            res = pool.map(episode, [(sdict(), attn, mu, sdv, tr[rng.integers(len(tr))], int(rng.integers(1 << 30)), True, 'bc') for _ in range(200)])
            recs = [s for _, rc in res for s in rc]; Y = torch.tensor([s['a'] for s in recs], dtype=torch.float32) * 0.8 + 0.1; Wt = torch.ones(len(recs))
            Xb = batchify(recs, attn)
        else:   # imitation of rollout: advantage-sign labels from rollout (API data), weight |Delta|
            X = torch.tensor(api['X']); Dl = torch.tensor(api['D'], dtype=torch.float32)
            Y = (Dl < 0).float() * 0.8 + 0.1; Wt = (Dl.abs() / Dl.abs().mean()).clamp(max=5); Xb = (X, None, None, None, None)
            assert not attn
        opt = torch.optim.Adam(net.parameters(), lr=2e-3); n = len(Y)
        for ep in range(400):
            idx = torch.randint(0, n, (512,)); z, _ = net(*[t[idx] if t is not None else None for t in Xb])
            l = (Wt[idx] * nn.functional.binary_cross_entropy_with_logits(z, Y[idx], reduction='none')).mean()
            opt.zero_grad(); l.backward(); opt.step()
        print('init', A.init, n, float(l), flush=True)
    opt = torch.optim.Adam(net.parameters(), lr=A.lr); t0 = time.time(); best = 1e18; it = 0
    while True:
        if it % 10 == 0:
            res = pool.map(episode, [(sdict(), attn, mu, sdv, r, 900 + s, True, 'eval') for r in dev for s in range(A.devseeds)])
            J = [m['J'] for m, _ in res]; gap = float(np.mean([(j - q) / q for j, q in zip(J, st_ref)]) * 100)
            rec = dict(it=it, dev_gap_vs_static30=gap, ontime=float(np.mean([m['ontime'] for m, _ in res])), mk=float(np.mean([m['mk'] for m, _ in res])), t=time.time() - t0)
            print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + '\n'); log.flush()
            torch.save(net.state_dict(), f'{A.out}/it{it}.pt')
            if gap < best: best = gap; torch.save(net.state_dict(), f'{A.out}/best.pt')
            if time.time() - t0 > A.hours * 3600: break
        if A.algo == 'ppo_pomo':     # K rollouts per scenario, scenario-shared baseline (common random numbers), no critic
            K = 8; jobs = []
            for _ in range(max(1, A.E // K)):
                r = tr[rng.integers(len(tr))]; sd0 = int(rng.integers(1 << 30))
                jobs += [(sdict(), attn, mu, sdv, r, sd0, False, 'train')] * K
            res = pool.map(episode, [(j[0], j[1], j[2], j[3], j[4], j[5], j[6], j[7] + str(k % K)) for k, j in enumerate(jobs)])
        else:
            res = pool.map(episode, [(sdict(), attn, mu, sdv, tr[rng.integers(len(tr))], int(rng.integers(1 << 30)), False, 'train') for _ in range(A.E)])
        recs = []
        if A.algo == 'ppo_pomo':
            for g in range(0, len(res), 8):
                Js = np.array([m['J'] for m, _ in res[g:g + 8]]); adv = -(Js - Js.mean()) / Js.mean() * 100
                for (m, rc), a in zip(res[g:g + 8], adv):
                    for s_ in rc: s_['adv'] = a; s_['ret'] = 0.0
                    recs += rc
        for m, rc in (res if A.algo != 'ppo_pomo' else []):
            if not rc: continue
            v = [s['v'] for s in rc] + [0.0]; g = 0.0
            for k in range(len(rc) - 1, -1, -1):
                delta = rc[k]['r'] + v[k + 1] - v[k]; g = delta + A.gae * g; rc[k]['adv'] = g; rc[k]['ret'] = g + v[k]
            recs += rc
        Xb = batchify(recs, attn); Ac = torch.tensor([s['a'] for s in recs], dtype=torch.float32)
        OL = torch.tensor([s['logp'] for s in recs], dtype=torch.float32); Ad = torch.tensor([s['adv'] for s in recs], dtype=torch.float32)
        Rt = torch.tensor([s['ret'] for s in recs], dtype=torch.float32); Ad = (Ad - Ad.mean()) / (Ad.std() + 1e-8); n = len(recs)
        epochs = A.epochs if A.algo != 'a2c' else 1; mb = 512 if A.algo != 'a2c' else n
        for ep in range(epochs):
            perm = torch.randperm(n)
            for b in range(0, n, mb):
                idx = perm[b:b + mb]; z, v = net(*[t[idx] if t is not None else None for t in Xb])
                lp = -nn.functional.binary_cross_entropy_with_logits(z, Ac[idx], reduction='none')
                p = torch.sigmoid(z); ent = -(p * torch.log(p + 1e-8) + (1 - p) * torch.log(1 - p + 1e-8)).mean()
                if A.algo != 'a2c':
                    ratio = torch.exp(lp - OL[idx]); pl = -torch.min(ratio * Ad[idx], ratio.clamp(1 - A.clip, 1 + A.clip) * Ad[idx]).mean()
                else: pl = -(lp * Ad[idx]).mean()
                vl = 0.0 if A.algo == 'ppo_pomo' else 0.5 * ((v - Rt[idx]) ** 2).mean()
                loss = pl + vl - A.ent * ent
                opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
        it += 1
if __name__ == '__main__': main()
