#!/usr/bin/env python3
"""One-shot exposed-map station-DP opportunity diagnostic, not a quality test."""
from __future__ import annotations
import argparse
import collections
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import sys
import time
import traceback
import tracemalloc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SNAPSHOT = HERE.parent / 'source_snapshot'
FREEZE = SNAPSHOT / 'ROUTE_RL_STAGEA_FREEZE_20261102.json'
ARCHIVE = SNAPSHOT / 'results/route_rl_stageA/eval_seed23_3solver_6_12'
INSTANCE_DIR = ROOT / 'completion/code/external/LRPHSD/data/Instances_Alg'
CONFIG = dict(station_union_max_targets=12, max_transition_checks=2_000_000,
              max_state_cells=180_000, map_scheduling_seconds=12.0,
              batch_scheduling_seconds=360.0, feasibility_eps=1e-7,
              cost_reconciliation_abs=1e-8, parent_regression_abs=1e-8,
              order='lexicographic_map/input_station/fixed_then_joint',
              archive_budgets=[6, 12], archive_seeds=[101, 102, 103])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def write(path, value):
    path = Path(path)
    payload = json.dumps(value, indent=2, allow_nan=False) + '\n'
    with path.open('w') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def domain(solution, by_slot=False):
    if by_slot:
        return [[sorted(n for trip in trips for n in trip) for trips in station]
                for station in solution['routes']]
    return [sorted(n for trips in station for trip in trips for n in trip)
            for station in solution['routes']]


def pct(before, after):
    return (before - after) / before * 100.0


def metadata():
    start = time.perf_counter()
    freeze = read(FREEZE)
    retrieval = read(SNAPSHOT / 'RETRIEVAL_MANIFEST.json')
    sources = {}
    for rel, expected in freeze['source_file_hashes'].items():
        actual = sha(SNAPSHOT / rel)
        if actual != expected:
            raise RuntimeError('frozen source mismatch: ' + rel)
        sources[str(SNAPSHOT / rel)] = actual
    maps = []
    files = [HERE / 'station_split_dp.py', HERE / 'test_station_dp.py',
             HERE / 'run_station_g2.py', HERE / 'G2_STATION_SPLIT_DP_PROTOCOL.md',
             HERE / 'g2_transaction/UNIT_TESTS.json', FREEZE,
             HERE / 'test_g2_driver.py', HERE / 'g2_transaction/DRIVER_TESTS.json',
             HERE.parent / 'failure/G2_ALNS_REUSE_MANIFEST.json',
             HERE.parent / 'failure/G2_ALNS_GREEDY_PARENTS.json']
    archive_files = {}
    for name, expected in sorted(freeze['data_split']['validation_maps'].items()):
        path = INSTANCE_DIR / (name + '.txt')
        actual = sha(path)
        if actual != expected:
            raise RuntimeError('input hash mismatch: ' + name)
        maps.append(dict(name=name, path=str(path), sha256=actual))
        for budget in CONFIG['archive_budgets']:
            for seed in CONFIG['archive_seeds']:
                stem = f'{name}__route_alns__s{seed}__b{budget}'
                for ext in ('.json', '.solution.json.gz'):
                    f = ARCHIVE / (stem + ext)
                    rel = str(f.relative_to(SNAPSHOT))
                    actual_f = sha(f)
                    if actual_f != retrieval[rel]['sha256']:
                        raise RuntimeError('archive hash mismatch: ' + rel)
                    archive_files[str(f)] = actual_f
    reuse = read(HERE.parent / 'failure/G2_ALNS_REUSE_MANIFEST.json')
    if reuse['issues'] or reuse['verified_rows'] != 144 or not reuse['source']['matches']:
        raise RuntimeError('archived identity audit incomplete')
    tests = read(HERE / 'g2_transaction/UNIT_TESTS.json')
    if tests['latest_exit_status'] != 0:
        raise RuntimeError('unit tests did not pass')
    for path in (HERE/'station_split_dp.py', HERE/'test_station_dp.py', SNAPSHOT/'lrphsd/evaluator.py'):
        if tests['attempts'][-1]['source_sha256_after'][str(path)] != sha(path):
            raise RuntimeError('unit test identity is stale '+str(path))
    return dict(schema='station_g2_metadata_only_v2', created_utc=datetime.now(timezone.utc).isoformat(),
                config=CONFIG, maps=maps, source_hashes=sources,
                files={str(f): sha(f) for f in files}, archive_hashes=archive_files,
                elapsed_seconds=time.perf_counter()-start,
                imports_of_project_code=0, greedy_calls=0, dp_calls=0, evaluator_calls=0)


def validate_reference(ins, parent, parent_audit, si, result, evaluate, fixed):
    record = result.as_dict()
    record['integration_accepted'] = False
    if not result.status.startswith('COMPLETE_'):
        return record
    candidate = copy.deepcopy(parent)
    candidate['routes'][si] = result.routes
    audit = evaluate(ins, candidate)
    result.raw_full_trial_audit = audit
    record['complete_trial_audit'] = audit
    old_minutes = sum(x['time_min'] for x in parent_audit['details'] if x['station'] == si)
    expected_cost = parent_audit['cost'] + (result.operating_minutes_dp - old_minutes)*ins.params.time_cost
    valid_cost = isinstance(audit.get('cost'), (int,float)) and math.isfinite(audit['cost'])
    residual = audit['cost'] - expected_cost if valid_cost else None
    regression = audit['cost'] - parent_audit['cost'] if valid_cost else None
    violations = []
    if candidate['station_types'] != parent['station_types']: violations.append('station_type_changed')
    if domain(candidate) != domain(parent): violations.append('station_union_changed')
    if fixed and domain(candidate, True) != domain(parent, True): violations.append('fixed_owner_changed')
    if not audit['feasible']: violations.append('independent_evaluator_rejected')
    if not valid_cost: violations.append('nonfinite_or_missing_evaluator_cost')
    elif abs(residual) > CONFIG['cost_reconciliation_abs']: violations.append('dp_evaluator_residual')
    if regression is not None and regression > CONFIG['parent_regression_abs']: violations.append('parent_cost_regression')
    record.update(raw_dp_status=result.status, complete_trial_audit=audit,
                  dp_predicted_complete_cost=expected_cost,
                  complete_cost_dp_evaluator_residual=residual,
                  complete_cost_candidate_minus_parent=regression,
                  station_evaluator_minutes=sum(x['time_min'] for x in audit.get('details',[]) if x['station']==si),
                  coverage_slack_min=(min((ins.radius(result.station_type) - math.hypot(ins.nodes[n].x-ins.stations[si].x,ins.nodes[n].y-ins.stations[si].y) for n in result.target_ids),default=None)),
                  validation_violations=violations)
    if violations:
        record['status'] = 'NUMERICAL_OR_IMPLEMENTATION_UNRESOLVED'
    else:
        record['integration_accepted'] = True
    return record


def archived_comparators(ins, parent, joint_audit, evaluate):
    rows = []
    for budget in CONFIG['archive_budgets']:
        for seed in CONFIG['archive_seeds']:
            stem = f'{ins.name}__route_alns__s{seed}__b{budget}'
            mp, sp = ARCHIVE/(stem+'.json'), ARCHIVE/(stem+'.solution.json.gz')
            row = dict(budget=budget, seed=seed, meta_path=str(mp), solution_path=str(sp))
            meta=solution=None
            try:
                row.update(meta_sha256=sha(mp), solution_sha256=sha(sp))
                meta, solution = read(mp), read(sp)
                audit = evaluate(ins, solution)
                row['independent_audit'] = audit
                issues=[]
                for key, expected in [('instance',ins.name),('instance_sha256',ins.sha256),
                                      ('method','route_alns'),('solver_seed',seed),('budget_seconds',float(budget)),
                                      ('solution_sha256',row['solution_sha256'])]:
                    if meta.get(key)!=expected: issues.append('identity_'+key)
                if meta.get('status')!='ok': issues.append('stored_status')
                if meta.get('task_identity')!=f'{ins.name}|route_alns|s{seed}|b{budget}': issues.append('task_identity')
                if solution.get('instance')!=ins.name or solution.get('instance_sha256')!=ins.sha256: issues.append('solution_identity')
                if solution.get('schema_version')!=1: issues.append('solution_schema')
                if solution['station_types']!=parent['station_types']: issues.append('station_types')
                if domain(solution)!=domain(parent): issues.append('station_unions')
                if domain(solution,True)!=domain(parent,True): issues.append('fixed_owners')
                if not audit['feasible']: issues.append('evaluator_feasibility')
                if abs(audit['cost']-meta['final_cost'])>CONFIG['cost_reconciliation_abs']: issues.append('saved_cost_residual')
                row.update(status='VALID_ARCHIVED_FIXED_OWNER_ANCHOR' if not issues else 'ARCHIVE_UNRESOLVED',
                           issues=issues, independent_audit=audit, saved_cost=meta['final_cost'],
                           cost_residual=audit['cost']-meta['final_cost'],
                           historical_end_to_end_seconds=meta.get('end_to_end_seconds'),
                           historical_search_seconds=meta.get('search_seconds'),
                           historical_model_load_seconds=meta.get('model_load_seconds'),
                           joint_candidate_gain_pct=pct(audit['cost'],joint_audit['cost']))
                if issues:
                    row['archived_meta'] = meta
                    row['archived_solution'] = solution
            except Exception as exc:
                row.update(status='ARCHIVE_UNRESOLVED', issues=[type(exc).__name__+': '+str(exc)], traceback=traceback.format_exc())
                row['archived_meta']=meta
                row['archived_solution']=solution
            rows.append(row)
    best={}
    for budget in CONFIG['archive_budgets']:
        cells=[r for r in rows if r['budget']==budget]
        if len(cells)==3 and all(r['status']=='VALID_ARCHIVED_FIXED_OWNER_ANCHOR' for r in cells):
            selected=min(cells,key=lambda r:r['independent_audit']['cost'])
            best[str(budget)] = dict(status='THREE_ARCHIVED_RUNS_NOT_SINGLE_BUDGET',
                                    cost=selected['independent_audit']['cost'], seed=selected['seed'],
                                    joint_candidate_gain_pct=selected['joint_candidate_gain_pct'],
                                    sum_historical_end_to_end_seconds=sum(r['historical_end_to_end_seconds'] for r in cells))
        else: best[str(budget)] = dict(status='ARCHIVE_UNRESOLVED')
    return rows,best


def run_map(item, out, batch_deadline, evaluate, build, read_instance, WorkBudget, solve_station):
    started=time.perf_counter(); deadline=min(started+CONFIG['map_scheduling_seconds'],batch_deadline)
    name=item['name']; md=out/name; md.mkdir()
    if sha(item['path'])!=item['sha256']: raise RuntimeError('input hash changed')
    ins=read_instance(item['path']); greedy_started=time.perf_counter(); parent=build(ins)
    greedy_seconds=time.perf_counter()-greedy_started
    saved_parent=next(r for r in read(HERE.parent/'failure/G2_ALNS_GREEDY_PARENTS.json')['maps'] if r['map']==name)
    if parent != saved_parent['canonical_solution']:
        raise RuntimeError('reconstructed Greedy differs from archived parent '+name)
    parent_audit=evaluate(ins,parent)
    if not parent_audit['feasible']: raise RuntimeError('Greedy infeasible '+name)
    all_ids=[n for station in domain(parent) for n in station]
    if sorted(all_ids)!=sorted(ins.target_ids) or len(all_ids)!=len(set(all_ids)):
        raise RuntimeError('invalid parent target partition')
    fixed,joint=copy.deepcopy(parent),copy.deepcopy(parent); stations=[]
    for si,kind in enumerate(parent['station_types']):
        ids=domain(parent)[si]
        fixed_ids={slot: domain(parent,True)[si][slot] for slot in ((1,) if kind==1 else (0,1))}
        row=dict(station_idx=si,station_type=kind,target_ids=ids,target_count=len(ids),parent_slot_target_ids=fixed_ids)
        for key,forced in [('fixed_owner',fixed_ids),('joint',None)]:
            budget=WorkBudget(deadline=deadline,max_transitions=CONFIG['max_transition_checks'])
            result=None
            if time.perf_counter() >= deadline:
                row[key]=dict(status=('UNATTEMPTED_BATCH_DEADLINE' if time.perf_counter() >= batch_deadline
                                      else 'UNATTEMPTED_MAP_DEADLINE'), integration_accepted=False)
                continue
            try:
                result=solve_station(ins,si,kind,ids,budget,fixed_slot_target_ids=forced)
                checked=validate_reference(ins,parent,parent_audit,si,result,evaluate,key=='fixed_owner')
            except Exception as exc:
                checked=dict(status='UNRESOLVED_EXCEPTION',integration_accepted=False,
                             exception_type=type(exc).__name__,detail=str(exc),traceback=traceback.format_exc(),
                             raw_result=(result.as_dict() if result is not None else None),
                             raw_trial_audit=getattr(result,'raw_full_trial_audit',None))
            row[key]=checked
            if checked['integration_accepted']:
                (fixed if key=='fixed_owner' else joint)['routes'][si]=checked['routes']
        stations.append(row)
    fixed_audit,joint_audit=evaluate(ins,fixed),evaluate(ins,joint)
    complete=all(s[k]['integration_accepted'] for s in stations for k in ('fixed_owner','joint'))
    valid=fixed_audit['feasible'] and joint_audit['feasible']
    status=('INVALID_FULL_MAP' if not valid else 'FULL_STATION_DOMAIN_NUMERICAL_REFERENCE' if complete
            else 'PARTIAL_FEASIBLE_INCUMBENT_WITH_UNRESOLVED_STATIONS')
    archived,best=archived_comparators(ins,parent,joint_audit,evaluate)
    for label,solution,audit in [('parent',parent,parent_audit),('fixed_owner',fixed,fixed_audit),('joint',joint,joint_audit)]:
        write(md/(label+'.solution.json'),solution); write(md/(label+'.audit.json'),audit)
    write(md/'stations.json',stations); write(md/'archived_comparators.json',archived)
    old_owners=domain(parent,True); new_owners=domain(joint,True)
    changed=sum(len(set(old_owners[s][0])^set(new_owners[s][0])) for s in range(len(old_owners)))
    record=dict(map=name,input_sha256=ins.sha256,status=status,station_count=len(stations),
                active_stations=sum(bool(s['target_ids']) for s in stations),
                targets=len(ins.target_ids),parent_cost=parent_audit['cost'],parent_fixed_cost=parent_audit['fixed_cost'],
                parent_operating_minutes=parent_audit['operating_minutes'],
                fixed_owner_cost=fixed_audit['cost'],joint_cost=joint_audit['cost'],
                fixed_owner_operating_minutes=fixed_audit['operating_minutes'],joint_operating_minutes=joint_audit['operating_minutes'],
                greedy_to_fixed_owner_gain_pct=pct(parent_audit['cost'],fixed_audit['cost']),
                greedy_to_joint_gain_pct=pct(parent_audit['cost'],joint_audit['cost']),
                fixed_owner_to_joint_gain_pct=pct(fixed_audit['cost'],joint_audit['cost']),
                reassignment_difference_attribution=('COMPLETE_NUMERICAL_REFERENCES' if complete else 'MIXED_COVERAGE_NOT_PURE_REASSIGNMENT_EFFECT'),
                target_slot_owner_changes=changed,fixed_and_joint_feasible=valid,
                remaining_opportunity_upper_bound='NOT_CERTIFIED; INCONCLUSIVE_FOR_UNRESOLVED_DOMAIN',
                archived_best_of3=best,archive_cells_verified=sum(r['status']=='VALID_ARCHIVED_FIXED_OWNER_ANCHOR' for r in archived),
                greedy_seconds=greedy_seconds,station_status_counts={key:dict(collections.Counter(s[key]['status'] for s in stations)) for key in ('fixed_owner','joint')},
                elapsed_seconds_before_record_write=time.perf_counter()-started,
                peak_tracemalloc_bytes=tracemalloc.get_traced_memory()[1],
                process_peak_rss_native=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(md/'map.json',record)
    elapsed=time.perf_counter()-started
    timing=dict(end_to_end_through_map_fsync_seconds=elapsed,scheduling_seconds=CONFIG['map_scheduling_seconds'],
                cap_overrun_seconds=max(0.0,elapsed-CONFIG['map_scheduling_seconds']))
    write(md/'TIMING.json',timing);record.update(timing)
    return record


def descriptive(rows,field):
    values=[r[field] for r in rows if isinstance(r.get(field),(float,int))]
    return dict(n_maps=len(rows),n_valid=len(values),n_missing=len(rows)-len(values),
                mean_pct=statistics.mean(values) if values else None,
                median_pct=statistics.median(values) if values else None,
                win_raw=sum(v>0 for v in values),tie_exact=sum(v==0 for v in values),loss_raw=sum(v<0 for v in values))


def main():
    p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--freeze',type=Path);args=p.parse_args()
    if args.dry_run:
        if args.out.exists(): raise RuntimeError('metadata output already exists')
        d=metadata(); write(args.out,d)
        print(json.dumps(dict(status='METADATA_ONLY_PASS',maps=len(d['maps']),archive_files=len(d['archive_hashes']),out=str(args.out),sha256=sha(args.out))))
        return
    if not args.freeze: raise RuntimeError('--freeze required')
    frozen=read(args.freeze); now=metadata()
    for field in ('config','maps','source_hashes','files','archive_hashes'):
        if frozen[field]!=now[field]: raise RuntimeError('freeze mismatch '+field)
    args.out.mkdir(exist_ok=False)
    write(args.out/'RUN_LOCK.json',dict(pid=os.getpid(),freeze_path=str(args.freeze),freeze_sha256=sha(args.freeze),created_utc=datetime.now(timezone.utc).isoformat()))
    # Project modules are imported only AFTER metadata-only path returns.
    sys.path.insert(0,str(SNAPSHOT));sys.path.insert(0,str(HERE))
    from lrphsd.evaluator import evaluate
    from lrphsd.greedy import build
    from lrphsd.problem import read_instance
    from station_split_dp import WorkBudget,solve_station
    start=time.perf_counter(); batch_deadline=start+CONFIG['batch_scheduling_seconds'];tracemalloc.start()
    rows=[]
    try:
        for item in frozen['maps']:
            try:
                row=run_map(item,args.out,batch_deadline,evaluate,build,read_instance,WorkBudget,solve_station)
            except Exception as exc:
                row=dict(map=item['name'],input_sha256=item['sha256'],status='UNRESOLVED_MAP_EXCEPTION',
                         error_type=type(exc).__name__,detail=str(exc),traceback=traceback.format_exc(),
                         fixed_and_joint_feasible=False,station_count=0,active_stations=0,
                         station_inventory_unavailable=True,archive_cells_verified=0,archived_best_of3={},
                         greedy_to_joint_gain_pct=None,end_to_end_through_map_fsync_seconds=None)
                md=args.out/item['name'];md.mkdir(exist_ok=True);write(md/'FAILURE.json',row)
            rows.append(row)
            print(json.dumps(dict(map=row['map'],status=row['status'],greedy_to_joint_gain_pct=row['greedy_to_joint_gain_pct'],elapsed=row['end_to_end_through_map_fsync_seconds'])),flush=True)
        complete=[r for r in rows if r['status']=='FULL_STATION_DOMAIN_NUMERICAL_REFERENCE']
        fields=['greedy_to_fixed_owner_gain_pct','greedy_to_joint_gain_pct','fixed_owner_to_joint_gain_pct']
        report=dict(schema='station_g2_opportunity_exposed_v2',status='DIAGNOSTIC_COMPLETED',
                    scope='historical exposed-data numerical opportunity; NOT new development, Formal, novelty or RL superiority',
                    config=CONFIG,freeze_sha256=sha(args.freeze),python=sys.version,platform=platform.platform(),
                    elapsed_core_batch_seconds=time.perf_counter()-start,
                    metadata_preflight_seconds=now['elapsed_seconds'],maps=rows,
                    map_count=len(rows),station_count=sum(r['station_count'] for r in rows),
                    active_stations=sum(r['active_stations'] for r in rows),complete_maps=len(complete),
                    all_full_incumbents_feasible=all(r['fixed_and_joint_feasible'] for r in rows),
                    archived_cells_verified=sum(r['archive_cells_verified'] for r in rows),
                    all_map_descriptive={field:descriptive(rows,field) for field in fields},
                    complete_map_descriptive={field:descriptive(complete,field) for field in fields},
                    pure_reassignment_attribution='complete-map stratum only; partial difference has mixed solve coverage',
                    remaining_domain_opportunity_upper_bound='INCONCLUSIVE; no formal lower bound for unresolved domain',
                    rl_superiority_proven=False,innovation_proven=False,g4_admitted=False)
        report['strata_by_size_family']={family:{field:descriptive([r for r in rows if r['map'].rsplit('_',1)[0]==family],field) for field in fields} for family in sorted(set(r['map'].rsplit('_',1)[0] for r in rows))}
        report['archived_best_of3_descriptive']={str(b):descriptive([dict(anchor_gain=r['archived_best_of3'].get(str(b),{}).get('joint_candidate_gain_pct')) for r in rows],'anchor_gain') for b in (6,12)}
        write(args.out/'REPORT.json',report)
        print(json.dumps({k:v for k,v in report.items() if k in ('status','map_count','station_count','active_stations','complete_maps','all_full_incumbents_feasible','archived_cells_verified','all_map_descriptive','archived_best_of3_descriptive')}),flush=True)
    except Exception as exc:
        write(args.out/'FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),completed_maps=rows))
        raise


if __name__=='__main__': main()
