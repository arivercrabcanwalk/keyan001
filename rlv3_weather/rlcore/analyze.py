"""Strict paired development reporting. No complete-case intersection; no formal claim from an exposed pilot."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys
import numpy as np

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from rlcore.registration import read_manifest, read_rows, index, publish

ACCOUNTED_STATUSES = {"PILOT_ACCOUNTED", "ENGINEERING_ACCOUNTED"}


def report_exit_code(out):
    return 0 if out["status"] in ACCOUNTED_STATUSES else 2


def values(b, ix, method):
    """Sufficient statistics [map, within-map day, numerator/denominator]."""
    return np.asarray([[(lambda r: (r["M_return"],1) if b["kind"]=="wx" else
                                    (r["high_on_time"],r["high_total"]))(ix[m,d,method])
                        for d in b["days"]] for m in b["maps"]], dtype=float)


def estimate(x):
    # Weather: balanced map then fixed conditions/days; B: ratio over all released high-priority jobs.
    den=x[...,1].sum()
    return float(x[...,0].sum()/den) if den>0 else None


def contrast(a,r,design, *, seeds=20261119, draws=2000):
    vals=[estimate(x) for x in (a,r)]
    if None in vals:
        return dict(difference=None,ci95=None,reason="undefined rate: zero released high-priority jobs")
    diff=vals[0]-vals[1]
    if a.shape[0]<2:
        return dict(difference=diff,ci95=None,reason="fewer than two independent maps")
    rng=np.random.default_rng(seeds); reps=[]; undefined=0
    n,t=a.shape[:2]
    for _ in range(draws):
        m=rng.integers(n,size=n)[:,None]
        if design=="independent_within_map": ds=rng.integers(t,size=(n,t))
        elif design=="crossed_shared_day": ds=rng.integers(t,size=(1,t))
        elif design=="fixed_conditions": ds=np.arange(t)[None,:]
        else: raise ValueError("unknown registered day design")
        x,y=estimate(a[m,ds]),estimate(r[m,ds])
        if x is None or y is None: undefined+=1
        else: reps.append(x-y)
    return dict(difference=diff,ci95=None if undefined else np.percentile(reps,[2.5,97.5]).tolist(),
                undefined_draws=undefined,draws=draws,inference="exploratory, conditional on listed checkpoints")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _author_comparison(b, ix, method):
    """Descriptive paired minutes against frozen full author, never an A1 row."""
    if any(not _number(meta.get("author_M_return")) for meta in b["maps"].values()):
        return dict(author_mean_M_return=None, mean_difference_min=None, per_map=[], ci95=None,
                    reason="missing registered full-author M_return for one or more maps")
    pairs=[]
    for path, meta in b["maps"].items():
        measured=float(np.mean([ix[path, d, method]["M_return"] for d in b["days"]]))
        author=float(meta["author_M_return"])
        pairs.append(dict(path=path, method_M_return=measured, author_M_return=author,
                          difference_min=measured-author, absolute_difference_min=abs(measured-author)))
    return dict(author_mean_M_return=float(np.mean([p["author_M_return"] for p in pairs])),
                mean_difference_min=float(np.mean([p["difference_min"] for p in pairs])),
                mean_absolute_difference_min=float(np.mean([p["absolute_difference_min"] for p in pairs])),
                paired_maps=len(pairs), per_map=pairs, unit="minutes", difference="method minus full author",
                ci95=None, inference="descriptive full-population paired differences only")


def _sum_count(rows, field):
    if any(type(row.get(field)) is not int or row[field] < 0 for row in rows):
        return None
    return sum(row[field] for row in rows)


def _method_accounting(b, raw, problems, missing):
    expected=len(b["maps"])*len(b["days"])
    def over_cap(row):
        path=row.get("path")
        meta=b["maps"].get(path, {}) if isinstance(path, str) else {}
        cap=meta.get("caps", {}).get(str(row.get("day")))
        tolerance=1e-7 if b.get("cap_role")=="FULL_SAME_WIND_AUTHOR" else 0
        return _number(cap) and _number(row.get("cost")) and row["cost"]>cap+tolerance
    return dict(registered=expected, received=len(raw), qualified_population=not problems and not missing,
                missing_count=len(missing), missing_cells=[list(key) for key in sorted(missing)],
                validation_problems=problems, validation_problem_count=len(problems),
                execution_errors=sum("error" in r or r.get("status")!="OK" for r in raw),
                physical_failures=sum(r.get("physically_feasible")==0 for r in raw),
                return_failures=sum(r.get("all_returned")==0 for r in raw),
                routine_failures=sum(r.get("routine_done")!=r.get("routine_total") for r in raw),
                time_budget_failures=sum(r.get("status")=="TIMEOUT" or
                    (_number(r.get("wall")) and r["wall"]>b["wall_s"]) for r in raw),
                cost_cap_failures=sum(over_cap(r) for r in raw),
                simulator_timeouts=sum(r.get("timeout")==1 for r in raw),
                all_work_completed=sum(r.get("complete_strict")==1 for r in raw))


def report(doc,rows):
    b=doc["body"]; ix,problems,missing=index(doc,rows); names=list(b["methods"])
    expected=len(b["maps"])*len(b["days"])
    costs_declared=b.get("cap_role", "NOT_REGISTERED")!="NOT_REGISTERED"
    costs_complete=costs_declared and all(_number(meta.get("caps", {}).get(str(day)))
                                        for meta in b["maps"].values() for day in b["days"])
    if costs_declared and not costs_complete:
        problems.append("registered cost-cap matrix is incomplete")
    if not problems and not missing and b["kind"]=="urg":
        for m in b["maps"]:
            for d in b["days"]:
                if len({(ix[m,d,k]["high_total"],ix[m,d,k]["norm_total"]) for k in names})!=1:
                    problems.append(f"unmatched release denominators {m} {d}")
    status="BLOCKED" if problems or missing else "PILOT_ACCOUNTED" if costs_complete else "ENGINEERING_ACCOUNTED"
    outcome=dict(status=status, formal=False, superiority_claim=False,
                 cost_reference=b.get("cap_role", "NOT_REGISTERED"), cost_registered=costs_complete,
                 problems=problems, missing=[list(x) for x in sorted(missing)],
                 registered_cells_per_method=expected, methods={}, comparisons={},
                 primary="final return, min" if b["kind"]=="wx" else "completed and arrived by SLA / all released high-priority",
                 reference=b["reference"], day_design=b["day_design"],
                 description_scope="each qualified method over every registered map/day; no success intersection",
                 inference="exploratory, conditional on listed checkpoints" if status=="PILOT_ACCOUNTED" else
                           "not performed: blocked matrix or engineering-only accounting")
    data={}
    for method in names:
        # Validate the original manifest separately for each whole method. Missing
        # cells of other methods do not erase this method's complete population.
        raw=[r for r in rows if r.get("method")==method]
        local_ix, local_problems, local_missing=index(doc,raw)
        local_missing={key for key in local_missing if key[2]==method}
        summary=_method_accounting(b,raw,local_problems,local_missing)
        outcome["methods"][method]=summary
        if not summary["qualified_population"]:
            continue
        rr=[local_ix[m,d,method] for m in b["maps"] for d in b["days"]]
        x=values(b,local_ix,method); data[method]=x
        summary.update(primary=estimate(x), cost=float(np.mean([r["cost"] for r in rr])),
                       J=float(np.mean([r["J"] for r in rr])), wall_mean_s=float(np.mean([r["wall"] for r in rr])))
        if b["kind"]=="wx" and b["day_design"]=="fixed_conditions":
            summary["author_comparison"]=_author_comparison(b,local_ix,method)
        if b["kind"]=="urg":
            for field in ("routine_done", "routine_total", "high_on_time", "high_total", "norm_on_time", "norm_total",
                          "urgent_done", "n_urgent", "unserved", "response_observed", "response_missing"):
                summary[field]=_sum_count(rr,field)
            summary["service_total"]=summary["routine_total"]+summary["n_urgent"]
            summary["service_done"]=(None if summary["urgent_done"] is None else
                                     summary["routine_done"]+summary["urgent_done"])
            summary["overall_completion"]=(None if summary["service_done"] is None or not summary["service_total"] else
                                            summary["service_done"]/summary["service_total"])
    # A failed or missing registered arm blocks every global contrast and CI.
    # No complete-case intersection or surviving-seed average is substituted.
    if status!="PILOT_ACCOUNTED":
        return outcome
    ref=data[b["reference"]]
    for method,x in data.items():
        if method!=b["reference"]: outcome["comparisons"][method]=contrast(x,ref,b["day_design"])
    rl=[x for k,x in data.items() if re.fullmatch(r"RL_s[0-9]+",k)]
    if rl:
        outcome["registered_seed_average_v_reference"]=contrast(np.mean(rl,axis=0),ref,b["day_design"])
    return outcome


def render(out, rows, folder):
    p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    publish(p/"gates.json",out)
    def display(x): return "N/A" if x is None else (f"{x:.5g}" if type(x) is float else str(x))
    lines=[f"# {out['status']}: development only", "", "Primary: "+out["primary"],"Reference: "+out["reference"],
           "Formal qualification / superiority: NOT ESTABLISHED. Lower cost alone is not a win.",
           "Population: "+out["description_scope"], "Inference: "+out["inference"],
           "Registered cost caps: "+str(out["cost_registered"])+" ("+out["cost_reference"]+")", ""]
    tex=[]
    def table(title,cols):
        lines.extend([title,"", "| method | "+" | ".join(cols)+" |","|"+"---|"*(len(cols)+1)])
        tex.extend([r"\begin{tabular}{l"+"r"*len(cols)+"}", "method & "+" & ".join(c.replace("_",r"\_") for c in cols)+r" \\"])
        for k,s in out["methods"].items():
            vs=[display(s.get(c)) for c in cols]
            lines.append("| "+" | ".join([k]+vs)+" |")
            tex.append(" & ".join([k.replace("_",r"\_")]+vs)+r" \\")
        lines.append("");tex.append(r"\end{tabular}")
    table("Complete-population method descriptions (N/A when the method fails any registered cell).",
          ("qualified_population","primary","cost","J","wall_mean_s"))
    table("Attempt and qualification accounting (all received attempts; missing cells remain explicit).",
          ("registered","received","execution_errors","physical_failures","return_failures","routine_failures",
           "time_budget_failures","cost_cap_failures","missing_count","all_work_completed"))
    if any("high_total" in summary for summary in out["methods"].values()):
        table("Emergency counts over all registered releases; service_done counts completed routine and urgent work.",
              ("routine_done","routine_total","high_on_time","high_total","norm_on_time","norm_total",
               "urgent_done","n_urgent","service_done","service_total","unserved","overall_completion"))
    for method,summary in out["methods"].items():
        author=summary.get("author_comparison")
        if author is None:
            continue
        lines.extend(["Full-author paired minutes: "+method,
                      "Author mean M_return: "+display(author["author_mean_M_return"])+" min; mean method-minus-author: "+display(author["mean_difference_min"])+" min. Descriptive only; no CI.", ""])
        tex.extend([r"\par Full-author paired minutes: "+method.replace("_",r"\_")+r"\par",
                    "Author mean: "+display(author["author_mean_M_return"])+" min; mean method-minus-author: "+
                    display(author["mean_difference_min"])+r" min. Descriptive only; no CI.\par"])
        if author.get("reason"):
            lines.extend([author["reason"],""]);continue
        lines.extend(["| map | method M_return | full author M_return | method - author (min) | absolute difference (min) |",
                      "|---|---|---|---|---|"])
        tex.extend([r"\begin{tabular}{lrrrr}",r"map & method & full author & difference (min) & absolute difference (min) \\"])
        for pair in author["per_map"]:
            lines.append("| "+" | ".join([pair["path"]]+[display(pair[k]) for k in
                         ("method_M_return","author_M_return","difference_min","absolute_difference_min")])+" |")
            tex.append(" & ".join([pair["path"].replace("_",r"\_")]+[display(pair[k]) for k in
                       ("method_M_return","author_M_return","difference_min","absolute_difference_min")])+r" \\")
        lines.append("");tex.append(r"\end{tabular}")
    lines+=["",f"Missing: {len(out['missing'])}. Problems: {len(out['problems'])}. See gates.json for all keys and conditional paired differences."]
    (p/"REPORT.md").write_text("\n".join(lines)+"\n")
    (p/"table.tex").write_text("\n".join(tex)+"\n")
    cols=["path","day","scen","method","status","error","physically_feasible","all_returned","routine_done","routine_total",
          "M_return","high_on_time","high_total","norm_on_time","norm_total","urgent_done","n_urgent","unserved",
          "response_observed","response_missing","failed","timeout","complete_strict","cost","J","wall","manifest_sha256","input_sha256"]
    with (p/"per_episode.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for field in ("res","scen","out"): p.add_argument("--"+field,required=True)
    p.add_argument("--registry"); p.add_argument("--tuned",help="deprecated; reference frozen in registry")
    a=p.parse_args(); doc=read_manifest(a.registry or a.res+".registry.json")
    if a.scen!=doc["body"]["scenario"]: raise ValueError("wrong scenario")
    rows=read_rows(a.res); out=report(doc,rows); render(out,rows,a.out)
    print(out["status"],"; formal=False; report:",a.out)
    return report_exit_code(out)


if __name__=="__main__": sys.exit(main())
