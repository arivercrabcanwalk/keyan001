"""Design b' v2: RL adaptive per-drone-type reserve (r_small, r_large) from a 6x6 grid (contextual bandit).
Policy pi(a | x, P), x = rich context features (forecast wind, uncertainty, gusts, instance geometry vs wind),
conditioned on log P (P ~ log-uniform [20, 250] in training). Training: policy gradient on simulated per-case returns
(normalised per case by the case's mean J over actions); 'exp' = expected (all-action) policy gradient
(Ciosek & Whiteson 2018) using the simulator's returns for every action; 'rf' = sampled REINFORCE with baseline.
Rewards from training-scenario sims (seed A); evaluation always on independent scenarios (seed B).
usage: rl_type.py train TABLE OUT ITERS SEED MODE"""
import wind, sys, json, math, collections, os, pickle, numpy as np, torch, torch.nn as nn
from wind.model import MS, VA
FCACHE = '/workspace/rl_wind/results/feat_cache.pkl'
_F = pickle.load(open(FCACHE, 'rb')) if os.path.exists(FCACHE) else {}
def feats(case, path, ctx):
    if case in _F: return _F[case]
    from lrphsd.problem import read_instance
    from wind.model import make_planning_instance
    ins = read_instance(path); q = make_planning_instance(ins, ctx, 0.0); p = ins.params
    R1 = ins.radius(1); wd = np.array([math.cos(ctx['theta']), math.sin(ctx['theta'])])
    u, uL, cosv = [], [], []
    for t in ins.targets:
        cand = [s for s in ins.stations if ins.gdist[s.id, t.id] <= R1 + 1e-7] or list(ins.stations)
        s = min(cand, key=lambda s: q.dist[s.id, t.id] + q.dist[t.id, s.id])
        e = (q.dist[s.id, t.id] + q.dist[t.id, s.id]) / p.speed * p.flight_energy + t.energy
        u.append(e / p.small_battery); uL.append(e / p.large_battery)
        v = np.array([t.x - s.x, t.y - s.y]); n = np.linalg.norm(v); cosv.append(float(v @ wd / n) if n > 0 else 0.0)
    u, uL, cosv = np.array(u), np.array(uL), np.array(cosv)
    def worst(w):  # round-trip slowdown factor for a head/tail axis wind of w m/s
        w = min(w * MS, 0.95 * VA); return VA * VA / (VA * VA - w * w)
    f1 = worst(ctx['W'] + 2 * ctx['sigma']) / worst(ctx['W']); f2 = worst(ctx['W'] + 2 * ctx['sigma'] + ctx['gmax']) / worst(ctx['W'])
    x = np.array([ctx['W'] / 10, ctx['sigma'] / 3, ctx['gust'] / 0.3, math.log(len(ins.targets)) / 5, len(ins.stations) / 10,
                  len(ins.targets) / len(ins.stations) / 15,
                  u.mean(), np.quantile(u, .5), np.quantile(u, .9), u.max(), (u > .5).mean(), (u > .7).mean(), (u > .85).mean(),
                  uL.mean(), np.quantile(uL, .9), (u * f1 > 1).mean(), (u * f2 > 1).mean(), (uL * f2 > 1).mean(), f1 - 1, f2 - 1,
                  np.abs(cosv).mean(), cosv.mean(), (np.abs(cosv) > .8).mean()], dtype=np.float32)
    _F[case] = x; return x
def save_cache(): pickle.dump(_F, open(FCACHE, 'wb'))
def _path(c, r):
    if r.get('path'): return r['path']
    from wind.cases import LIU, DEVDIR
    b = c.split('#')[0]; return f'{DEVDIR}/{b}.txt' if b.startswith('d') else f'{LIU}/{b}.txt'
def load(table, A=None):
    """returns cases, actions, X, cost, fail, undeliv, mk (infeasible -> nan)"""
    C = collections.defaultdict(dict)
    for l in open(table):
        r = json.loads(l); k = tuple(r['reserve']) if isinstance(r['reserve'], list) else (r['reserve'], r['reserve']); C[r['case']][k] = r
    A = A or sorted({a for c in C for a in C[c]}); cs = sorted(c for c in C if all(a in C[c] for a in A))
    X = np.stack([feats(c, _path(c, next(iter(C[c].values()))), next(iter(C[c].values()))['ctx']) for c in cs]); save_cache()
    g = lambda k: np.array([[np.nan if C[c][a].get('infeasible') else C[c][a][k] for a in A] for c in cs])
    return cs, A, X, g('cost'), g('failed'), g('undelivered'), g('makespan')
class Pol(nn.Module):
    def __init__(s, nf, na, h=128):
        super().__init__(); s.net = nn.Sequential(nn.Linear(nf + 2, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(), nn.Linear(h, na))
    def forward(s, x, P):
        lp = torch.log(P)[:, None]; return s.net(torch.cat([x, (lp - 4.3) / 1.0, ((lp - 4.3) ** 2)], 1))
H = int(os.environ.get('H', 128)); WD = float(os.environ.get('WD', 1e-4)); ENT = float(os.environ.get('ENT', 0.02))
def train(table, out, iters=6000, seed=0, mode='exp', sub=None):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    cs, A, X, cost, fail, _, _ = load(table)
    if sub is not None: X, cost, fail = X[sub], cost[sub], fail[sub]; cs = [cs[i] for i in sub]
    n = len(cs); print('train cases', n, 'actions', len(A), flush=True)
    mu, sd = X.mean(0), X.std(0) + 1e-6; Xt = torch.tensor((X - mu) / sd, dtype=torch.float32)
    feas = ~np.isnan(cost); mask = torch.tensor(feas)
    C0, F0 = torch.tensor(np.nan_to_num(cost, nan=0.0)), torch.tensor(np.nan_to_num(fail, nan=0.0))
    pol = Pol(X.shape[1], len(A), H); opt = torch.optim.Adam(pol.parameters(), 1e-3, weight_decay=WD)
    for it in range(iters):
        idx = torch.tensor(rng.integers(0, n, 256)); P = torch.tensor(np.exp(rng.uniform(math.log(20), math.log(250), 256)), dtype=torch.float32)
        lg = pol(Xt[idx], P).masked_fill(~mask[idx], -1e9); logp = torch.log_softmax(lg, 1)
        J = (C0[idx] + P[:, None].double() * F0[idx]).float()
        Jm = torch.where(mask[idx], J, torch.zeros_like(J)).sum(1) / mask[idx].sum(1)
        R = torch.where(mask[idx], -(J / Jm[:, None] - 1) * 100, torch.zeros_like(J))      # % better than case mean
        if mode == 'exp':
            pi = logp.exp(); loss = -(pi * R).sum(1).mean()
        else:
            a = torch.distributions.Categorical(logits=lg).sample(); Ra = R.gather(1, a[:, None]).squeeze(1)
            b = (logp.exp() * R).sum(1).detach(); loss = -((Ra - b) * logp.gather(1, a[:, None]).squeeze(1)).mean()
        ent = -(logp.exp() * torch.where(mask[idx], logp, torch.zeros_like(logp))).sum(1).mean()
        loss = loss - ENT * ent
        opt.zero_grad(); loss.backward(); opt.step()
        if it % 1000 == 0: print(it, 'expR %.3f ent %.3f' % ((logp.exp() * R).sum(1).mean().item(), ent.item()), flush=True)
    torch.save(dict(sd=pol.state_dict(), mu=mu, sdv=sd, nf=X.shape[1], A=A, H=H), out)
def act(model, X, P, feas=None):
    m = torch.load(model, weights_only=False); pol = Pol(m['nf'], len(m['A']), m.get('H', 128)); pol.load_state_dict(m['sd'])
    with torch.no_grad():
        lg = pol(torch.tensor((X - m['mu']) / m['sdv'], dtype=torch.float32), torch.full((len(X),), float(P)))
        if feas is not None: lg = lg.masked_fill(~torch.tensor(feas), -1e9)
    return lg.argmax(1).numpy()
if __name__ == '__main__':
    if sys.argv[1] == 'train': train(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
