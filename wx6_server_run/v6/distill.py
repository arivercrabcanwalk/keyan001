"""Stage D (RL6): distil the rollout teacher into the 1-ms token-scoring network (v6/net6.py).

Loss: soft-target cross-entropy  -sum_a q*(a|s) log pi(a|s),  q* = softmax(-(Q(s,.) - min Q)/tau) over legal actions,
with per-sample weight w = min(1, (Q_2nd - Q_min)/tau) (decisions where the teacher is indifferent carry little
signal). Model selection on a held-out 10 % of the shards (split by (map, day)) by the TEACHER REGRET
  E[ Q(s, argmax pi) - min_a Q(s,a) ]  (J5 units per decision), the quantity that bounds the policy-improvement loss.
numpy + Adam; a few minutes on CPU for ~1e5 samples (no GPU needed)."""
import os, sys, glob, json, time, argparse
import numpy as np
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from v6.net6 import Net6, save, load, KEYS
from v6 import feat6 as F6


def load_shards(dirs, rounds=None):
    X, Mk, Q, G = [], [], [], []
    files = []
    for d in dirs:
        files += sorted(glob.glob(os.path.join(d, "r*_*.npz")))
    for k, f in enumerate(files):
        if rounds is not None and int(os.path.basename(f).split("_")[0][1:]) not in rounds:
            continue
        try:
            z = np.load(f)
        except Exception:
            continue
        if len(z["Q"]) == 0:
            continue
        X.append(z["X"].astype(np.float32)); Mk.append(z["mask"]); Q.append(z["Q"].astype(np.float64))
        G.append(np.full(len(z["Q"]), k))
    if not X:
        raise SystemExit("[distill] no teacher samples found")
    return np.concatenate(X), np.concatenate(Mk).astype(bool), np.concatenate(Q), np.concatenate(G)


def targets(Q, mask, tau):
    Qm = np.where(mask, Q, np.inf)
    qmin = Qm.min(1, keepdims=True)
    z = np.where(mask, -(Qm - qmin) / tau, -np.inf)
    e = np.exp(z - z.max(1, keepdims=True)) * mask
    T = e / e.sum(1, keepdims=True)
    srt = np.sort(Qm, 1)
    gap = np.where(np.isfinite(srt[:, 1]), srt[:, 1] - srt[:, 0], 0.0)
    w = np.minimum(1.0, gap / tau)
    return T, w


def regret(net, X, mask, Q, bs=4096):
    r = []; agree = []
    for s in range(0, len(X), bs):
        z = net.logits(X[s:s + bs]); z = np.where(mask[s:s + bs], z, -np.inf)
        a = z.argmax(1)
        Qm = np.where(mask[s:s + bs], Q[s:s + bs], np.inf)
        r.append(Qm[np.arange(len(a)), a] - Qm.min(1)); agree.append(a == Qm.argmin(1))
    return float(np.concatenate(r).mean()), float(np.concatenate(agree).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="comma-separated teacher shard dirs")
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", default=""); ap.add_argument("--tau", type=float, default=20.0)
    ap.add_argument("--epochs", type=int, default=40); ap.add_argument("--bs", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--ablate", default="none")
    ap.add_argument("--bootstrap", type=int, default=1, help="seed-specific bootstrap resample of the training shards")
    a = ap.parse_args()
    t0 = time.time()
    X, Mk, Q, G = load_shards(a.data.split(","))
    rng = np.random.default_rng(a.seed)
    shards = np.unique(G); rng0 = np.random.default_rng(12345)          # validation split is seed-INDEPENDENT
    val_sh = set(rng0.choice(shards, max(1, len(shards) // 10), replace=False).tolist())
    isv = np.array([g in val_sh for g in G])
    tr = np.flatnonzero(~isv); va = np.flatnonzero(isv)
    if a.bootstrap:                                                     # seeds differ by data resample + init
        trs = np.array(sorted(set(G[tr].tolist())))
        pick = rng.choice(trs, len(trs), replace=True)
        cnt = np.bincount(pick, minlength=G.max() + 1)
        tr = np.concatenate([np.repeat(np.flatnonzero(G == s), cnt[s]) for s in np.flatnonzero(cnt)])
    T, W = targets(Q, Mk, a.tau)
    net = load(a.init) if a.init else Net6(seed=a.seed)
    if a.init:
        net = Net6(seed=a.seed); src = load(a.init); net.p = {k: v.copy() for k, v in src.p.items()}
    net.fmask = F6.ablation_mask(a.ablate)
    m = {k: np.zeros_like(v) for k, v in net.p.items()}; v2 = {k: np.zeros_like(v) for k, v in net.p.items()}
    step = 0; best = (np.inf, None); hist = []
    r0, ag0 = regret(net, X[va], Mk[va], Q[va])
    print(f"[distill] n_train={len(tr)} n_val={len(va)} shards={len(shards)} init val regret={r0:.2f} agree={ag0:.3f}", flush=True)
    bad = 0
    for ep in range(a.epochs):
        perm = rng.permutation(tr); L = []
        lr = a.lr * (0.5 if ep >= a.epochs * 0.6 else 1.0)
        for s in range(0, len(perm), a.bs):
            b = perm[s:s + a.bs]
            loss, g = net.loss_grad(X[b], Mk[b], T[b], W[b])
            step += 1; L.append(loss)
            for k in KEYS:
                m[k] = 0.9 * m[k] + 0.1 * g[k]; v2[k] = 0.999 * v2[k] + 0.001 * g[k] ** 2
                mh = m[k] / (1 - 0.9 ** step); vh = v2[k] / (1 - 0.999 ** step)
                net.p[k] -= lr * mh / (np.sqrt(vh) + 1e-8)
        rv, ag = regret(net, X[va], Mk[va], Q[va])
        hist.append(dict(ep=ep, loss=float(np.mean(L)), val_regret=rv, val_agree=ag))
        print(f"[distill] ep {ep} loss {np.mean(L):.4f} val_regret {rv:.2f} agree {ag:.3f}", flush=True)
        if rv < best[0] - 1e-6:
            best = (rv, {k: v.copy() for k, v in net.p.items()}); bad = 0
        else:
            bad += 1
            if bad >= 8:
                break
    net.p = best[1]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    save(net, a.out, stage="distill", seed=a.seed, tau=a.tau, ablate=a.ablate, val_regret=best[0], init_val_regret=r0,
         n_train=int(len(tr)), n_val=int(len(va)))
    json.dump(dict(hist=hist, best_val_regret=best[0], init_val_regret=r0, sec=time.time() - t0),
              open(a.out.replace(".npz", ".json"), "w"), indent=1)
    print(f"[distill] saved {a.out} best val regret {best[0]:.2f} ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
