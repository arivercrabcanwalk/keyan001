"""Train the constructive policy.
--algo pomo (default): multi-sample REINFORCE with shared (per-instance mean of N samples) baseline.
--algo a2c          : REINFORCE with a learned critic baseline V(graph, cond) (actor-critic ablation).
--nocond            : kappa / reserve not given to the policy (conditioning ablation)."""
import sys, os, time, json, argparse, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt')
from rt.inst import gen
from rt.env import Batch
from rt.model import Policy, rollout
SIZES = [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]
def sample_cond(rng, B):
    kap = np.where(rng.random(B) < 0.25, 0.0, np.exp(rng.uniform(np.log(0.05), np.log(15), B)))
    rsv = rng.choice([0.0, 0.1, 0.2], B, p=[0.5, 0.3, 0.2])
    return kap, rsv
def dev_set():
    rng = np.random.default_rng(424242)
    out = []
    for ns, n in SIZES:
        for i in range(8):
            out.append((ns, n, gen(n, ns, rng)))
    return out
def validate(pol, dev, kappa, rsv):
    pol.eval(); res = []
    with torch.no_grad():
        for ns, n in SIZES:
            ins = [x[2] for x in dev if x[1] == n]
            bt = Batch([a for a, b in ins], [b for a, b in ins], np.full(len(ins), kappa), np.full(len(ins), rsv), N=1)
            F, c, mk, lp, s, _ = rollout(pol, bt, greedy=True)
            res.append(float(F.mean()))
    pol.train(); return res
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--B', type=int, default=16); ap.add_argument('--N', type=int, default=16)
    ap.add_argument('--lr', type=float, default=3e-4); ap.add_argument('--hours', type=float, default=2.0)
    ap.add_argument('--algo', default='pomo'); ap.add_argument('--nocond', action='store_true')
    ap.add_argument('--threads', type=int, default=4); ap.add_argument('--resume', default=None)
    a = ap.parse_args()
    torch.set_num_threads(a.threads); torch.manual_seed(a.seed); rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    pol = Policy(cond=not a.nocond)
    if a.resume: pol.load_state_dict(torch.load(a.resume))
    opt = torch.optim.Adam(pol.parameters(), lr=a.lr)
    dev = dev_set(); log = open(f'{a.out}/log.jsonl', 'a')
    t0 = time.time(); it = 0; best = None
    while time.time() - t0 < a.hours * 3600:
        ns, n = SIZES[rng.integers(len(SIZES))]
        ins = [gen(n, ns, rng) for _ in range(a.B)]
        kap, rsv = sample_cond(rng, a.B)
        N = a.N if a.algo == 'pomo' else max(1, a.N // 4)
        bt = Batch([x for x, y in ins], [y for x, y in ins], kap, rsv, N=N)
        F, c, mk, logp, s, _ = rollout(pol, bt)
        Fb = F.view(a.B, N)
        if a.algo == 'pomo':
            adv = (Fb - Fb.mean(1, keepdim=True)) / Fb.mean(1, keepdim=True) * 100
            loss = (adv.detach().view(-1) * logp).mean(); vl = 0.0
        else:
            v = pol.value(torch.cat([pol.gm, pol.c], 1)).squeeze(1)              # predicts F/n
            tgt = (Fb.mean(1) / n).detach()
            vl = ((v - tgt) ** 2).mean()
            adv = (F / n - v.detach()[s.inst]) / tgt[s.inst] * 100
            loss = (adv.detach() * logp).mean() + vl
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0); opt.step()
        it += 1
        if it % 25 == 0:
            rec = dict(it=it, min=round((time.time() - t0) / 60, 1), size=n, F=float(F.mean()), fail=int(s.fail.sum()))
            if it % 100 == 0:
                rec['val_k0'] = validate(pol, dev, 0.0, 0.0); rec['val_k2'] = validate(pol, dev, 2.0, 0.0)
                score = sum(rec['val_k0']) + sum(rec['val_k2'])
                if best is None or score < best:
                    best = score; torch.save(pol.state_dict(), f'{a.out}/best.pt')
                torch.save(pol.state_dict(), f'{a.out}/last.pt')
            log.write(json.dumps(rec) + '\n'); log.flush(); print(json.dumps(rec), flush=True)
    torch.save(pol.state_dict(), f'{a.out}/last.pt')
if __name__ == '__main__': main()
