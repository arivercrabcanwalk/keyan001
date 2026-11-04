"""Order-invariant BC from ALNS demonstrations.
A demonstration fixes WHICH trips exist (station type, drone, target set, cyclic order) but not the order in which
the decoder emits trips, nor the direction of each trip. At every step the loss is -log sum_{a in A*} p(a), where A* is
the set of actions consistent with the demo (tokens with remaining trips; either endpoint of a remaining trip of the
active token; the next target inside a trip). The env then follows the model's most likely consistent action.
usage: DEMO=... train_bc2.py OUT_DIR EPOCHS THREADS [INIT]"""
import sys, os, json, time, random, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt')
from rt.env import Batch, State
from rt.model import Policy
from rt.train import dev_set, validate
def trips_of(d):
    n = len(d['tg']); T = {}
    for s, kind in enumerate(d['types']):
        if not kind: continue
        for di in ((0, 1) if kind == 2 else (1,)):
            ty = 0 if kind == 1 else (1 if di == 0 else 2)
            for trip in d['routes'][s][di]:
                if trip: T.setdefault(n + 3 * s + ty, []).append([t - 1 for t in trip])
    return T
def run_batch(pol, b):
    n = len(b[0]['tg']); R = len(b)
    bt = Batch([np.array(d['tg']) for d in b], [np.array(d['st']) for d in b], np.array([d['kappa'] for d in b]), np.array([d['reserve'] for d in b]), N=1)
    s = State(bt); pol.encode(bt)
    rem = [trips_of(d) for d in b]; cur = [[] for _ in b]; act_tok = [None] * R
    valid = torch.ones(R, dtype=torch.bool); nll = torch.zeros(R); steps = torch.zeros(R)
    V = n + bt.K
    for t in range(4 * n + 10):
        if s.done.all(): break
        m = s.mask()
        allow = torch.zeros(R, V, dtype=torch.bool)
        for r in range(R):
            if s.done[r]: allow[r, 0] = True; continue
            if cur[r]: allow[r, cur[r][0]] = True
            elif act_tok[r] is not None and s.need_t[r]:
                for tr in rem[r].get(act_tok[r], []): allow[r, tr[0]] = True; allow[r, tr[-1]] = True
            else:
                for k, L in rem[r].items():
                    if L: allow[r, k] = True
        allow_m = allow & m
        bad = ~allow_m.any(1) & ~s.done
        if bad.any():
            valid &= ~bad; s.finish_fail(bad); allow_m[bad, 0] = True; m = m.clone(); m[bad, 0] = True
        lg = pol.logits(bt, s, m); lp = torch.log_softmax(lg, -1)
        live = (~s.done).float()
        nll = nll - torch.logsumexp(lp.masked_fill(~allow_m, -1e9), -1) * live; steps += live
        a = lp.detach().masked_fill(~allow_m, -1e18).argmax(-1)
        for r in range(R):
            if s.done[r]: continue
            x = int(a[r])
            if x >= n: act_tok[r] = x
            elif cur[r]: cur[r].pop(0)
            else:
                L = rem[r][act_tok[r]]
                for i, tr in enumerate(L):
                    if tr[0] == x: cur[r] = tr[1:]; L.pop(i); break
                    if tr[-1] == x: cur[r] = tr[::-1][1:]; L.pop(i); break
        s.step(a)
    return (nll / steps.clamp(min=1))[valid].mean(), int(valid.sum())
def main():
    out, epochs, th = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    torch.set_num_threads(th); os.makedirs(out, exist_ok=True)
    D = [json.loads(l) for l in open(os.environ['DEMO'])]
    random.seed(0); val = D[-200:]; tr = D[:-200]
    pol = Policy()
    if len(sys.argv) > 4: pol.load_state_dict(torch.load(sys.argv[4]))
    opt = torch.optim.Adam(pol.parameters(), lr=1e-3)
    dev = dev_set(); log = open(f'{out}/log.jsonl', 'a'); t0 = time.time(); best = None
    def batches(L, B):
        g = {}
        for d in L: g.setdefault(len(d['tg']), []).append(d)
        bs = []
        for n, x in g.items():
            random.shuffle(x); bs += [x[i:i + B] for i in range(0, len(x), B)]
        random.shuffle(bs); return bs
    for ep in range(epochs):
        for g in opt.param_groups: g['lr'] = 1e-3 * (0.5 ** (ep // 3))
        tl = []
        for b in batches(tr, 64):
            loss, nv = run_batch(pol, b); opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0); opt.step(); tl.append(loss.item())
        with torch.no_grad(): vl = np.mean([run_batch(pol, b)[0].item() for b in batches(val, 64)])
        rec = dict(ep=ep, min=round((time.time() - t0) / 60, 1), train_nll=float(np.mean(tl)), val_nll=float(vl),
                   val_k0=validate(pol, dev, 0.0, 0.0), val_k2=validate(pol, dev, 2.0, 0.0))
        print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + '\n'); log.flush()
        torch.save(pol.state_dict(), f'{out}/ep{ep}.pt'); torch.save(pol.state_dict(), f'{out}/last.pt')
        sc = sum(rec['val_k0']) + sum(rec['val_k2'])
        if best is None or sc < best: best = sc; torch.save(pol.state_dict(), f'{out}/best.pt')
if __name__ == '__main__': main()
