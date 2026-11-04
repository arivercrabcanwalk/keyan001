"""Design (b'): strong-wind regime, RL adaptive battery reserve (contextual bandit, REINFORCE).
Action = reserve level r in GRID used by the planner (one plan per case, same compute as fixed-r NoRL).
Reward = -(cost + P*failed_trips) per day, estimated by MC on TRAINING scenarios (seed A); all reported numbers use
independent scenarios (seed B, wind/resim.py). Policy is conditioned on the failure price P (log P input).
usage: rl_reserve.py train TABLE OUT | eval MODEL TABLE_B P..."""
import wind, sys, json, math, collections, numpy as np, torch, torch.nn as nn
GRID = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
PS = [25, 50, 100, 200]
_FC = {}
def feats(case, path, ctx):
    if case in _FC: return _FC[case]
    from lrphsd.problem import read_instance
    from wind.model import make_planning_instance
    ins = read_instance(path); q = make_planning_instance(ins, ctx, 0.0); p = ins.params
    u = []
    for t in ins.targets:
        best = min((q.dist[s.id, t.id] + q.dist[t.id, s.id]) for s in ins.stations
                   if ins.gdist[s.id, t.id] <= ins.radius(1) + 1e-7) if any(ins.gdist[s.id, t.id] <= ins.radius(1) + 1e-7 for s in ins.stations) else \
               min((q.dist[s.id, t.id] + q.dist[t.id, s.id]) for s in ins.stations)
        u.append(best / p.speed * p.flight_energy / p.small_battery)
    u = np.array(u)
    f = np.array([ctx['W'] / 10, ctx['sigma'] / 3, ctx['gust'] / 0.3, math.log(len(ins.targets)) / 5, len(ins.stations) / 10,
                  u.mean(), np.quantile(u, .5), np.quantile(u, .9), u.max(), (u > .5).mean(), (u > .7).mean()], dtype=np.float32)
    _FC[case] = f; return f
def load(table):
    C = collections.defaultdict(dict)
    for l in open(table):
        r = json.loads(l); C[r['case']][r['reserve']] = r
    cs = sorted(c for c in C if len(C[c]) == len(GRID) and not any(C[c][g].get('infeasible') for g in GRID))
    def path(c):
        r = C[c][GRID[0]]
        if r.get('path'): return r['path']
        from wind.cases import LIU, DEVDIR
        b = c.split('#')[0]; return f'{DEVDIR}/{b}.txt' if b.startswith('d') else f'{LIU}/{b}.txt'
    X = np.stack([feats(c, path(c), C[c][GRID[0]]['ctx']) for c in cs])
    cost = np.array([[C[c][g]['cost'] for g in GRID] for c in cs]); fail = np.array([[C[c][g]['failed'] for g in GRID] for c in cs])
    return cs, X, cost, fail
class Pol(nn.Module):
    def __init__(s, nf):
        super().__init__(); s.net = nn.Sequential(nn.Linear(nf + 1, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, len(GRID)))
    def forward(s, x, P): return s.net(torch.cat([x, torch.log(P)[:, None] / 5], 1))
def train(table, out, iters=4000, seed=0):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    cs, X, cost, fail = load(table); n = len(cs); print('train cases', n)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    pol = Pol(X.shape[1]); opt = torch.optim.Adam(pol.parameters(), 1e-3, weight_decay=1e-4)
    Xt = torch.tensor((X - mu) / sd)
    for it in range(iters):
        idx = rng.integers(0, n, 256); P = rng.choice(PS, 256).astype(np.float32)
        logits = pol(Xt[idx], torch.tensor(P)); d = torch.distributions.Categorical(logits=logits)
        a = d.sample().numpy()
        J = cost[idx, a] + P * fail[idx, a]
        Jref = (cost[idx] + P[:, None] * fail[idx]).mean(1)        # per-case scale
        R = -(J / Jref - 1.0) * 100                                # percent
        # shared baseline per (case,P): 8 extra samples
        with torch.no_grad():
            a2 = d.sample((8,)).numpy(); b = np.mean([-((cost[idx, x] + P * fail[idx, x]) / Jref - 1) * 100 for x in a2], 0)
        A = torch.tensor(R - b, dtype=torch.float32)
        loss = -(A * d.log_prob(torch.tensor(a))).mean() - 0.01 * d.entropy().mean()
        opt.zero_grad(); loss.backward(); opt.step()
        if it % 500 == 0: print(it, 'meanR %.3f ent %.3f' % (R.mean(), d.entropy().mean().item()), flush=True)
    torch.save(dict(sd=pol.state_dict(), mu=mu, sdv=sd, nf=X.shape[1]), out)
def act(model, X, P, greedy=True):
    m = torch.load(model, weights_only=False); pol = Pol(m['nf']); pol.load_state_dict(m['sd'])
    with torch.no_grad():
        lg = pol(torch.tensor((X - m['mu']) / m['sdv'], dtype=torch.float32), torch.full((len(X),), float(P)))
    return lg.argmax(1).numpy()
if __name__ == '__main__':
    if sys.argv[1] == 'train': train(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4000)
