import sys,glob,os,random,json,numpy as np,torch
sys.path.insert(0,'/workspace/rl_v3')
from rlv3.train_rank import load,prep,heldout,D
from rlv3.model import Scorer, G0
files=sorted(glob.glob(f'{D}/*.npz')); nm=lambda f: os.path.basename(f).split('_l')[0]
te=[f for f in files if heldout(nm(f))]
X,V,C,va=prep(*load(te))
m=Scorer(); m.load_state_dict(torch.load('/workspace/rl_v3/models/bc_s0.pt')); m.eval()
with torch.no_grad(): S=m(torch.tensor(X),torch.tensor(va)).numpy()
lam=X[:,0,G0]; rng=random.Random(3)
res={}
for i in range(len(X)):
    idx=[j for j in np.flatnonzero(va[i]) if np.isfinite(V[i,j])]
    if len(idx)<4: continue
    sub=rng.sample(idx,4); v=V[i,sub]
    if v.max()-v.min()<=0: continue
    w=np.flatnonzero(v==v.min())
    key='lam0' if lam[i]==0 else ('lam<=0.2' if lam[i]<=0.2 else 'lam>=0.5')
    r=res.setdefault(key,[[],[],[]])
    r[0].append(1.0 if int(np.argmax(S[i,sub])) in w else 0.0); r[1].append(len(w)/4)
    # relative gain of model-top1 vs random pick (% of cur obj)
    r[2].append((v[int(np.argmax(S[i,sub]))]-v.mean())/C[i]*100)
for k,(h,rd,g) in sorted(res.items()):
    print(k,'n=%d hit=%.3f rand=%.3f  (top1 - mean of 4) = %.4f%% of cur obj'%(len(h),np.mean(h),np.mean(rd),np.mean(g)))
h=sum((r[0] for r in res.values()),[]); rd=sum((r[1] for r in res.values()),[])
print('ALL all-feasible subsets: hit=%.3f rand=%.3f n=%d'%(np.mean(h),np.mean(rd),len(h)))
