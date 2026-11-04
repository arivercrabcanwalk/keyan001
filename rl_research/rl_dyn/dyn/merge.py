"""merge result files and add pseudo-method NAME = per-(path,seed) mean over given methods. usage: merge.py OUT NAME m1,m2,.. files..."""
import sys, json, collections
out, name, ms = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
L = [json.loads(l) for f in sys.argv[4:] for l in open(f)]
g = collections.defaultdict(list)
for x in L:
    if x['method'] in ms: g[(x['path'], x['seed'])].append(x)
with open(out, 'w') as f:
    for x in L: f.write(json.dumps(x) + '\n')
    for k, v in g.items():
        if len(v) != len(ms): continue
        y = dict(v[0]); y['method'] = name
        for key in v[0]:
            if isinstance(v[0][key], (int, float)) and not isinstance(v[0][key], bool) and key != 'seed': y[key] = sum(z[key] for z in v) / len(v)
        f.write(json.dumps(y) + '\n')
