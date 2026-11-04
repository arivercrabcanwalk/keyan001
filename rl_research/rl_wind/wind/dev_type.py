"""dev check: RL (rl_type) vs best fixed tuned on TRAIN table, evaluated on dev seed-B. usage: dev_type.py MODEL TRAIN DEV_A DEV_B"""
import wind, sys, numpy as np
from wind.rl_type import load, act
m, tr, da, db = sys.argv[1:5]
_, A, Xtr, ctr, ftr, _, _ = load(tr); cs, _, Xd, ca, fa, _, _ = load(da, A); csb, _, _, cb, fb, _, _ = load(db, A)
feas = ~np.isnan(ca); n = len(cs); ar = np.arange(n)
for P in (25, 50, 100, 200):
    Jt = ctr + P * ftr; f = min(range(len(A)), key=lambda i: np.nanmean(Jt[:, i]) if not np.isnan(Jt[:, i]).all() else 1e18)
    Jb = cb + P * fb; k = act(m, Xd, P, feas)
    fx = np.nanmean(Jb[:, f]); rl = Jb[ar, k].mean(); orc = Jb[ar, np.nanargmin(ca + P * fa, 1)].mean()
    print(f'P={P}: fixed{A[f]} {fx:.1f}  RL {rl:.1f} ({100*(rl-fx)/fx:+.2f}%)  sim-select {100*(orc-fx)/fx:+.2f}%  RL acts {len(set(k))} distinct')
