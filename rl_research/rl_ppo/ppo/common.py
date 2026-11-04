import sys, os
sys.path.insert(0, '/workspace/rl_ppo'); sys.path.insert(0, '/workspace/rl_v3/engine')
INST = '/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg'
TRDIR = '/workspace/rl_v3/instances/train'
SIZES = ['5_35', '6_50', '7_65', '8_80', '10_110']
TEST = [f'{s}_{i}' for s in SIZES for i in range(1, 11)]
DEV = [f'g{s}_{i}' for s in SIZES for i in (19, 20, 21, 22)]
TRAIN = [f'g{s}_{i}' for s in SIZES for i in range(1, 19)] + \
        sorted(f[:-4] for f in os.listdir(TRDIR) if f.startswith('o'))
TUNE = [f'g{s}_{i}' for s in SIZES for i in range(1, 19)]   # NoRL tuning set (subset of TRAIN, Liu-size groups)
_cache = {}
def load(name):
    if name not in _cache:
        from lrphsd.problem import read_instance
        p = f'{INST}/{name}.txt' if not name.startswith(('g', 'o')) else f'{TRDIR}/{name}.txt'
        _cache[name] = read_instance(p)
    return _cache[name]
