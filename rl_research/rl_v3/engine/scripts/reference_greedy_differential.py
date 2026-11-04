#!/usr/bin/env python3
from pathlib import Path
import sys,json,subprocess,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from lrphsd.problem import read_instance,normalized
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from lrphsd.exact import solve_exact
home=Path((ROOT/'.runtime/JAVA_HOME.txt').read_text().strip());files=sorted((ROOT/'external/LRPHSD/data/Instances_Alg').glob('*.txt'))
command=[str(home/'bin/java'),'-XX:ActiveProcessorCount=1','-XX:+UseSerialGC','-Xms32m','-Xmx512m','-cp',str(ROOT/'build/reference_classes'),'test1.GreedyProbe',*[str(p) for p in files]]
p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=60)
out=ROOT/'results/reference'
if (out/'greedy_differential.json').exists():
    out=out/('recheck_'+str(time.time_ns()));out.mkdir()
(out/'greedy_probe.stdout.log').write_text(p.stdout);(out/'greedy_probe.stderr.log').write_text(p.stderr)
assert p.returncode==0
java={};errors=[]
for line in p.stdout.splitlines():
    if line.startswith('REFERENCE_JSON='):
        name,data=line[len('REFERENCE_JSON='):].split('\t',1);java[name]=json.loads(data)
    elif line.startswith('REFERENCE_ERROR='):errors.append(line)
rows=[]
for path in files:
    ins=read_instance(path);own=build(ins);a=evaluate(ins,own);ref=java.get(path.name)
    row={'instance':ins.name,'input_sha256':ins.sha256,'independent_cost':a['cost'],'independent_feasible':a['feasible'],'reference_present':ref is not None}
    if ref:
        b=evaluate(ins,ref);row.update(reference_reported_cost=ref['reference_reported_cost'],reference_recomputed_cost=b['cost'],reference_feasible=b['feasible'] and not ref.get('reference_integrity_issues'),same_station_types=own['station_types']==ref['station_types'],same_routes=normalized(own)['routes']==normalized(ref)['routes'],objective_abs_error=abs(a['cost']-b['cost']),reference_integrity_issues=ref.get('reference_integrity_issues',[]))
    rows.append(row)
summary={'formal_instances':len(files),'reference_outputs':len(java),'reference_errors':errors,'same_types':sum(r.get('same_station_types',False) for r in rows),'same_routes':sum(r.get('same_routes',False) for r in rows),'objective_matched_1e7':sum(r.get('objective_abs_error',float('inf'))<1e-7 for r in rows),'independent_feasible':sum(r['independent_feasible'] for r in rows),'reference_feasible':sum(r.get('reference_feasible',False) for r in rows),'rows':rows}
(out/'greedy_differential.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='rows'},sort_keys=True),flush=True)
# Exact certifications use only the ten official n=10 cases, never toy data.
cert=[]
refs={r['instance']:r for r in json.loads((ROOT/'results/reference/published_reference.json').read_text())['rows']}
certdir=out/'exact_certificates';certdir.mkdir(exist_ok=True)
for path in files:
    if int(path.stem.split('_')[1])!=10:continue
    ins=read_instance(path);sol,meta=solve_exact(ins);audit=evaluate(ins,sol)
    assert audit['feasible'] and abs(audit['cost']-meta['optimal_objective'])<1e-7
    (certdir/f'{ins.name}.solution.json').write_text(json.dumps(sol,indent=2)+'\n')
    cert.append({'instance':ins.name,'input_sha256':ins.sha256,'exact_objective':audit['cost'],'published_gurobi_ub':refs[ins.name]['gurobi_ub'],'published_tsalns_best':refs[ins.name]['tsalns_best'],'published_ub_matches_at_precision':round(audit['cost'],2)==round(refs[ins.name]['gurobi_ub'],2),'feasible':audit['feasible'],'elapsed_seconds':meta['elapsed_seconds']})
(out/'exact_certificates.json').write_text(json.dumps({'method':'independent exact subset DP, not TSALNS','instances':cert},indent=2)+'\n')
print('EXACT_REAL_CERTIFICATES='+str(len(cert))+'; PUBLISHED_UB_MATCHES='+str(sum(r['published_ub_matches_at_precision'] for r in cert)),flush=True)
if not all(r.get('objective_abs_error',float('inf'))<1e-7 and r.get('same_routes') for r in rows):raise SystemExit(2)
