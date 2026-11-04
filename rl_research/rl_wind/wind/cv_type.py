"""5-fold CV on the training table: RL vs fixed (tuned on the training folds). usage: cv_type.py TABLE ITERS MODE"""
import wind, sys, os, numpy as np
from wind.rl_type import load, train, act
tab, iters, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3]
cs, A, X, c, f, _, _ = load(tab); n = len(cs); rng = np.random.default_rng(0); perm = rng.permutation(n); folds = np.array_split(perm, 5)
res = {P: [] for P in (25, 50, 100, 200)}
for k, va in enumerate(folds):
    trn = np.setdiff1d(perm, va); mp = f'/tmp/cv_{os.getpid()}_{k}.pt'
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()): train(tab, mp, iters, k, mode, sub=trn)
    feas = ~np.isnan(c[va])
    for P in res:
        Jt = c[trn] + P * f[trn]; fi = min(range(len(A)), key=lambda i: np.nanmean(Jt[:, i]) if not np.isnan(Jt[:, i]).any() else 1e18)
        Jv = c[va] + P * f[va]; a = act(mp, X[va], P, feas)
        res[P].append((np.nanmean(Jv[:, fi]), Jv[np.arange(len(va)), a].mean()))
for P, v in res.items():
    fx = sum(x[0] for x in v); rl = sum(x[1] for x in v); print(f'P={P}: RL vs fixed {100*(rl-fx)/fx:+.2f}%')
