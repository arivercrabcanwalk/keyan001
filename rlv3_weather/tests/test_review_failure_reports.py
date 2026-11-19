"""Report-only finite matrices; no real maps, policies, training or solving."""
import copy
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def modules(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("RLV3_ROOT", str(root))
    monkeypatch.syspath_prepend(str(root))
    return SimpleNamespace(**{name: importlib.import_module("rlcore." + name)
                              for name in ("analyze", "engineering_smoke", "registration")})


def matrix(modules, kind="wx", caps=True):
    methods = ["RL_s0", "REOPT", "INIT_s0"]
    maps = {name: dict(days={"0": "input-"+name}, caps={"0": 6.} if caps else {},
                      author_M_return=author, requirements={"0": dict(routine_total=2, fixed=1.,
                      n_open=1, n_dabs=0, n_drones=1, high_total=high if kind=="urg" else 0,
                      norm_total=2 if kind=="urg" else 0)})
            for name, author, high in (("synthetic-a", 30., 1), ("synthetic-b", 60., 9))}
    body = dict(schema="rlv3-paired-pilot-v2", role="development_only", formal=False,
                kind=kind, scenario="fixed_e4" if kind=="wx" else "emerg_random_low",
                wall_s=2., reference="REOPT", methods={name: dict(spec=name) for name in methods},
                days=[0], day_design="fixed_conditions" if kind=="wx" else "independent_within_map",
                maps=maps, cap_role="EXPLICIT_OPERATIONAL_BUDGET" if caps else "NOT_REGISTERED")
    doc = dict(body=body, sha256=modules.registration.digest(body))
    rows=[]
    for method in methods:
        for pos, (name, meta) in enumerate(maps.items()):
            req=meta["requirements"]["0"]
            high = req["high_total"]
            rows.append(dict(path=name, day=0, scen=body["scenario"], method=method, spec=method,
                status="OK", wall=.1, cost=5., J=10., physically_feasible=1, all_returned=1,
                routine_done=2, complete_strict=int(kind=="wx"), n_urgent=high+req["norm_total"],
                urgent_done=1 if kind=="urg" else 0, high_on_time=1 if kind=="urg" and pos==0 else 0,
                norm_on_time=0, unserved=high+req["norm_total"]-1 if kind=="urg" else 0,
                response_observed=1 if kind=="urg" else 0,
                response_missing=high+req["norm_total"]-1 if kind=="urg" else 0,
                M_return=([20.,40.] if method=="RL_s0" else [25.,50.] if method=="REOPT" else [50.,90.])[pos],
                manifest_sha256=doc["sha256"], input_sha256=meta["days"]["0"], **req))
    return doc,rows


def test_unregistered_cost_is_engineering_accounted_and_cli_success(modules, monkeypatch, tmp_path):
    doc,rows=matrix(modules,caps=False)
    out=modules.analyze.report(doc,rows)
    assert out["status"]=="ENGINEERING_ACCOUNTED"
    assert out["comparisons"]=={}
    monkeypatch.setattr(modules.analyze,"read_manifest",lambda path: doc)
    monkeypatch.setattr(modules.analyze,"read_rows",lambda path: rows)
    monkeypatch.setattr(sys,"argv",["analyze","--res","synthetic","--scen","fixed_e4","--out",str(tmp_path)])
    assert modules.analyze.main()==0
    assert json.loads((tmp_path/"gates.json").read_text())["status"]=="ENGINEERING_ACCOUNTED"


@pytest.mark.parametrize("failure", ["cap", "execution", "missing", "duplicate", "physical", "wall"])
def test_blocked_arm_keeps_qualified_full_populations_without_global_inference(modules, failure):
    doc,rows=matrix(modules)
    bad=rows[-1]
    if failure=="cap": bad["cost"]=7.
    elif failure=="execution": bad.update(status="ERROR",error="synthetic failure")
    elif failure=="missing": rows.pop()
    elif failure=="physical": bad.update(physically_feasible=0,all_returned=0)
    elif failure=="wall": bad["wall"]=3.
    else: rows.append(copy.deepcopy(bad))
    out=modules.analyze.report(doc,rows)
    assert out["status"]=="BLOCKED" and out["comparisons"]=={}
    assert "registered_seed_average_v_reference" not in out
    rl=out["methods"]["RL_s0"]
    assert rl["qualified_population"] and rl["registered"]==rl["received"]==2
    assert rl["primary"]==30. and rl["cost"]==5.
    assert rl["author_comparison"]["author_mean_M_return"]==45.
    assert rl["author_comparison"]["mean_difference_min"]==-15.
    assert [v["difference_min"] for v in rl["author_comparison"]["per_map"]]==[-10.,-20.]
    assert rl["author_comparison"]["ci95"] is None
    init=out["methods"]["INIT_s0"]
    assert not init["qualified_population"] and "primary" not in init
    if failure=="cap": assert init["cost_cap_failures"]==1
    if failure=="execution": assert init["execution_errors"]==1
    if failure=="missing": assert init["missing_count"]==1
    if failure=="physical": assert init["physical_failures"]==init["return_failures"]==1
    if failure=="wall": assert init["time_budget_failures"]==1
    assert out["methods"]["REOPT"]["primary"]==37.5


def test_failed_rl_seed_is_never_replaced_with_successful_seed_subset(modules):
    doc,rows=matrix(modules)
    rows[1]["cost"]=7.
    out=modules.analyze.report(doc,rows)
    assert out["status"]=="BLOCKED"
    assert not out["methods"]["RL_s0"]["qualified_population"]
    assert "primary" not in out["methods"]["RL_s0"]
    assert out["methods"]["REOPT"]["primary"]==37.5
    assert "registered_seed_average_v_reference" not in out


def test_B_full_population_service_counts_survive_unrelated_failure(modules, tmp_path):
    doc,rows=matrix(modules,"urg")
    rows[-1].update(status="ERROR",error="synthetic failure")
    out=modules.analyze.report(doc,rows)
    rl=out["methods"]["RL_s0"]
    assert out["status"]=="BLOCKED"
    assert rl["primary"]==.1 and rl["high_on_time"]==1 and rl["high_total"]==10
    assert rl["norm_on_time"]==0 and rl["norm_total"]==4
    assert rl["routine_done"]==rl["routine_total"]==4
    assert rl["urgent_done"]==2 and rl["n_urgent"]==14
    assert rl["service_done"]==6 and rl["service_total"]==18 and rl["unserved"]==12
    modules.analyze.render(out,rows,tmp_path)
    text=(tmp_path/"REPORT.md").read_text()
    assert "high_total" in text and "norm_total" in text and "service_total" in text
    assert "INIT_s0" in text and "BLOCKED" in text


def test_complete_cost_registered_matrix_keeps_pilot_accounting(modules):
    doc,rows=matrix(modules)
    out=modules.analyze.report(doc,rows)
    assert out["status"]=="PILOT_ACCOUNTED"
    assert out["methods"]["RL_s0"]["author_comparison"]["author_mean_M_return"]==45.
    assert out["comparisons"]["RL_s0"]["difference"]==-7.5


def test_author_difference_uses_registered_author_and_handles_missing_metadata(modules):
    doc,rows=matrix(modules)
    del doc["body"]["maps"]["synthetic-b"]["author_M_return"]
    doc["sha256"]=modules.registration.digest(doc["body"])
    for row in rows: row["manifest_sha256"]=doc["sha256"]
    out=modules.analyze.report(doc,rows)
    assert out["methods"]["RL_s0"]["author_comparison"]["mean_difference_min"] is None
    assert "missing" in out["methods"]["RL_s0"]["author_comparison"]["reason"]


def test_engineering_smoke_accepts_only_engineering_report_status_without_running_policy(modules, monkeypatch, tmp_path):
    smoke=modules.engineering_smoke
    folder=tmp_path/"synthetic-smoke"
    input_hash="synthetic-exogenous-input"
    doc=dict(sha256="synthetic-registry",body=dict(maps={str(folder/"manual_tiny.txt"):
             dict(days={"20261119":input_hash})}))
    rows=[dict(input_sha256=input_hash,n_urgent=0) for _ in range(2)]
    monkeypatch.setattr(smoke,"load_ins",lambda path: SimpleNamespace(name="synthetic",sha256="synthetic-map"))
    monkeypatch.setattr(smoke,"read_manifest",lambda path: doc)
    monkeypatch.setattr(smoke,"read_rows",lambda path: rows)
    monkeypatch.setattr(smoke,"index",lambda *args: ({},[],set()))
    def run(command,**kwargs):
        target=Path(command[command.index("--out")+1])
        if "rlcore.evaluate" in command:
            target.write_text("synthetic episodes\n")
            Path(str(target)+".registry.json").write_text("synthetic registry\n")
        else:
            target.mkdir()
            for filename in ("REPORT.md","table.tex","per_episode.csv"):
                (target/filename).write_text("synthetic rendered artifact\n")
            (target/"gates.json").write_text(json.dumps(dict(status="ENGINEERING_ACCOUNTED")))
        return SimpleNamespace(stdout="synthetic command\n",stderr="",returncode=0)
    monkeypatch.setattr(smoke.subprocess,"run",run)
    monkeypatch.setattr(sys,"argv",["engineering_smoke","--out",str(folder),"--scen","fixed_e4"])
    assert smoke.main()==0
    receipt=json.loads((folder/"SMOKE.json").read_text())
    assert receipt["status"]=="ENGINEERING_PASS" and receipt["reporting_status"]=="ENGINEERING_ACCOUNTED"
    assert not receipt["scientific_eligible"] and not receipt["formal"]
