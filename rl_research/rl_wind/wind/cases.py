"""Case sets. A case = (instance file, wind context). dev = rl_rt held-out generated instances; test = Liu's 50 (5_35..10_110)."""
import wind, numpy as np, zlib
from wind.model import sample_context
LIU = '/workspace/rl_wind/engine/external/LRPHSD/data/Instances_Alg'
DEVDIR = '/workspace/rl_rt/instances/dev'
SIZES = ['5_35', '6_50', '7_65', '8_80', '10_110']
def _ctx(tag):
    return sample_context(np.random.default_rng(zlib.crc32(tag.encode())))
def dev_cases(k=2):
    return [(f'{DEVDIR}/d{s}_{i}.txt', f'd{s}_{i}#w{j}', _ctx(f'dev{s}_{i}_{j}')) for s in SIZES for i in (1, 2, 3, 4) for j in range(k)]
def test_cases(k=2):
    return [(f'{LIU}/{s}_{i}.txt', f'{s}_{i}#w{j}', _ctx(f'test{s}_{i}_{j}')) for s in SIZES for i in range(1, 11) for j in range(k)]
TRDIR = '/workspace/rl_wind/instances/train'
def train_cases(n=150):
    import os
    os.makedirs(TRDIR, exist_ok=True)
    from wind.rt_gen import write_instance
    out = []
    for i in range(n):
        ns, nt = [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)][i % 5]
        p = f'{TRDIR}/w{ns}_{nt}_{i}.txt'
        if not os.path.exists(p): write_instance(p, nt, ns, 50_000_000 + i)
        out.append((p, f'w{ns}_{nt}_{i}', _ctx(f'train{i}')))
    return out
