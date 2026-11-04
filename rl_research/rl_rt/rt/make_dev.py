"""Held-out generated dev instances for go/no-go (never Liu's test set). seed 777, 4 per size.
Not used in training (training generates on the fly with other seeds) nor for checkpoint selection (that uses seed 424242)."""
import sys, numpy as np
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine')
from rt.inst import gen
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from lrphsd import fidelity_ops_v5 as ops
sys.path.insert(0, '/workspace/rl_v3'); from rlv3.gen_instances import reserve_ins
rng = np.random.default_rng(777)
for ns, n in [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]:
    for i in range(1, 5):
        while True:
            tg, st = gen(n, ns, rng)
            rows = ['CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME']
            k = 1
            for x, y in tg: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.2000\t10.0000'); k += 1
            for x, y in st: rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000'); k += 1
            p = f'/workspace/rl_rt/instances/dev/d{ns}_{n}_{i}.txt'; open(p, 'w').write('\n'.join(rows) + '\n')
            try:
                ins = read_instance(p); ops.prepare(ins); assert evaluate(ins, build(ins))['feasible']
                i2 = reserve_ins(ins, 0.2); ops.prepare(i2); assert evaluate(i2, build(i2))['feasible']
                break
            except Exception as e: print('regen', p, str(e)[:60])
print('ok')
