import sys, json, collections, numpy as np
L = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
by = collections.defaultdict(list)
for x in L: by[x['pol']].append(x)
ref = {(x['path'], x['seed']): x for x in by['myopic']}
print('%-14s %8s %7s %7s %7s %7s %7s %7s %6s %7s' % ('pol', 'J', 'dJ%', 'cost', 'mk', 'pen', 'ontime', 'ontH', 'resp', 'ms'))
for k, v in by.items():
    a = lambda f: np.mean([x[f] for x in v])
    dj = np.mean([(x['J'] - ref[(x['path'], x['seed'])]['J']) / ref[(x['path'], x['seed'])]['J'] for x in v]) * 100
    print('%-14s %8.2f %7.2f %7.1f %7.1f %7.2f %7.3f %7.3f %6.2f %7.1f' % (k, a('J'), dj, a('cost'), a('mk'), a('pen'), a('ontime'), a('ontime_h'), a('resp'), a('ms')))
