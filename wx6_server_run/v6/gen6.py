"""Fresh v6 maps (generated AFTER the preregistration, seed 20261118; never seen by any earlier version):
  Test-G : Liu sizes (5_35, 6_50, 7_65, 8_80, 10_110) x 20 maps = 100 maps  -> data/instances/fresh6/
  Test-L : 12_150, 15_200, 20_300 x 10 maps = 30 maps (side grows with sqrt(#stations)) -> data/instances/large6/
Liu-style generator (targets uniform within 4.75 km of some station). Idempotent."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from v6.common import ROOT, gen, size_scale, write_instance

rng = np.random.default_rng(20261118)
n = 0
for ns, nt in [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]:
    for k in range(1, 21):
        p = os.path.join(ROOT, "data/instances/fresh6", f"g{ns}_{nt}_{k}.txt")
        tg, st = gen(nt, ns, rng)
        if not os.path.exists(p):
            write_instance(p, tg, st); n += 1
for ns, nt in [(12, 150), (15, 200), (20, 300)]:
    for k in range(1, 11):
        p = os.path.join(ROOT, "data/instances/large6", f"G{ns}_{nt}_{k}.txt")
        tg, st = gen(nt, ns, rng, scale=size_scale(nt, ns))
        if not os.path.exists(p):
            write_instance(p, tg, st); n += 1
print(f"[gen6] wrote {n} new maps")
