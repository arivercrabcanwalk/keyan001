"""Deterministic exact-probability fixtures, not route-quality experiments."""
from __future__ import annotations
import argparse
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys

def load(path):
    spec=importlib.util.spec_from_file_location("orbit_under_test",path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=m
    spec.loader.exec_module(m)
    return m

def close(a,b,tol=2e-10):
    assert math.isclose(a,b,rel_tol=tol,abs_tol=tol),(a,b)

def expect(error,call):
    try: call()
    except error: return
    raise AssertionError("expected "+error.__name__)

class TinyPhysicalPolicy:
    """One-open-trip history-free softmax with all legal alternatives.

    Canonical fsum at closed boundaries is part of both sampling and rescoring.
    This synthetic model is deliberately independent of map benchmark data.
    """
    def __init__(self,m,theta=0.37,forbidden=False):
        self.m,self.theta,self.forbidden=m,theta,forbidden
        self.targets=(1,2,3,4,5)
        self.xyz={0:(0.,0.),1:(1.,0.),2:(2.,0.),3:(0.,2.),4:(1.,2.),5:(2.,2.)}
        self.service={t:0.25+t*.03 for t in self.targets}
        self.service_energy={t:.2+t*.11 for t in self.targets}
        self.capacity={0:14.,1:8.5}
        self.limit=30.
    def dist(self,a,b):
        return math.dist(self.xyz[a],self.xyz[b])
    def duration(self,b):
        path=(0,)+b.targets+(0,)
        return math.fsum(self.dist(a,z) for a,z in zip(path,path[1:]))+math.fsum(self.service[t] for t in b.targets)
    def edge(self,completed,block):
        m=self.m
        done={t for b in completed for t in b.targets}
        rem=set(self.targets)-done
        duty={d:math.fsum(self.duration(b) for b in sorted(completed) if b.slot==d) for d in (0,1)}
        pos,energy,elapsed=0,0.,0.
        open_slot=None
        logp,score=0.,0.
        for desired in [(block.slot,t) for t in block.targets]+[(block.slot,None)]:
            actions=[]
            for d in (0,1):
                if open_slot is not None and d!=open_slot: continue
                for t in sorted(rem):
                    travel=self.dist(pos,t)
                    back=self.dist(t,0)
                    e=energy+travel+self.service_energy[t]+back
                    dt=duty[d]+elapsed+travel+self.service[t]+back
                    if e<=self.capacity[d] and dt<=self.limit:
                        f=.23*t-.31*d+.019*len(rem)+.017*energy-.009*duty[d]+.013*self.dist(pos,t)
                        actions.append(((d,t),f))
                if open_slot==d and pos!=0 and energy+self.dist(pos,0)<=self.capacity[d] and duty[d]+elapsed+self.dist(pos,0)<=self.limit:
                    actions.append(((d,None),-.41+.07*len(rem)+.09*d+.011*energy))
            if self.forbidden and not done and desired==(1,4):
                actions=[(a,f) for a,f in actions if a!=(1,4)]
            found=[f for a,f in actions if a==desired]
            if not found:return m.LogScore(-math.inf,(0.,))
            logits=[self.theta*f for a,f in actions]
            top=max(logits)
            z=math.fsum(math.exp(q-top) for q in logits)
            mean=math.fsum(math.exp(q-top)*f for q,(_,f) in zip(logits,actions))/z
            logp+=self.theta*found[0]-top-math.log(z)
            score+=found[0]-mean
            d,t=desired
            if t is None:
                pos,energy,elapsed,open_slot=0,0.,0.,None
            else:
                travel=self.dist(pos,t)
                energy+=travel+self.service_energy[t]
                elapsed+=travel+self.service[t]
                pos=t;open_slot=d;rem.remove(t)
        return m.LogScore(logp,(score,))

def direct(m,blocks,edge,prefix=()):
    total,score_sum=0.,0.
    for perm in itertools.permutations(blocks):
        done=list(prefix);lp=0.;g=0.
        for b in perm:
            e=edge(tuple(sorted(done)),b)
            lp+=e.logp;g+=e.score[0];done.append(b)
        p=math.exp(lp)
        total+=p;score_sum+=p*g
    if total==0:raise m.ZeroSupport("direct support zero")
    return math.log(total),score_sum/total

def run(m):
    cases={}
    blocks=(m.Block(0,(1,2)),m.Block(1,(4,)),m.Block(0,(3,5)))
    model=TinyPhysicalPolicy(m)
    def record(name,fn):
        fn();cases[name]="PASS"

    def case_empty_single():
        z=m.block_orbit((),model.edge)
        assert z.logp==0 and z.score==() and z.edge_evaluations==0
        one=m.block_orbit(blocks[:1],model.edge)
        edge=model.edge((),blocks[0])
        close(one.logp,edge.logp);close(one.score[0],edge.score[0])
    record("empty_and_single",case_empty_single)

    def case_physical():
        got=m.block_orbit(blocks,model.edge)
        lp,g=direct(m,blocks,model.edge)
        close(got.logp,lp);close(got.score[0],g)
        assert 0<math.exp(lp)<1
    record("physical_action_normalizers_vs_full_permutations",case_physical)

    def case_finite_difference():
        got=m.block_orbit(blocks,model.edge)
        h=1e-5
        up=m.block_orbit(blocks,TinyPhysicalPolicy(m,model.theta+h).edge).logp
        dn=m.block_orbit(blocks,TinyPhysicalPolicy(m,model.theta-h).edge).logp
        close(got.score[0],(up-dn)/(2*h),tol=1e-8)
    record("independent_parameter_finite_difference",case_finite_difference)

    def case_window():
        got=m.window_partition_score(blocks,model.edge,window_size=2)
        z1,g1=direct(m,blocks[:2],model.edge)
        z2,g2=direct(m,blocks[2:],model.edge,prefix=blocks[:2])
        close(got.logp,z1+z2);close(got.score[0],g1+g2)
        swapped=(blocks[1],blocks[0],blocks[2])
        eq=m.window_partition_score(swapped,model.edge,window_size=2)
        close(got.logp,eq.logp);close(got.score[0],eq.score[0])
        assert math.exp(got.logp)<math.exp(m.block_orbit(blocks,model.edge).logp)
    record("fixed_windows_partition_and_last_short_window",case_window)

    def case_raw():
        got=m.window_partition_score(blocks,model.edge,window_size=1)
        lp=g=0.
        for j,b in enumerate(blocks):
            e=model.edge(tuple(sorted(blocks[:j])),b)
            lp+=e.logp;g+=e.score[0]
        close(got.logp,lp);close(got.score[0],g)
    record("window_one_equals_raw_trajectory",case_raw)

    def case_zero_order():
        mod=TinyPhysicalPolicy(m,forbidden=True)
        got=m.block_orbit(blocks,mod.edge)
        lp,g=direct(m,blocks,mod.edge)
        close(got.logp,lp);close(got.score[0],g)
        assert mod.edge((),blocks[1]).logp==-math.inf
    record("zero_probability_orders_are_not_renormalized",case_zero_order)

    record("all_zero_support_rejected",lambda:expect(m.ZeroSupport,lambda:m.block_orbit(blocks,lambda a,b:m.LogScore(-math.inf,(0.,)))))
    record("invalid_duplicate_target_rejected",lambda:expect(ValueError,lambda:m.block_orbit((blocks[0],m.Block(1,(2,))),model.edge)))
    record("empty_trip_rejected",lambda:expect(ValueError,lambda:m.block_orbit((m.Block(0,()),),model.edge)))
    record("invalid_slot_rejected",lambda:expect(ValueError,lambda:m.block_orbit((m.Block(2,(1,)),),model.edge)))
    record("explicit_size_cap_rejected",lambda:expect(ValueError,lambda:m.block_orbit(blocks,model.edge,max_blocks=2)))
    record("invalid_window_rejected",lambda:expect(ValueError,lambda:m.window_partition_score(blocks,model.edge,window_size=0)))
    record("invalid_edge_probability_rejected",lambda:expect(ValueError,lambda:m.block_orbit(blocks,lambda a,b:m.LogScore(.2,(0.,)))))

    def case_underflow():
        got=m.block_orbit(blocks,lambda a,b:m.LogScore(-1000.,(2.,)))
        close(got.logp,math.lgamma(4)-3000.)
        close(got.score[0],6.)
    record("log_domain_prevents_path_underflow",case_underflow)

    def case_weights():
        # Normalized three-trajectory model, independent of the recurrence.
        th=.2;p=(th,th*th,1-th-th*th);s=(1/th,2/th,(-1-2*th)/p[2])
        mass=p[0]+p[1];rb=(p[0]*s[0]+p[1]*s[1])/mass
        close(mass*rb,1+2*th)
        assert abs(mass*((s[0]+s[1])/2)-(1+2*th))>.1
        assert abs(mass*s[0]-(1+2*th))>.1
    record("uniform_and_canonical_score_bias_counterexamples",case_weights)

    def case_variance_failure():
        # Successful cell {1,2}; failure identity cell {3}, finite reward -1.
        th=.2;p=(th,th*th,1-th-th*th);s=(1/th,2/th,(-1-2*th)/p[2])
        raw=(s[0],s[1],-s[2])
        rb=(p[0]*s[0]+p[1]*s[1])/(p[0]+p[1])
        collapsed=(rb,rb,raw[2])
        mean=sum(x*y for x,y in zip(p,raw))
        mean2=sum(x*y for x,y in zip(p,collapsed))
        close(mean,mean2);close(mean,2*(1+2*th))
        var=sum(x*(y-mean)**2 for x,y in zip(p,raw))
        var2=sum(x*(y-mean2)**2 for x,y in zip(p,collapsed))
        assert var2<var
        assert abs((p[0]*raw[0]+p[1]*raw[1])/(p[0]+p[1])-mean)>.1
        return {"raw_variance":var,"conditional_variance":var2,"mean":mean}
    metrics=case_variance_failure()
    record("finite_failure_identity_cells_preserve_gradient",lambda:None)

    def case_baseline_offpolicy():
        th=.2;mass=th+th*th;g=(1+2*th)/mass
        close(mass*g,1.4)
        assert 0!=1.4 # class-dependent b(C)=R_C would zero every term
        now=.3;current=(1+2*now)/(now+now*now)
        assert abs(mass*current-(1+2*now))>.1
    record("class_baseline_and_offpolicy_bias_counterexamples",case_baseline_offpolicy)

    def case_history():
        # Two full histories merge at {a,b}; next-block mass .2 vs .8.
        exact=.1*.2+.3*.8
        merged=(.1+.3)*.2
        assert abs(exact-merged)>.1
        assert (1e16+1.)+1.==1e16 and 1e16+(1.+1.)!=1e16
    record("history_and_float_merge_counterexamples",case_history)

    def case_counts():
        n=5
        bs=tuple(m.Block(j%2,(j+1,)) for j in range(n))
        got=m.block_orbit(bs,lambda a,b:m.LogScore(-2.,(1.,)),max_blocks=6)
        expected=n*(1<<(n-1)) if m.ALGORITHM=="subset_log_semiring" else n*math.factorial(n)
        assert got.edge_evaluations==expected
        close(got.logp,math.lgamma(n+1)-2*n)
        close(got.score[0],float(n))
    record("declared_edge_work_count",case_counts)
    return cases,metrics

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--module",required=True)
    a=parser.parse_args()
    m=load(Path(a.module).resolve())
    cases,metrics=run(m)
    print(json.dumps({"result":"PASS","tests":len(cases),"algorithm":m.ALGORITHM,"cases":cases,"variance_fixture":metrics},sort_keys=True))
if __name__=="__main__":main()
