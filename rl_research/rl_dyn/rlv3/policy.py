import numpy as np, torch
from .model import Scorer
class GreedyScorer:
    """Evaluation proposer: score G heuristic candidates, repair the top-M."""
    name='rl'; needs_feats=True
    def __init__(self, ckpt, **kw):
        self.m=Scorer(**kw); self.m.load_state_dict(torch.load(ckpt, map_location='cpu')); self.m.eval()
        self.np=NpScorer(self.m)
    def pick(self, fx, M, glob):
        if len(fx)<=M: return list(range(len(fx))), None
        s=self.np(fx)
        return list(np.argsort(-s)[:M]), None

class NpScorer:
    """Numpy re-implementation of Scorer.forward for fast single-group inference."""
    def __init__(self, model=None, sd=None, film=True, cond=True):
        if model is not None:
            sd={k:v.detach().numpy().astype(np.float64) for k,v in model.state_dict().items()}
            film, cond = model.film, model.cond
        self.sd=sd; self.film=film; self.cond=cond
        from .model import LOC0, LOC1, G0
        self.LOC0,self.LOC1,self.G0=LOC0,LOC1,G0
    def __call__(self, X):
        sd=self.sd; X=X.astype(np.float64)
        if not self.cond: X=X.copy(); X[:,self.G0:self.G0+3]=0
        loc=X[:,self.LOC0:self.LOC1]; h=np.concatenate([X,loc-loc.mean(0,keepdims=True)],1)
        h1=h@sd['l1.weight'].T+sd['l1.bias']
        if self.film:
            c=X[0,self.G0:self.G0+3]
            z=np.maximum(c@sd['f.0.weight'].T+sd['f.0.bias'],0)@sd['f.2.weight'].T+sd['f.2.bias']
            g1,b1,g2,b2=np.split(z,4)
            h1=h1*(1+g1)+b1
        h1=np.maximum(h1,0); h2=h1@sd['l2.weight'].T+sd['l2.bias']
        if self.film: h2=h2*(1+g2)+b2
        h2=np.maximum(h2,0)
        return (h2@sd['out.weight'].T+sd['out.bias'])[:,0]

class SampleScorer:
    """Training proposer: Plackett-Luce (Gumbel top-k) sample of M of G candidates; logs groups."""
    name='rl_sample'; needs_feats=True
    def __init__(self, sd, film=True, cond=True, rng=None, temp=1.0):
        self.np=NpScorer(sd=sd, film=film, cond=cond); self.rng=rng or np.random.default_rng(0); self.temp=temp
        self.buf=[]
    def pick(self, fx, M, glob):
        if len(fx)<=M: return list(range(len(fx))), None
        s=self.np(fx)/self.temp
        g=self.rng.gumbel(size=len(s))
        seq=list(np.argsort(-(s+g))[:M])
        return seq, (fx, seq)
    def observe(self, info, picked, vals, cur):
        fx, seq = info
        self.buf.append((fx.astype(np.float32), np.array(seq), np.array(vals, dtype=np.float64), cur))
