"""Group-baseline PPO-style policy gradient (no critic) for the candidate proposer.
Each step: G candidates, policy samples M (Plackett-Luce), all M repaired; advantage of each
repaired candidate = group-standardised improvement among the M (GRPO/POMO-style shared baseline).
Loss: clipped ratio per PL term * A  +  beta * KL(pi || pi_BC) over the G candidates.
Variants: --algo grpo (default) | ppo_critic | a2c ; --nocond ; --nobc (random init, no KL)."""
import sys, os, json, time, random, argparse, numpy as np, torch
sys.path.insert(0,'/workspace/rl_v3'); import rlv3
from multiprocessing import Pool
from rlv3.model import Scorer, G0
TR='/workspace/rl_v3/instances/train'
def train_pool():
    out=[]
    for f in sorted(os.listdir(TR)):
        n=f[:-4]
        if n.startswith('g'):
            i=int(n.split('_')[-1])
            if i>=19: continue   # 19-22 dev (gate 2), 23-24 spare held-out; gate-1 held-out never trained on by RL either
        else:
            if int(n.split('_')[-1])>=9: continue
        out.append(n)
    return out
def rollout(task):
    sd, film, cond, name, lam, rsv, seed, sec, G, M = task
    import torch; torch.set_num_threads(1)
    from rlv3.search4 import solve4
    from rlv3.policy import SampleScorer
    from lrphsd.problem import read_instance
    p=SampleScorer(sd, film=film, cond=cond, rng=np.random.default_rng(seed))
    r=solve4(read_instance(f'{TR}/{name}.txt'), p, seed=seed, seconds=sec, M=M, G=G, lam=lam, reserve=rsv)
    return p.buf, (r['objective']/r['init_obj'], lam, name)
def to_batch(buf, Gmax=8):
    B=len(buf); F=buf[0][0].shape[1]; M=max(len(b[1]) for b in buf)
    X=np.zeros((B,Gmax,F),np.float32); valid=np.zeros((B,Gmax),bool); seq=np.zeros((B,M),np.int64); A=np.zeros((B,M),np.float32); R=np.zeros((B,M),np.float32); keep=np.ones(B,bool)
    for i,(fx,s,v,cur) in enumerate(buf):
        g=len(fx); X[i,:g]=fx; valid[i,:g]=True; seq[i,:len(s)]=s
        r=(v-cur)/cur*100
        fin=np.isfinite(r)
        if fin.sum()==0: keep[i]=False; continue
        r=np.where(fin,r,np.max(r[fin])+0.5)
        if r.max()-r.min()<1e-9: keep[i]=False; continue
        A[i,:len(s)]=(r.mean()-r)/(r.std()+1e-6); R[i,:len(s)]=-r
    return X[keep],valid[keep],seq[keep],A[keep],R[keep]
def pl_terms(scores, seq, valid):
    # log-prob of each sequential PL choice
    out=[]; avail=valid.clone()
    for k in range(seq.shape[1]):
        s=scores.masked_fill(~avail,-1e9)
        lp=torch.log_softmax(s,-1).gather(1,seq[:,k:k+1]).squeeze(1)
        out.append(lp); avail=avail.clone(); avail.scatter_(1,seq[:,k:k+1],False)
    return torch.stack(out,1)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seed',type=int,default=0); ap.add_argument('--iters',type=int,default=40)
    ap.add_argument('--eps-per-iter',type=int,default=8); ap.add_argument('--sec',type=float,default=6.0)
    ap.add_argument('--G',type=int,default=8); ap.add_argument('--M',type=int,default=4)
    ap.add_argument('--lr',type=float,default=3e-4); ap.add_argument('--beta',type=float,default=0.05)
    ap.add_argument('--clip',type=float,default=0.2); ap.add_argument('--epochs',type=int,default=3)
    ap.add_argument('--bc',default='/workspace/rl_v3/models/bc_s0.pt'); ap.add_argument('--nobc',action='store_true')
    ap.add_argument('--nocond',action='store_true'); ap.add_argument('--algo',default='grpo')
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    torch.manual_seed(a.seed); rng=random.Random(a.seed); torch.set_num_threads(4)
    cond=not a.nocond
    model=Scorer(cond=cond)
    ref=None
    if not a.nobc:
        model.load_state_dict(torch.load(a.bc)); ref=Scorer(cond=cond); ref.load_state_dict(torch.load(a.bc)); ref.eval()
    critic=None
    if a.algo in ('ppo_critic','a2c'):
        # state-value baseline from global features (replaces the group baseline)
        critic=torch.nn.Sequential(torch.nn.Linear(10,64),torch.nn.ReLU(),torch.nn.Linear(64,1))
    params=list(model.parameters())+(list(critic.parameters()) if critic else [])
    opt=torch.optim.Adam(params,a.lr)
    pool=train_pool(); os.makedirs(a.out,exist_ok=True)
    log=open(f'{a.out}/log.jsonl','a')
    with Pool(8, maxtasksperchild=4) as P:
        for it in range(a.iters):
            t0=time.time()
            sd={k:v.detach().numpy().astype(np.float64) for k,v in model.state_dict().items()}
            tasks=[]
            for e in range(a.eps_per_iter):
                lam=rng.choices([0,0.1,0.2,0.5,1,2],[1,1,1,2.3,2.3,2.4])[0]; rsv=rng.choice([0.0,0.1])
                tasks.append((sd,True,cond,rng.choice(pool),float(lam),rsv,rng.randrange(10**6),a.sec,a.G,a.M))
            res=P.map(rollout,tasks)
            buf=[g for b,_ in res for g in b]; stats=[s for _,s in res]
            X,valid,seq,A,R=to_batch(buf)
            X=torch.tensor(X); valid=torch.tensor(valid); seq=torch.tensor(seq); A=torch.tensor(A)
            R=torch.tensor(R); R=R.clamp(-5,5)/ (R.clamp(-5,5).std()+1e-6)
            with torch.no_grad():
                old=pl_terms(model(X,valid),seq,valid)
                refs=torch.log_softmax(ref(X,valid),-1) if ref is not None else None
            N=len(X); bs=2048; tl=0
            for ep in range(a.epochs if a.algo!='a2c' else 1):
                perm=torch.randperm(N)
                for k in range(0,N,bs):
                    b=perm[k:k+bs]
                    s=model(X[b],valid[b]); lp=pl_terms(s,seq[b],valid[b])
                    adv=A[b]
                    if critic is not None:
                        # critic baseline on raw relative improvement is unavailable per item; use group-free advantage:
                        # A_item = r_item - V(global state)  (r standardised per batch)
                        v=critic(X[b][:,0,G0:G0+10]).squeeze(-1)
                        adv=(R[b]-v.detach().unsqueeze(1))
                        vloss=((v.unsqueeze(1)-R[b])**2).mean()
                    else: vloss=0
                    if a.algo=='a2c':
                        pg=-(lp*adv).mean()
                    else:
                        ratio=torch.exp(lp-old[b])
                        pg=-torch.min(ratio*adv,ratio.clamp(1-a.clip,1+a.clip)*adv).mean()
                    loss=pg+0.5*vloss
                    if refs is not None and a.beta>0:
                        lpf=torch.log_softmax(s,-1); pf=lpf.exp()
                        kl=(pf*(lpf-refs[b])).masked_fill(~valid[b],0).sum(-1).mean()
                        loss=loss+a.beta*kl
                    opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params,1.0); opt.step(); tl+=loss.item()
            rec=dict(it=it,groups=N,loss=tl,rel_final=float(np.mean([s[0] for s in stats])),sec=time.time()-t0)
            log.write(json.dumps(rec)+'\n'); log.flush(); print(json.dumps(rec),flush=True)
            torch.save(model.state_dict(),f'{a.out}/last.pt')
if __name__=='__main__': main()
