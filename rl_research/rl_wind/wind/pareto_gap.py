"""RL points vs the lower convex hull of fixed (r_s,r_l) points (hull = achievable by mixing two fixed actions across cases).
Reports failure-rate gap at equal cost (negative = RL below the hull = dominates mixtures of fixed policies)."""
import wind, sys, numpy as np
from wind.rl_type import load, act
R = '/workspace/rl_wind/results/'
_, A, *_ = load(R + 'hr_train_type.jsonl')
cst, _, Xt, ctA, ftA, _, _ = load(R + 'hr_test_type.jsonl', A); _, _, _, cB, fB, _, _ = load(R + 'hr_test_type_rs.jsonl', A)
feas = ~np.isnan(ctA); n = len(cst); ar = np.arange(n)
fx = np.array([(cB[:, i].mean(), fB[:, i].mean()) for i in range(len(A)) if feas[:, i].all()])
pts = sorted(map(tuple, fx)); hull = []
for p in pts:
    while len(hull) >= 2 and (hull[-1][0]-hull[-2][0])*(p[1]-hull[-2][1]) - (hull[-1][1]-hull[-2][1])*(p[0]-hull[-2][0]) <= 0: hull.pop()
    hull.append(p)
hull = np.array(hull); i = int(hull[:, 1].argmin()); hull = hull[:i + 1]
PS = np.exp(np.linspace(np.log(15), np.log(400), 14)); rows = []
for m in sys.argv[1].split(','):
    for P in PS:
        k = act(m, Xt, P, feas); c, f = cB[ar, k].mean(), fB[ar, k].mean()
        if hull[0, 0] <= c <= hull[-1, 0]:
            fh = np.interp(c, hull[:, 0], hull[:, 1]); rows.append((m[-6:-3], P, c, f, f - fh, 100 * (f - fh) / fh))
for r in rows: print(f'{r[0]} P={r[1]:6.1f} cost {r[2]:.1f} fail {r[3]:.3f} gap-to-hull {r[4]:+.3f} ({r[5]:+.1f}%)')
g = np.array([r[5] for r in rows]); print(f'mean gap {g.mean():+.2f}%  RL below hull in {(g<0).sum()}/{len(g)} points')
