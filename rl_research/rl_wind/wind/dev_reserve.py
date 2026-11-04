import wind, sys, numpy as np
from wind.rl_reserve import load, act, GRID
R='/workspace/rl_wind/results/'
for tab in sys.argv[2:]:
    cs, X, ca, fa = load(R+tab)
    import json, collections
    print(tab, len(cs))
    for P in (25,50,100,200):
        J=ca+P*fa; bf=J.mean(0).argmin(); a=act(sys.argv[1], X, P)
        rl=J[np.arange(len(cs)),a].mean()
        print(f'  P={P} fixed r={GRID[bf]} J={J[:,bf].mean():.2f}  RL J={rl:.2f} ({100*(rl-J[:,bf].mean())/J[:,bf].mean():+.2f}%)  oracle {100*(J.min(1).mean()-J[:,bf].mean())/J[:,bf].mean():+.2f}%  acts {np.bincount(a,minlength=9)}')
