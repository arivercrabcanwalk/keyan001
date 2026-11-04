"""Open-loop distillation of an RL policy: per (lam,sec) and segment, the per-head mode of the actions the
policy took on DEV traces -> fixed schedule (no state feedback). Ablation: is the gain from state-dependence?"""
import json, collections, sys, numpy as np
C = collections.defaultdict(list)
for l in open(sys.argv[1]):
    j = json.loads(l); C[f"{j['lam']}_{j['sec']}"].append(j['cfgs'])
out = {}
for k, L in C.items():
    A = np.array(L)  # n x S x 5
    sched = []
    for s in range(A.shape[1]):
        sched.append([int(np.bincount(A[:, s, h]).argmax()) for h in range(5)])
    out[k] = sched
json.dump(out, open(sys.argv[2], 'w'))
for k in sorted(out): print(k, out[k])
