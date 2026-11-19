#!/usr/bin/env python3
"""Read archived identities only; no project imports/evaluator/solver execution."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import gzip, hashlib, json, math, sys, time

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'route_rl_research/20261103'
SNAP = BASE / 'source_snapshot'
EVAL = SNAP / 'results/route_rl_stageA/eval_seed23_3solver_6_12'
DATA = ROOT / 'completion/code/external/LRPHSD<EXECUTION_PATH>'
OUT = BASE / 'failure'
START = time.perf_counter()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def semantic_sha(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text())

retrieval = load(SNAP / 'RETRIEVAL_MANIFEST.json')
freeze = load(SNAP / 'ROUTE_RL_STAGEA_FREEZE_20261102.json')
run = load(EVAL / 'run_manifest.json')
summary = load(EVAL / 'summary.json')
maps = freeze['data_split']['validation_maps']
issues = []
file_records = {}

def record(path):
    path = Path(path)
    rel = str(path.relative_to(SNAP)) if path.is_relative_to(SNAP) else None
    rr = retrieval.get(rel) if rel is not None else None
    got = {'path': str(path.resolve()), 'exists': path.is_file()}
    if not got['exists']:
        got.update(status='MISSING', sha256=None)
    else:
        got.update(bytes=path.stat().st_size, sha256=sha(path))
        if rel is not None:
            got['retrieval_manifest_sha256'] = rr.get('sha256') if isinstance(rr, dict) else None
            got['matches_retrieval_manifest'] = bool(isinstance(rr,dict) and rr.get('sha256')==got['sha256'] and rr.get('bytes')==got['bytes'])
            got['status'] = 'HASH_MATCH' if got['matches_retrieval_manifest'] else 'RETRIEVAL_HASH_UNVERIFIED'
        else:
            got['status'] = 'HASH_READ'
    file_records[str(path.resolve())] = got
    return got

for p in (SNAP/'RETRIEVAL_MANIFEST.json', SNAP/'ROUTE_RL_STAGEA_FREEZE_20261102.json', SNAP/'ROUTE_RL_STAGEA_SOURCE_MANIFEST_20261102.json', EVAL/'run_manifest.json', EVAL/'summary.json', SNAP/'ROUTE_RL_STAGEA_FINAL_AUDIT_20261102.md', ROOT/'stage_a_audit/VERIFICATION.txt', Path(__file__)):
    record(p)

source_files = sorted((SNAP/'route_rl').glob('*.py')) + [SNAP/'lrphsd'/x for x in ('problem.py','greedy.py','evaluator.py')]
source_digest = hashlib.sha256(''.join(sha(p) for p in source_files).encode()).hexdigest()
source_record = {'computed_digest':source_digest, 'run_manifest_digest':run.get('source_sha256'), 'freeze_training_digest':freeze.get('training_code_sha256'), 'summary_digest':summary.get('source_sha256'), 'matches':source_digest==run.get('source_sha256')==freeze.get('training_code_sha256')==summary.get('source_sha256'), 'files':[]}
for name, expected in freeze['source_file_hashes'].items():
    rec = record(SNAP/name)
    source_record['files'].append({'relative_path':name,'sha256':rec.get('sha256'),'frozen_sha256':expected,'matches':rec.get('sha256')==expected})
if not source_record['matches'] or not all(r['matches'] for r in source_record['files']):
    issues.append({'issue':'source_identity_mismatch'})
if run.get('maps') != maps:
    issues.append({'issue':'run_maps_do_not_match_validation_freeze'})
if run.get('solver_seeds') != [101,102,103] or run.get('budgets_seconds') != [6.0,12.0] or 'route_alns' not in run.get('methods',[]):
    issues.append({'issue':'run_matrix_mismatch'})


def view_solution(sol, target_ids, station_ids):
    errors = []
    types = sol.get('station_types')
    routes = sol.get('routes')
    station_targets, slot_targets, seen = [], [], []
    if not isinstance(types,list) or len(types)!=len(station_ids) or not isinstance(routes,list) or len(routes)!=len(station_ids):
        return {'errors':['station_dimension'], 'station_types':types, 'station_targets':None, 'slot_targets':None}
    for si,(kind,slots) in enumerate(zip(types,routes)):
        if type(kind) is not int or kind not in (0,1,2): errors.append('station_type:'+str(si))
        if not isinstance(slots,list) or len(slots)!=2:
            errors.append('slot_dimension:'+str(si)); station_targets.append([]);slot_targets.append([]);continue
        station_seen, st_slots = [], []
        for di,trips in enumerate(slots):
            slot_seen = []
            if not isinstance(trips,list): errors.append('trip_dimension:'+str(si)+':'+str(di));trips=[]
            for ti,trip in enumerate(trips):
                if not isinstance(trip,list):errors.append('trip_format:'+str(si)+':'+str(di)+':'+str(ti));continue
                if trip and (kind==0 or (kind==1 and di==0)):errors.append('ineligible_slot:'+str(si)+':'+str(di))
                for nid in trip:
                    if type(nid) is not int or nid not in target_ids: errors.append('invalid_target:'+str(nid))
                    slot_seen.append(nid)
            st_slots.append(sorted(slot_seen));station_seen+=slot_seen
        station_targets.append(sorted(station_seen));slot_targets.append(st_slots);seen+=station_seen
    if Counter(seen)!=Counter(target_ids): errors.append('not_exactly_once_target_cover')
    return {'errors':errors, 'station_types':types, 'station_targets':station_targets, 'slot_targets':slot_targets, 'target_count':len(seen), 'station_ids':station_ids}

parents, rows, input_rows = [], [], []
for name, expected in sorted(maps.items()):
    ip=DATA/(name+'.txt');ir=record(ip);input_errors=[]
    if ir.get('sha256')!=expected:input_errors.append('instance_hash_mismatch')
    targets, station_ids = [], []
    if ip.is_file():
        for line in ip.read_text(encoding='utf-8-sig').splitlines()[1:]:
            if not line.strip():continue
            node,x,y,energy,service=map(float,line.split())
            (targets if energy>0 else station_ids).append(int(node))
    input_rows.append({'map':name,'input_path':str(ip.resolve()),'input_sha256':ir.get('sha256'),'frozen_sha256':expected,'target_ids':targets,'station_ids':station_ids,'issues':input_errors})
    canonical = None;canonical_meta = None;greedy_semantics=set();greedy_domains=set();greedy_costs=set();greedy_hash_rows=[]
    for budget in (6,12):
        for seed in (101,102,103):
            result={'map':name,'solver_seed':seed,'budget_seconds':budget,'method':'route_alns','expected_input_sha256':expected,'issues':list(input_errors)}
            objs={}
            for method in ('route_alns','greedy'):
                stem=f'{name}__{method}__s{seed}__b{budget}'
                mp=EVAL/(stem+'.json');sp=EVAL/(stem+'.solution.json.gz')
                mr=record(mp);sr=record(sp)
                item={'meta_path':str(mp.resolve()),'meta_sha256':mr.get('sha256'),'solution_path':str(sp.resolve()),'solution_file_sha256':sr.get('sha256'),'meta_archive_hash_matches':mr.get('matches_retrieval_manifest'),'solution_archive_hash_matches':sr.get('matches_retrieval_manifest')}
                if not mr['exists'] or not sr['exists']:
                    result['issues'].append(method+':missing_artifact');result[method]=item;continue
                if not mr.get('matches_retrieval_manifest') or not sr.get('matches_retrieval_manifest'):result['issues'].append(method+':retrieval_hash_mismatch')
                try:
                    meta=load(mp);sol=json.loads(gzip.decompress(sp.read_bytes()));view=view_solution(sol,targets,station_ids)
                except Exception as exc:
                    result['issues'].append(method+':parse_error:'+type(exc).__name__);result[method]=item;continue
                for key,ev in [('instance',name),('instance_sha256',expected),('method',method),('solver_seed',seed),('budget_seconds',float(budget)),('task_identity',f'{name}|{method}|s{seed}|b{budget}')]:
                    if meta.get(key)!=ev:result['issues'].append(method+':meta_identity:'+key)
                if sol.get('instance')!=name or sol.get('instance_sha256')!=expected:result['issues'].append(method+':solution_input_identity')
                if sol.get('schema_version')!=1:result['issues'].append(method+':solution_schema')
                if meta.get('solution_sha256')!=sr['sha256']:result['issues'].append(method+':meta_solution_hash_mismatch')
                if meta.get('status')!='ok' or meta.get('feasible') is not True or meta.get('missing')!=0 or meta.get('visited')!=len(targets):result['issues'].append(method+':stored_result_failure')
                audit=meta.get('audit',{})
                if audit.get('feasible') is not True or audit.get('issues')!=[] or audit.get('missing')!=0 or audit.get('visited')!=len(targets):result['issues'].append(method+':stored_audit_failure')
                if audit.get('cost')!=meta.get('final_cost') or audit.get('operating_minutes')!=meta.get('final_operating_minutes'):result['issues'].append(method+':stored_cost_inconsistency')
                if not isinstance(meta.get('final_cost'),(float,int)) or not math.isfinite(meta['final_cost']):result['issues'].append(method+':nonfinite_cost')
                for err in view['errors']:result['issues'].append(method+':structure:'+err)
                item.update({'solution_semantic_sha256':semantic_sha(sol),'stored_independent_audit_feasible':audit.get('feasible'),'stored_audit_issues':audit.get('issues'),'initial_cost':meta.get('initial_cost'),'final_cost':meta.get('final_cost'),'fixed_cost':audit.get('fixed_cost'),'operating_minutes':audit.get('operating_minutes'),'station_types':view['station_types'],'station_targets':view['station_targets'],'slot_targets':view['slot_targets'],'visited':meta.get('visited'),'search_seconds':meta.get('search_seconds'),'end_to_end_seconds':meta.get('end_to_end_seconds'),'model_load_seconds_global_field':meta.get('model_load_seconds'),'empty_trip_count':sum(not trip for slots in sol['routes'] for trips in slots for trip in trips),'recorded_source_identity_kind':'RUN_MANIFEST_SHARED_NOT_PER_RESULT_FIELD'})
                result[method]=item;objs[method]=(meta,sol,view)
            if 'greedy' in objs:
                gm,gs,gv=objs['greedy'];greedy_semantics.add(semantic_sha(gs));greedy_domains.add(semantic_sha({'types':gv['station_types'],'station':gv['station_targets'],'slot':gv['slot_targets']}));greedy_costs.add(gm['final_cost']);greedy_hash_rows.append({'budget':budget,'seed':seed,'meta_path':result['greedy']['meta_path'],'solution_path':result['greedy']['solution_path'],'solution_sha256':result['greedy']['solution_file_sha256']})
                if canonical is None:canonical=gs;canonical_meta=gm
            if len(objs)==2:
                am,asol,av=objs['route_alns'];gm,gsol,gv=objs['greedy']
                result['same_station_types_as_saved_greedy']=av['station_types']==gv['station_types']
                result['same_target_station_ownership_as_saved_greedy']=av['station_targets']==gv['station_targets']
                result['same_target_slot_ownership_as_saved_greedy']=av['slot_targets']==gv['slot_targets']
                result['initial_cost_matches_saved_greedy']=am['initial_cost']==gm['final_cost']
                for key in ('same_station_types_as_saved_greedy','same_target_station_ownership_as_saved_greedy','same_target_slot_ownership_as_saved_greedy','initial_cost_matches_saved_greedy'):
                    if not result[key]:result['issues'].append(key+':false')
                result['raw_greedy_minus_alns_cost']=gm['final_cost']-am['final_cost']
            result['status']='VERIFIED_ARCHIVED_IDENTITY_AND_FIXED_OWNER_DOMAIN' if not result['issues'] else 'UNRESOLVED_IDENTITY_OR_DOMAIN'
            rows.append(result)
    parent={'map':name,'input_sha256':expected,'greedy_semantic_solution_count_across_six_cells':len(greedy_semantics),'greedy_domain_count_across_six_cells':len(greedy_domains),'greedy_cost_count_across_six_cells':len(greedy_costs),'saved_cells':greedy_hash_rows,'issues':[]}
    if canonical is not None:
        parent.update({'canonical_solution':canonical,'canonical_solution_semantic_sha256':semantic_sha(canonical),'stored_greedy_cost':canonical_meta['final_cost'],'station_targets':view_solution(canonical,targets,station_ids)['station_targets'],'slot_targets':view_solution(canonical,targets,station_ids)['slot_targets']})
    if len(greedy_hash_rows)!=6 or len(greedy_semantics)!=1 or len(greedy_domains)!=1 or len(greedy_costs)!=1:parent['issues'].append('greedy_parent_not_identical_across_six_cells')
    parents.append(parent)

expected_stems={f'{name}__route_alns__s{seed}__b{b}' for name in maps for b in (6,12) for seed in (101,102,103)}
actual_meta={p.name[:-5] for p in EVAL.glob('*__route_alns__*.json')}
actual_sol={p.name[:-len('.solution.json.gz')] for p in EVAL.glob('*__route_alns__*.solution.json.gz')}
matrix={'expected':144,'meta_count':len(actual_meta),'solution_count':len(actual_sol),'missing_meta':sorted(expected_stems-actual_meta),'extra_meta':sorted(actual_meta-expected_stems),'missing_solution':sorted(expected_stems-actual_sol),'extra_solution':sorted(actual_sol-expected_stems)}
if any(matrix[k] for k in ('missing_meta','extra_meta','missing_solution','extra_solution')):issues.append({'issue':'artifact_matrix_difference','details':matrix})
for pr in parents:
    if pr['issues']:issues.append({'map':pr['map'],'issue':'parent_inconsistency','details':pr['issues']})
for row in rows:
    if row['issues']:issues.append({'map':row['map'],'budget':row['budget_seconds'],'seed':row['solver_seed'],'details':row['issues']})
status='PASS_ARCHIVED_IDENTITY_FIXED_OWNER_DOMAIN' if not issues else 'UNRESOLVED_IDENTITIES_RETAINED'
report={'schema':'g2_archived_alns_identity_reuse_v1','created_utc':datetime.now(timezone.utc).isoformat(),'status':status,'scope':'read-only identity/hash/schema/domain audit; no fresh evaluator/solver execution','source':source_record,'matrix':matrix,'maps':len(maps),'verified_rows':sum(not r['issues'] for r in rows),'issues':issues,'new_project_code_imports':0,'new_solver_calls':0,'new_evaluator_calls':0,'new_training_calls':0,'new_quality_matrix_calls':0,'server_connections':0,'input_records':input_rows,'parents':parents,'rows':rows,'files':file_records,'analysis_wall_seconds':time.perf_counter()-START,'historical_feasibility_only':True,'fresh_physical_feasibility_not_recomputed':True,'comparison_role':'historical strongest saved route-only baseline anchor, fixed target-to-slot domain; not fair-budget performance of a new method','certified_optimality':False}
out=OUT/'G2_ALNS_REUSE_MANIFEST.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
parent=OUT/'G2_ALNS_GREEDY_PARENTS.json';parent.write_text(json.dumps({'schema':'g2_saved_greedy_parents_v1','source_manifest_path':str(out.resolve()),'source_manifest_sha256':sha(out),'maps':parents},ensure_ascii=False,indent=2)+'\n')
lines=['# G2 archived route-only ALNS reuse audit','',f'UTC: {report["created_utc"]}. Status: **{status}**.','', 'This is a read-only identity/structure audit of already saved Stage-A results. It imports no project code and runs no evaluator, solver, DP, training or quality matrix. Physical feasibility/cost fields are historical records, not freshly recomputed.', '', '## Verified scope',f'- Expected: 24 validation maps × 2 budgets (6/12s) × 3 solver seeds (101/102/103) = 144 route_alns cells; present metadata {matrix["meta_count"]}, gzip complete solutions {matrix["solution_count"]}; verified rows {report["verified_rows"]}.',f'- Matching frozen instance bytes, archived file SHA256, result identities, compressed solution SHA256, JSON schema, once-only target coverage, station type and both station/slot target ownership are checked per cell. Source digest reconstructed as {source_digest}.', '- Every saved Greedy companion is checked; per-map six-cell solution/domain/cost identity is retained. Canonical complete Greedy parents are saved separately for root to compare against any newly reconstructed parent. This audit does not execute Greedy.', '- Global run-manifest source identity is shared by the results. Individual result JSON lacks an independent per-result source field; this linkage is recorded rather than invented.', '- All per-cell paths/hashes, full station types/target memberships, stored costs, runtime fields and missing/mismatch issues are retained in the manifest. No best-of-seed selection is made.', '', '## Interpretation', '- These ALNS solutions are fixed target-to-slot as well as fixed target-to-station baselines. They are usable archived anchors within the same frozen outer domain after this identity audit, but a new joint-slot DP candidate includes expanded decisions.', '- Greedy-to-joint DP improvement combines route reorder/repack and slot reassignment. Fixed-owner reference-to-joint separates the slot effect only when both have full witnesses and status; an archived ALNS-to-joint difference is historical opportunity, not a new 6s/12s fair-budget method result.', '- No rigorous lower bound or headroom upper bound is supplied. No RL superiority, novelty, new development or Formal claim is made. Current root-owned G2 implementation/experiments are not covered by this audit.', '', '## Existing independent evaluator evidence', '- The archived meta contains audit.feasible=true, empty issues and full cost/details for each accepted row. stage_a_audit/VERIFICATION.txt records the earlier 720/720 independent evaluator audit command/results. This run only verifies preserved bytes/identities and structural ownership; it does not re-score energy/duty/geometry.', '', '## Reproduction command', 'python3 <LOCAL_PATH>', '', '## Outputs', str(out.resolve()), str(parent.resolve()), '', '## Issues', json.dumps(issues,ensure_ascii=False,indent=2)]
md=OUT/'G2_ALNS_REUSE_AUDIT.md';md.write_text('\n'.join(lines)+'\n')
print('ALNS_REUSE',status,'rows',len(rows),'verified',report['verified_rows'],'missing_meta',len(matrix['missing_meta']),'missing_solution',len(matrix['missing_solution']),'issues',len(issues))
print('SOURCE',source_digest,'match',source_record['matches'])
print('GREEDY_PARENTS',len(parents),'all_six_cell_identical',all(not p['issues'] for p in parents))
print('PROJECT_IMPORTS 0 SOLVER 0 EVALUATOR 0 TRAINING 0 QUALITY 0 SERVER_CONNECTIONS 0')
for p in (out,parent,md):
    b=p.read_bytes();print('OUTPUT',str(p.resolve()),hashlib.sha256(b).hexdigest(),'bytes',len(b))
raise SystemExit(0 if not issues else 2)
