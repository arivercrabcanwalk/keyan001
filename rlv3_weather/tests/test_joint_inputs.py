"""Local contract unit tests; no scientific approval or author receipt is forged.

Successful prepare wiring uses mocked admission/freezer boundaries, explicitly
not actual G0/G3 qualification.  Handwritten coordinates test only hashing and
data isolation.  No policy, optimizer, author solver, or subprocess runs here.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from rlcore import campaign, common, joint_inputs as I, registration as R
from lrphsd.problem import empty_solution, read_instance


NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
REAL_INVENTORY = I._inventory


def write(path, obj):
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    return str(path)


def joint_config():
    return dict(schema=I.SCHEMA, mechanism_id=I.MECHANISM, implementation_sha256="a"*64,
                purpose={"train_plans": "training", "val_plans": "validation"},
                scenario="fixed_e4", structures=["joint", "serial"], objectives=["J", "L"],
                paired_initialization=True,
                config=dict(seed=103, bc_epochs=2, pg_steps=3, rollouts=4,
                            lr=0.0001, device="cpu", wall_seconds=60),
                max_bc_epochs=4, max_bc_updates=4, max_pg_updates=12,
                max_policy_rollouts=48, single_launch=True, retry_policy="NO_AUTO_RETRY",
                valid_from="2026-11-20T00:00:00+00:00", valid_until="2026-11-21T00:00:00+00:00")


def cfg_config():
    return dict(ticket_id="unit-test-not-an-approval", device="cpu", seeds=[103, 211, 307], train_scenario="fixed_e4",
                train_hours=1, campaign_hours=1, joint_training=joint_config())


@pytest.mark.parametrize("field,value", [
    ("mechanism_id", "operator_selector"), ("scenario", "weather"),
    ("purpose", {"train_plans": "training", "val_plans": "training"}),
    ("structures", ["joint"]), ("objectives", ["J"]),
    ("paired_initialization", 1), ("single_launch", 1),
    ("retry_policy", "RETRY"), ("max_bc_updates", 8),
    ("max_policy_rollouts", 47), ("max_pg_updates", True),
    ("valid_from", "2026-11-21T00:00:00Z"),
    ("valid_until", "2026-11-20T11:59:00Z"),
    ("valid_until", "2026-11-20T12:00:30Z"),
    ("valid_until", "2026-11-21T00:00:00"),
])
def test_joint_scope_budget_and_time_fail_closed(field, value):
    cfg = cfg_config()
    cfg["joint_training"][field] = value
    with pytest.raises(ValueError):
        I._validate_joint(cfg, NOW)


@pytest.mark.parametrize("field,value", [
    ("seed", True), ("seed", -1), ("bc_epochs", -1), ("pg_steps", 0),
    ("rollouts", 0), ("lr", float("nan")), ("lr", 0),
    ("device", "auto"), ("wall_seconds", 3601),
])
def test_invalid_config_not_admitted(field, value):
    cfg = cfg_config()
    cfg["joint_training"]["config"][field] = value
    with pytest.raises(ValueError):
        I._validate_joint(cfg, NOW)


def test_explicit_scope_accepts_only_exact_known_fields():
    cfg = cfg_config()
    assert I._validate_joint(cfg, NOW) == cfg["joint_training"]
    cfg["joint_training"]["outcomes"] = []
    with pytest.raises(ValueError, match="complete joint_training"):
        I._validate_joint(cfg, NOW)
    cfg.pop("joint_training")
    with pytest.raises(ValueError, match="complete joint_training"):
        I._validate_joint(cfg, NOW)


def test_old_receipt_without_joint_extension_does_not_admit(tmp_path):
    # This is an unapproved empty document, not a fictitious approved receipt.
    empty = write(tmp_path/"unapproved.json", {})
    cfg = dict(mechanism_receipt=empty, comparison_receipt=empty)
    with pytest.raises(ValueError, match="explicitly approve"):
        I._validate_receipts(cfg, joint_config())


def test_hn01_check_rejects_other_site():
    with pytest.raises(ValueError, match="registered hn01"):
        I._check_host(dict(site="local", approved_machine_sha256="0"*64))


def map_file(path, variant=0, *, translated=False):
    if translated:
        # Same exact geometry, different IDs/order/translation/decimal notation.
        text = ("CUST_NO X Y ENERGY SERVICE\n"
                "104 17.2 -9.6 0 0\n"
                "102 18.3 -7.4 .04 2\n"
                "101 17.3 -9.4 .04 2\n")
    else:
        text = ("CUST_NO X Y ENERGY SERVICE\n"
                "1 .1 .2 .04 2\n"
                f"2 {1.1+variant} 2.2 .04 2\n"
                "100 0 0 0 0\n")
    path.write_text(text, encoding="utf-8")
    ins = read_instance(path)
    sol = empty_solution(ins, [2])
    sol["routes"][0][0] = [[1, 2]]
    return dict(path=str(path), solution=sol)


def test_exact_fingerprint_catches_decimal_translation_id_and_order_alias(tmp_path):
    a, b = tmp_path/"a.txt", tmp_path/"b.txt"
    map_file(a); map_file(b, translated=True)
    assert R.file_sha(a) != R.file_sha(b)
    assert I.geometry_fingerprint(a) == I.geometry_fingerprint(b)


def test_exact_fingerprint_retains_wind_direction_and_service(tmp_path):
    a, b = tmp_path/"a.txt", tmp_path/"b.txt"
    map_file(a); map_file(b)
    original = b.read_text()
    b.write_text(original.replace("1 .1 .2", "1 .2 .1"))
    assert I.geometry_fingerprint(a) != I.geometry_fingerprint(b)
    b.write_text(original.replace(".04 2", ".04 3"))
    assert I.geometry_fingerprint(a) != I.geometry_fingerprint(b)


@pytest.fixture
def wiring(tmp_path, monkeypatch):
    root = tmp_path/"rlv3_weather"
    root.mkdir()
    monkeypatch.setattr(campaign, "HERE", root)
    monkeypatch.setattr(common, "ROOT", str(root))
    cfg = cfg_config()
    cfg["joint_training"]["implementation_sha256"] = I.implementation_fingerprint(root)
    # Use a wide window for deterministic prepare wiring, no live authorization.
    cfg["joint_training"]["valid_from"] = "2020-01-01T00:00:00Z"
    cfg["joint_training"]["valid_until"] = "2099-01-01T00:00:00Z"
    cfg.update(root=str(root), mechanism_receipt=str(root/"G0-NOT-PRESENT"),
               comparison_receipt=str(root/"G3-NOT-PRESENT"))
    rows = {}
    for i, split in enumerate(("train_plans", "val_plans", "pilot_plans")):
        row = map_file(root/f"{split}.txt", i)
        row["outcomes"] = ["PRIVATE-RAW-OUTCOME"]
        rows[split] = row
        cfg[split] = write(root/f"{split}.jsonl", row)
    cfg["pilot_plans"] = {"fixed_e4": cfg["pilot_plans"]}
    cfg["cost_manifests"] = {"fixed_e4": str(root/"NO-AUTHOR-ARTIFACT")}
    cfg["selection_anchor_manifests"] = {k: str(root/f"{k}-NO-ANCHOR") for k in ("train_plans", "val_plans")}
    cfg["population_registry"] = write(root/"population.json", dict(
        joint_geometry_schema=I.GEOMETRY_SCHEMA, reviewed_joint_geometry=True,
        excluded_joint_geometry=["f"*64]))
    ticket = root/"ticket.json"
    write(ticket, cfg)
    calls = []

    def frozen(actual):
        calls.append(copy.deepcopy(actual))
        return dict(selection_anchors={split: {row["path"]: dict(cost=42+i, solution=R.digest(row["solution"]))}
                                        for i, (split, row) in enumerate(rows.items()) if split != "pilot_plans"},
                    receipts={"mechanism_receipt": "a"*64, "comparison_receipt": "b"*64},
                    code=I.implementation_fingerprint(root))

    # Explicit mock boundaries; there are no claimed scientific receipts on disk.
    monkeypatch.setattr(I, "_check_host", lambda cfg: None)
    monkeypatch.setattr(I, "_validate_receipts", lambda cfg, joint: None)
    monkeypatch.setattr(I, "_inventory", lambda cfg, ticket, root: {str(ticket): R.file_sha(ticket)})
    monkeypatch.setattr(campaign, "freeze_inputs", frozen)
    return root, cfg, rows, ticket, calls


def test_prepare_delegates_real_freezer_and_returns_only_train_val(wiring):
    root, _, rows, ticket, calls = wiring
    train, val, meta = I.prepare(str(ticket))
    assert len(calls) == 1
    assert len(train) == len(val) == 1
    assert train[0][0] == {k: rows["train_plans"][k] for k in ("path", "solution")}
    assert train[0][1:] == ("fixed_e4", 42.0)
    assert val[0][1:] == ("fixed_e4", 43.0)
    serialized = json.dumps((train, val, meta), allow_nan=False)
    assert "PRIVATE-RAW-OUTCOME" not in serialized
    assert rows["pilot_plans"]["path"] not in serialized
    assert set(meta["config"]) == I.CONFIG_FIELDS
    assert meta["scenario"] == "fixed_e4" and meta["ticket_id"] == "unit-test-not-an-approval"
    assert meta["single_launch"] is True and meta["retry_policy"] == "NO_AUTO_RETRY"
    assert all(Path(c[0]["path"]).is_absolute() for c in train+val)


def test_prepare_requires_absolute_entry_and_matching_existing_root(wiring):
    root, cfg, _, ticket, _ = wiring
    with pytest.raises(ValueError, match="must be absolute"):
        I.prepare("ticket.json")
    cfg["root"] = str(root.parent)
    write(ticket, cfg)
    with pytest.raises(ValueError, match="ticket root differs"):
        I.prepare(str(ticket))


def test_existing_root_symlink_is_accepted(wiring):
    root, cfg, _, ticket, _ = wiring
    alias = root.parent/"package-alias"
    alias.symlink_to(root, target_is_directory=True)
    cfg["root"] = str(alias)
    write(ticket, cfg)
    I.prepare(str(ticket))


@pytest.mark.parametrize("split", ["val_plans", "pilot_plans"])
def test_exact_alias_between_splits_rejected_before_freezer(wiring, split):
    root, _, rows, ticket, calls = wiring
    map_file(Path(rows[split]["path"]), translated=True)
    with pytest.raises(ValueError, match="translated or exposed"):
        I.prepare(str(ticket))
    assert not calls


def test_exposure_registry_requires_reviewed_exact_geometry(wiring):
    _, cfg, _, ticket, calls = wiring
    write(Path(cfg["population_registry"]), {"excluded_geometry": ["f"*64]})
    with pytest.raises(ValueError, match="reviewed exact-geometry"):
        I.prepare(str(ticket))
    assert not calls


def test_explicit_exact_exposure_hash_rejects_train_map(wiring):
    _, cfg, rows, ticket, calls = wiring
    write(Path(cfg["population_registry"]), dict(joint_geometry_schema=I.GEOMETRY_SCHEMA,
        reviewed_joint_geometry=True, excluded_joint_geometry=[I.geometry_fingerprint(rows["train_plans"]["path"])]))
    with pytest.raises(ValueError, match="translated or exposed"):
        I.prepare(str(ticket))
    assert not calls


def test_changed_input_during_admission_is_rejected(wiring, monkeypatch):
    _, _, _, ticket, _ = wiring
    count = 0
    def inventory(cfg, entry, root):
        nonlocal count
        count += 1
        return {str(entry): R.file_sha(entry) if count == 1 else "b"*64}
    monkeypatch.setattr(I, "_inventory", inventory)
    with pytest.raises(ValueError, match="changed during"):
        I.prepare(str(ticket))


def test_missing_full_author_binding_rejected_after_freezer(wiring, monkeypatch):
    _, _, _, ticket, _ = wiring
    original = campaign.freeze_inputs
    def no_binding(cfg):
        body = original(cfg)
        body["selection_anchors"]["train_plans"] = {}
        return body
    monkeypatch.setattr(campaign, "freeze_inputs", no_binding)
    with pytest.raises(ValueError, match="cover split exactly"):
        I.prepare(str(ticket))


def test_invalid_or_duplicate_json_is_rejected(tmp_path):
    path = tmp_path/"invalid.json"
    for content in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        path.write_text(content)
        with pytest.raises(ValueError):
            I._read(path)


def test_changed_implementation_cannot_reuse_approval(wiring):
    root, _, _, ticket, calls = wiring
    (root/"rlcore").mkdir()
    (root/"rlcore"/"changed.py").write_text("# a different implementation\n")
    with pytest.raises(ValueError, match="differs from explicitly approved"):
        I.prepare(str(ticket))
    assert not calls


def test_inventory_hashes_nested_execution_bytes_without_certifying_them(wiring, monkeypatch):
    root, cfg, rows, ticket, _ = wiring
    original_sha = R.file_sha
    monkeypatch.setattr(R, "file_sha", lambda p: "d"*64 if str(p) == "/etc/machine-id" else original_sha(p))
    # These are unapproved dummy input documents; _inventory only follows paths.
    # They make no solver/admission claims and are never passed to the freezer.
    for key in ("mechanism_receipt", "comparison_receipt"):
        Path(cfg[key]).write_text("{}\n")
    execution = root/"NOT-EXECUTED.json"
    write(execution, {"status": "NOT_EXECUTED", "unit_test_only": True})
    anchor = root/"unapproved-anchor.json"
    write(anchor, {"provenance": {"run_receipt_path": execution.name}})
    for split in ("train_plans", "val_plans"):
        write(Path(cfg["selection_anchor_manifests"][split]), {rows[split]["path"]: anchor.name})
    write(Path(cfg["cost_manifests"]["fixed_e4"]), {rows["pilot_plans"]["path"]: {"0": str(anchor)}})
    hashes = REAL_INVENTORY(cfg, ticket, root)
    assert hashes[str(execution)] == R.file_sha(execution)
    assert hashes[str(anchor)] == R.file_sha(anchor)
    assert all(str(Path(row["path"])) in hashes for row in rows.values())
    execution.write_text("{\"status\":\"STILL_NOT_EXECUTED\"}\n")
    assert REAL_INVENTORY(cfg, ticket, root)[str(execution)] != hashes[str(execution)]
