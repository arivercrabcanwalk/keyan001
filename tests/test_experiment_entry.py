import importlib.util
from pathlib import Path
import argparse
import pytest

P=Path(__file__).resolve().parents[1]/"rlv3_review/run_experiments.py"
spec=importlib.util.spec_from_file_location("paired_entry",P); entry=importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)

def test_separate_packages_and_explicit_seeds():
    assert entry.stages("B")==["B"]
    assert entry.stages("A")==["A-fixed","A-weather"]
    assert all(entry.STAGES[s][0]=="rlv3_weather" for s in entry.stages("A"))
    assert entry.STAGES["B"][0]=="rlv3_emergency"
    assert entry.seeds_arg("101,211,307")==[101,211,307]
    for bad in ("-1","","1,1","1,x"):
        with pytest.raises(argparse.ArgumentTypeError):entry.seeds_arg(bad)

def test_scoreboard_never_rewards_an_unfinished_route():
    sample=lambda good,m:dict(method="pg",scenario="fixed_e4",result=dict(eligible=good,complete_strict=good,M_return=m,J=99))
    r=entry.score_rows("A-fixed",101,[sample(False,1),sample(True,42)])[0]
    assert r["cases"]==2 and r["eligible_on_fixed"]==1 and r["mean_M_on_eligible_or_complete"]==42
    assert r["urgent_high_total"] is None

def test_weather_and_emergency_reuse_same_event_learner():
    root=P.parents[1]
    assert (root/"rlv3_weather/rlcore/event_learning.py").read_bytes()==(root/"rlv3_emergency/rlcore/event_learning.py").read_bytes()

def test_transfer_selection_ignores_scores_and_covers_sizes():
    spec=importlib.util.spec_from_file_location("stage",P.with_name("execute_stage.py"))
    stage=importlib.util.module_from_spec(spec); spec.loader.exec_module(stage)
    rows=[dict(path=f"test/{size}_{n}_{i}.txt",method="tsalns",sec=10,
               solution=dict(instance_sha256=str(i))) for size,n in [(5,35),(10,110)] for i in [1,0,2]]
    assert len(stage.select(rows,"standard"))==4
    assert stage.select(rows,"quick")==stage.select(rows[::-1],"quick")==[rows[1]]
