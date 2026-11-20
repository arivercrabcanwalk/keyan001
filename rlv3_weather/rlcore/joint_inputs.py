"""Fail-closed admission for a single, prospectively approved fixed-wind round.

``prepare(absolute_ticket_path)`` reuses ``campaign.freeze_inputs``; it grants no
G0/G3 approval and performs no training, author solve, or scientific comparison.
The existing campaign ticket/receipts remain required.  Each G0/G3 receipt must
add an identical ``joint_training`` object with exactly these fields::

    {
      "schema": "rlv3-joint-training-admission-v1",
      "mechanism_id": "joint_slot_route_v1",
      "implementation_sha256": "<implementation_fingerprint() after code freeze>",
      "purpose": {"train_plans": "training", "val_plans": "validation"},
      "scenario": "fixed_e4",
      "structures": ["joint", "serial"], "objectives": ["J", "L"],
      "paired_initialization": true,
      "config": {"seed": 103, "bc_epochs": 2, "pg_steps": 3,
                 "rollouts": 4, "lr": 0.0001, "device": "cpu",
                 "wall_seconds": 60},
      "max_bc_epochs": 4, "max_bc_updates": 4,
      "max_pg_updates": 12, "max_policy_rollouts": 48,
      "single_launch": true, "retry_policy": "NO_AUTO_RETRY",
      "valid_from": "2026-11-20T00:00:00+00:00",
      "valid_until": "2026-11-21T00:00:00+00:00"
    }

Those numbers illustrate field arithmetic, not an approval or runnable ticket.
BC takes one optimizer step per complete epoch and structure; each PG update
uses one prospectively chosen case and ``rollouts`` samples.  The outer launcher
must atomically consume ticket_id once and meter all work against wall_seconds.

The population registry also needs ``joint_geometry_schema=GEOMETRY_SCHEMA``,
``reviewed_joint_geometry=true``, and nonempty ``excluded_joint_geometry``.
Use ``geometry_fingerprint`` on the reviewed prior-exposure union to build it.
No pilot row, pilot path, raw outcome, or original ticket is returned to training.
"""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from . import campaign, common, registration as R

SCHEMA = "rlv3-joint-training-admission-v1"
GEOMETRY_SCHEMA = "rlv3-exact-translation-geometry-v1"
MECHANISM = "joint_slot_route_v1"
FIXED = {"nowind", "fixed_e4", "fixed_n8"}
CONFIG_FIELDS = {"seed", "bc_epochs", "pg_steps", "rollouts", "lr", "device", "wall_seconds"}
JOINT_FIELDS = {"schema", "mechanism_id", "implementation_sha256", "purpose", "scenario", "structures", "objectives",
                "paired_initialization", "config", "max_bc_epochs", "max_bc_updates",
                "max_pg_updates", "max_policy_rollouts", "single_launch", "retry_policy",
                "valid_from", "valid_until"}
SOLUTION_FIELDS = {"schema_version", "instance", "instance_sha256", "station_types", "routes"}


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key: " + key)
        out[key] = value
    return out


def _read(path):
    return _decode(Path(path).read_text(encoding="utf-8"))


def _decode(text):
    def invalid(value):
        raise ValueError("nonfinite JSON value: " + value)
    return json.loads(text, object_pairs_hook=_object, parse_constant=invalid)


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def implementation_fingerprint(root=None):
    """Same real source closure and algorithm used by campaign.freeze_inputs."""
    root = campaign.HERE.resolve() if root is None else Path(root).resolve()
    code = sorted((root/"rlcore").glob("*.py")) + sorted((root/"vendor/lrphsd").glob("*.py"))
    return R.digest([(p.relative_to(root).as_posix(), R.file_sha(p)) for p in code])


def _path(value, root):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("registered input path must be a nonempty string")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def geometry_fingerprint(path):
    """Exact decimal translation, row-order, filename and node-ID invariant.

    Wind has an absolute direction, so rotations/reflections are not aliases.
    Node energy/service and the target/station distinction remain significant.
    The official parser validates the physical grammar before canonicalization.
    """
    from lrphsd.problem import read_instance
    read_instance(path)
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines()[1:]:
        if line.strip():
            values = tuple(Decimal(v) for v in line.split())
            if len(values) != 5 or not all(v.is_finite() for v in values):
                raise ValueError("invalid exact geometry")
            rows.append(values)
    # Enough precision for exact subtraction even for widely separated exponents.
    exponent_min = min(v.as_tuple().exponent for row in rows for v in row[1:3])
    adjusted_max = max(v.adjusted() for row in rows for v in row[1:3])
    precision = max(28, adjusted_max - exponent_min + 3)
    if precision > 10000:
        raise ValueError("geometry decimal precision exceeds admitted representation")
    def canonical(v):
        return "0" if not v else format(v.normalize(), "f")
    with localcontext() as ctx:
        ctx.prec = precision
        x0 = min(r[1] for r in rows); y0 = min(r[2] for r in rows)
        groups = [[], []]
        for _, x, y, energy, service in rows:
            groups[int(energy == 0)].append(tuple(canonical(v) for v in (x-x0, y-y0, energy, service)))
        return R.digest({"schema": GEOMETRY_SCHEMA, "nodes": [sorted(g) for g in groups]})


def _time(value):
    if not isinstance(value, str):
        raise ValueError("joint authorization time must be timezone-aware ISO8601")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid joint authorization time") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("joint authorization time requires timezone")
    return moment.astimezone(timezone.utc)


def _validate_joint(cfg, now):
    joint = cfg.get("joint_training")
    if not isinstance(joint, dict) or set(joint) != JOINT_FIELDS:
        raise ValueError("explicit complete joint_training admission required")
    if (joint["schema"] != SCHEMA or joint["mechanism_id"] != MECHANISM
            or not _hash(joint["implementation_sha256"])
            or joint["purpose"] != {"train_plans": "training", "val_plans": "validation"}
            or joint["scenario"] not in FIXED or joint["scenario"] != cfg.get("train_scenario")
            or joint["structures"] != ["joint", "serial"] or joint["objectives"] != ["J", "L"]
            or joint["paired_initialization"] is not True or joint["single_launch"] is not True
            or joint["retry_policy"] != "NO_AUTO_RETRY"):
        raise ValueError("wrong mechanism, physical condition, split purpose or paired launch authorization")
    config = joint["config"]
    if not isinstance(config, dict) or set(config) != CONFIG_FIELDS:
        raise ValueError("one complete prespecified joint config required")
    for field, minimum in (("seed", 0), ("bc_epochs", 0), ("pg_steps", 1), ("rollouts", 1)):
        if type(config[field]) is not int or config[field] < minimum:
            raise ValueError("invalid joint config " + field)
    for field in ("lr", "wall_seconds"):
        if type(config[field]) not in (int, float) or not math.isfinite(config[field]) or config[field] <= 0:
            raise ValueError("invalid joint config " + field)
    if config["device"] not in ("cpu", "cuda") or config["device"] != cfg.get("device"):
        raise ValueError("joint device must match explicit CPU/CUDA campaign registration")
    if config["seed"] not in cfg.get("seeds", []):
        raise ValueError("joint seed is not in the prospectively approved campaign seeds")
    for hours in ("train_hours", "campaign_hours"):
        value = cfg.get(hours)
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0 or config["wall_seconds"] > value*3600:
            raise ValueError("joint wall_seconds exceeds campaign " + hours)
    expected = {"max_bc_epochs": 2*config["bc_epochs"], "max_bc_updates": 2*config["bc_epochs"],
                "max_pg_updates": 4*config["pg_steps"],
                "max_policy_rollouts": 4*config["pg_steps"]*config["rollouts"]}
    if any(type(joint[k]) is not int or joint[k] != v for k, v in expected.items()):
        raise ValueError("joint update/rollout budget differs from paired run accounting")
    start, end = _time(joint["valid_from"]), _time(joint["valid_until"])
    if not start <= now < end or (end-now).total_seconds() < config["wall_seconds"]:
        raise ValueError("joint approval inactive, expired or insufficient for registered wall budget")
    if not isinstance(cfg.get("ticket_id"), str) or not cfg["ticket_id"].strip():
        raise ValueError("nonempty approved ticket_id required")
    return joint


def _check_host(cfg):
    machine = Path("/etc/machine-id")
    if (cfg.get("site") != "hn01" or not _hash(cfg.get("approved_machine_sha256"))
            or not machine.is_file() or R.file_sha(machine) != cfg["approved_machine_sha256"]):
        raise ValueError("joint scientific input admission requires the registered hn01 machine")


def _validate_receipts(cfg, joint):
    # Base receipt identity/status/reviewer/condition checks remain in the real freezer.
    for name in ("mechanism_receipt", "comparison_receipt"):
        receipt = _read(cfg[name])
        if not isinstance(receipt, dict) or R.digest(receipt.get("joint_training")) != R.digest(joint):
            raise ValueError("G0/G3 must explicitly approve this joint mechanism, purpose, config and time window")


def _rows(path):
    # The original loader validates the existing author-plan schema; reject JSON
    # ambiguities before invoking it, including duplicate keys and nonfinite data.
    def invalid(value):
        raise ValueError("nonfinite plan JSON value: " + value)
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line, object_pairs_hook=_object, parse_constant=invalid)
    rows = common.load_plans(str(path))
    for row in rows:
        # No outcome-bearing row or auxiliary solution field enters the actor.
        if not SOLUTION_FIELDS <= set(row["solution"]):
            raise ValueError("incomplete physical author solution")
        sol = row["solution"]
        if (type(sol["schema_version"]) is not int or sol["schema_version"] != 1
                or not isinstance(sol["instance"], str) or not _hash(sol["instance_sha256"])):
            raise ValueError("invalid physical author solution identity/schema")
    return rows


def _inventory(cfg, ticket, root):
    """Hash the transitive file inputs, including external author execution records."""
    paths = {ticket, Path("/etc/machine-id")}
    for key in ("mechanism_receipt", "comparison_receipt", "population_registry", "train_plans", "val_plans"):
        paths.add(Path(cfg[key]))
    for key in ("pilot_plans", "cost_manifests", "selection_anchor_manifests"):
        paths.update(Path(p) for p in cfg[key].values())
    plans = {cfg["train_plans"], cfg["val_plans"], *cfg["pilot_plans"].values()}
    for plan in plans:
        paths.update(_path(row["path"], root) for row in _rows(plan))
    anchors = set()
    for manifest in cfg["selection_anchor_manifests"].values():
        body = _read(manifest)
        if not isinstance(body, dict):
            raise ValueError("invalid same-wind split manifest")
        anchors.update(_path(p, Path(manifest).parent) for p in body.values())
    for manifest in cfg["cost_manifests"].values():
        body = _read(manifest)
        if not isinstance(body, dict) or any(not isinstance(v, dict) for v in body.values()):
            raise ValueError("invalid same-wind pilot manifest")
        for cell in body.values():
            for path in cell.values():
                if not isinstance(path, str) or not Path(path).is_absolute():
                    raise ValueError("pilot author anchor paths must be absolute")
                anchors.add(_path(path, root))
    paths.update(anchors)
    for anchor in anchors:
        record = _read(anchor)
        provenance = record.get("provenance", {}) if isinstance(record, dict) else {}
        paths.add(_path(provenance.get("run_receipt_path"), anchor.parent))
    paths.update(p.resolve() for p in (root/"data/instances").glob("*/*.txt"))
    paths.update(p.resolve() for p in (root/"rlcore").glob("*.py"))
    paths.update(p.resolve() for p in (root/"vendor/lrphsd").glob("*.py"))
    return {str(p): R.file_sha(p) for p in sorted(paths)}


def _exact_geometry_check(cfg, root):
    population = _read(cfg["population_registry"])
    excluded = population.get("excluded_joint_geometry")
    if (population.get("joint_geometry_schema") != GEOMETRY_SCHEMA
            or population.get("reviewed_joint_geometry") is not True
            or not isinstance(excluded, list) or not excluded
            or any(not _hash(h) for h in excluded) or len(excluded) != len(set(excluded))):
        raise ValueError("reviewed exact-geometry prior-exposure exclusion registry required")
    excluded = set(excluded)
    for old in (root/"data/instances").glob("*/*.txt"):
        excluded.add(geometry_fingerprint(old))
    seen = set()
    for split in ("train_plans", "val_plans", "pilot_plans"):
        plan_paths = list(dict.fromkeys(cfg[split].values())) if split == "pilot_plans" else [cfg[split]]
        split_geometries = None
        for plan in plan_paths:
            geos = [geometry_fingerprint(_path(row["path"], root)) for row in _rows(plan)]
            if len(geos) != len(set(geos)) or set(geos) & (seen | excluded):
                raise ValueError("duplicate, translated or exposed exact map geometry")
            if split_geometries is not None and set(geos) != split_geometries:
                raise ValueError("pilot conditions differ in exact geometry")
            split_geometries = set(geos)
        seen.update(split_geometries or set())


def prepare(ticket_path):
    """Return ``(train_cases, val_cases, metadata)`` after actual scientific gates.

    Cases are ``(row, fixed_scenario, full_same_wind_author_cost)``.  Returned rows
    contain only physical solution fields.  Metadata is strict JSON and exposes
    only hashes of the complete sealed input closure, never pilot data/paths.
    ``prepare`` is read-only; the outer launcher owns the atomic one-use ledger.
    """
    ticket = Path(ticket_path)
    if not ticket.is_absolute():
        raise ValueError("joint ticket entry path must be absolute")
    ticket = ticket.resolve()
    ticket_bytes = ticket.read_bytes()
    cfg = _decode(ticket_bytes.decode("utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("joint ticket must be a JSON object")
    root = campaign.HERE.resolve()
    # Honor an existing matching ROOT (including symlinks); never silently rebase.
    if Path(common.ROOT).resolve() != root:
        raise ValueError("RLV3_ROOT differs from the executing weather package")
    if "root" in cfg and _path(cfg["root"], root) != root:
        raise ValueError("ticket root differs from the executing weather package")
    for key in ("mechanism_receipt", "comparison_receipt", "population_registry", "train_plans", "val_plans"):
        cfg[key] = str(_path(cfg.get(key), root))
    for key in ("pilot_plans", "cost_manifests", "selection_anchor_manifests"):
        values = cfg.get(key)
        if not isinstance(values, dict):
            raise ValueError("missing campaign input mapping " + key)
        cfg[key] = {k: str(_path(v, root)) for k, v in values.items()}
    joint = _validate_joint(cfg, datetime.now(timezone.utc))
    _check_host(cfg)
    _validate_receipts(cfg, joint)
    if implementation_fingerprint(root) != joint["implementation_sha256"]:
        raise ValueError("joint implementation differs from explicitly approved source closure")
    before = _inventory(cfg, ticket, root)
    if before.get(str(ticket)) != sha256(ticket_bytes).hexdigest():
        raise ValueError("registered ticket changed before joint admission")
    _exact_geometry_check(cfg, root)
    sealed = campaign.freeze_inputs(cfg)  # Real G0/G3, full author and all split gates.
    if sealed["code"] != joint["implementation_sha256"]:
        raise ValueError("joint freezer source closure differs from approved implementation")
    selected = sealed["selection_anchors"]
    cases = []
    case_hashes = {}
    for split in ("train_plans", "val_plans"):
        rows = _rows(cfg[split])
        if set(selected[split]) != {r["path"] for r in rows}:
            raise ValueError("same-wind cost binding does not cover split exactly")
        values = []
        for row in rows:
            binding = selected[split][row["path"]]
            cap = binding.get("cost")
            if (type(cap) not in (int, float) or not math.isfinite(cap) or cap <= 0
                    or binding.get("solution") != R.digest(row["solution"])):
                raise ValueError("invalid same-wind full-author cap/solution binding")
            physical = {key: row["solution"][key] for key in SOLUTION_FIELDS}
            clean = {"path": str(_path(row["path"], root)), "solution": physical}
            values.append((clean, joint["scenario"], float(cap)))
        cases.append(values)
        case_hashes[split] = R.digest(values)
    after = _inventory(cfg, ticket, root)
    if before != after:
        raise ValueError("registered input changed during joint admission")
    # A final wall-window check prevents slow preflight consuming the authorized run.
    _validate_joint(cfg, datetime.now(timezone.utc))
    metadata = dict(schema=SCHEMA, ticket_id=cfg["ticket_id"], mechanism_id=MECHANISM,
                    scenario=joint["scenario"], valid_from=joint["valid_from"], valid_until=joint["valid_until"],
                    config=joint["config"], authorization_sha256=R.digest(joint),
                    ticket_sha256=before[str(ticket)], input_sha256=R.digest(before),
                    input_file_count=len(before), input_file_sha256=sorted(before.values()),
                    gate_receipt_sha256={k: sealed["receipts"][k] for k in ("mechanism_receipt", "comparison_receipt")},
                    campaign_freeze_sha256=R.digest(sealed), source_sha256=sealed["code"], case_sha256=case_hashes,
                    budget={k: joint[k] for k in ("max_bc_epochs", "max_bc_updates", "max_pg_updates", "max_policy_rollouts")},
                    single_launch=True, retry_policy="NO_AUTO_RETRY", formal=False)
    # Round-trip ensures numpy/path/nonfinite data never leaks into metadata.
    metadata = json.loads(json.dumps(metadata, sort_keys=True, allow_nan=False))
    return cases[0], cases[1], metadata
