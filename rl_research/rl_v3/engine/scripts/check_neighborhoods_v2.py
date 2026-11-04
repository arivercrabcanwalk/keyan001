import sys,random,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lrphsd.problem import read_instance, normalized
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from lrphsd import fidelity_ops_v5 as ops
from carl.kernel import CAEngine
from carl.core import Coverage,Mirror,fixed_cost
from carl.neighborhood import Context,generate,apply_move
counts=[0]*4; changes=[0]*4; failures=[];attempts=0
for path in sorted((ROOT/'external/LRPHSD/data/Instances_Alg').glob('*.txt')):
 ins=read_instance(path);ops.prepare(ins);eng=CAEngine(ins);sol=build(ins);eng.load(0,sol);cov=Coverage(ins);rng=random.Random(83)
 for step in range(120):
  ctx=Context(ins,eng,Mirror(ins,sol),cov,rng);f=step%4;mv=generate(ctx,f,step%3);attempts+=1
  if mv is None:continue
  new=apply_move(eng,mv,sol['station_types'],ins)
  if new is None:continue
  out=eng.export(1);a=evaluate(ins,out)
  assert a['feasible'],(path.name,mv.tag,a['issues'])
  assert abs(a['cost']-(eng.cost(1)+fixed_cost(ins,new)))<1e-7
  counts[f]+=1;changes[f]+=out['routes']!=sol['routes'] or out['station_types']!=sol['station_types']
  if not mv.full_rebuild and mv.classic is None:
   touched={si for si,k in mv.kinds}
   touched.update(ctx.mirror.pos[n][0] for n in mv.ids)
   touched.update(si for si in range(ctx.nst) if (mv.station_mask>>si)&1 or (mv.polish>0 and (mv.polish>>si)&1))
   if mv.two_opt:touched.add(mv.two_opt[0])
   for st in mv.stages:touched.update(si for si in range(ctx.nst) if (st[1]>>si)&1)
   for si in range(ctx.nst):
    if si not in touched:assert normalized(out)['routes'][si]==normalized(sol)['routes'][si] and new[si]==sol['station_types'][si],(path.name,mv.tag,si,out["routes"][si],sol["routes"][si],mv)
  if rng.random()<.35:eng.clone(1,0);sol=out
 eng.free()
assert all(n>0 for n in changes)
print(json.dumps(dict(attempts=attempts,feasible_by_family=counts,changed_by_family=changes,failures=failures)))
