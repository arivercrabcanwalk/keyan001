"""Explicit monotonic budget, per-call-site RNGs, counters and exact memoization."""
from collections import Counter
from functools import lru_cache
import time
from .java_random import JavaRandom
from .evaluator import evaluate

MASK=(1<<64)-1
def derive(seed,site,ordinal):
    h=0
    for c in site:h=(31*h+ord(c))&0xffffffff
    z=(seed^h^(((ordinal+1)*0x9e3779b97f4a7c15)&MASK))&MASK
    z=((z^(z>>30))*0xbf58476d1ce4e5b9)&MASK
    z=((z^(z>>27))*0x94d049bb133111eb)&MASK
    return (z^(z>>31))&MASK

class Sink:
    def __init__(self,factory,site,ordinal):self.factory=factory;self.site=site;self.ordinal=ordinal;self.count=0
    def append(self,row):
        self.count+=1;self.factory.calls+=1
        if self.factory.detail:self.factory.draws.append({'source':self.site,'instance':self.ordinal,'call':self.count,**row})
    def __len__(self):return self.count

class Streams:
    def __init__(self,seed,mode='split',detail=False):
        self.seed=seed;self.mode=mode;self.detail=detail;self.counts=Counter();self.calls=0;self.draws=[];self.created=[];self.persistent={}
    def create(self,site):
        if self.mode=='shared':
            if 'shared' not in self.persistent:
                rng=JavaRandom(self.seed);rng.draws=Sink(self,'shared',0);self.persistent['shared']=rng
            return self.persistent['shared']
        ordinal=self.counts[site];self.counts[site]+=1;seed=derive(self.seed,site,ordinal)
        rng=JavaRandom(seed);rng.draws=Sink(self,site,ordinal)
        if self.detail:self.created.append({'source':site,'instance':ordinal,'derived_seed_unsigned':str(seed),'creation':sum(self.counts.values())})
        return rng
    def math(self):
        if 'math' not in self.persistent:self.persistent['math']=self.create('Math.random')
        return self.persistent['math']

class AbsoluteBudget:
    def __init__(self,deadline_ns=None,reserve=.25):self.deadline_ns=deadline_ns;self.reserve_ns=int(reserve*1e9)
    def alive(self):return self.deadline_ns is None or time.monotonic_ns()<self.deadline_ns-self.reserve_ns
    def __gt__(self,unused):return self.alive()  # frozen v2/v3 elapsed < seconds adapter

class Runtime:
    def __init__(self,ins,cache=False):
        self.ins=ins;self.cache=cache;self.counts=Counter();self.timings=Counter();self._time=None;self._energy=None
    def setup(self,time_fn,energy_fn):
        def t(si,trip):self.counts['route_time_cache_misses']+=1;return time_fn(self.ins,si,list(trip))
        def e(si,trip,segment):self.counts['route_energy_cache_misses']+=1;return energy_fn(self.ins,si,list(trip),segment)
        self._time=lru_cache(maxsize=32768)(t);self._energy=lru_cache(maxsize=32768)(e)
    def path_time(self,si,trip):self.counts['route_time_api_calls']+=1;return self._time(si,tuple(trip))
    def path_energy(self,si,trip,segment):self.counts['route_energy_api_calls']+=1;return self._energy(si,tuple(trip),segment)

class Guard:
    """Cache independently recomputed station fragments, preserving visit checks."""
    def __init__(self,ins,cached=False):self.ins=ins;self.cached=cached;self.calls=0;self.hits=0;self.entries={}
    def valid(self,sol):
        self.calls+=1
        if not self.cached:return evaluate(self.ins,sol)['feasible']
        # Solver-owned shape/types are canonical. Reject foreign/malformed inputs
        # using the independent evaluator rather than indexing unchecked values.
        types=sol.get('station_types');routes=sol.get('routes')
        if not isinstance(types,list) or not isinstance(routes,list) or len(types)!=len(self.ins.stations) or len(routes)!=len(types):return evaluate(self.ins,sol)['feasible']
        if sol.get('instance_sha256',self.ins.sha256)!=self.ins.sha256:return False
        seen=Counter()
        try:
            for si,(kind,station) in enumerate(zip(types,routes)):
                if type(kind) is not int or kind not in (0,1,2) or len(station)!=2:return evaluate(self.ins,sol)['feasible']
                key=(si,kind,tuple(tuple(tuple(t) for t in d) for d in station))
                if key in self.entries:self.hits+=1;valid,visits=self.entries[key]
                else:
                    empty={'station_types':[0]*len(types),'routes':[[[],[]] for _ in types]}
                    empty['station_types'][si]=kind;empty['routes'][si]=station
                    audit=evaluate(self.ins,empty,allow_missing=True)
                    valid=audit['feasible'];visits=Counter(n for d in station for t in d for n in t)
                    if len(self.entries)>=32768:self.entries.clear()
                    self.entries[key]=(valid,visits)
                if not valid:return False
                seen.update(visits)
        except (TypeError,KeyError):return evaluate(self.ins,sol)['feasible']
        return all(seen[n]==1 for n in self.ins.target_ids) and all(n in self.ins.target_ids for n in seen)
