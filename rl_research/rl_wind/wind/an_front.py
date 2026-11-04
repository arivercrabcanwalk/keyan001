import json, sys, numpy as np
rows = [json.loads(l) for l in open(sys.argv[1])]; ms = list(rows[0]['res'])
pl = np.mean([r['res']['plan']['J'] for r in rows])
for m in ms:
    J = np.mean([r['res'][m]['J'] for r in rows]); c = np.mean([r['res'][m]['cost'] for r in rows]); f = np.mean([r['res'][m]['fail'] for r in rows])
    print(f'{m:10s} J {J:8.2f} ({100*(J-pl)/pl:+.2f}% vs plan) cost {c:8.2f} fail {f:.3f}')
