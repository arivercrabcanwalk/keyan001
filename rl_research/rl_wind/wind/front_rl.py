"""Design c' RL: online next-trip policy observing whether the front has passed (posterior over T) and per-trip
pre/post-front wind effects. REINFORCE with a shared (per drone & scenario) baseline over G sampled rollouts.
usage: front_rl.py train TABLE OUT ITERS [seed]"""
import wind, sys, json, math, time, zlib, numpy as np, torch, torch.nn as nn
from scipy.stats import norm
from wind.front import front_ctx, sample_scen, load_case, fly, P_FAIL
NF = 19
def feats(dr, rem, t, fc):
    sT = fc['sT']; That = fc['That']
    S0 = max(1e-9, 1 - norm.cdf((t - That) / sT))
    rows = []
    for i in rem:
        D1, F1, E1, I1 = dr.trips[i].summary(fc['w1'], dr.cap); D2, F2, E2, I2 = dr.trips[i].summary(fc['w2fc'], dr.cap)
        pd = (norm.cdf((t + D1 - That) / sT) - norm.cdf((t - That) / sT)) / S0
        ph = (norm.cdf((t + D1 / 2 - That) / sT) - norm.cdf((t - That) / sT)) / S0
        g = (F2 - F1) * dr.tc + P_FAIL * (I2 - I1)
        rows.append([D1 / 60, D2 / 60, (F2 - F1) / max(F1, 1e-6), g / 10, g / max(D1, 1e-6), E1, E2, float(I1), float(I2), pd, ph])
    X = np.array(rows, dtype=np.float32)
    rk = lambda v: (np.argsort(np.argsort(-v)) / max(1, len(v) - 1)).astype(np.float32)
    totD = X[:, 0].sum() * 60
    gl = np.array([np.clip((That - t) / sT, -3, 3), t / 100, len(rem) / 10, totD / max(That - t, 10.0) / 5, sT / 45,
                   math.hypot(*fc['w2fc']) / 600, math.hypot(*fc['w1']) / 600], dtype=np.float32)
    return np.concatenate([X, rk(X[:, 4])[:, None], np.repeat(gl[None], len(rem), 0)], 1)
class Net(nn.Module):
    def __init__(s):
        super().__init__(); s.f = nn.Sequential(nn.Linear(NF, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 1))
    def forward(s, x): return s.f(x).squeeze(-1)
def episode(net, dr, T, w1, w2, fc, greedy=False, rng=None):
    t = 0.0; fail = 0; rem = list(range(len(dr.trips))); dec = []
    L1 = [tr.legdur(w1) for tr in dr.trips]; L2 = [tr.legdur(w2) for tr in dr.trips]
    while rem:
        if t < T and len(rem) > 1:
            X = feats(dr, rem, t, fc)
            with torch.no_grad(): lg = net(torch.from_numpy(X)).numpy()
            if greedy: k = int(lg.argmax())
            else:
                p = np.exp(lg - lg.max()); p /= p.sum(); k = int(rng.choice(len(p), p=p))
            dec.append((X, k))
        else: k = 0
        i = rem.pop(k); t, f, ok = fly(dr.trips[i], t, T, L1[i], L2[i], dr.cap); fail += (not ok)
    return dict(cost=t * dr.tc, fail=fail, end=t), dec
def make_rl(path):
    net = Net(); net.load_state_dict(torch.load(path)); net.eval()
    def pol(dr, rem, t, passed, w2k, fc):
        if passed: return 0
        with torch.no_grad(): return int(net(torch.from_numpy(feats(dr, rem, t, fc))).argmax())
    return pol
def train(table, out, iters, seed=0, B=48, G=8):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    rows = [json.loads(l) for l in open(table)]
    rows = [r for r in rows if not r.get('infeasible') and abs(r['reserve'] - 0.15) < 1e-9]
    pool = []
    for r in rows:
        ins, fixed, drones = load_case(r); fc = front_ctx(r['case'], r['ctx'])
        pool += [(dr, fc) for dr in drones if len(dr.trips) >= 2]
    print('train drones', len(pool), flush=True)
    net = Net(); opt = torch.optim.Adam(net.parameters(), 1e-3); t0 = time.time()
    for it in range(iters):
        Xs, Ks, As = [], [], []; Rm = []
        for b in rng.integers(0, len(pool), B):
            dr, fc = pool[b]; T, w2 = sample_scen(fc, rng, 1); T, w2 = T[0], w2[0]
            eps = [episode(net, dr, T, fc['w1'], w2, fc, rng=rng) for _ in range(G)]
            R = np.array([-(e[0]['cost'] + P_FAIL * e[0]['fail']) for e in eps]); A = R - R.mean()
            Rm.append(R.mean())
            for (res, dec), a in zip(eps, A):
                for X, k in dec: Xs.append(X); Ks.append(k); As.append(a)
        if not Xs: continue
        loss = 0.0; ent = 0.0
        for X, k, a in zip(Xs, Ks, As):
            lp = torch.log_softmax(net(torch.from_numpy(X)), 0); loss = loss - a * lp[k]; ent = ent - (lp.exp() * lp).sum()
        loss = loss / len(Xs) - 0.005 * ent / len(Xs)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        if it % 50 == 0:
            print(f'{it} R {np.mean(Rm):.2f} dec {len(Xs)} ent {ent.item()/len(Xs):.3f} {time.time()-t0:.0f}s', flush=True)
            torch.save(net.state_dict(), out)
    torch.save(net.state_dict(), out)
if __name__ == '__main__':
    train(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 0)
