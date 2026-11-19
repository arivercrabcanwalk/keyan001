"""Fixed-wind campaign contracts on temporary handwritten inputs only.

The author/G0/G3 records below are deliberately fictitious contract fixtures.
They verify metadata binding, not actual author execution or scientific admission.
Only freeze_inputs is called; no training, policy, solve or comparison is run.
"""
import copy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from rlcore import campaign, common, fixed_anchor, registration
from lrphsd.problem import empty_solution, read_instance


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


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


def write_contract_anchor(path, row, wind):
    """Handwritten fixture only: these fields do not attest an actual author run."""
    ins = read_instance(row["path"])
    record = dict(schema="liu-full-same-wind-author-run-v1", map_sha256=ins.sha256,
                  solution_sha256=fixed_anchor.digest(row["solution"]),
                  parameters_sha256=fixed_anchor.digest(asdict(ins.params)), wind_id=wind,
                  wind_m_s=list(fixed_anchor.WINDS[wind]),
                  energy_model="author_node_energy_plus_flight_rate", solver="TSALNS",
                  complete_author_run=True, solve_included_wind=True, exit_status=0,
                  outer_iterations=500, inner_iterations=5000, full_strength=True,
                  downgraded=False, budget_s=1800.0, wall_s=1.0,
                  author_repository="fixture://not-an-author-run", author_commit="a" * 40,
                  author_source_sha256="b" * 64,
                  command="HANDWRITTEN CONTRACT ONLY; no author process executed", run_id=path.stem)
    run = path.with_suffix(".execution.json")
    write_json(run, record)
    provenance = dict(record, run_receipt_path=run.name,
                      run_receipt_sha256=registration.file_sha(run))
    write_json(path, dict(solution=row["solution"], provenance=provenance))
    return str(path)


def execution_path(anchor_path):
    anchor_path = Path(anchor_path)
    record = json.loads(anchor_path.read_text())
    return anchor_path.parent / record["provenance"]["run_receipt_path"]


def change_bound_provenance(anchor_path, **changes):
    """Keep the fake external record consistent while testing semantic rejection."""
    anchor_path = Path(anchor_path)
    body = json.loads(anchor_path.read_text())
    prov = body["provenance"]
    prov.update(changes)
    run = execution_path(anchor_path)
    record = {k: v for k, v in prov.items() if k not in {"run_receipt_path", "run_receipt_sha256"}}
    write_json(run, record)
    prov["run_receipt_sha256"] = registration.file_sha(run)
    write_json(anchor_path, body)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "rlv3_weather"
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
    conditions = ["nowind", "fixed_e4", "fixed_n8"]
    cfg = dict(phase="development", package=root.name, device="cpu",
               ticket_id="HANDWRITTEN-CONTRACT-ONLY", approved_machine_sha256="1" * 64,
               train_scenario="fixed_e4", evaluation=conditions, primary_condition="fixed_e4",
               primary_reference="REOPT", eval_days="123", seeds=[11, 23, 37],
               train_hours=1, rl_hours=1, episode_wall_s=1, campaign_hours=1,
               comparators=["A1", "GREEDY", "REOPT"], pilot_plans={}, cost_manifests={},
               selection_anchor_manifests={})
    anchors = {}
    for split in ("train_plans", "val_plans"):
        cfg[split] = write_json(root / f"{split}.jsonl", rows[split])
        anchors[split] = write_contract_anchor(root / "anchors" / f"{split}.json", rows[split], "W04E")
        cfg["selection_anchor_manifests"][split] = write_json(root / f"selection-{split}.json",
                                                               {rows[split]["path"]: anchors[split]})
    for sc in conditions:
        cfg["pilot_plans"][sc] = write_json(root / f"{sc}.jsonl", rows["pilot_plans"])
        anchors[sc] = write_contract_anchor(root / "anchors" / f"{sc}.json", rows["pilot_plans"],
                                            fixed_anchor.SCENARIO_WINDS[sc])
        cfg["cost_manifests"][sc] = write_json(root / f"caps-{sc}.json",
                                               {rows["pilot_plans"]["path"]: {"0": anchors[sc]}})
    for field, gate in (("mechanism_receipt", "G0"), ("comparison_receipt", "G3")):
        cfg[field] = write_json(root / f"{gate}.json", dict(
            gate=gate, status="APPROVED_FOR_DEVELOPMENT", package=root.name,
            conditions=conditions, ticket_id=cfg["ticket_id"],
            approved_machine_sha256=cfg["approved_machine_sha256"],
            reviewer="fixture-only", decision_basis="handwritten contract; no real approval"))
    cfg["population_registry"] = write_json(root / "population.json", dict(
        reviewed_prior_exposure=True, excluded_raw=["0" * 64], excluded_geometry=["f" * 64],
        expected_raw={s: [r["solution"]["instance_sha256"]] for s, r in rows.items()}))
    return root, cfg, rows, anchors


def test_all_fixed_winds_bind_original_train_validation_and_pilot_receipts(inputs):
    root, cfg, rows, anchors = inputs
    sealed = campaign.freeze_inputs(cfg)
    assert set(sealed["registered_inputs"]) == {"nowind", "fixed_e4", "fixed_n8"}
    assert all(len(v) == 64 for v in sealed["registered_inputs"].values())
    assert set(sealed["selection_anchors"]) == {"train_plans", "val_plans"}
    for split in ("train_plans", "val_plans"):
        bound = sealed["selection_anchors"][split][rows[split]["path"]]
        assert bound["anchor_file"] == registration.file_sha(anchors[split])
        assert bound["solution"] == fixed_anchor.digest(rows[split]["solution"])
        assert bound["cost"] > 0 and len(bound["author_receipt"]) == 64
    assert all(Path(p).is_relative_to(root) for p in sealed["sources"])


@pytest.mark.parametrize("split", ["train_plans", "val_plans"])
@pytest.mark.parametrize("defect", ["no-manifest", "incomplete-manifest", "missing-original", "wrong-wind",
                                    "missing-execution", "tampered-execution", "changed-route", "weakened-author"])
def test_fixed_selection_requires_each_original_same_wind_record(inputs, split, defect):
    _, cfg, rows, anchors = inputs
    artifact = anchors[split]
    if defect == "no-manifest":
        del cfg["selection_anchor_manifests"][split]
        message = "same-wind train/validation"
    elif defect == "incomplete-manifest":
        write_json(Path(cfg["selection_anchor_manifests"][split]), {})
        message = "cover every registered training/validation map"
    elif defect == "missing-original":
        Path(artifact).unlink()
        message = "No such file"
    else:
        message = "missing full same-wind anchor|changed training/validation deployment"
        if defect == "wrong-wind":
            change_bound_provenance(artifact, wind_id="W00", wind_m_s=[0.0, 0.0])
        elif defect == "missing-execution":
            execution_path(artifact).unlink()
        elif defect == "tampered-execution":
            run = execution_path(artifact)
            run.write_text(run.read_text() + "\n")
        elif defect == "changed-route":
            changed = copy.deepcopy(rows[split])
            changed["solution"]["routes"][0][0] = [[2, 1]]
            write_json(Path(cfg[split]), changed)
        else:
            change_bound_provenance(artifact, outer_iterations=1)
    with pytest.raises((ValueError, FileNotFoundError), match=message):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("sc", ["nowind", "fixed_e4", "fixed_n8"])
@pytest.mark.parametrize("defect", ["wrong-wind", "missing-execution"])
def test_fixed_pilot_rejects_wrong_or_missing_original_wind_receipt(inputs, sc, defect):
    _, cfg, _, anchors = inputs
    artifact = anchors[sc]
    if defect == "wrong-wind":
        wind = "W04E" if sc == "nowind" else "W00"
        change_bound_provenance(artifact, wind_id=wind, wind_m_s=list(fixed_anchor.WINDS[wind]))
    else:
        execution_path(artifact).unlink()
    with pytest.raises(ValueError, match="missing eligible same-wind author"):
        campaign.freeze_inputs(cfg)


def test_pilot_plan_cannot_replace_the_bound_author_solution(inputs):
    _, cfg, rows, _ = inputs
    changed = copy.deepcopy(rows["pilot_plans"])
    changed["solution"]["routes"][0][0] = [[2, 1]]
    write_json(Path(cfg["pilot_plans"]["fixed_e4"]), changed)
    with pytest.raises(ValueError, match="deployed plan was substituted"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("mutation", ["missing-primary", "foreign-primary", "duplicate", "cross-paper", "unknown", "engineering"])
def test_invalid_or_unregistered_conditions_rejected(inputs, mutation):
    _, cfg, _, _ = inputs
    if mutation == "missing-primary":
        cfg.pop("primary_condition")
    elif mutation == "foreign-primary":
        cfg["primary_condition"] = "weather"
    elif mutation == "duplicate":
        cfg["evaluation"] = ["fixed_e4", "fixed_e4"]
    elif mutation == "cross-paper":
        cfg["train_scenario"] = "emerg_random_low"
    elif mutation == "unknown":
        cfg["train_scenario"] = "not-a-registered-scenario"
    else:
        cfg["evaluation"] = ["weather_paired_clear"]
        cfg["primary_condition"] = "weather_paired_clear"
    with pytest.raises(ValueError, match="primary condition|cross-paper or unsupported|engineering-only"):
        campaign.freeze_inputs(cfg)


@pytest.mark.parametrize("field", ["mechanism_receipt", "comparison_receipt", "population_registry"])
def test_missing_admission_or_population_receipts_rejected(inputs, field):
    _, cfg, _, _ = inputs
    Path(cfg[field]).unlink()
    with pytest.raises(ValueError, match="missing " + field):
        campaign.freeze_inputs(cfg)


def test_shipped_history_is_rejected_without_reading_historical_maps(inputs):
    root, cfg, rows, _ = inputs
    old = root / "data" / "instances" / "manual-history" / "old.txt"
    old.parent.mkdir(parents=True)
    old.write_bytes(Path(rows["pilot_plans"]["path"]).read_bytes())
    with pytest.raises(ValueError, match="exposed population"):
        campaign.freeze_inputs(cfg)


def test_cross_split_reuse_is_rejected_even_with_valid_author_bindings(inputs):
    _, cfg, rows, anchors = inputs
    write_json(Path(cfg["val_plans"]), rows["train_plans"])
    write_json(Path(cfg["selection_anchor_manifests"]["val_plans"]),
               {rows["train_plans"]["path"]: anchors["train_plans"]})
    pop_path = Path(cfg["population_registry"])
    pop = json.loads(pop_path.read_text())
    pop["expected_raw"]["val_plans"] = pop["expected_raw"]["train_plans"]
    write_json(pop_path, pop)
    with pytest.raises(ValueError, match="map leakage between splits"):
        campaign.freeze_inputs(cfg)
