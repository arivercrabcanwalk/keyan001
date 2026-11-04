"""Train a DAC controller. --algo ppo | a2c | reinforce
PPO: clipped surrogate (eps .2), GAE(gamma=1, lam=.95), value normalisation (running mean/std of returns),
obs normalisation (running), entropy bonus, minibatch epochs; parallel CPU rollouts (multiprocessing).
A2C: same actor-critic, single gradient step per batch, no clipping/ratio (on-policy), GAE(lam=1 -> MC-n-step).
REINFORCE: no critic; group-relative baseline (mean return of the G episodes of the same instance/lambda/budget,
GRPO/POMO-style), normalised.
Instances: TRAIN (generated g*_1..18 + Liu non-test size groups). Liu-50 never used."""
import sys, os, json, math, time, random, argparse
sys.path.insert(0, '/workspace/rl_ppo')
import numpy as np, torch, torch.nn as nn
from multiprocessing import Pool
from ppo import dac, common
from ppo.agent import episode

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True); ap.add_argument('--algo', default='ppo')
ap.add_argument('--heads', default='T,M,I,R'); ap.add_argument('--defT', type=int, default=1)
ap.add_argument('--defM', type=int, default=2); ap.add_argument('--defI', type=int, default=1)
ap.add_argument('--lams', default='0,0.05,0.1,0.2,0.5,1,2'); ap.add_argument('--secs', default='0.3,1.0')
ap.add_argument('--ninst', type=int, default=16); ap.add_argument('--G', type=int, default=4)
ap.add_argument('--iters', type=int, default=400); ap.add_argument('--hours', type=float, default=3)
ap.add_argument('--lr', type=float, default=3e-4); ap.add_argument('--ent', type=float, default=0.01)
ap.add_argument('--epochs', type=int, default=4); ap.add_argument('--clip', type=float, default=0.2)
ap.add_argument('--gae', type=float, default=0.95); ap.add_argument('--W', type=int, default=4)
ap.add_argument('--seed', type=int, default=0); ap.add_argument('--hid', type=int, default=64)
ap.add_argument('--insts', default='train'); ap.add_argument('--grpb', type=int, default=1); ap.add_argument('--resume', default='')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
torch.manual_seed(a.seed); np.random.seed(a.seed); rnd = random.Random(a.seed)
torch.set_num_threads(1)
active = [n in a.heads.split(',') for n in ['T', 'M', 'F', 'I', 'R']]
defaults_spec = [a.defT, a.defM, None, a.defI, 0]
lams = [float(x) for x in a.lams.split(',')]; secs = [float(x) for x in a.secs.split(',')]
INSTS = common.TRAIN if a.insts == 'train' else common.TUNE

class Net(nn.Module):
    def __init__(s):
        super().__init__()
        s.body = nn.Sequential(nn.Linear(dac.NOBS, a.hid), nn.Tanh(), nn.Linear(a.hid, a.hid), nn.Tanh())
        s.heads = nn.ModuleList([nn.Linear(a.hid, n) for n in dac.NHEAD])
        s.v = nn.Sequential(nn.Linear(dac.NOBS, a.hid), nn.Tanh(), nn.Linear(a.hid, a.hid), nn.Tanh(), nn.Linear(a.hid, 1))
        for h in s.heads: nn.init.zeros_(h.weight); nn.init.zeros_(h.bias)   # uniform start
    def dist(s, x):
        h = s.body(x); return [torch.distributions.Categorical(logits=hd(h)) for hd in s.heads]
net = Net()
opt = torch.optim.Adam(net.parameters(), lr=a.lr)
mu = np.zeros(dac.NOBS, np.float32); sd = np.ones(dac.NOBS, np.float32); nobs = 0
rmu, rsd = 0.0, 1.0
it0 = 0
if a.resume:
    ck = torch.load(a.resume, weights_only=False); net.load_state_dict(ck['net']); mu, sd = ck['mu'], ck['sd']; rmu, rsd = ck['rmu'], ck['rsd']; it0 = ck['it'] + 1
def np_params():
    b = net.body; P = dict(w1=b[0].weight.detach().numpy().copy(), b1=b[0].bias.detach().numpy().copy(),
                           w2=b[2].weight.detach().numpy().copy(), b2=b[2].bias.detach().numpy().copy())
    for j, h in enumerate(net.heads):
        P[f'h{j}w'] = h.weight.detach().numpy().copy(); P[f'h{j}b'] = h.bias.detach().numpy().copy()
    return P
def save(path, it):
    torch.save(dict(net=net.state_dict(), mu=mu, sd=sd, rmu=rmu, rsd=rsd, it=it, args=vars(a), active=active,
                    defaults=defaults_spec), path)
log = open(f'{a.out}/log.jsonl', 'a'); t_start = time.time()
pool = Pool(a.W, maxtasksperchild=200)
for it in range(it0, a.iters):
    if time.time() - t_start > a.hours * 3600: break
    P = np_params(); tasks = []
    for g in range(a.ninst):
        inst = rnd.choice(INSTS); lam = rnd.choice(lams); sec = rnd.choice(secs)
        for k in range(a.G):
            tasks.append((P, active, mu, sd, inst, lam, sec, rnd.randrange(10**6), False, defaults_spec, None, rnd.randrange(10**9)))
    eps = pool.map(episode, tasks, chunksize=1)
    # obs norm update (raw obs reconstructed: x*sd+mu)
    X = np.concatenate([np.array(e['obs']) for e in eps]); raw = X * sd + mu
    if it < 30:   # warm-up running stats, then frozen (keeps policy input stationary)
        n2 = len(raw); m2 = raw.mean(0); v2 = raw.var(0)
        tot = nobs + n2; d = m2 - mu
        newmu = mu + d * n2 / tot
        newvar = (sd ** 2 * nobs + v2 * n2 + d ** 2 * nobs * n2 / tot) / tot if nobs else v2
        mu = newmu.astype(np.float32); sd = np.sqrt(np.maximum(newvar, 1e-6)).astype(np.float32); nobs = tot
        X = (raw - mu) / sd; X = np.clip(X, -5, 5)
    else:
        pass
    # per-episode arrays
    Xs, As, LP, ADV, RET = [], [], [], [], []
    rets = np.array([sum(e['rew']) for e in eps])
    if a.algo == 'reinforce':
        R = rets.reshape(a.ninst, a.G); adv = (R - R.mean(1, keepdims=True)) / (R.std(1, keepdims=True) + 1e-3)
        off = 0
        for i, e in enumerate(eps):
            T = len(e['rew']); x = X[off:off + T]; off += T
            Xs.append(x); As += e['acts']; LP += e['logp']; ADV += [adv.flat[i]] * T; RET += [0] * T
    else:
        with torch.no_grad():
            V = net.v(torch.tensor(X)).squeeze(-1).numpy() * rsd + rmu
        off = 0; lamg = a.gae if a.algo == 'ppo' else 1.0
        Rm = np.array([e['rew'] for e in eps]).reshape(a.ninst, a.G, -1)
        Bm = (Rm.sum(1, keepdims=True) - Rm) / max(a.G - 1, 1)   # leave-one-out group mean per segment
        Bm = Bm.reshape(len(eps), -1)
        for ei, e in enumerate(eps):
            T = len(e['rew']); x = X[off:off + T]; v = V[off:off + T]; off += T
            r = np.array(e['rew']) - (Bm[ei] if a.grpb else 0); gae = 0.0; adv = np.zeros(T)
            for t in reversed(range(T)):
                nv = v[t + 1] if t + 1 < T else 0.0
                delta = r[t] + nv - v[t]; gae = delta + lamg * gae; adv[t] = gae
            Xs.append(x); As += e['acts']; LP += e['logp']; ADV += list(adv); RET += list(adv + v)
        RET_a = np.array(RET); rmu = 0.9 * rmu + 0.1 * RET_a.mean() if it > it0 else RET_a.mean()
        rsd = 0.9 * rsd + 0.1 * (RET_a.std() + 1e-3) if it > it0 else RET_a.std() + 1e-3
    Xt = torch.tensor(np.concatenate(Xs)); At = torch.tensor(As); LPt = torch.tensor(LP, dtype=torch.float32)
    ADVt = torch.tensor(ADV, dtype=torch.float32); RETt = (torch.tensor(RET, dtype=torch.float32) - rmu) / rsd
    if a.algo != 'reinforce': ADVt = (ADVt - ADVt.mean()) / (ADVt.std() + 1e-8)
    n = len(Xt); epochs = a.epochs if a.algo == 'ppo' else 1
    stats = []
    for ep in range(epochs):
        perm = torch.randperm(n) if a.algo == 'ppo' else torch.arange(n)
        mb = max(n // 4, 32) if a.algo == 'ppo' else n
        for s0 in range(0, n, mb):
            idx = perm[s0:s0 + mb]
            ds = net.dist(Xt[idx]); lp = 0; ent = 0
            for j, d in enumerate(ds):
                if not active[j]: continue
                lp = lp + d.log_prob(At[idx, j]); ent = ent + d.entropy()
            if a.algo == 'ppo':
                ratio = torch.exp(lp - LPt[idx])
                pl = -torch.min(ratio * ADVt[idx], torch.clamp(ratio, 1 - a.clip, 1 + a.clip) * ADVt[idx]).mean()
            else:
                pl = -(lp * ADVt[idx]).mean()
            loss = pl - a.ent * ent.mean()
            if a.algo != 'reinforce':
                vl = ((net.v(Xt[idx]).squeeze(-1) - RETt[idx]) ** 2).mean(); loss = loss + 0.5 * vl
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
            stats.append((pl.item(), ent.mean().item()))
    # head marginals for logging
    with torch.no_grad():
        ds = net.dist(Xt); marg = [d.probs.mean(0).numpy().round(3).tolist() for d in ds]
    gaps = [(e['obj'] / e['init'] - 1) * 100 for e in eps]
    rec = dict(it=it, t=round(time.time() - t_start), ret=float(rets.mean()), gap=float(np.mean(gaps)),
               pl=float(np.mean([s[0] for s in stats])), ent=float(np.mean([s[1] for s in stats])), marg=marg)
    log.write(json.dumps(rec) + '\n'); log.flush()
    print(it, rec['t'], round(rec['ret'], 3), round(rec['ent'], 3), [m for j, m in enumerate(marg) if active[j]], flush=True)
    save(f'{a.out}/last.pt', it)
    if it % 25 == 0: save(f'{a.out}/it{it}.pt', it)
pool.close()
