"""Synthetic tuning/launch counterexamples; no maps, training or solving."""
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
                              for name in ("tune", "train")})


def complete(**changes):
    row = dict(J=100., cost=5., author_cost=10., author_cost_cap=10., M_return=20.,
               complete_strict=1, physically_feasible=1, all_returned=1,
               timeout=0, failed=0, routine_total=1, routine_done=1,
               high_on_time=0, high_total=1, inc_cell=0, inc_land=0)
    return dict(row, **changes)


def summary(score=20., **changes):
    return dict(dict(J=100., strict=1., physical=1., qualified=1., score=score), **changes)


def tuned_doc():
    return dict(scen="fixed_e4", overall="GREEDY@0", best={"GREEDY-T": "GREEDY@0", "REOPT-T": "REOPT@0.1"},
                grid={"GREEDY@0": summary(5.), "REOPT@0": summary(10.), "REOPT@0.1": summary(7.)})


def test_weather_selector_uses_registered_score_and_per_map_qualification(modules):
    agg = {"fast": summary(5., J=1000.), "cheap": summary(20., J=1.),
           "over_cap": summary(1., J=0., qualified=.5)}
    assert modules.tune.select_qualified({"F": list(agg)}, agg, "wx") == ({"F-T": "fast"}, "fast", [])


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -float("inf")])
def test_nonfinite_scores_never_qualify(modules, invalid):
    assert modules.tune.select_qualified({"F": ["bad"]}, {"bad": summary(invalid)}, "wx") == ({}, None, ["F"])


def test_one_records_cap_from_actual_layout(modules, monkeypatch):
    env = SimpleNamespace(L={"author_cost": 8.})
    monkeypatch.setattr(modules.tune, "make_env", lambda *args: env)
    monkeypatch.setattr(modules.tune.PO, "make", lambda spec: object())
    monkeypatch.setattr(modules.tune.PO, "run_episode", lambda *args: complete(author_cost=999., author_cost_cap=999.))
    row = modules.tune.one((dict(path="synthetic"), 50000, "fixed_e4", "x", "A1"))
    assert row["author_cost"] == row["author_cost_cap"] == 8.
    assert row["path"] == "synthetic" and row["day"] == 50000


def run_synthetic_main(modules, monkeypatch, tmp_path, scenario, days, results):
    seen = []
    rows = [dict(path="synthetic-a"), dict(path="synthetic-b")]
    monkeypatch.setattr(modules.tune, "load_plans", lambda path: rows)
    monkeypatch.setattr(modules.tune, "grid", lambda scen: {"REOPT": ["REOPT@0"]})
    class Pool:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def map(self, fun, jobs, chunksize):
            seen.extend(jobs)
            return [dict(results[job[0]["path"]], method=job[3], path=job[0]["path"], day=job[1]) for job in jobs]
    import multiprocessing
    monkeypatch.setattr(multiprocessing, "get_context", lambda method: SimpleNamespace(Pool=lambda *a, **k: Pool()))
    out = tmp_path / "tuned.json"
    monkeypatch.setattr(sys, "argv", ["tune.py", "--plans", "synthetic", "--scen", scenario,
                                    "--days", str(days), "--maps", "2", "--out", str(out), "--workers", "1"])
    return out, seen


@pytest.mark.parametrize("scenario", ["nowind", "fixed_e4", "fixed_n8"])
def test_fixed_conditions_evaluate_once_per_map(modules, monkeypatch, tmp_path, scenario):
    out, seen = run_synthetic_main(modules, monkeypatch, tmp_path, scenario, 20,
                                  {p: complete() for p in ("synthetic-a", "synthetic-b")})
    modules.tune.main()
    doc = json.loads(out.read_text())
    assert len(seen) == doc["evaluated_episodes"] == 2
    assert len(doc["dev_days"]) == 1
    assert doc["grid"]["REOPT@0"]["score"] == 20.
    assert doc["selection_objective"] == "M_return_with_per_map_author_cost_cap"


def test_one_over_cap_map_blocks_family_even_when_mean_cost_is_below_mean_cap(modules, monkeypatch, tmp_path):
    results = {"synthetic-a": complete(cost=11.), "synthetic-b": complete(cost=1.)}
    out, _ = run_synthetic_main(modules, monkeypatch, tmp_path, "fixed_e4", 20, results)
    with pytest.raises(SystemExit) as stop:
        modules.tune.main()
    assert stop.value.code == 3
    doc = json.loads(out.read_text())
    assert doc["grid"]["REOPT@0"]["cost"] == 6.
    assert doc["grid"]["REOPT@0"]["qualified"] == .5
    assert doc["overall"] is None


def test_B_keeps_all_released_high_priority_jobs_in_pooled_rate(modules, monkeypatch, tmp_path):
    results = {"synthetic-a": complete(high_on_time=1, high_total=1),
               "synthetic-b": complete(high_on_time=0, high_total=9, complete_strict=0, timeout=1)}
    out, seen = run_synthetic_main(modules, monkeypatch, tmp_path, "emerg_high", 2, results)
    modules.tune.main()
    doc = json.loads(out.read_text())
    assert len(seen) == 4
    assert doc["grid"]["REOPT@0"]["qualified"] == 1.
    assert doc["grid"]["REOPT@0"]["score"] == -.1
    assert doc["selection_objective"] == "negative_pooled_high_on_time_rate"


@pytest.mark.parametrize("reference", ["REOPT", "REOPT-T", "TUNED_OVERALL"])
def test_reference_is_resolved_before_training(modules, reference):
    assert modules.tune.require_tuned_reference(tuned_doc(), "fixed_e4", reference) == "GREEDY@0"


@pytest.mark.parametrize("reference,spec", [("REOPT", "REOPT@0"), ("REOPT-T", "REOPT@0.1"),
                                           ("TUNED_OVERALL", "GREEDY@0")])
def test_each_actual_reference_must_qualify(modules, reference, spec):
    doc = tuned_doc()
    doc["grid"][spec]["qualified"] = .5
    with pytest.raises(ValueError, match="eligible|qualified"):
        modules.tune.require_tuned_reference(doc, "fixed_e4", reference)


def test_direct_B_reference_uses_raw_REOPT_probe(modules):
    doc = dict(scen="emerg_high", overall="REOPT", best={"REOPT-T": "REOPT"}, grid={"REOPT": summary(-.5)})
    assert modules.tune.require_tuned_reference(doc, "emerg_high", "REOPT") == "REOPT"


def test_preflight_rejects_missing_reference_stale_scenario_and_nonfinite_teacher(modules):
    for mutate in (lambda d: d["best"].pop("REOPT-T"), lambda d: d.update(scen="fixed_n8"),
                   lambda d: d["grid"][d["overall"]].update(score=float("nan"))):
        doc = tuned_doc()
        mutate(doc)
        with pytest.raises(ValueError):
            modules.tune.require_tuned_reference(doc, "fixed_e4", "REOPT-T")
