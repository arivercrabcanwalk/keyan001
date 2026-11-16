"""Fresh static test maps (never seen by anyone before the pre-registration): Liu sizes x 10 each, seed 20261116;
plus large maps (12_150, 15_200, 20_300) x 5. Written in the official format to data/instances/fresh*/."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, gen, size_scale, write_instance
rng = np.random.default_rng(20261116)
for ns, n in [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]:
    for k in range(1, 11):
        tg, st = gen(n, ns, rng); write_instance(os.path.join(ROOT, "data/instances/fresh", f"f{ns}_{n}_{k}.txt"), tg, st)
for ns, n in [(12, 150), (15, 200), (20, 300)]:
    for k in range(1, 6):
        tg, st = gen(n, ns, rng, scale=size_scale(n, ns)); write_instance(os.path.join(ROOT, "data/instances/fresh_large", f"F{ns}_{n}_{k}.txt"), tg, st)
print("fresh instances written")
