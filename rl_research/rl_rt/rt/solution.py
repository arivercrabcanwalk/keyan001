"""Decode an action sequence into the official solution format and evaluate with lrphsd.evaluator."""
import numpy as np
from .inst import TOK_KIND, TOK_DI
def decode(acts, n, ns, target_ids):
    types = [0] * ns; routes = [[[], []] for _ in range(ns)]
    cur = None
    for a in acts:
        a = int(a)
        if a < 0: break
        if a < n:
            cur.append(target_ids[a])
        else:
            k = a - n; s, ty = divmod(k, 3)
            if types[s] == 0: types[s] = int(TOK_KIND[ty])
            cur = []; routes[s][int(TOK_DI[ty])].append(cur)
    for s in range(ns):
        for d in range(2):
            routes[s][d] = [t for t in routes[s][d] if t]
    return types, routes
def to_solution(ins, types, routes):
    return {'schema_version': 1, 'instance': ins.name, 'instance_sha256': ins.sha256, 'station_types': types, 'routes': routes}
def makespan(ins, sol):
    from lrphsd.evaluator import evaluate
    r = evaluate(ins, sol)
    t = {}
    for d in r['details']:
        t[(d['station'], d['drone'])] = t.get((d['station'], d['drone']), 0) + d['time_min']
    return r, (max(t.values()) if t else 0.0)
