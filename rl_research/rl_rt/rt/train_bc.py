"""BC warm start from ALNS demonstrations (data/demo.jsonl), teacher forcing through the same env/masks.
usage: train_bc.py OUT_DIR EPOCHS [THREADS]"""
import sys, os, json, time, random, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt')
from rt.env import Batch, State
from rt.model import Policy
from rt.train import dev_set, validate
def to_actions(d):
    n = len(d['tg']); acts = []
    for s, kind in enumerate(d['types']):
        if not kind: continue
        for di in ((0, 1) if kind == 2 else (1,)):
            ty = 0 if kind == 1 else (1 if di == 0 else 2)
            for trip in d['routes'][s][di]:
                if not trip: continue
                acts.append(n + 3 * s + ty); acts += [t - 1 for t in trip]
    return acts
def forced(pol, bt, A, train=True):
    """A: (R, T) long, -1 padded. returns per-sample logp sum, valid flags."""
    s = State(bt)
    if pol is not None: pol.encode(bt)
    logp = torch.zeros(s.R); valid = torch.ones(s.R, dtype=torch.bool)
    for t in range(A.shape[1]):
        if s.done.all(): break
        m = s.mask()
        a = A[:, t].clone(); a[s.done | (a < 0)] = 0
        ok = m.gather(1, a[:, None]).squeeze(1) | s.done
        valid &= ok
        if pol is not None:
            lg = pol.logits(bt, s, m)
            lp = torch.log_softmax(lg, -1).gather(1, a[:, None]).squeeze(1)
            logp = logp + lp * (~s.done & ok).float()
        bad = ~ok
        if bad.any(): s.finish_fail(bad)
        s.step(a)
    return logp, valid & s.visited.all(1)
def main():
    out, epochs = sys.argv[1], int(sys.argv[2]); th = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    torch.set_num_threads(th); os.makedirs(out, exist_ok=True)
    D = [json.loads(l) for l in open(os.environ.get('DEMO', '/workspace/rl_rt/data/demo.jsonl'))]
    by = {}
    for d in D: by.setdefault(len(d['tg']), []).append(d)
    # validity filter (env only)
    keep = []
    for n, L in by.items():
        for i in range(0, len(L), 256):
            ch = L[i:i + 256]; acts = [to_actions(d) for d in ch]; T = max(map(len, acts))
            A = torch.tensor([a + [-1] * (T - len(a)) for a in acts])
            bt = Batch([np.array(d['tg']) for d in ch], [np.array(d['st']) for d in ch], np.array([d['kappa'] for d in ch]), np.array([d['reserve'] for d in ch]), N=1)
            with torch.no_grad(): _, v = forced(None, bt, A)
            keep += [(d, a) for d, a, ok in zip(ch, acts, v.tolist()) if ok]
    print('demos', len(D), 'valid under env masks', len(keep), flush=True)
    random.seed(0); val = keep[-200:]; tr = keep[:-200]
    pol = Policy(); opt = torch.optim.Adam(pol.parameters(), lr=1e-3)
    dev = dev_set(); log = open(f'{out}/log.jsonl', 'a'); t0 = time.time(); best = None
    def batches(L, B):
        g = {}
        for d, a in L: g.setdefault(len(d['tg']), []).append((d, a))
        bs = []
        for n, x in g.items():
            random.shuffle(x); bs += [x[i:i + B] for i in range(0, len(x), B)]
        random.shuffle(bs); return bs
    def run(b, train):
        T = max(len(a) for d, a in b); A = torch.tensor([a + [-1] * (T - len(a)) for d, a in b])
        bt = Batch([np.array(d['tg']) for d, a in b], [np.array(d['st']) for d, a in b], np.array([d['kappa'] for d, a in b]), np.array([d['reserve'] for d, a in b]), N=1)
        lp, v = forced(pol, bt, A); return -(lp / torch.tensor([len(a) for d, a in b])).mean()
    for ep in range(epochs):
        for g in opt.param_groups: g['lr'] = 1e-3 * (0.5 ** (ep // 3))
        tl = []
        for b in batches(tr, 64):
            loss = run(b, True); opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0); opt.step(); tl.append(loss.item())
        with torch.no_grad(): vl = np.mean([run(b, False).item() for b in batches(val, 64)])
        rec = dict(ep=ep, min=round((time.time() - t0) / 60, 1), train_nll=float(np.mean(tl)), val_nll=float(vl),
                   val_k0=validate(pol, dev, 0.0, 0.0), val_k2=validate(pol, dev, 2.0, 0.0))
        print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + '\n'); log.flush()
        torch.save(pol.state_dict(), f'{out}/ep{ep}.pt'); torch.save(pol.state_dict(), f'{out}/last.pt')
        sc = sum(rec['val_k0']) + sum(rec['val_k2'])
        if best is None or sc < best: best = sc; torch.save(pol.state_dict(), f'{out}/best.pt')
if __name__ == '__main__': main()
