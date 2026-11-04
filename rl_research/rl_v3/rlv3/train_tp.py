"""Train the target-level residual policy (v2) with a group-relative baseline (no critic).
Per step the engine draws M=4 candidates from the policy; all are repaired; each candidate's
advantage = group-standardised improvement among the 4 (shared baseline, POMO/GRPO-style).
Loss = PPO-clip on the Plackett-Luce log-prob of every target-sampling call of the candidate
       + beta * KL(pi || pi_ref) on the first-choice distribution of each call.
--bc-iters K : first K iterations are behaviour cloning of best-of-4 winners (from the initial,
               i.e. heuristic, policy), then pi_ref := BC policy.
--algo a2c   : no clipping, single epoch;  --algo ppo_critic : learned value V(g) baseline instead
               of the group baseline (standard PPO);  --nocond : lambda/reserve/risk zeroed."""
import sys, os, json, time, random, argparse, numpy as np, torch
sys.path.insert(0,'/workspace/rl_v3'); import rlv3
import multiprocessing as mp
from rlv3.tpolicy import init_params, FT, FG, HID, HID2
from rlv3.train_rl import train_pool
from carl.actions import N_OPERATORS
TR='/workspace/rl_v3/instances/train'
PMAX=96
def rollout(task):
    params, nocond, name, lam, rsv, seed, sec, M = task
    from rlv3.search4 import solve4
    from rlv3.tpolicy import TargetPolicy
    from lrphsd.problem import read_instance
    p=TargetPolicy(params, lam=lam, reserve=rsv, log=True, nocond=nocond)
    r=solve4(read_instance(f'{TR}/{name}.txt'), p, seed=seed, seconds=sec, M=M, G=M, lam=lam, reserve=rsv)
    # compact: per call -> (state idx, rows, order, cand advantage index)
    S=p.states; calls=[]; G=[]; adv=[]
    for gi,(g,cl,picked,vals,cur) in enumerate(p.groups):
        r_=(vals-cur)/cur*100; fin=np.isfinite(r_)
        if fin.sum()==0: continue
        r_=np.where(fin,r_,r_[fin].max()+0.5)
        if r_.max()-r_.min()<1e-9: continue
        A=(r_.mean()-r_)/(r_.std()+1e-6); win=(r_==r_.min()).astype(float); win/=win.sum()
        amap={c:(A[k],win[k],-r_[k]) for k,c in enumerate(picked)}
        for (c,sid,rows,order) in cl:
            if c not in amap or len(rows)>PMAX: continue
            calls.append((len(G),sid,rows.astype(np.int32),order.astype(np.int16))+amap[c])
        G.append(g)
    return S, G, calls, (r['objective']/r['init_obj'], lam, name, r['steps'])
class TorchPol(torch.nn.Module):
    def __init__(self, params):
        super().__init__()
        self.P=torch.nn.ParameterDict({k:torch.nn.Parameter(torch.tensor(v,dtype=torch.float32)) for k,v in params.items()})
    def forward(self, X, g, nocond=False):
        # X (B,P,FT), g (B,FG)
        P=self.P; c=g[:,N_OPERATORS+3:N_OPERATORS+6]
        h=X@P['W1t']+(g@P['W1g']+P['b1']).unsqueeze(1)
        h=h*(1+(c@P['Wc'])).unsqueeze(1)
        h=torch.relu(h); h2=torch.relu(h@P['W2']+P['b2'])
        return h2@P['w3']+P['b3']
    def np_params(self):
        return {k:v.detach().numpy().astype(np.float64) for k,v in self.P.items()}
def assemble(res):
    Sall=[]; Gall=[]; rows=[]; orders=[]; gi=[]; A=[]; W=[]; R=[]; soff=0; goff=0
    for S,G,calls,_ in res:
        for (g,sid,rw,od,a,w,r) in calls:
            rr=np.where(rw>=0, rw+soff, -1)
            rows.append(rr); orders.append(od); gi.append(g+goff); A.append(a); W.append(w); R.append(r)
        soff+=sum(len(s) for s in S); goff+=len(G)
        Sall.extend(S); Gall.extend(G)
    Sall=np.concatenate(Sall+[np.zeros((1,FT),np.float32)])  # last row = zero for missing
    zero=len(Sall)-1
    B=len(rows); Pm=max(len(r) for r in rows); K=max(len(o) for o in orders)
    RW=np.full((B,Pm),zero,np.int64); V=np.zeros((B,Pm),bool); OD=np.zeros((B,K),np.int64); KM=np.zeros((B,K),bool)
    for i,(r,o) in enumerate(zip(rows,orders)):
        RW[i,:len(r)]=np.where(r>=0,r,zero); V[i,:len(r)]=True; OD[i,:len(o)]=o; KM[i,:len(o)]=True
    return (torch.tensor(Sall),torch.tensor(np.stack(Gall)),torch.tensor(RW),torch.tensor(V),torch.tensor(OD),torch.tensor(KM),
            torch.tensor(np.array(gi)),torch.tensor(np.array(A),dtype=torch.float32),torch.tensor(np.array(W),dtype=torch.float32),torch.tensor(np.array(R),dtype=torch.float32))
def pl_logp(s, valid, OD, KM):
    avail=valid.clone(); tot=torch.zeros(s.shape[0]); first=None
    for k in range(OD.shape[1]):
        ls=torch.log_softmax(s.masked_fill(~avail,-1e9),-1)
        if k==0: first=ls
        t=ls.gather(1,OD[:,k:k+1]).squeeze(1)
        tot=tot+torch.where(KM[:,k],t,torch.zeros_like(t))
        avail=avail.clone(); avail.scatter_(1,OD[:,k:k+1],avail.gather(1,OD[:,k:k+1])&~KM[:,k:k+1])
    return tot, first
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seed',type=int,default=0); ap.add_argument('--iters',type=int,default=60)
    ap.add_argument('--eps',type=int,default=8); ap.add_argument('--sec',type=float,default=6.0); ap.add_argument('--M',type=int,default=4)
    ap.add_argument('--lr',type=float,default=1e-3); ap.add_argument('--beta',type=float,default=0.02); ap.add_argument('--clip',type=float,default=0.2)
    ap.add_argument('--epochs',type=int,default=3); ap.add_argument('--bc-iters',type=int,default=3)
    ap.add_argument('--algo',default='grpo'); ap.add_argument('--nocond',action='store_true'); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    torch.manual_seed(a.seed); rng=random.Random(a.seed); torch.set_num_threads(4)
    os.makedirs(a.out,exist_ok=True); log=open(f'{a.out}/log.jsonl','a')
    pol=TorchPol(init_params(a.seed)); ref=None
    critic=torch.nn.Sequential(torch.nn.Linear(FG,64),torch.nn.ReLU(),torch.nn.Linear(64,1)) if a.algo=='ppo_critic' else None
    params=list(pol.parameters())+(list(critic.parameters()) if critic else [])
    opt=torch.optim.Adam(params,a.lr)
    pool=train_pool()
    bc_buf=[]
    ctx=mp.get_context('forkserver')
    if True:
        for it in range(a.iters):
            t0=time.time(); npp=pol.np_params()
            tasks=[]
            for e in range(a.eps):
                lam=rng.choices([0,0.1,0.2,0.5,1,2],[1,1,1,2.3,2.3,2.4])[0]; rsv=rng.choice([0.0,0.1])
                tasks.append((npp,a.nocond,rng.choice(pool),float(lam),rsv,rng.randrange(10**6),a.sec,a.M))
            try:
                with ctx.Pool(8) as P:
                    res=P.map_async(rollout,tasks).get(timeout=120)
            except Exception as e:
                print('rollout failure',type(e).__name__,e,flush=True); continue
            print('rollouts %.1fs'%(time.time()-t0),flush=True)
            Sall,Gm,RW,V,OD,KM,GI,A,W,R=assemble(res)
            if a.nocond: Gm[:,N_OPERATORS+3:N_OPERATORS+6]=0
            N=len(RW); bs=4096; tl=0.0
            phase='bc' if it<a.bc_iters else 'rl'
            with torch.no_grad():
                old=torch.cat([pl_logp(pol(Sall[RW[i:i+bs]],Gm[GI[i:i+bs]]),V[i:i+bs],OD[i:i+bs],KM[i:i+bs])[0] for i in range(0,N,bs)])
                refl=None
                if ref is not None:
                    refl=torch.cat([torch.log_softmax(ref(Sall[RW[i:i+bs]],Gm[GI[i:i+bs]]).masked_fill(~V[i:i+bs],-1e9),-1) for i in range(0,N,bs)])
            Rn=R/(R.std()+1e-6)
            epochs=(6 if phase=='bc' else (1 if a.algo=='a2c' else a.epochs))
            for ep in range(epochs):
                perm=torch.randperm(N)
                for k in range(0,N,bs):
                    b=perm[k:k+bs]
                    s=pol(Sall[RW[b]],Gm[GI[b]]); lp,first=pl_logp(s,V[b],OD[b],KM[b])
                    if phase=='bc':
                        loss=-(W[b]*lp).sum()/W[b].sum().clamp(min=1)   # imitate best-of-4 winners
                    else:
                        if critic is not None:
                            v=critic(Gm[GI[b]]).squeeze(-1); adv=Rn[b]-v.detach(); vloss=((v-Rn[b])**2).mean()
                        else:
                            adv=A[b]; vloss=0.0
                        if a.algo=='a2c':
                            pg=-(lp*adv).mean()
                        else:
                            ratio=torch.exp(lp-old[b]); pg=-torch.min(ratio*adv,ratio.clamp(1-a.clip,1+a.clip)*adv).mean()
                        loss=pg+0.5*vloss
                        if refl is not None and a.beta>0:
                            pf=first.exp(); kl=(pf*(first-refl[b])).masked_fill(~V[b],0).sum(-1).mean(); loss=loss+a.beta*kl
                    opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params,1.0); opt.step(); tl+=float(loss.detach())
            if phase=='bc' and it==a.bc_iters-1:
                ref=TorchPol(pol.np_params()); ref.eval()
                torch.save(pol.state_dict(),f'{a.out}/bc.pt'); json.dump(pol.np_params(),open(f'{a.out}/bc.json','w'),default=lambda x:x.tolist())
            if ref is None and phase=='rl' and a.bc_iters==0:
                ref=TorchPol(init_params(a.seed)); ref.eval()   # no-BC: KL to the heuristic (uniform) policy
            st=[x[3] for x in res]
            rec=dict(it=it,phase=phase,calls=N,loss=tl,rel_final=float(np.mean([s[0] for s in st])),steps=float(np.mean([s[3] for s in st])),
                     w3=float(pol.P['w3'].abs().mean()),sec=round(time.time()-t0,1))
            log.write(json.dumps(rec)+'\n'); log.flush(); print(json.dumps(rec),flush=True)
            json.dump(pol.np_params(),open(f'{a.out}/last.json','w'),default=lambda x:x.tolist())
            if it%10==9: json.dump(pol.np_params(),open(f'{a.out}/it{it+1}.json','w'),default=lambda x:x.tolist())
if __name__=='__main__': main()
