"""Gate 1: offline listwise ranker (BC warm start). Train on training instances, test on held-out instances."""
import sys, os, glob, re, json, numpy as np, torch, random
sys.path.insert(0,'/workspace/rl_v3'); import rlv3
from rlv3.model import Scorer, LOC0
torch.set_num_threads(8)
D='/workspace/rl_v3/data/g1'
def heldout(name):
    m=re.match(r'g\d+_\d+_(\d+)$',name)
    if m: return int(m.group(1))>=19
    m=re.match(r'o\d+_\d+_(\d+)$',name); return int(m.group(1))>=9
def load(files):
    Xs=[];Vs=[];Cs=[]
    for f in files:
        z=np.load(f)
        if z['X'].ndim!=3 or len(z['X'])==0: continue
        Xs.append(z['X'][::4]); Vs.append(z['V'][::4]); Cs.append(z['cur'][::4])
    return np.concatenate(Xs), np.concatenate(Vs), np.concatenate(Cs)
def prep(X,V,C):
    V=V.copy(); V[np.isnan(V)]=np.inf
    valid=np.zeros(V.shape,bool)
    n=(X.sum(-1)!=0)  # padded rows are all-zero
    valid=n
    fin=np.isfinite(V)&valid
    keep=(fin.sum(1)>=2)
    vmin=np.where(fin,V,np.inf).min(1)
    # informative: not all finite values equal
    vmax=np.where(fin,V,-np.inf).max(1)
    keep&= (vmax-vmin)>1e-9*np.abs(vmin)
    return X[keep],V[keep],C[keep],valid[keep]
def target(V,valid,tau):
    # soft target: softmax(-(v-vmin)/ (tau*|cur|)) over finite; inf -> 0
    fin=np.isfinite(V)
    vmin=np.where(fin,V,np.inf).min(1,keepdims=True)
    z=np.where(fin, -(V-vmin)/tau, -np.inf)
    z=z-z.max(1,keepdims=True); e=np.exp(z); return e/e.sum(1,keepdims=True)
def evaluate_groups(model,X,V,C,valid,rng,M=4,reps=3):
    """hit rate on random 4-subsets; plus best-of-4-chosen-from-8 gain."""
    with torch.no_grad():
        S=model(torch.tensor(X),torch.tensor(valid)).numpy()
    hits=[];rnd=[];gain_model=[];gain_rand=[];gain_first=[];gain_or=[]
    for i in range(len(X)):
        idx=np.flatnonzero(valid[i])
        for _ in range(reps):
            sub=rng.sample(list(idx),min(M,len(idx)))
            v=V[i,sub]
            if not np.isfinite(v).any() or np.nanmax(np.where(np.isfinite(v),v,np.nan))-np.nanmin(np.where(np.isfinite(v),v,np.nan))<=0: continue
            w=np.flatnonzero(v==v.min())
            hits.append(1.0 if int(np.argmax(S[i,sub])) in w else 0.0); rnd.append(len(w)/len(sub))
        if len(idx)>=8:
            top=idx[np.argsort(-S[i,idx])[:M]]
            r=rng.sample(list(idx),M)
            b=lambda s:(min(V[i,s]) if np.isfinite(V[i,s]).any() else C[i])
            gain_model.append(b(top)); gain_rand.append(b(r)); gain_first.append(b(idx[:M])); gain_or.append(b(idx))
    rel=lambda a,b_: np.mean((np.array(a)-np.array(b_))/C[:1].mean()*0+ (np.array(a)-np.array(b_)))
    return dict(hit=float(np.mean(hits)),rand=float(np.mean(rnd)),n=len(hits),
                best4_model_minus_rand=float(np.mean(np.array(gain_model)-np.array(gain_rand))),
                best4_model_minus_first=float(np.mean(np.array(gain_model)-np.array(gain_first))),
                best8_minus_rand=float(np.mean(np.array(gain_or)-np.array(gain_rand))), ng=len(gain_model))
def heuristic_eval(X,V,C,valid,rng,col):
    class H:
        def __call__(s,Xt,vt):
            return torch.tensor(np.where(vt.numpy(), Xt.numpy()[...,col], -1e9))
    return evaluate_groups(H(),X,V,C,valid,rng)
if __name__=='__main__':
    files=sorted(glob.glob(f'{D}/*.npz'))
    nm=lambda f: os.path.basename(f).split('_l')[0]
    tr=[f for f in files if not heldout(nm(f))]; te=[f for f in files if heldout(nm(f))]
    Xtr,Vtr,Ctr,vtr=prep(*load(tr)); Xte,Vte,Cte,vte=prep(*load(te))
    print('train groups',len(Xtr),'test groups',len(Xte),'train files',len(tr),'test files',len(te),flush=True)
    # value scale: normalise by current objective (tau in % of cur)
    relV=lambda V,C: (V-C[:,None])/C[:,None]*100
    Ttr=target(relV(Vtr,Ctr),vtr,tau=0.05)
    rng=random.Random(0)
    seed=int(sys.argv[1]) if len(sys.argv)>1 else 0
    torch.manual_seed(seed)
    model=Scorer(); opt=torch.optim.Adam(model.parameters(),1e-3,weight_decay=1e-5)
    Xt=torch.tensor(Xtr); vt=torch.tensor(vtr); Tt=torch.tensor(Ttr,dtype=torch.float32)
    N=len(Xt); bs=1024
    for ep in range(8):
        perm=torch.randperm(N); tot=0
        model.train()
        for k in range(0,N,bs):
            b=perm[k:k+bs]
            s=model(Xt[b],vt[b]); lp=torch.log_softmax(s,-1)
            loss=-(Tt[b]*lp.clamp(min=-1e4)).sum(-1).mean()
            opt.zero_grad(); loss.backward(); opt.step(); tot+=loss.item()*len(b)
        model.eval()
        ev=evaluate_groups(model,Xte[:20000],Vte[:20000],Cte[:20000],vte[:20000],random.Random(1))
        print('ep',ep,'loss %.4f'%(tot/N),json.dumps(ev),flush=True)
    os.makedirs('/workspace/rl_v3/models',exist_ok=True)
    torch.save(model.state_dict(),f'/workspace/rl_v3/models/bc_s{seed}.pt')
    ev=evaluate_groups(model,Xte,Vte,Cte,vte,random.Random(2))
    print('FINAL heldout',json.dumps(ev))
    from rlv3.model import LOC0
    for name,col in [('max_saving',LOC0+4),('btl_frac',LOC0+1),('sum_saving',LOC0+5)]:
        print('heuristic',name,json.dumps(heuristic_eval(Xte[:20000],Vte[:20000],Cte[:20000],vte[:20000],random.Random(2),col)))
