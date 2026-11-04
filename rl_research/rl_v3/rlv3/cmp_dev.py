import sys,json,glob,os,numpy as np
from scipy.stats import wilcoxon
base=sys.argv[1]; others=sys.argv[2:]
def load(f):
    return {(r['inst'],r['lam'],r['reserve'],r['seed']):r for r in map(json.loads,open(f))}
B=load(base)
for o in others:
    if not os.path.exists(o): continue
    O=load(o); keys=[k for k in O if k in B]
    print('==',os.path.basename(o),'vs',os.path.basename(base),'n=%d'%len(keys),'steps %.0f vs %.0f'%(np.mean([O[k]['steps'] for k in keys]),np.mean([B[k]['steps'] for k in keys])))
    for lamset,name in [((0.0,),'lam0'),((1.0,2.0),'lam1,2'),(None,'all')]:
        d=np.array([(O[k]['objective']/B[k]['objective']-1)*100 for k in keys if lamset is None or k[1] in lamset])
        if len(d)<5: continue
        p=wilcoxon(d).pvalue if np.any(d) else 1
        print('  %-7s mean %+.3f%%  median %+.3f%%  better %d/%d  p=%.3g'%(name,d.mean(),np.median(d),(d<0).sum(),len(d),p))
