"""A exploration contracts; execute on hn01 with the shared physics tests.

No optimizer updates or full experimental campaign run inside these tests.
"""
import importlib
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def explore(monkeypatch):
    base = Path(__file__).resolve().parents[1]
    root = base if base.name == "rlv3_weather" else base / "rlv3_weather"
    monkeypatch.setenv("RLV3_ROOT", str(root))
    monkeypatch.syspath_prepend(str(root))
    for name in list(sys.modules):
        if name == "rlcore" or name.startswith("rlcore."):
            sys.modules.pop(name)
    return importlib.import_module("rlcore.explore_weather")


def test_profiles_have_independent_multistation_populations(explore):
    for cfg in explore.PROFILES.values():
        assert min(cfg.train_maps, cfg.val_maps, cfg.test_maps) > 0
        assert len(cfg.station_types) >= 3 and set(cfg.station_types) == {1, 2}
        assert cfg.bc_epochs > 0 and cfg.pg_steps > 0 and cfg.rollouts >= 2
    assert explore.SCENARIOS == ("fixed_e4", "fixed_n8")


def test_generator_reproduces_bytes_and_split_rng_is_independent(explore, tmp_path):
    paths = [tmp_path / name for name in ("a.txt", "b.txt", "c.txt")]
    cfg = explore.PROFILES["quick"]
    common = dict(station_types=cfg.station_types, targets_per_station=cfg.targets_per_station)
    first = explore._fresh_map(paths[0], seed=17, **common)
    second = explore._fresh_map(paths[1], seed=17, **common)
    explore._fresh_map(paths[2], seed=18, **common)
    assert first == second and paths[0].read_bytes() == paths[1].read_bytes()
    assert paths[0].read_bytes() != paths[2].read_bytes()
    assert len({explore._seed(17, "population", split, index)
                for split in ("train", "val", "test") for index in range(32)}) == 96


def test_same_wind_reference_is_audited_and_not_original_author(explore, tmp_path):
    from rlcore.joint_route import JointRoute
    cfg = explore.PROFILES["quick"]
    path = tmp_path / "fresh.txt"
    own = explore._fresh_map(path, seed=7, station_types=cfg.station_types,
                             targets_per_station=cfg.targets_per_station)
    for scenario in explore.SCENARIOS:
        row, audit = explore._singleton_reference(path, own, cfg.station_types, scenario)
        assert audit["physical_feasible"] and not audit.get("scientific_eligible", False)
        env = JointRoute(row, scenario, audit["metrics"]["cost"])
        while not env.done:
            env.step(env.teacher_action())
        assert env.result()["eligible"] and not env.result()["scientific_eligible"]
        assert set(env.assignment) == set(own)
        assert env.assignment == own


def test_two_opt_control_does_not_change_membership_or_weaken_failure(explore, tmp_path):
    from rlcore.joint_route import JointRoute
    from rlcore.common import load_ins
    from rlcore.fixed_anchor import audit_fixed_anchor
    path = tmp_path / "crossed.txt"
    path.write_text("CUST_NO X Y ENERGY SERVICE\n"
                    "1 400 400 .1 1\n2 -400 -400 .1 1\n"
                    "3 400 -400 .1 1\n4 -400 400 .1 1\n100 0 0 0 0\n")
    instance = load_ins(str(path))
    solution = dict(schema_version=1, instance=instance.name, instance_sha256=instance.sha256,
                    station_types=[2], routes=[[[[1, 2, 3, 4]], []]])
    audit = audit_fixed_anchor(instance, solution, wind="fixed_e4", map_path=path)
    case = ({"path": str(path), "solution": solution}, "fixed_e4", audit["metrics"]["cost"])
    env = JointRoute(*case)
    while not env.done:
        env.step(env.teacher_action())
    original = dict(result=env.result(), actions=env.trace)
    changed = explore._two_opt_episode(original, case)
    assert changed["result"]["eligible"]
    assert changed["result"]["cost"] <= original["result"]["cost"]
    assert changed["result"]["M_return"] <= original["result"]["M_return"]
    assert set(changed["result"]["solution"]["routes"][0][0][0]) == {1, 2, 3, 4}
    assert changed["result"]["postprocess"]["moves"] > 0
    assert original["result"]["solution"] == solution
    failure = dict(result=dict(eligible=False, termination_reason="dead_end"), actions=[])
    failed = explore._two_opt_episode(failure, case)
    assert not failed["result"]["eligible"]
    assert failed["result"]["termination_reason"] == "dead_end"
    assert failed["result"]["postprocess"]["status"] == "SKIPPED_INELIGIBLE"


def test_manifest_splits_geometry_before_duplicating_wind(explore, tmp_path, monkeypatch):
    cfg = explore.Profile(1, 1, 1, (2, 1, 2), (1, 2), 1, 1, 2, .001, 60)
    monkeypatch.setitem(explore.PROFILES, "tiny_contract_test", cfg)
    population, manifest = explore.build_population(tmp_path, seed=17, profile="tiny_contract_test")
    assert {split: len(cases) for split, cases in population.items()} == {"train": 2, "val": 2, "test": 2}
    geometry = {split: {e["geometry_sha256"] for e in manifest["entries"] if e["split"] == split}
                for split in population}
    assert not geometry["train"] & geometry["val"]
    assert not geometry["train"] & geometry["test"]
    assert not geometry["val"] & geometry["test"]
    assert manifest["unique_base_map_geometry"] == 3
    assert manifest["urgent_jobs"] == 0 and not manifest["original_author_reference"]
    assert json.loads((tmp_path / "population_manifest.json").read_text()) == manifest
    for split in population:
        plans = [json.loads(line) for line in (tmp_path / "dataset" / split / "plans.jsonl").read_text().splitlines()]
        assert len(plans) == 1 and set(plans[0]) == {"path", "solution"}
    _, clone = explore.build_population(tmp_path / "relocated", seed=17, profile="tiny_contract_test")
    assert clone["population_sha256"] == manifest["population_sha256"]


def test_aggregate_keeps_failure_in_all_case_denominator(explore):
    rows = [dict(method="x", result=dict(eligible=True, M_return=10), score_j=4, score_m=10),
            dict(method="x", result=dict(eligible=False, M_return=None), score_j=1004, score_m=1502)]
    agg = explore._aggregate(rows)["x"]
    assert agg["cases"] == 2 and agg["failure_count"] == 1
    assert agg["mean_J_all"] == 504 and agg["mean_L_all"] == 756
    assert agg["mean_eligible_M"] == 10
    rows[1]["score_m"] = None
    assert explore._aggregate(rows)["x"]["mean_L_all"] is None


def test_cli_rejects_invalid_output_or_reuse_before_generation(explore, tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        explore.run(out=Path("relative"), seed=1)
    with pytest.raises(FileExistsError, match="already exists"):
        explore.run(out=tmp_path, seed=1)
