"""Diagnostic single-factor interventions; never part of the default solver."""
import copy,inspect
from . import fidelity_ops_v4 as ops
def configure(name):
    if name=='py_deepcopy':ops.clone=copy.deepcopy
    if name=='py_local_first':
        source=inspect.getsource(ops.local_candidate);lines=[]
        for line in source.splitlines(True):
            lines.append(line)
            if 'trip[a:b+1]=reversed' in line:
                n=len(line)-len(line.lstrip());lines.extend([' '*n+'break\n',' '*(n-8)+'if improved:break\n'])
        exec(compile(''.join(lines),'<isolated-first-improvement>','exec'),ops.__dict__)
    if name=='py_repair_score':
        source=inspect.getsource(ops.repair_candidate).replace('score=(limit-after)/limit','score=.6*(limit-after)/limit+.4/(1+abs(single_time*ins.params.time_cost))')
        exec(compile(source,'<isolated-new-route-score>','exec'),ops.__dict__)
    if name=='py_empty_slots':
        source=inspect.getsource(ops.covered_drones).replace("        if not any(sol['routes'][si]):continue\n",'')
        exec(compile(source,'<isolated-empty-storage-semantics>','exec'),ops.__dict__)
