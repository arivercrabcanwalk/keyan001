"""Finite handwritten negative controls, no historical maps and no scientific comparisons."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest

from rlcore.analyze import report, contrast
from rlcore.registration import digest, index, freeze, read_manifest, read_rows
from rlcore.common import load_plans


def matrix(kind="wx"):
    b=dict(schema="rlv3-paired-pilot-v2",role="development_only",formal=False,kind=kind,
        scenario="fixed_e4" if kind=="wx" else "emerg_random_low",wall_s=2,reference="REOPT",
        methods={k:dict(spec=k) for k in ("RL_s0","REOPT")},days=[1],day_design="fixed_conditions",
        maps={"m":dict(days={"1":"fixed_input"},caps={"1":5},requirements={"1":{
            "routine_total":1,"fixed":1,"n_open":1,"n_dabs":0,"n_drones":1,"norm_total":0,"high_total":int(kind!="wx")}})},cap_role="EXPLICIT_OPERATIONAL_BUDGET")
    doc={"body":b,"sha256":digest(b)}
    rows=[dict(path="m",day=1,scen=b["scenario"],method=k,spec=k,status="OK",wall=.1,fixed=1,cost=5,J=5,
        physically_feasible=1,all_returned=1,routine_done=1,routine_total=1,complete_strict=int(kind=="wx"),n_open=1,n_drones=1,n_dabs=0,
        n_urgent=int(kind!="wx"),high_on_time=0,high_total=int(kind!="wx"),norm_on_time=0,norm_total=0,
        M_return=2,manifest_sha256=doc["sha256"],input_sha256="fixed_input") for k in b["methods"]]
    return doc,rows


def test_empty_missing_duplicate_error_never_pass():
    d,r=matrix()
    for broken in [[],r[:1],r+[r[0]],r[:1]+[dict(r[1],status="ERROR",error="bad")]]:
        assert report(d,broken)["status"]=="BLOCKED"


@pytest.mark.parametrize("change",[{"wall":3},{"cost":5.01},{"M_return":None},{"physically_feasible":0},
    {"all_returned":0},{"routine_done":0},{"input_sha256":"other"},{"manifest_sha256":"other"},
    {"day":True},{"spec":"different-checkpoint"},{"status":"TIMEOUT"},{"n_urgent":1},{"J":float("nan")},
    {"n_open":2},{"fixed":0},{"n_drones":3}])
def test_hard_gates(change):
    d,r=matrix(); r[0].update(change)
    assert report(d,r)["status"]=="BLOCKED"


def test_high_miss_is_zero_but_no_high_is_na():
    d,r=matrix("urg"); out=report(d,r)
    assert out["status"]=="PILOT_ACCOUNTED" and out["methods"]["RL_s0"]["primary"]==0
    r[0].update(high_total=0,norm_total=1)
    assert report(d,r)["status"]=="BLOCKED"
    r[1].update(high_total=0,norm_total=1)
    assert report(d,r)["status"]=="BLOCKED"
    d["body"]["maps"]["m"]["requirements"]["1"].update(high_total=0,norm_total=1)
    d["sha256"]=digest(d["body"])
    for row in r: row["manifest_sha256"]=d["sha256"]
    assert report(d,r)["methods"]["RL_s0"]["primary"] is None


def test_scalar_differences_wrap_pairs_and_day_design():
    a=np.asarray([[[1.,1],[3,1]],[[4,1],[7,1]]])
    for design in ("crossed_shared_day","independent_within_map","fixed_conditions"):
        o=contrast(a,a,design,draws=30)
        assert o["difference"]==0 and o["ci95"]==[0,0]


def test_invalid_cap_tolerance_does_not_transfer():
    d,r=matrix()
    r[0]["cost"]=5.+1e-8
    assert report(d,r)["status"]=="BLOCKED"


def test_resume_rejects_incompatible_registration(tmp_path):
    d,_=matrix(); p=tmp_path/"r.json"
    assert freeze(p,d["body"])==d
    b=copy.deepcopy(d["body"]);b["wall_s"]=3
    with pytest.raises(ValueError):freeze(p,b)
    body=read_manifest(p);body["sha256"]="bad";p.write_text(json.dumps(body))
    with pytest.raises(ValueError): read_manifest(p)


def test_no_drop_on_malformed_inputs(tmp_path):
    f=tmp_path/"rows"
    for bad in ['{"error":"timeout"}\n','', '{"solution": {}, "path":"m"}\n{"solution":{}, "path":"m"}\n']:
        f.write_text(bad)
        with pytest.raises(ValueError):load_plans(str(f))
    f.write_text('{"wrong":NaN}')
    with pytest.raises(ValueError):read_rows(f)
