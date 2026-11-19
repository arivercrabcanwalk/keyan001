#!/usr/bin/env python3
"""Only parse saved one-shot results; never import or invoke a solver."""
from pathlib import Path
import collections
import hashlib
import json
import statistics

HERE=Path(__file__).resolve().parent
OUT=HERE/'g2_results_v2'
report=json.loads((OUT/'REPORT.json').read_text())

def stats(rows,field):
    values=[r[field] for r in rows if r.get(field) is not None]
    return dict(n_maps=len(rows),n_valid=len(values),mean_pct=statistics.mean(values) if values else None,
                median_pct=statistics.median(values) if values else None,
                wins_raw=sum(v>0 for v in values),ties_exact=sum(v==0 for v in values),losses_raw=sum(v<0 for v in values))

fields=['greedy_to_fixed_owner_gain_pct','greedy_to_joint_gain_pct','fixed_owner_to_joint_gain_pct']
all_stations=[]; maprows=[]; residuals=[];duty_margin=[]
for m in report['maps']:
    md=OUT/m['map'];stations=json.loads((md/'stations.json').read_text())
    parent=json.loads((md/'parent.solution.json').read_text())
    fixed=json.loads((md/'fixed_owner.solution.json').read_text());joint=json.loads((md/'joint.solution.json').read_text())
    audits={k:json.loads((md/(k+'.audit.json')).read_text()) for k in ('parent','fixed_owner','joint')}
    if not all(a['feasible'] for a in audits.values()):raise AssertionError('infeasible')
    if parent['station_types']!=fixed['station_types'] or parent['station_types']!=joint['station_types']:raise AssertionError('type mismatch')
    for s in stations:
        si=s['station_idx'];row=dict(map=m['map'],station_idx=si,station_type=s['station_type'],n=s['target_count'])
        for key,label in [('fixed_owner','fixed_owner'),('joint','joint')]:
            z=s[key];row[key+'_status']=z['status'];row[key+'_accepted']=z['integration_accepted']
            if 'complete_cost_dp_evaluator_residual' in z:residuals.append(abs(z['complete_cost_dp_evaluator_residual']))
        for label in ('parent','fixed_owner','joint'):
            a=audits[label];mins=sum(x['time_min'] for x in a['details'] if x['station']==si)
            row[label+'_operating_minutes']=mins
            row[label+'_slot_target_ids']=[[n for t in trips for n in t] for trips in (parent if label=='parent' else fixed if label=='fixed_owner' else joint)['routes'][si]]
        row['same_coverage_complete']=row['fixed_owner_accepted'] and row['joint_accepted']
        row['fixed_minus_joint_minutes']=row['fixed_owner_operating_minutes']-row['joint_operating_minutes']
        all_stations.append(row)
    r={**m};r['complete']=m['status']=='FULL_STATION_DOMAIN_NUMERICAL_REFERENCE'
    r['active_joint_sd_slots']=sum(bool(trips[1]) for kind,trips in zip(joint['station_types'],joint['routes']) if kind==2)
    r['all_dabs_targets_on_ld']=all(not trips[1] for kind,trips in zip(joint['station_types'],joint['routes']) if kind==2)
    maprows.append(r)
strata={name:{f:stats(rows,f) for f in fields} for name,rows in [('all',maprows),('complete',[r for r in maprows if r['complete']]),('partial',[r for r in maprows if not r['complete']])]}
by_type={}
for kind in (0,1,2):
    ss=[s for s in all_stations if s['station_type']==kind]
    matched=[s for s in ss if s['same_coverage_complete']]
    by_type[str(kind)]={'n_stations':len(ss),'n_nonempty':sum(s['n']>0 for s in ss),'paired_complete':len(matched),
                       'fixed_status':dict(collections.Counter(s['fixed_owner_status'] for s in ss)),
                       'joint_status':dict(collections.Counter(s['joint_status'] for s in ss)),
                       'paired_fixed_minus_joint_minutes_sum':sum(s['fixed_minus_joint_minutes'] for s in matched),
                       'paired_positive_minutes_station_count':sum(s['fixed_minus_joint_minutes']>1e-8 for s in matched),
                       'role':'station quantities descriptive; maps remain primary statistical unit'}
data=dict(schema='station_g2_saved_result_descriptive_v1',new_solver_evaluator_calls=0,
          report_sha256=hashlib.sha256((OUT/'REPORT.json').read_bytes()).hexdigest(),map_strata=strata,
          station_types=by_type,station_records=all_stations,map_records=maprows,
          peak_abs_cost_reconciliation_residual=max(residuals,default=0),
          source_all_original_report_values_retained=True,
          interpretation='Oracle/domain-reference only; partial mixed coverage; no RL superiority/novelty; no remaining-space upper bound')
(HERE/'G2_SUMMARY.json').write_text(json.dumps(data,indent=2)+'\n')
lines=['# Station split-DP G2: historical opportunity diagnostic',
       'Original exposed 24-map diagnostic. No new training/development/Formal. All full original costs retain fixed fees.',
       '',
       f"Maps: {report['map_count']}; stations: {report['station_count']}; active: {report['active_stations']}; both numerical references complete: {report['complete_maps']}; partial: {24-report['complete_maps']}.",
       f"All parent/fixed/joint full-map incumbents evaluator-feasible; all 144 archived ALNS anchors independently rescored. Core batch wall: {report['elapsed_core_batch_seconds']:.6f}s. This is diagnostic runtime, not equal-resource solver evidence.",
       '',
       '|Scope (maps)|Greedy → fixed owner mean|Greedy → joint mean|Fixed → joint mean|',
       '|---|---:|---:|---:|']
for label,ss in strata.items():
    lines.append(f"|{label} ({ss[fields[0]]['n_maps']})|"+'|'.join(f"{ss[f]['mean_pct']:.6f}%" for f in fields)+'|')
lines+=['','The all/partial fixed→joint contrast mixes completed station coverage and cannot be labelled pure reassignment gain. Only the complete-map stratum supports the qualified numerical-reference contrast. None is a certified IEEE/real optimum or opportunity upper bound.',
        '',
        '|Map|Complete?|Greedy→fixed %|Greedy→joint %|Fixed→joint %|ALNS6 best-of3→joint %|ALNS12 best-of3→joint %|End-to-end s|',
        '|---|---|---:|---:|---:|---:|---:|---:|']
for m in maprows:
    lines.append(f"|{m['map']}|{'yes' if m['complete'] else 'partial'}|"+'|'.join(f"{m[f]:.6f}" for f in fields)+f"|{m['archived_best_of3']['6']['joint_candidate_gain_pct']:.6f}|{m['archived_best_of3']['12']['joint_candidate_gain_pct']:.6f}|{m['end_to_end_through_map_fsync_seconds']:.6f}|")
lines+=['','|Station type|All / nonempty|Paired complete|Fixed statuses|Joint statuses|Paired fixed→joint minutes (sum)|','|---|---|---:|---|---|---:|']
for k,x in by_type.items():
    lines.append(f"|{k}|{x['n_stations']} / {x['n_nonempty']}|{x['paired_complete']}|{x['fixed_status']}|{x['joint_status']}|{x['paired_fixed_minus_joint_minutes_sum']:.9f}|")
lines+=['','Archived best-of3 means three saved runs at each budget and keeps all 144 cells. Their fixed-owner domain is narrower than the new joint-slot domain, so even the ~1.53% average difference does not establish strength against a station-joint non-RL algorithm. Sixteen maps improve and eight lose against each archived best-of3 anchor. No new fair 6s/12s comparison has occurred.',
        'Resource cutoffs, size limits and timeout rows remain unchanged. Do not enlarge this old pool/cutoff or rerun timed-out stations to seek positives. Unresolved stations make remaining-opportunity ceilings INCONCLUSIVE.',
        'G0 remains open. G3 requires a strong station-joint assignment-and-route non-RL baseline on new development data. G4 is not admitted from this diagnostic; route-constructive RL and all innovative claims still require distinct new mechanism/effect evidence.',
        f"Maximum absolute DP/evaluator complete-cost reconciliation residual: {data['peak_abs_cost_reconciliation_residual']:.12g}. Feasibility tolerance and raw signs are distinct from this residual."]
(HERE/'G2_REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'maps':len(maprows),'stations':len(all_stations),'map_strata':strata,'station_types':by_type,'peak_residual':data['peak_abs_cost_reconciliation_residual']},indent=2))
