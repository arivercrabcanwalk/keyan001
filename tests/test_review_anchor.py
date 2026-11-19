"""Independent fixed-wind author-anchor checks on new hand-written instances."""
import copy
import hashlib
import importlib
import json
import math
from dataclasses import asdict

import pytest

anchor = importlib.import_module("rlv3_weather.rlcore.fixed_anchor")
problem = importlib.import_module("rlv3_weather.vendor.lrphsd.problem")


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "manual.txt"
    path.write_text("CUST_NO X Y ENERGY SERVICE\n1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n")
    instance = problem.read_instance(path)
    solution = problem.empty_solution(instance, [2])
    solution["routes"] = [[[[1]], [[2]]]]
    return path, instance, solution


def provenance(tmp_path, instance, solution, wind="W04E", budget=1800.0):
    record = dict(schema="liu-full-same-wind-author-run-v1", map_sha256=instance.sha256,
                  solution_sha256=anchor.digest(solution), parameters_sha256=anchor.digest(asdict(instance.params)), wind_id=wind,
                  wind_m_s=list(anchor.WINDS[wind]),
                  energy_model="author_node_energy_plus_flight_rate", solver="TSALNS",
                  complete_author_run=True, solve_included_wind=True, exit_status=0,
                  outer_iterations=500, inner_iterations=5000, full_strength=True, downgraded=False,
                  budget_s=budget, wall_s=budget, author_repository="fixture-author-repository",
                  author_commit="a" * 40, author_source_sha256="b" * 64,
                  command="fixture author solve --wind 4 0 --budget 1800", run_id="manual-fixture")
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(record, sort_keys=True))
    return dict(record, run_receipt_path=str(run_path),
                run_receipt_sha256=hashlib.sha256(run_path.read_bytes()).hexdigest())


def test_independent_fixed_wind_metrics_and_no_implicit_provenance(source):
    path, instance, solution = source
    r = anchor.audit_fixed_anchor(instance, solution, wind="W04E", map_path=path)
    along = 900 / (19 * 60) + 900 / (11 * 60)
    across = 1800 / (math.sqrt(15**2 - 4**2) * 60)
    assert r["physical_feasible"] is True
    assert r["metrics"]["operating_minutes"] == pytest.approx(along + across + 20)
    assert r["metrics"]["M_return"] == pytest.approx(10 + along)
    assert r["metrics"]["cost"] == pytest.approx(43.4 + .5 * (along + across + 20))
    assert r["trips"][0]["energy"] == pytest.approx(.2 + .018 * along)
    assert r["status"] == "ENGINEERING_ONLY" and not r["scientific_eligible"]


def test_environment_uses_same_wind_anchor_and_not_a_calm_admission(tmp_path):
    from rlv3_weather.rlcore.scen import make_env
    path = tmp_path / "wind_capacity.txt"
    # Small craft, 0.81 battery. Calm: 0.77 + 2*.018 = .806.
    # N8, on a north/south leg: 0.77 + .018*(15/23 + 15/7) > .81.
    path.write_text("CUST_NO X Y ENERGY SERVICE\n1 0 900 .77 10\n100 0 0 0 0\n")
    ins = problem.read_instance(path)
    solution = problem.empty_solution(ins,[1])
    solution["routes"] = [[[],[[1]]]]
    row = {"path":str(path),"solution":solution}
    calm = make_env(row,0,"nowind")
    assert calm.L["author_cost"] == pytest.approx(27.8+.5*12)
    with pytest.raises(ValueError,match="infeasible same-wind"):
        make_env(row,0,"fixed_n8")


def test_seeding_follows_map_bytes_not_filename_or_lookup_path():
    from rlv3_weather.rlcore.scen import day_key
    assert day_key(7,"a"*64)==day_key(7,"a"*64)
    assert len({day_key(7,"a"*64),day_key(8,"a"*64),day_key(7,"b"*64)})==3


def test_positive_energy_zero_service_time_rejected_before_dispatch(tmp_path):
    from rlv3_weather.rlcore.scen import make_env
    path=tmp_path/"zero_service.txt"
    path.write_text("CUST_NO X Y ENERGY SERVICE\n1 0 900 .2 0\n100 0 0 0 0\n")
    ins=problem.read_instance(path)
    solution=problem.empty_solution(ins,[1]); solution["routes"]=[[[],[[1]]]]
    with pytest.raises(ValueError,match="positive inspection duration"):
        make_env({"path":str(path),"solution":solution},0,"nowind")


def test_complete_same_wind_execution_record_is_bound(source, tmp_path):
    path, instance, solution = source
    prov = provenance(tmp_path, instance, solution)
    r = anchor.audit_fixed_anchor(instance, solution, prov, wind="fixed_e4", map_path=path)
    assert r["full_same_wind_author"] and r["scientific_eligible"]
    assert r["status"] == "FULL_SAME_WIND_AUTHOR_RECORDED"
    assert r["formal"] is False and r["issues"] == r["provenance_issues"] == []
    json.dumps(r, allow_nan=False)


def test_calm_author_rescoring_and_ten_second_warmstart_are_engineering(source, tmp_path):
    path, instance, solution = source
    for prov in (provenance(tmp_path, instance, solution, wind="W00"),
                 provenance(tmp_path, instance, solution, budget=10)):
        r = anchor.audit_fixed_anchor(instance, solution, prov, wind="W04E", map_path=path)
        assert r["physical_feasible"] and not r["full_same_wind_author"]
        assert r["status"] == "ENGINEERING_ONLY"


def test_lowered_author_iterations_are_engineering_even_with_1800s(source, tmp_path):
    path, instance, solution = source
    for key, value in (("outer_iterations", 10), ("inner_iterations", 100),
                       ("full_strength", False), ("downgraded", True)):
        prov = provenance(tmp_path, instance, solution)
        prov[key] = value
        # Even an internally consistent short-strength run record is ineligible.
        record = {k:v for k,v in prov.items() if k not in {"run_receipt_path", "run_receipt_sha256"}}
        run = tmp_path / "run.json"; run.write_text(json.dumps(record))
        prov["run_receipt_sha256"] = hashlib.sha256(run.read_bytes()).hexdigest()
        r = anchor.audit_fixed_anchor(instance, solution, prov, wind="W04E", map_path=path)
        assert r["physical_feasible"] and not r["scientific_eligible"]
        assert "provenance:" + key in r["provenance_issues"]


def test_mutated_execution_record_and_solution_fail_bindings(source, tmp_path):
    path, instance, solution = source
    prov = provenance(tmp_path, instance, solution)
    run = tmp_path / "run.json"
    run.write_text(run.read_text() + "\n")
    r = anchor.audit_fixed_anchor(instance, solution, prov, wind="W04E", map_path=path)
    assert not r["scientific_eligible"] and "provenance:run_receipt_hash" in r["provenance_issues"]
    prov = provenance(tmp_path, instance, solution)
    changed = copy.deepcopy(solution)
    changed["routes"] = [[[[2]], [[1]]]]
    r = anchor.audit_fixed_anchor(instance, changed, prov, wind="W04E", map_path=path)
    assert r["physical_feasible"] and not r["scientific_eligible"]
    assert "provenance:solution_sha256" in r["provenance_issues"]


@pytest.mark.parametrize("mutation,issue", [
    (lambda s: s["routes"][0][0][0].append(2), "duplicate:2"),
    (lambda s: s["routes"][0][1].clear(), "missing:2"),
    (lambda s: s["station_types"].__setitem__(0, 0), "closed_station:0:0:0"),
    (lambda s: s["station_types"].__setitem__(0, 1), "large_drone_at_small_station:0:0:0"),
    (lambda s: s["routes"][0][0][0].__setitem__(0, 999), "unknown_target:0:0:0"),
    (lambda s: s.__setitem__("instance_sha256", "f" * 64), "solution_map_hash"),
])
def test_author_route_structure_is_checked(source, mutation, issue):
    path, instance, solution = source
    mutation(solution)
    r = anchor.audit_fixed_anchor(instance, solution, wind="W00", map_path=path)
    assert not r["physical_feasible"] and issue in r["issues"]


def test_node_energy_trip_battery_radius_and_cumulative_duty(tmp_path):
    path = tmp_path / "manual_cap.txt"
    path.write_text("CUST_NO X Y ENERGY SERVICE\n1 5100 0 .9 601\n100 0 0 0 0\n")
    instance = problem.read_instance(path)
    solution = problem.empty_solution(instance, [2]); solution["routes"] = [[[[1]], []]]
    r = anchor.audit_fixed_anchor(instance, solution, wind="W08N", map_path=path)
    assert not r["physical_feasible"]
    assert {"station_radius:0:1", "battery:0:0:0", "cumulative_duty:0:0"} <= set(r["issues"])
    assert r["trips"][0]["node_energy"] == .9


def test_map_bytes_must_match_instance(source, tmp_path):
    path, instance, solution = source
    prov = provenance(tmp_path, instance, solution)
    path.write_text(path.read_text() + "\n")
    r = anchor.audit_fixed_anchor(instance, solution, prov, wind="W04E", map_path=path)
    assert not r["physical_feasible"] and not r["scientific_eligible"]


def test_mutated_instance_cannot_reuse_hash_of_unmodified_map(source):
    path, instance, solution = source
    instance.targets = (problem.Node(1, 900, 0, .01, 10), instance.targets[1])
    r = anchor.audit_fixed_anchor(instance, solution, wind="W04E", map_path=path)
    assert not r["physical_feasible"] and "instance_map_content" in r["issues"]


def test_anchor_file_api_and_supported_domain(source, tmp_path):
    path, instance, solution = source
    artifact = tmp_path / "anchor.json"
    artifact.write_text(json.dumps(dict(solution=solution)))
    r = anchor.audit_anchor_file(artifact, path, "fixed_n8")
    assert r["physical_feasible"] and r["wind_id"] == "W08N"
    assert r["anchor_file_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="only"):
        anchor.audit_fixed_anchor(instance, solution, wind=(6, 0), map_path=path)


def test_anchor_file_resolves_relative_run_receipt(source, tmp_path, monkeypatch):
    path, instance, solution = source
    prov = provenance(tmp_path, instance, solution)
    prov["run_receipt_path"] = "run.json"
    artifact = tmp_path / "anchor-relative.json"
    artifact.write_text(json.dumps(dict(solution=solution, provenance=prov)))
    monkeypatch.chdir(tmp_path.parent)
    r = anchor.audit_anchor_file(artifact, path, "W04E")
    assert r["full_same_wind_author"] and r["provenance_issues"] == []
    output = tmp_path / "audit.json"
    assert anchor.main(["--anchor", str(artifact), "--map", str(path), "--wind", "W04E", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["audit_sha256"] == r["audit_sha256"]
