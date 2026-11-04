"""Generate held-out maps with a constructive feasibility witness; not Liu data."""
import sys,json,random,math,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from lrphsd.problem import read_instance,empty_solution
from lrphsd.evaluator import evaluate
out=R/'datasets/locked_v2'
if out.exists():raise SystemExit('locked suite exists; preserve it')
out.mkdir(parents=True)
rows=[]
for ns,nt in ((8,50),(16,100),(24,200),(32,300)):
 for distribution in ('uniform','clustered','boundary'):
  for seed in (701,702,703,704,705):
   rng=random.Random(ns*100000+nt*100+seed+10000000*('uniform','clustered','boundary').index(distribution))
   stations=[((i%math.ceil(math.sqrt(ns)))*6500,(i//math.ceil(math.sqrt(ns)))*6500) for i in range(ns)]
   targets=[];owners=[]
   for j in range(nt):
    si=j%ns;x,y=stations[si];theta=rng.uniform(0,2*math.pi)
    radius=3000*math.sqrt(rng.random()) if distribution=='uniform' else (rng.uniform(200,900) if distribution=='clustered' else rng.uniform(3500,3900))
    targets.append((x+radius*math.cos(theta),y+radius*math.sin(theta)));owners.append(si)
   name=f'{ns}_{nt}_{distribution}_{seed}';p=out/(name+'.txt')
   lines=['CUST_NO XCOORD YCOORD ENERGY SERVICE']
   lines += [f'{j+1} {x:.6f} {y:.6f} 0.2 10' for j,(x,y) in enumerate(targets)]
   lines += [f'{nt+i+1} {x} {y} 0 0' for i,(x,y) in enumerate(stations)]
   p.write_text('\n'.join(lines)+'\n');ins=read_instance(p);sol=empty_solution(ins,[2]*ns)
   for j,si in enumerate(owners):sol['routes'][si][(j//ns)%2].append([j+1])
   a=evaluate(ins,sol);assert a['feasible'],a['issues']
   (out/(name+'.witness.json')).write_text(json.dumps(sol))
   rows.append(dict(name=name,sha256=ins.sha256,stations=ns,targets=nt,distribution=distribution,seed=seed,witness_cost=a['cost']))
manifest=dict(protocol='held-out-v2-generated-not-paper',rows=rows,selection='all 60 maps; no result-dependent exclusion',caveat='constructive generator, limited distribution family; not real-world evidence')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('LOCKED',len(rows),'feasible maps')
