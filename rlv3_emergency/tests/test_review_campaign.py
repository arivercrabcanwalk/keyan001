"""Campaign admission contracts on temporary handwritten inputs only.

All G0/G3 approvals are fictitious fixture records, not research admission.
Only freeze_inputs is called: no policy, training, author solve or comparison.
"""
import copy
import json
from pathlib import Path

import pytest

from rlcore import campaign, common, registration
from lrphsd.problem import empty_solution, read_instance


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_plan(path, row):
    return write_json(path, row)  # A one-row JSONL file.


def manual_row(path, shape):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "CUST_NO X Y ENERGY SERVICE\n"
        f"1 {400 + 17 * shape} 0 .04 2\n"
        f"2 200 {350 + 31 * shape} .04 2\n"
        "100 0 0 0 0\n101 100 0 0 0\n", encoding="utf-8")
    ins = read_instance(path)
    sol = empty_solution(ins, [2, 0])
    sol["routes"][0][0] = [[1, 2]]
    return {"path": str(path), "solution": sol}


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "rlv3_emergency"
    root.mkdir()
    monkeypatch.setattr(campaign, "HERE", root)
    monkeypatch.setattr(common, "ROOT", str(root))
    monkeypatch.setattr(common, "_INS", {})
    monkeypatch.setattr(registration, "ROOT", str(root))
    # macOS platform.platform() may itself spawn uname; keep this fixture local.
    monkeypatch.setattr(campaign.platform, "platform", lambda: "handwritten-contract-platform")

    def no_process(*args, **kwargs):
        pytest.fail("campaign contract tests must never launch a process")

    monkeypatch.setattr(campaign.subprocess, "Popen", no_process)
    rows = {s: manual_row(root / "maps" / f"{s}.txt", i)
            for i, s in enumerate(("train_plans", "val_plans", "pilot_plans"), 1)}
    conditions = ["emerg_random_low", "emerg_clustered_mid"]
    cfg = dict(phase="development", package=root.name, device="cpu",
               ticket_id="HANDWRITTEN-CONTRACT-ONLY", approved_machine_sha256="1" * 64,
               train_scenario=conditions[0], evaluation=conditions,
               primary_condition=conditions[0], primary_reference="REOPT",
               eval_days="123", seeds=[11, 23, 37], train_hours=1,
               rl_hours=1, episode_wall_s=1, campaign_hours=1,
               comparators=["A1", "GREEDY", "REOPT"], pilot_plans={}, cost_manifests={})
    for split in ("train_plans", "val_plans"):
        cfg[split] = write_plan(root / f"{split}.jsonl", rows[split])
    for sc in conditions:
        cfg["pilot_plans"][sc] = write_plan(root / f"{sc}.jsonl", rows["pilot_plans"])
        cfg["cost_manifests"][sc] = write_json(root / f"caps-{sc}.json",
                                               {rows["pilot_plans"]["path"]: {"123": 1000.0}})
    for field, gate in (("mechanism_receipt", "G0"), ("comparison_receipt", "G3")):
        cfg[field] = write_json(root / f"{gate}.json", dict(
            gate=gate, status="APPROVED_FOR_DEVELOPMENT", package=root.name,
            conditions=conditions, ticket_id=cfg["ticket_id"],
            approved_machine_sha256=cfg["approved_machine_sha256"],
            reviewer="fixture-only", decision_basis="handwritten contract; no real approval"))
    cfg["population_registry"] = write_json(root / "population.json", dict(
        reviewed_prior_exposure=True, excluded_raw=["0" * 64], excluded_geometry=["f" * 64],
        expected_raw={s: [r["solution"]["instance_sha256"]] for s, r in rows.items()}))
    return root, cfg, rows


def replace_split(root, cfg, split, row):
    """Keep the independent roster consistent so a leakage check is exercised."""
    write_plan(Path(cfg[split]), row)
    pop_path = Path(cfg["population_registry"])
    pop = json.loads(pop_path.read_text())
    pop["expected_raw"][split] = [row["solution"]["instance_sha256"]]
    write_json(pop_path, pop)


def test_two_paired_emergency_conditions_freeze_without_execution(inputs):
    root, cfg, rows = inputs
    sealed = campaign.freeze_inputs(cfg)
    assert set(sealed["registered_inputs"]) == set(cfg["evaluation"])
    assert all(len(v) == 64 for v in sealed["registered_inputs"].values())
    assert sealed["selection_anchors"] == {}
    assert set(sealed["receipts"]) >= {"mechanism_receipt", "comparison_receipt", "population_registry"}
    assert all(Path(p).is_relative_to(root) for p in sealed["sources"])
    assert sealed["sources"][rows["pilot_plans"]["path"]] == rows["pilot_plans"]["solution"]["instance_sha256"]


@pytest.mark.parametrize("change", ["station", "route"])
def test_paired_emergency_cannot_change_deployment_or_author_route(inputs, change):
    root, cfg, rows = inputs
    changed = copy.deepcopy(rows["pilot_plans"])
    if change == "station":
        changed["solution"]["station_types"] = [0, 2]
        changed["solution"]["routes"] = [[[], []], [[[1, 2]], []]]
    else:
        changed["solution"]["routes"][0][0] = [[2, 1]]
    # Both alternatives are resource-feasible: reject the pairing drift itself.
    common.plan_layout(common.load_ins(changed["path"]), changed["solution"])
    write_plan(Path(cfg["pilot_plans"][cfg["evaluation"][1]]), changed)
    with pytest.raises(ValueError, match="deployment changed between paired"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("mutation", ["missing-primary", "foreign-primary", "duplicate", "cross-paper", "unknown"])
def test_invalid_or_unregistered_conditions_rejected(inputs, mutation):
    _, cfg, _ = inputs
    if mutation == "missing-primary":
        cfg.pop("primary_condition")
    elif mutation == "foreign-primary":
        cfg["primary_condition"] = "emerg_random_high"
    elif mutation == "duplicate":
        cfg["evaluation"] = [cfg["evaluation"][0]] * 2
    elif mutation == "cross-paper":
        cfg["train_scenario"] = "fixed_e4"
    else:
        cfg["train_scenario"] = "not-a-registered-scenario"
    with pytest.raises(ValueError, match="primary condition|cross-paper or unsupported"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("field", ["mechanism_receipt", "comparison_receipt", "population_registry"])
def test_missing_admission_or_population_receipts_rejected(inputs, field):
    _, cfg, _ = inputs
    Path(cfg[field]).unlink()
    with pytest.raises(ValueError, match="missing " + field):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("gate", ["mechanism_receipt", "comparison_receipt"])
@pytest.mark.parametrize("field,value", [("ticket_id", "other-ticket"), ("package", "rlv3_weather"),
                                         ("conditions", ["emerg_random_low"]),
                                         ("approved_machine_sha256", "2" * 64)])
def test_admission_receipt_scope_is_bound(inputs, gate, field, value):
    _, cfg, _ = inputs
    path = Path(cfg[gate])
    receipt = json.loads(path.read_text())
    receipt[field] = value
    write_json(path, receipt)
    with pytest.raises(ValueError, match="wrong scoped development admission"):
        campaign.freeze_inputs(cfg)


def test_shipped_history_is_rejected_even_when_plan_uses_another_name(inputs):
    root, cfg, rows = inputs
    old = root / "data" / "instances" / "manual-history" / "old.txt"
    old.parent.mkdir(parents=True)
    old.write_bytes(Path(rows["pilot_plans"]["path"]).read_bytes())
    with pytest.raises(ValueError, match="exposed population"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("identity", ["raw", "translated-geometry"])
def test_cross_split_leakage_rejected_with_consistent_roster(inputs, identity):
    root, cfg, rows = inputs
    row = copy.deepcopy(rows["train_plans"])
    if identity == "translated-geometry":
        source = Path(row["path"]).read_text().splitlines()
        path = root / "maps" / "translated.txt"
        lines = [source[0]]
        for line in source[1:]:
            nid, x, y, en, service = line.split()
            lines.append(f"{nid} {float(x) + 100} {float(y) + 200} {en} {service}")
        path.write_text("\n".join(lines) + "\n")
        ins = read_instance(path)
        row["path"] = str(path)
        row["solution"].update(instance=ins.name, instance_sha256=ins.sha256)
        assert campaign.geom(path) == campaign.geom(rows["train_plans"]["path"])
    replace_split(root, cfg, "val_plans", row)
    with pytest.raises(ValueError, match="map leakage between splits"):
        campaign.freeze_inputs(cfg)


def test_pilot_conditions_cannot_swap_base_map(inputs):
    root, cfg, _ = inputs
    other = manual_row(root / "maps" / "other-pilot.txt", 9)
    write_plan(Path(cfg["pilot_plans"][cfg["evaluation"][1]]), other)
    with pytest.raises(ValueError, match="share exactly the same base maps"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("change", ["missing-day", "nonpositive"])
def test_operating_budget_must_cover_each_actual_pilot_cell(inputs, change):
    _, cfg, rows = inputs
    caps = {} if change == "missing-day" else {"123": 0}
    write_json(Path(cfg["cost_manifests"][cfg["evaluation"][0]]),
               {rows["pilot_plans"]["path"]: caps})
    with pytest.raises(ValueError, match="cost registration|positive per-cell"):
        campaign.freeze_inputs(cfg)
