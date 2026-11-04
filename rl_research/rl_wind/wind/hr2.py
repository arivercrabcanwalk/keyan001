"""Headroom under hidden gust regime: fixed margin rule vs regime-aware margin (knows the regime) vs oracle."""
import wind, sys, json, zlib, numpy as np, collections
from multiprocessing import get_context
from lrphsd.problem import read_instance
from wind.online import Scenario2, run2, pol_none, make_margin, pol_oracle
MARG = [0.0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25]
def job(r):
    ins = read_instance(r['path']); out = []
    pols = [('none', pol_none), ('oracle', pol_oracle)] + [(f'm{m}', make_margin(m)) for m in MARG]
    for s in range(60):
        sc = Scenario2(r['ctx'], zlib.crc32(f"{r['case']}#{s}".encode()))
        for name, pol in pols:
            m = run2(ins, r['solution'], r['ctx'], sc, pol); out.append(dict(case=r['case'], reserve=r['reserve'], s=s, pol=name, **m))
    return out
if __name__ == '__main__':
    rows = [json.loads(l) for l in open('results/plans_dev.jsonl')]; rows = [r for r in rows if r['reserve'] in (0.0, 0.05, 0.1)]
    with get_context('forkserver').Pool(7) as p, open(sys.argv[1], 'w') as f:
        for res in p.imap_unordered(job, rows):
            for x in res: f.write(json.dumps(x) + '\n')
