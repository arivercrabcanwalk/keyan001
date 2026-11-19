"""Independent fsum reduction from retained original records, no new solves."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, math, socket
assert socket.gethostname()=='EXECUTION_HOST'
ROOT=Path(__file__).resolve().parent.parent
P=ROOT.parent; R=P/'recovery_v2'; V=P/'execution_v1'
def read(p):return json.loads(Path(p).read_text())
def close(a,b):assert abs(a-b)<=1e-10,(a,b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    result=read(ROOT/'results/SUMMARY.json');reg=read(V/'REGISTRATION.json')
    bins=defaultdict(list);mapbin=defaultdict(list);seen=set()
    for c in reg['controls']:
        f=read(R/'guards/controls'/c['row_id']/'FINAL_DELIVERY.json')
        assert f['registration']==c and f['status']=='ONTIME_VALID'
        assert c['row_id'] not in seen;seen.add(c['row_id'])
        u=100*(1-f['itt_M_return']/f['anchor_M_return'])
        bins[c['method'],c['deadline_s']].append(u)
        mapbin[c['map_id'],c['method'],c['deadline_s']].append(u)
    assert len(seen)==2880 and set(map(len,bins.values()))=={720}
    for x in result['method_budget_summary']:
        values=bins[x['method'],x['deadline_s']]
        close(math.fsum(values)/720,x['mean_improvement_author_pct'])
        assert sum(x['row_wdl_vs_author'].values())==720
        assert sum(x['map_wdl_vs_author'].values())==24
    u={k:math.fsum(v)/30 for k,v in mapbin.items()}
    methods=['native_strong_minmax_ALNS','independent_common_H']
    independent=[[],[],[],[],[],[],[],[]]
    for m in reg['maps']:
        mi=m['map_id'];a6=u[mi,methods[0],6];h6=u[mi,methods[1],6];a12=u[mi,methods[0],12];h12=u[mi,methods[1],12]
        for bucket,v in zip(independent,[a6,h6,a12,h12,h6-a6,h12-a12,a12-a6,h12-h6]):bucket.append(v)
    for j,x in enumerate(result['eight_contrasts']):
        close(math.fsum(independent[j])/24,x['mean_pct_or_pp'])
        lo,hi=x['exploratory_pointwise95_percentile_CI'];blo,bhi=x['exploratory_bonferroni8_percentile_CI']
        assert blo<=lo<=hi<=bhi
        assert min(independent[j])-1e-10<=blo<=bhi<=max(independent[j])+1e-10
    freeze=read(ROOT/'results/DEPLOYMENT_BASELINE_FREEZE.json')
    assert freeze['both_controls_remain_mandatory'] and freeze['population_exposed']
    assert len(freeze['choices'])==2
    for x in freeze['choices']:
        means={m:math.fsum(bins[m,x['deadline_s']])/720 for m in methods}
        expected=methods[1] if means[methods[1]]>means[methods[0]] else methods[0]
        assert x['method']==expected and x['global_only']
    csvrows=list(csv.DictReader((ROOT/'results/ALL_REGISTERED_SEED_ROWS.csv').open()))
    assert len(csvrows)==2880 and {x['row_id'] for x in csvrows}==seen
    assert len(list(csv.DictReader((ROOT/'results/ALL_24_MAP_EFFECTS.csv').open())))==24
    out={'status':'INDEPENDENT_ORIGINAL_RECORD_FSUM_AUDIT_PASS','all_registered_rows':2880,
        'independent_maps':24,'eight_contrast_means_verified':8,'global_deployment_choices_verified':2,
        'all_seeds_preserved':True,'new_solves':0,'training':0,'Formal':0,
        'summary_sha256':sha(ROOT/'results/SUMMARY.json'),'audit_source_sha256':sha(Path(__file__))}
    (ROOT/'results/INDEPENDENT_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
