"""Headroom of per-trip recourse: oracle vs best fixed-margin rule, on dev plans from headroom.py (reserve 0 and 0.05)."""
import wind, sys, json, zlib, numpy as np, collections
from multiprocessing import get_context
from lrphsd.problem import read_instance
from wind.online import Scenario, run, pol_none, make_margin, pol_oracle, make_lookahead
from wind.cases import dev_cases
MARG = [0.0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.2]
PATH = {c: p for p, c, x in dev_cases()}
def job(r):
    ins = read_instance(PATH[r['case']]); out = []
    import os
    if os.environ.get('LOOK'): pols = [(f'la{e}', make_lookahead(e)) for e in (0.01, 0.03, 0.1, 0.2)]
    else: pols = [('none', pol_none), ('oracle', pol_oracle)] + [(f'm{m}', make_margin(m)) for m in MARG]
    for s in range(int(sys.argv[2])):
        sc = Scenario(r['ctx'], zlib.crc32(f"{r['case']}#{s}".encode()))
        for name, pol in pols:
            out.append(dict(case=r['case'], reserve=r['reserve'], s=s, pol=name, **run(ins, r['solution'], r['ctx'], sc, pol)))
    return out
if __name__ == '__main__':
    rows = [json.loads(l) for l in open('results/hr_dev.jsonl')]
    rows = [r for r in rows if r['reserve'] in (0.0, 0.05)]
    with get_context('forkserver').Pool(7) as p, open(sys.argv[1], 'w') as f:
        for res in p.imap_unordered(job, rows):
            for x in res: f.write(json.dumps(x) + '\n')
