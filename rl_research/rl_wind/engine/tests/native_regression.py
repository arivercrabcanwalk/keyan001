import sys, random
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from carl.kernel import CAEngine
from carl.neighborhood import Move,apply_move
ins=read_instance(root/'external/LRPHSD/data/Instances_Alg/5_35_1.txt')
eng=CAEngine(ins);sol=build(ins);eng.load(0,sol)
original_destroy=eng.destroy;original_repair=eng.repair_scoped
calls=[];repairs=[]
def destroy(src,dst,op,seed):
 out=original_destroy(src,dst,op,seed);calls.append((src,dst,len(out[0])));return out
def repair(*args):repairs.append(1);return original_repair(*args)
eng.destroy=destroy;eng.repair_scoped=repair
fails=0
for mode in ('classic','rebuild'):
 calls.clear();repairs.clear()
 mv=Move(2,2,classic=(0,0),seed=11,alns_iters=40) if mode=='classic' else Move(0,2,full_rebuild=True,seed=11,alns_iters=40)
 kinds=apply_move(eng,mv,sol['station_types'],ins)
 ok=kinds is not None and len(repairs)>0 and all(a!=b for a,b,n in calls) and evaluate(ins,eng.export(1))['feasible']
 print(('PASS' if ok else 'FAIL'),mode,'destroy_calls='+str(len(calls)),'nonempty='+str(sum(n>0 for a,b,n in calls)),'repair_calls='+str(len(repairs)))
 fails+=not ok
eng.free();sys.exit(bool(fails))
