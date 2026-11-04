
#!/usr/bin/env python3
"""Paired anytime and operator diagnostics with complete-seed accounting."""
import argparse, json, math, sys, csv
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from carl.stats import paired_summary, wilcoxon_signed_rank, bootstrap_ci, holm


def load_run(path):
    root=Path(path); mpath=root/"manifest.json"
    if not mpath.exists(): raise ValueError(f"missing manifest: {mpath}")
    manifest=json.loads(mpath.read_text())
    if manifest.get("finished") is None or manifest.get("errors") != 0:
        raise ValueError(f"unfinished/failed manifest: {mpath}")
    methods=manifest["methods"]; seeds=[int(x) for x in manifest["seeds"]]
    instances=[Path(x).stem for x in manifest["instances"]]
    expected={(m,i,s) for m in methods for i in instances for s in seeds}
    if len(expected)!=manifest["tasks"]: raise ValueError("manifest task count mismatch")
    files=sorted(root.glob("*__s*.json"))
    if len(files)!=len(expected): raise ValueError(f"run count mismatch: {len(files)} != {len(expected)}")
    runs={}
    code_hashes=set(); instance_hashes={}
    for f in files:
        d=json.loads(f.read_text())
        if d.get("status")!="ok" or d.get("feasible") is not True:
            raise ValueError(f"failed or infeasible result: {f}")
        key=(d["method"],d["instance"],int(d["seed"]))
        if key not in expected or key in runs: raise ValueError(f"unexpected/duplicate task: {key}")
        if abs(float(d["seconds"])-float(manifest["seconds"]))>1e-12:
            raise ValueError(f"budget mismatch: {f}")
        if not d.get("task_identity") or not d.get("provenance"):
            raise ValueError(f"missing provenance: {f}")
        provenance=d["provenance"]
        if not provenance.get("code_sha256") or not provenance.get("instance_sha256"):
            raise ValueError(f"missing source/instance hash: {f}")
        code_hashes.add(provenance["code_sha256"])
        old=instance_hashes.setdefault(d["instance"],provenance["instance_sha256"])
        if old!=provenance["instance_sha256"]:
            raise ValueError(f"instance hash mismatch across methods: {d['instance']}")
        runs[key]=d
    if set(runs)!=expected: raise ValueError("incomplete task matrix")
    if len(code_hashes)!=1: raise ValueError("mixed code hashes in run")
    return manifest,runs


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",required=True)
    ap.add_argument("--reference",default="m0")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    manifest,runs=load_run(a.run)
    methods=manifest["methods"]; instances=[Path(x).stem for x in manifest["instances"]]
    seeds=[int(x) for x in manifest["seeds"]]; ref=a.reference
    if ref not in methods: raise ValueError("reference method absent")
    # Anytime means are valid only when every seed for an instance has a value.
    cps=("0.25","0.5","0.75","1.0")
    anytime={}; comparisons=[]
    for cp in cps:
        per_method={}
        for method in methods:
            per_instance={}
            for inst in instances:
                vals=[]
                for seed in seeds:
                    value=(runs[(method,inst,seed)].get("anytime") or {}).get(cp)
                    if value is None: break
                    vals.append(float(value))
                if len(vals)==len(seeds): per_instance[inst]=float(np.mean(vals))
            per_method[method]=per_instance
        anytime[cp]={}
        for method in methods:
            vals=list(per_method[method].values())
            anytime[cp][method]={"mean":float(np.mean(vals)) if vals else None,
                                 "n_instances":len(vals),
                                 "n_runs":len(vals)*len(seeds)}
        cp_comps=[]
        for method in methods:
            if method==ref: continue
            common=sorted(set(per_method[method]) & set(per_method[ref]))
            if len(common)<3: continue
            x=[per_method[method][i] for i in common]
            y=[per_method[ref][i] for i in common]
            cp_comps.append({"checkpoint":cp,"method":method,"reference":ref,
                             "instances":common,**paired_summary(x,y),
                             "wilcoxon":wilcoxon_signed_rank(x,y),
                             "bootstrap":bootstrap_ci(x,y)})
        if cp_comps:
            adj=holm([c["wilcoxon"]["p_value"] for c in cp_comps])
            for c,pv in zip(cp_comps,adj): c["p_holm"]=pv
        comparisons.extend(cp_comps)
    # Planned controller/neighbor ablations, paired by instance after seed aggregation.
    cost_by=defaultdict(lambda:defaultdict(list))
    for (method,inst,seed),d in runs.items():
        cost_by[method][inst].append(float(d["cost"]))
    ablation_pairs=(("m1d_noxchg","m1d"),("m1d_nojoint","m1d"),
                    ("m2_noxchg","m2"),("m2_nojoint","m2"))
    ablation_results=[]
    for treatment,control in ablation_pairs:
        if treatment not in methods or control not in methods: continue
        common=sorted(set(cost_by[treatment]) & set(cost_by[control]))
        if len(common)<3: continue
        x=[float(np.mean(cost_by[treatment][i])) for i in common]
        y=[float(np.mean(cost_by[control][i])) for i in common]
        ablation_results.append({"treatment":treatment,"control":control,
                                 "instances":common,**paired_summary(x,y),
                                 "wilcoxon":wilcoxon_signed_rank(x,y),
                                 "bootstrap":bootstrap_ci(x,y)})
    if ablation_results:
        adj=holm([r["wilcoxon"]["p_value"] for r in ablation_results])
        for r,pv in zip(ablation_results,adj): r["p_holm"]=pv

    # Aggregate operator diagnostics without pooling missing operators as zero attempts.
    operator=defaultdict(Counter)
    for (method,inst,seed),d in runs.items():
        c=d.get("counters",{})
        for metric in ("operator_attempts","operator_feasible","operator_accepted",
                       "operator_improved","operator_best","operator_changed","operator_no_change"):
            for op,n in (c.get(metric) or {}).items():
                operator[(method,op)][metric]+=int(n)
    op_rows=[]
    for (method,op),c in sorted(operator.items()):
        attempts=c["operator_attempts"]
        op_rows.append({"method":method,"operator":op,"attempts":attempts,
                        "feasible":c["operator_feasible"],"accepted":c["operator_accepted"],
                        "improved":c["operator_improved"],"best":c["operator_best"],
                        "changed":c["operator_changed"],"no_change":c["operator_no_change"],
                        "feasible_rate":c["operator_feasible"]/attempts if attempts else None,
                        "accept_rate":c["operator_accepted"]/attempts if attempts else None,
                        "improve_rate":c["operator_improved"]/attempts if attempts else None,
                        "best_rate":c["operator_best"]/attempts if attempts else None})
    time_summary={}
    for method in methods:
        rs=[d for (m,_,_),d in runs.items() if m==method]
        for field in ("initialization_seconds","search_seconds","finalization_seconds",
                      "controller_load_seconds","evaluation_seconds","end_to_end_seconds",
                      "budget_overrun_seconds"):
            vals=[d.get(field) for d in rs if isinstance(d.get(field),(int,float))]
            time_summary.setdefault(method,{})[field]=float(np.mean(vals)) if vals else None
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    (out/"anytime_diagnostics.json").write_text(json.dumps({
        "run":str(a.run),"budget":manifest["seconds"],"methods":methods,
        "instances":instances,"seeds":seeds,"anytime":anytime,
        "paired_comparisons":comparisons,"ablation_comparisons":ablation_results,
        "time_summary":time_summary,
        "method_config_note":"m1d_noxchg/m2_noxchg replace the 25% cross-exchange routing draw with relocate; not a no-op deletion."
    },indent=2))
    with (out/"operator_summary.csv").open("w",newline="") as f:
        if op_rows:
            w=csv.DictWriter(f,fieldnames=list(op_rows[0]));w.writeheader();w.writerows(op_rows)
    lines=[f"# Anytime and operator diagnostics: {a.run}","",
           f"Budget: {manifest['seconds']} s; tasks: {manifest['tasks']}; errors: 0.",
           "Anytime means below require a complete value for every seed within an instance; comparisons use only instances complete for both methods.","",
           "| checkpoint | method | mean best cost | complete instances | paired vs ref % | p Holm | 95% CI |",
           "|---|---|---:|---:|---:|---:|---|"]
    for cp in cps:
        for method in methods:
            rec=anytime[cp][method]
            comp=next((x for x in comparisons if x["checkpoint"]==cp and x["method"]==method),None)
            diff=f"{comp['pct_diff']:+.3f}" if comp else "-"
            pv=f"{comp['p_holm']:.4f}" if comp else "-"
            ci=(f"[{comp['bootstrap']['lo']:+.3f}, {comp['bootstrap']['hi']:+.3f}]"
                if comp else "-")
            mean=f"{rec['mean']:.4f}" if rec["mean"] is not None else "-"
            lines.append(f"| {cp} | {method} | {mean} | {rec['n_instances']} | {diff} | {pv} | {ci} |")
    lines += ["","## Paired ablation comparisons (final cost)","",
              "Negative mean difference means the treatment (left) is better than its control (right).",
              "| treatment | control | mean diff | wins/losses | Cohen dz | rank-biserial | p raw | p Holm | 95% CI |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in ablation_results:
        ci=r["bootstrap"]
        lines.append(f"| {r['treatment']} | {r['control']} | {r['mean_diff']:+.4f} | "
                     f"{r['wins']}/{r['losses']} | {r['cohen_dz']:+.3f} | "
                     f"{r['wilcoxon']['rank_biserial']:+.3f} | {r['wilcoxon']['p_value']:.4f} | "
                     f"{r['p_holm']:.4f} | [{ci['lo']:+.4f}, {ci['hi']:+.4f}] |")
    lines += ["","## Operator diagnostics","",
              "Rates use all attempts tagged with the operator; see operator_summary.csv for counts and rates."]
    for method in methods:
        rows=[r for r in op_rows if r["method"]==method and not r["operator"].startswith("no_candidate")]
        if not rows: continue
        lines += ["",f"### {method}","","| operator | attempts | feasible % | accepted % | improved % | best updates |",
                  "|---|---:|---:|---:|---:|---:|"]
        for r in sorted(rows,key=lambda z:z["attempts"],reverse=True):
            lines.append(f"| {r['operator']} | {r['attempts']} | {100*r['feasible_rate']:.1f} | "
                         f"{100*r['accept_rate']:.1f} | {100*r['improve_rate']:.1f} | {r['best']} |")
    (out/"DIAGNOSTICS.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines[:25]))


if __name__=="__main__": main()
