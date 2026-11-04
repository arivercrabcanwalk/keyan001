import numpy as np
def write_instance(path, n, ns, seed):
    """Liu-style generator (same as rl_rt.inst.gen): stations uniform, targets uniform within 4750 m of a station."""
    rng = np.random.default_rng(seed)
    st = rng.uniform(0, 15000, (ns, 2)); tg = np.zeros((0, 2))
    while len(tg) < n:
        c = rng.uniform(0, 15000, (4 * n, 2)); d = np.sqrt(((c[:, None] - st[None]) ** 2).sum(-1)).min(1); tg = np.concatenate([tg, c[d <= 4750]])
    tg = tg[:n]; rows = ['CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME']; k = 1
    for x, y in tg: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.2000\t10.0000'); k += 1
    for x, y in st: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000'); k += 1
    open(path, 'w').write('\n'.join(rows) + '\n')
