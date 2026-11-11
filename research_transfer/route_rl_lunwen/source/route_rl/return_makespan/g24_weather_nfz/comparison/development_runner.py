#!/usr/bin/env python3
"""Prospective, bounded weather-route DEVELOPMENT comparison; never formal evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
G24 = HERE.parent
RM = G24.parent
ROOT = RM.parents[2]
GEN = RM / "g23/data/generator_v2"
AUTHOR = RM / "g23/author_baseline"
REPRO = ROOT / "reproduction/reviewer_package_semfix"
for p in (G24, RM, GEN, AUTHOR, REPRO):
    sys.path.insert(0, str(p))

import generator_v2 as generator
import author_runner
from lrphsd.problem import read_instance
from scorer import CostAnchor
from weather_scenario_io import load_weather_scenario
from weather_author_anchor import prepare_author_weather_anchor
from weather_full_map import WeatherFullMapEnv, replay_weather_solution

SCHEMA = "weather_common_map_development_v3"
LEGACY_SCHEMA = "weather_common_map_development_v1"
SEEDS = (103, 211, 307)
SLOTS = [("train", "opportunity", i) for i in range(1, 5)] + [
    ("validation", "calibration", 1), ("heldout_development", "validation", 1)]
ALGORITHMS = ("PPO", "A2C", "REINFORCE")
RESOURCE_LIMITS = {"cpu_threads": 1, "max_episode_steps": 128,
                   "max_transitions_per_run": 4096, "max_demonstration_transitions": 512,
                   "train_wall_s_per_algorithm_seed": 600}
TRAINING = {"ppo_epochs": 2, "ppo_minibatch": 32, "gamma": 1.0,
            "gae_lambda": 1.0, "entropy_coef": 0.02, "max_grad": 0.5,
            "learning_rate": 0.003, "behavior_clone_epochs": 12,
            "behavior_clone_minibatch": 64}
V1_PROBE_IDENTITIES = frozenset({
    ("8e0a0982d4735440fa192a4b4a89bf15607056ad945e384501b5c219328aec6f", "2eb7aa002e8c758ec1ede9a27789be5d4d16e5c52ece80556d23e1670224db37"),
    ("25b01c3a589142255855e966ae5035b903c3012328c65a53495f4681336a83e5", "3090355d2320f61c5fce2c4219d4b5e7471cd9838178441e80b9e2dda7be7792"),
    ("5f429dd6967f152589876a800fb161223b002de6b6e1df6f7eb1b540045cd2fd", "03e112076adff430a824319366be399a29fdbc48089410b0b359f70d22711fce"),
    ("cbe72c28e799d0d90aa4517c4c7e1b6025b045d222a015a96e14156cab12d97d", "c1fed2c363badf70e564af6be69785f9fe23fddaaf45ce0171cddd83c57566ce"),
    ("098896e1cb02d503d29fe6a0b2250547976d13eb9973905d243e062a178460f7", "8a338e764f9526c71fd0424d51cdcb4f4257460d3f8f807856a2306809329ed6"),
    ("049910dea869cfbf30d0e87b9d131d6daae2d90527fec9c93c88136e54a3b794", "0b83230f16b710f403d2a611272a71cbc9c147d24cf88748d50309e310ff7b50"),
})

# Set before numerical backends are imported; runtime values are checked later.
for _thread_env in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_thread_env] = "1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_key(path):
    """A source/bundle identity is always a project-relative POSIX key."""
    path = Path(path).resolve()
    try:
        key = path.relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"dependency escapes project root: {path}") from error
    if not key or key.startswith("../") or "\\" in key:
        raise ValueError(f"unsafe dependency key: {key!r}")
    return key


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def replace_json(path, value):
    """Durably replace a mutable progress snapshot; immutable receipts use write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path, value):
    with Path(path).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dependencies():
    paths = [Path(__file__), GEN / "generator_v2.py", AUTHOR / "author_runner.py",
             G24 / "weather_author_anchor.py", G24 / "weather_scenario_io.py",
             G24 / "weather_full_map.py", G24 / "weather_oracle.py", G24 / "weather_replay.py",
             G24 / "weather_policy.py", G24 / "rl_algorithms.py", G24 / "run_full_map_smoke.py",
             RM / "scorer.py", REPRO / "lrphsd/problem.py", REPRO / "lrphsd/evaluator.py",
             REPRO / "lrphsd/__init__.py"]
    paths += list(generator.default_exclusion_paths())
    beam = HERE / "physical_baselines.py"
    if beam.is_file():
        paths.append(beam)
    result = {}
    for path in paths:
        path = Path(path)
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing regular dependency: {path}")
        key = canonical_key(path)
        if key in result:
            raise ValueError(f"duplicate dependency: {key}")
        result[key] = sha(path)
    return dict(sorted(result.items()))


def slots():
    return [{"id": f"{partition}_{ordinal}", "split": split,
             "partition": partition, "ordinal": ordinal}
            for split, partition, ordinal in SLOTS]


def _check_namespace(namespace):
    if not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,119}", namespace):
        raise ValueError("namespace must be 8..120 ASCII [A-Za-z0-9._-] characters")


def _settings(updates, episodes):
    if type(updates) is not int or not 1 <= updates <= 100:
        raise ValueError("updates must be an integer in 1..100")
    if type(episodes) is not int or not 1 <= episodes <= 32:
        raise ValueError("episodes must be an integer in 1..32")
    return {"updates": updates, "episodes_per_update": episodes,
            "resource_limits": dict(RESOURCE_LIMITS), "training": dict(TRAINING)}


def require_v1_probe_exclusions():
    """Make future v3 generation reject every retained v1 development identity."""
    path = generator.default_exclusion_paths()[-1]
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = manifest.get("records")
    identities = {(row.get("raw_sha256"), row.get("canonical_geometry_sha256"))
                  for row in rows} if isinstance(rows, list) else set()
    if identities != V1_PROBE_IDENTITIES:
        raise ValueError("Windows v1 six-map exclusion manifest identity mismatch")


def register(path, namespace, updates=4, episodes=2):
    """Freeze a future v3 allocation.  It cannot reuse any v1 materialization."""
    _check_namespace(namespace)
    require_v1_probe_exclusions()
    registration = {"schema": SCHEMA, "namespace": namespace, "family": [3, 20],
                    "slots": slots(), "seeds": list(SEEDS), "algorithms": list(ALGORITHMS),
                    **_settings(updates, episodes),
                    "checkpoint_rule": "last completed update; no validation selection",
                    "author_profile": "J1b", "author_timeout_s": 180,
                    "author_seed_namespace": namespace + ":J1b",
                    "scenario_rule": "fixed-global-square-and-wind-v1",
                    "budgets_s": [6, 12], "original_cost_tolerance": 1e-7,
                    "weather_cost_tolerance": 1e-7, "dependencies": dependencies(),
                    "materialization_mode": "new_generation_excludes_v1_probe_identities",
                    "execution_authorization": "user_authorized_<EXPERIMENT_SERVER>_weather_nfz_route_rl_development_20261104",
                    "status": "development_only_not_formal_no_replacement",
                    "map_generation_performed": False}
    write(path, registration)
    return registration


def _normalize_legacy_dependencies(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("legacy registration has no dependencies")
    result = {}
    for raw_key, digest in value.items():
        if not isinstance(raw_key, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("malformed legacy dependency")
        key = raw_key.replace("\\", "/")
        if key.startswith("/") or key.startswith("../") or "/../" in key or key in result:
            raise ValueError("unsafe/duplicate legacy dependency key")
        result[key] = digest
    return dict(sorted(result.items()))


def _v1_expected_fields(r):
    if r.get("schema") != LEGACY_SCHEMA or r.get("family") != [3, 20] or r.get("slots") != slots():
        raise ValueError("unexpected v1 allocation")
    if r.get("seeds") != list(SEEDS) or r.get("algorithms") != ["PPO", "A2C"]:
        raise ValueError("unexpected v1 algorithms or seeds")
    _check_namespace(r.get("namespace"))
    if type(r.get("updates")) is not int or not 1 <= r["updates"] <= 100 or type(r.get("episodes_per_update")) is not int or not 1 <= r["episodes_per_update"] <= 32:
        raise ValueError("invalid legacy training bounds")
    expected = {"checkpoint_rule": "last update, no validation selection", "author_profile": "J1b",
                "author_timeout_s": 180, "author_seed_namespace": r["namespace"] + ":J1b",
                "scenario_rule": "fixed-global-square-and-wind-v1", "budgets_s": [6, 12],
                "original_cost_tolerance": 1e-7, "weather_cost_tolerance": 1e-7,
                "status": "development_only_not_formal_no_replacement", "map_generation_performed": False}
    for field, value in expected.items():
        if r.get(field) != value:
            raise ValueError(f"unexpected v1 field: {field}")


def verify_legacy_bundle(registration, bundle):
    """Validate the frozen v1 source bundle against its Windows-key registration."""
    r = read(registration)
    _v1_expected_fields(r)
    deps = _normalize_legacy_dependencies(r.get("dependencies"))
    bundle = Path(bundle)
    if not bundle.is_file():
        raise ValueError("legacy source bundle is required for an amendment")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        for key, digest in deps.items():
            name = "lunwen/" + key
            if name not in names or hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f"legacy bundle dependency mismatch: {key}")
        manifest_name = "lunwen/WINDOWS_BUNDLE_MANIFEST.json"
        if manifest_name not in names:
            raise ValueError("legacy bundle manifest missing")
        manifest = json.loads(archive.read(manifest_name))
        if manifest.get("schema") != "route_rl_windows_cpu_bundle_v1":
            raise ValueError("unexpected legacy bundle manifest schema")
    return r, deps


def legacy_identity_rows(material):
    result = []
    for row in material.get("slots", []):
        if row.get("status") != "generated" or not re.fullmatch(r"[0-9a-f]{64}", row.get("raw_sha256", "")) or not re.fullmatch(r"[0-9a-f]{64}", row.get("geometry_sha256", "")):
            raise ValueError("amendment requires the six generated v1 maps")
        result.append({key: row[key] for key in ("id", "split", "partition", "ordinal", "raw_sha256", "geometry_sha256")})
    if result != [{**slot, "raw_sha256": result[i]["raw_sha256"], "geometry_sha256": result[i]["geometry_sha256"]}
                  for i, slot in enumerate(slots())] or len(result) != 6:
        raise ValueError("legacy map identities/allocation mismatch")
    return result


def amend(path, namespace, updates, episodes, legacy_registration, legacy_materialization, legacy_bundle):
    """Bind v3 execution to the existing v1 six-map materialization, never replace it."""
    _check_namespace(namespace)
    require_v1_probe_exclusions()
    old, _ = verify_legacy_bundle(legacy_registration, legacy_bundle)
    material_path = Path(legacy_materialization) / "MATERIALIZATION.json"
    material = read(material_path)
    if material.get("schema") != LEGACY_SCHEMA or material.get("registration_sha256") != sha(legacy_registration):
        raise ValueError("legacy materialization registration receipt mismatch")
    identities = legacy_identity_rows(material)
    registration = {"schema": SCHEMA, "namespace": namespace, "family": [3, 20], "slots": slots(),
                    "seeds": list(SEEDS), "algorithms": list(ALGORITHMS), **_settings(updates, episodes),
                    "checkpoint_rule": "last completed update; no validation selection",
                    "author_profile": "J1b", "author_timeout_s": 180,
                    "author_seed_namespace": old["author_seed_namespace"],
                    "scenario_rule": "fixed-global-square-and-wind-v1", "budgets_s": [6, 12],
                    "original_cost_tolerance": 1e-7, "weather_cost_tolerance": 1e-7,
                    "dependencies": dependencies(), "materialization_mode": "v1_amendment_exact_six_maps_only",
                    "amendment": {"legacy_registration_sha256": sha(legacy_registration),
                                  "legacy_materialization_sha256": sha(material_path),
                                  "legacy_bundle_sha256": sha(legacy_bundle), "legacy_schema": LEGACY_SCHEMA,
                                  "map_identities": identities},
                    "status": "development_only_not_formal_no_replacement",
                    "execution_authorization": "user_authorized_<EXPERIMENT_SERVER>_weather_nfz_route_rl_development_20261104",
                    "map_generation_performed": True}
    write(path, registration)
    receipt = {"schema": "weather_common_map_development_v1_to_v3_amendment_v1",
               "amended_registration_sha256": sha(path), "legacy_registration_sha256": sha(legacy_registration),
               "legacy_materialization_sha256": sha(material_path), "legacy_bundle_sha256": sha(legacy_bundle),
               "map_identities": identities,
               "statement": "v3 is bound to the unchanged v1 materialization; no replacement map was generated or precommitted"}
    write(Path(path).with_name(Path(path).stem + ".AMENDMENT_RECEIPT.json"), receipt)
    return registration


def verify(registration):
    r = read(registration)
    expected = {"schema": SCHEMA, "family": [3, 20], "slots": slots(), "seeds": list(SEEDS),
                "algorithms": list(ALGORITHMS), "checkpoint_rule": "last completed update; no validation selection",
                "author_profile": "J1b", "author_timeout_s": 180,
                "scenario_rule": "fixed-global-square-and-wind-v1", "budgets_s": [6, 12],
                "original_cost_tolerance": 1e-7, "weather_cost_tolerance": 1e-7,
                "status": "development_only_not_formal_no_replacement",
                "execution_authorization": "user_authorized_<EXPERIMENT_SERVER>_weather_nfz_route_rl_development_20261104"}
    for field, value in expected.items():
        if r.get(field) != value:
            raise ValueError(f"unexpected registered field: {field}")
    _check_namespace(r.get("namespace"))
    mode = r.get("materialization_mode")
    if r.get("author_seed_namespace") != r["namespace"] + ":J1b" and mode != "v1_amendment_exact_six_maps_only":
        raise ValueError("unexpected author seed namespace")
    if r.get("dependencies") != dependencies() or any("\\" in key for key in r["dependencies"]):
        raise ValueError("frozen source/dependency hash mismatch")
    if _settings(r.get("updates"), r.get("episodes_per_update")) != {key: r.get(key) for key in ("updates", "episodes_per_update", "resource_limits", "training")}:
        raise ValueError("resource/training configuration mismatch")
    if mode not in ("new_generation_excludes_v1_probe_identities", "v1_amendment_exact_six_maps_only"):
        raise ValueError("unknown materialization mode")
    if mode == "new_generation_excludes_v1_probe_identities":
        if r.get("map_generation_performed") is not False or "amendment" in r:
            raise ValueError("new v3 registration may not claim an amendment/materialization")
    else:
        amendment = r.get("amendment")
        if r.get("map_generation_performed") is not True or not isinstance(amendment, dict):
            raise ValueError("amended v3 registration is missing its materialization receipt")
        required = ("legacy_registration_sha256", "legacy_materialization_sha256", "legacy_bundle_sha256")
        if amendment.get("legacy_schema") != LEGACY_SCHEMA or any(not re.fullmatch(r"[0-9a-f]{64}", amendment.get(key, "")) for key in required):
            raise ValueError("malformed amendment hashes")
        identities = amendment.get("map_identities")
        if not isinstance(identities, list) or len(identities) != 6 or [row.get("id") for row in identities] != [row["id"] for row in slots()]:
            raise ValueError("malformed amendment map identities")
        for row in identities:
            if set(row) != {"id", "split", "partition", "ordinal", "raw_sha256", "geometry_sha256"} or not re.fullmatch(r"[0-9a-f]{64}", row["raw_sha256"]) or not re.fullmatch(r"[0-9a-f]{64}", row["geometry_sha256"]):
                raise ValueError("malformed amendment map identity")
        if {(row["raw_sha256"], row["geometry_sha256"]) for row in identities} != V1_PROBE_IDENTITIES:
            raise ValueError("amendment does not bind the excluded Windows v1 map identities")
    require_v1_probe_exclusions()
    return r


def scenario(instance_hash):
    return {"schema": "weather_map_scenario_v1", "name": "fixed-global-square-and-wind-v1",
            "instance_sha256": instance_hash,
            "wind_knots": [{"time_s": 0, "east_mps": 1, "north_mps": 0},
                           {"time_s": 900, "east_mps": -1, "north_mps": 1},
                           {"time_s": 1800, "east_mps": 0, "north_mps": -1}],
            "no_fly_zone": {"vertices_m": [[6750, 6750], [7250, 6750], [7250, 7250], [6750, 7250]],
                            "on_s": 300, "off_s": 1200},
            "flight": {"speed_m_per_min": 900, "flight_energy_per_min": 0.018}}


def materialize(registration, out):
    r = verify(registration)
    if r["materialization_mode"] == "v1_amendment_exact_six_maps_only":
        raise ValueError("an amended v3 registration is bound to existing maps and cannot materialize replacements")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    exclusions = generator.load_required_exclusions()
    seen_raw, seen_geometry = set(), set()
    ledger = []
    for slot in r["slots"]:
        started = time.perf_counter()
        d = out / slot["id"]
        d.mkdir()
        try:
            row = generator.generate_allocated_instance(3, 20, namespace=r["namespace"],
                        partition=slot["partition"], ordinal=slot["ordinal"], exclusions=exclusions)
        except Exception as error:
            row = {"status": "generation_exception", "failure_reason": f"{type(error).__name__}: {error}",
                   "raw_sha256": None, "canonical_geometry_sha256": None}
        if row["status"] == "generated" and (row["raw_sha256"] in seen_raw or row["canonical_geometry_sha256"] in seen_geometry):
            row["status"], row["failure_reason"] = "generation_failed", "within_allocation_identity_collision"
        if row["raw_sha256"] is not None:
            seen_raw.add(row["raw_sha256"])
        if row["canonical_geometry_sha256"] is not None:
            seen_geometry.add(row["canonical_geometry_sha256"])
        write(d / "generation.json", row)
        if row["status"] == "generated":
            (d / "instance.txt").write_text(row["solver_input_text"], encoding="utf-8", newline="\n")
            if sha(d / "instance.txt") != row["raw_sha256"]:
                raise RuntimeError("instance byte identity mismatch")
            write(d / "scenario.json", scenario(row["raw_sha256"]))
        ledger.append({**slot, "status": row["status"], "reason": row["failure_reason"],
                       "raw_sha256": row["raw_sha256"], "geometry_sha256": row["canonical_geometry_sha256"],
                       "elapsed_s": time.perf_counter() - started})
    write(out / "MATERIALIZATION.json", {"schema": SCHEMA, "registration_sha256": sha(registration), "slots": ledger})


def validate_materialization(registration, out):
    r = verify(registration)
    material = read(Path(out) / "MATERIALIZATION.json")
    if r["materialization_mode"] == "v1_amendment_exact_six_maps_only":
        amendment = r.get("amendment")
        if not isinstance(amendment, dict) or sha(Path(out) / "MATERIALIZATION.json") != amendment.get("legacy_materialization_sha256"):
            raise ValueError("amended v3 materialization receipt mismatch")
        if material.get("schema") != LEGACY_SCHEMA or material.get("registration_sha256") != amendment.get("legacy_registration_sha256"):
            raise ValueError("amended v3 legacy materialization provenance mismatch")
        if legacy_identity_rows(material) != amendment.get("map_identities"):
            raise ValueError("amended v3 map identities changed")
    elif material["registration_sha256"] != sha(registration):
        raise ValueError("registration changed since materialization")
    if [row["id"] for row in material["slots"]] != [row["id"] for row in r["slots"]]:
        raise ValueError("materialization slot identity mismatch")
    for row in material["slots"]:
        d = Path(out) / row["id"]
        g = read(d / "generation.json")
        if g["status"] != row["status"] or g["raw_sha256"] != row["raw_sha256"]:
            raise ValueError("generation receipt mismatch")
        if row["status"] == "generated":
            if sha(d / "instance.txt") != row["raw_sha256"]:
                raise ValueError("instance hash mismatch")
            if read(d / "scenario.json") != scenario(row["raw_sha256"]):
                raise ValueError("scenario mismatch")
    return r, material


def anchors(registration, out, java_home, build_dir):
    r, material = validate_materialization(registration, out)
    out = Path(out).resolve()
    if (out / "ANCHORS.json").exists():
        raise FileExistsError("anchor batch already exists")
    author_runner.verify_build(REPRO, "J1b", Path(java_home), Path(build_dir))
    rows = []
    for slot in material["slots"]:
        row = {"id": slot["id"], "status": slot["status"], "reason": slot["reason"]}
        started = time.perf_counter()
        d = out / slot["id"]
        if row["status"] == "generated":
            try:
                seed = author_runner.seed_for_input(slot["raw_sha256"], r["author_seed_namespace"])
                result = author_runner.run_one(d / "instance.txt", "J1b", seed, d / "author", REPRO,
                                               RM / "scorer.py", Path(java_home), Path(build_dir), 180)
                row.update(author_seed=seed, author_status=result["status"])
                if not result["anchor_eligible"]:
                    raise ValueError("author_anchor_ineligible")
                receipt = prepare_author_weather_anchor(d / "instance.txt", d / "author", d / "scenario.json")
                write(d / "weather_anchor.json", receipt)
                row.update(status="eligible", reason=None,
                           artifact_hashes={str(p.relative_to(d)): sha(p) for p in
                                            (d / "weather_anchor.json", d / "author/RUN.json",
                                             d / "author/solution.json", d / "scenario.json")})
            except Exception as error:
                row.update(status="anchor_failed", reason=f"{type(error).__name__}: {error}")
        row["elapsed_s"] = time.perf_counter() - started
        rows.append(row)
    write(out / "ANCHORS.json", {"schema": SCHEMA, "registration_sha256": sha(registration), "slots": rows})


def import_anchors(registration, out, source_registration, source_out,
                   expected_source_registration_sha256, expected_source_anchors_sha256):
    """Import existing author executions with explicit immutable v2 provenance.

    No solver is invoked. All six rows, including failures, and every source
    output outside its experiment subdirectory are retained byte-for-byte.
    Only a new v3 ledger is written; the v2 ledger is preserved separately.
    """
    source_out, out = Path(source_out).resolve(), Path(out).resolve()
    if sha(source_registration) != expected_source_registration_sha256:
        raise ValueError("source registration hash mismatch")
    if sha(source_out / "ANCHORS.json") != expected_source_anchors_sha256:
        raise ValueError("source anchor ledger hash mismatch")
    r, material = validate_materialization(registration, source_out)
    source = read(source_registration)
    ledger = read(source_out / "ANCHORS.json")
    if source.get("schema") != "weather_common_map_development_v2" or ledger.get("schema") != source["schema"]:
        raise ValueError("only frozen v2 author executions can be imported")
    if ledger.get("registration_sha256") != expected_source_registration_sha256:
        raise ValueError("source anchor registration mismatch")
    physics_names = {"weather_author_anchor.py", "weather_scenario_io.py", "weather_full_map.py",
                     "weather_oracle.py", "weather_replay.py", "scorer.py", "problem.py",
                     "evaluator.py", "author_runner.py"}
    for key, digest in r["dependencies"].items():
        if Path(key).name in physics_names and source.get("dependencies", {}).get(key) != digest:
            raise ValueError(f"source physics/author dependency mismatch: {key}")
    if source.get("amendment") != r.get("amendment") or source.get("author_seed_namespace") != r["author_seed_namespace"]:
        raise ValueError("source materialization/author seed provenance mismatch")
    if [row["id"] for row in ledger["slots"]] != [row["id"] for row in material["slots"]]:
        raise ValueError("source anchor allocation mismatch")
    for row in ledger["slots"]:
        for relative, digest in row.get("artifact_hashes", {}).items():
            if sha(source_out / row["id"] / relative) != digest:
                raise ValueError(f"source anchor artifact hash mismatch: {row['id']}/{relative}")
    inventory = {}
    for path in sorted(source_out.rglob("*")):
        relative = path.relative_to(source_out)
        if relative.parts[0] == "experiment":
            continue
        if path.is_symlink():
            raise ValueError("source import rejects symbolic links")
        if path.is_file():
            inventory[relative.as_posix()] = sha(path)
    out.mkdir(parents=True, exist_ok=False)
    for relative, digest in inventory.items():
        target = out / ("SOURCE_ANCHORS.v2.json" if relative == "ANCHORS.json" else relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_out / relative, target)
        if sha(target) != digest:
            raise RuntimeError("imported artifact byte identity mismatch")
    receipt = {"schema": "weather_author_v2_to_v3_import_v1",
               "source_registration_sha256": expected_source_registration_sha256,
               "source_anchors_sha256": expected_source_anchors_sha256,
               "target_registration_sha256": sha(registration),
               "source_materialization_sha256": sha(source_out / "MATERIALIZATION.json"),
               "source_files": inventory, "author_solver_calls": 0,
               "source_registration": source}
    write(out / "ANCHOR_IMPORT_RECEIPT.json", receipt)
    write(out / "ANCHORS.json", {"schema": SCHEMA, "registration_sha256": sha(registration),
                                  "slots": ledger["slots"],
                                  "import_receipt_sha256": sha(out / "ANCHOR_IMPORT_RECEIPT.json")})
    validate_materialization(registration, out)
    return receipt


def model_state_digest(model):
    """Content identity independent of torch checkpoint container metadata."""
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        value = value.detach().cpu().contiguous()
        digest.update(canonical_json([name, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def load_case(directory):
    directory = Path(directory)
    instance = read_instance(directory / "instance.txt")
    solution = read(directory / "author/solution.json")
    anchor = CostAnchor.from_solution(instance, solution)
    weather, _ = load_weather_scenario(directory / "scenario.json", expected_instance_sha256=instance.sha256)
    receipt = read(directory / "weather_anchor.json")
    return instance, anchor, weather, receipt["weather_cost_cap"]


def run_episode(case, model=None, *, stochastic=False, deadline=None, max_steps=None):
    import torch
    from rl_algorithms import masked_policy_distribution
    from run_full_map_smoke import failure_reward_penalty
    start = time.perf_counter()
    env = WeatherFullMapEnv(*case[:3], weather_cost_cap=case[3])
    events, transitions = [], []
    while not env.terminated:
        if deadline is not None and time.perf_counter() - start >= deadline:
            return {"complete": False, "failure": "deadline", "events": events,
                    "transitions": transitions, "elapsed_s": time.perf_counter() - start}
        if max_steps is not None and len(events) >= max_steps:
            return {"complete": False, "failure": "step_limit", "events": events,
                    "transitions": transitions, "elapsed_s": time.perf_counter() - start}
        obs = env.observation()
        legal = [i for i, allowed in enumerate(obs["mask"]) if allowed]
        if model is None:
            targets = [i for i in legal if not obs["actions"][i].is_return]
            index = min(targets, key=lambda i: (float(obs["candidates"][i, 5]), i)) if targets else legal[0]
            value = old_logp = 0.0
        else:
            with torch.no_grad():
                dist, v = masked_policy_distribution(model, obs)
                index = int(dist.sample().item()) if stochastic else int(torch.argmax(dist.logits))
                old_logp = float(dist.log_prob(torch.tensor(index)).item()); value = float(v)
        a = obs["actions"][index]
        _, reward, done, info = env.step(a)
        if info["failure"] is not None:
            reward -= failure_reward_penalty(env.instance)
        transitions.append({"global": obs["global"], "candidates": obs["candidates"], "mask": obs["mask"],
                            "action": index, "reward": reward, "done": done, "value": value, "old_logp": old_logp})
        events.append({"station_idx": a.station_idx, "slot": a.slot,
                       "target": "RETURN" if a.is_return else a.target_id, "reward": reward,
                       "completion_min": info.get("completion_min"), "failure": info["failure"],
                       "elapsed_s": time.perf_counter() - start})
    elapsed = time.perf_counter() - start
    complete = env.done and env.failure is None and (deadline is None or elapsed <= deadline)
    return {"complete": complete, "failure": env.failure if elapsed <= (deadline or float("inf")) else "deadline",
            "events": events, "transitions": transitions, "elapsed_s": elapsed,
            "result": env.result() if complete else None}


def author_demonstration(case, solution, *, deadline=None, max_steps=None):
    """Encode a weather-admissible author route as masked physical actions.

    Route ordering comes only from the supplied author solution.  At every
    prefix the environment reconstructs its current action table and rejects
    the demonstration if the next target or RETURN is not a legal physical
    action under the fixed forecast, caps, and battery/duty constraints.
    """
    from weather_full_map import WeatherMapAction
    start = time.perf_counter()
    env = WeatherFullMapEnv(*case[:3], weather_cost_cap=case[3])
    events, transitions = [], []

    def take(expected):
        if deadline is not None and time.perf_counter() - start >= deadline:
            raise TimeoutError("demonstration_deadline")
        if max_steps is not None and len(events) >= max_steps:
            raise RuntimeError("demonstration_step_limit")
        observation = env.observation()
        matches = [index for index, action in enumerate(observation["actions"]) if action == expected]
        if len(matches) != 1 or not bool(observation["mask"][matches[0]]):
            raise ValueError(f"author demonstration action is not legal: {expected}")
        index = matches[0]
        _, reward, _done, info = env.step(expected)
        if info["failure"] is not None:
            raise ValueError(f"author demonstration reached {info['failure']}")
        transitions.append({"global": observation["global"], "candidates": observation["candidates"],
                            "mask": observation["mask"], "action": index})
        events.append({"station_idx": expected.station_idx, "slot": expected.slot,
                       "target": "RETURN" if expected.is_return else expected.target_id,
                       "reward": reward, "completion_min": info.get("completion_min"),
                       "failure": info["failure"], "elapsed_s": time.perf_counter() - start})

    routes = solution.get("routes") if isinstance(solution, dict) else None
    if not isinstance(routes, list) or len(routes) != len(env.instance.stations):
        raise ValueError("author demonstration has invalid route dimensions")
    for station_idx, station_routes in enumerate(routes):
        if not isinstance(station_routes, list) or len(station_routes) != 2:
            raise ValueError(f"author demonstration has invalid slot dimensions: {station_idx}")
        for slot, trips in enumerate(station_routes):
            if not isinstance(trips, list):
                raise ValueError(f"author demonstration has invalid trips: {station_idx}:{slot}")
            for trip in trips:
                if not isinstance(trip, list) or not trip:
                    raise ValueError(f"author demonstration has invalid trip: {station_idx}:{slot}")
                for target_id in trip:
                    take(WeatherMapAction(station_idx, slot, target_id))
                take(WeatherMapAction(station_idx, slot))
    elapsed = time.perf_counter() - start
    if not env.done or env.failure is not None:
        raise ValueError(f"author demonstration did not complete: {env.failure}")
    if deadline is not None and elapsed > deadline:
        raise TimeoutError("demonstration_deadline")
    return {"complete": True, "failure": None, "events": events, "transitions": transitions,
            "elapsed_s": elapsed, "result": env.result()}


def select_timed_result(episode, anchor, elapsed, budget):
    """Do not report an output delivered on time when a cooperative call overran."""
    if elapsed > budget:
        return {"status": "deadline_missed", "selected": None, "selected_score": None}
    if anchor is None:
        return {"status": "fallback_unavailable", "selected": None, "selected_score": None}
    improves = episode["complete"] and episode["result"]["replay"]["M_return"] < anchor["M_return"]
    return {"status": "delivered", "selected": "candidate" if improves else "author_anchor",
            "selected_score": episode["result"]["replay"] if improves else anchor}


def apply_runtime_limits():
    """Apply and verify the one-CPU execution contract before training/evaluation."""
    import torch
    notices = []
    try:
        torch.set_num_threads(RESOURCE_LIMITS["cpu_threads"])
    except RuntimeError as error:
        notices.append(f"set_num_threads:{type(error).__name__}: {error}")
    try:
        torch.set_num_interop_threads(RESOURCE_LIMITS["cpu_threads"])
    except RuntimeError as error:
        notices.append(f"set_num_interop_threads:{type(error).__name__}: {error}")
    actual = {"torch_threads": torch.get_num_threads(),
              "torch_interop_threads": torch.get_num_interop_threads(),
              "environment": {name: os.environ.get(name) for name in
                              ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                               "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}}
    if actual["torch_threads"] != 1 or actual["torch_interop_threads"] != 1:
        raise RuntimeError(f"one-CPU runtime limit was not applied: {actual}")
    return {**actual, "notices": notices}


def beam_episode(case, deadline, max_steps):
    """Optional physical-route baseline; missing code is a recorded comparison failure."""
    try:
        from physical_baselines import beam_construct
    except ImportError as error:
        return {"complete": False, "failure": f"beam_baseline_unavailable: {error}",
                "events": [], "transitions": [], "elapsed_s": 0.0}
    episode = beam_construct(case, deadline, width=16)
    if not isinstance(episode, dict):
        raise ValueError("beam_construct must return a route episode dictionary")
    episode.setdefault("transitions", [])
    episode.setdefault("events", [])
    episode.setdefault("elapsed_s", 0.0)
    if len(episode["events"]) > max_steps:
        episode.update(complete=False, failure="step_limit", result=None)
    return episode


def experiment(registration, out):
    import numpy as np
    import torch
    from weather_policy import WeatherPointerActorCritic
    from rl_algorithms import (a2c_update, behavior_clone_update, ppo_update,
                               reinforce_update)
    from run_full_map_smoke import _seed
    r, material = validate_materialization(registration, out)
    out = Path(out).resolve()
    anchor_rows = read(out / "ANCHORS.json")
    if anchor_rows["registration_sha256"] != sha(registration):
        raise ValueError("anchor registration mismatch")
    if [x["id"] for x in anchor_rows["slots"]] != [x["id"] for x in material["slots"]]:
        raise ValueError("anchor allocation mismatch")
    for row in anchor_rows["slots"]:
        if row["status"] == "eligible":
            for name, expected in row["artifact_hashes"].items():
                if sha(out / row["id"] / name) != expected:
                    raise ValueError(f"anchor artifact changed: {row['id']}/{name}")
    results_dir = out / "experiment"
    results_dir.mkdir(exist_ok=False)
    split = {x["id"]: x["split"] for x in material["slots"]}
    eligible = [x["id"] for x in anchor_rows["slots"] if x["status"] == "eligible"]
    cases = {name: load_case(out / name) for name in eligible}
    train_ids = [name for name in eligible if split[name] == "train"]
    runtime_limits = apply_runtime_limits()
    report = {"schema": SCHEMA, "scope": "development only; no formal, best-method, novelty, or strong-baseline claim",
              "registration_sha256": sha(registration), "anchor_ledger": anchor_rows["slots"],
              "runtime": {"python": sys.version, "platform": platform.platform(),
                          "numpy": np.__version__, "torch": str(torch.__version__),
                          "limits": runtime_limits}, "frozen_settings": {
                              "updates": r["updates"], "episodes_per_update": r["episodes_per_update"],
                              "resource_limits": r["resource_limits"], "training": r["training"]},
              "training": [], "controls": [], "comparisons": []}
    replace_json(results_dir / "RESULTS.partial.json", report)

    def persist():
        replace_json(results_dir / "RESULTS.partial.json", report)

    if not train_ids:
        report["status"] = "no_eligible_training_maps"
        write(results_dir / "RESULTS.json", report)
        return
    demonstrations, demonstration_receipts = [], []
    demonstration_started = time.perf_counter()
    demonstration_count = 0
    try:
        for map_id in train_ids:
            solution_path = out / map_id / "author/solution.json"
            demonstration = author_demonstration(
                cases[map_id], read(solution_path),
                max_steps=r["resource_limits"]["max_episode_steps"],
                deadline=max(0.0, r["resource_limits"]["train_wall_s_per_algorithm_seed"]
                             - (time.perf_counter() - demonstration_started)),
            )
            demonstrations.append(demonstration)
            demonstration_count += len(demonstration["transitions"])
            demonstration_receipts.append({"map": map_id, "solution_sha256": sha(solution_path),
                                           "action_count": len(demonstration["transitions"]),
                                           "events": demonstration["events"],
                                           "replay": demonstration["result"]["replay"]})
            if demonstration_count > r["resource_limits"]["max_demonstration_transitions"]:
                raise RuntimeError("demonstration_transition_limit")
        report["demonstrations"] = {"mode": "eligible_train_author_weather_anchor_behavior_cloning_v1",
                                    "status": "ok", "transition_count": demonstration_count,
                                    "records": demonstration_receipts,
                                    "elapsed_s": time.perf_counter() - demonstration_started}
    except Exception as error:
        report["demonstrations"] = {"status": "failed", "transition_count": demonstration_count,
                                    "records": demonstration_receipts,
                                    "elapsed_s": time.perf_counter() - demonstration_started,
                                    "error": f"{type(error).__name__}: {error}"}
        report["status"] = "demonstration_failed"
        write(results_dir / "DEMONSTRATIONS.json", report["demonstrations"])
        persist()
        write(results_dir / "RESULTS.json", report)
        return
    write(results_dir / "DEMONSTRATIONS.json", report["demonstrations"])
    demo_sha = sha(results_dir / "DEMONSTRATIONS.json")
    demo_elapsed = report["demonstrations"]["elapsed_s"]
    report["demonstration_receipt_sha256"] = demo_sha
    report["shared_demonstration_construction_s"] = demo_elapsed
    # Charge the full shared demo preparation to each train run conservatively.
    # The observed once-only cost remains separately reported for total accounting.
    bc_controls = {}
    persist()
    for algorithm in r["algorithms"]:
        for seed in r["seeds"]:
            started = time.perf_counter()
            _seed(seed)
            model = WeatherPointerActorCritic(global_dim=WeatherFullMapEnv.global_dim,
                                              candidate_dim=WeatherFullMapEnv.candidate_dim)
            optimizer = torch.optim.Adam(model.parameters(), lr=r["training"]["learning_rate"])
            history = []; total_transitions = 0
            checkpoint = results_dir / f"{algorithm.lower()}_{seed}_last.pt"
            record_path = results_dir / f"training_{algorithm.lower()}_{seed}.json"
            record = {"status": "running", "algorithm": algorithm, "seed": seed,
                      "train_ids": train_ids, "history": history, "total_transitions": total_transitions,
                      "warm_start": None, "training_regime": f"BC+{algorithm}",
                      "demonstration_receipt_sha256": demo_sha,
                      "demonstration_transition_count": demonstration_count,
                      "demonstration_preparation_s_charged": demo_elapsed,
                      "frozen_settings": {"updates": r["updates"], "episodes_per_update": r["episodes_per_update"],
                                          "resource_limits": r["resource_limits"], "training": r["training"]}}
            try:
                record["warm_start"] = behavior_clone_update(
                    model, optimizer, demonstrations,
                    epochs=r["training"]["behavior_clone_epochs"],
                    minibatch=r["training"]["behavior_clone_minibatch"],
                    max_grad=r["training"]["max_grad"],
                    rng=random.Random(seed * 1000003 + 19),
                    deadline=max(0.0, r["resource_limits"]["train_wall_s_per_algorithm_seed"]
                                 - demo_elapsed - (time.perf_counter() - started)),
                )
                state_digest = model_state_digest(model)
                if seed not in bc_controls:
                    bc_checkpoint = results_dir / f"bc_{seed}_only.pt"
                    torch.save({"state_dict": model.state_dict(), "global_dim": WeatherFullMapEnv.global_dim,
                                "candidate_dim": WeatherFullMapEnv.candidate_dim, "hidden_dim": model.hidden_dim,
                                "algorithm": "BC", "seed": seed, "training_regime": "BC-only",
                                "demonstration_receipt_sha256": demo_sha,
                                "state_dict_sha256": state_digest}, bc_checkpoint)
                    control = {"status": "ok", "algorithm": "BC", "seed": seed,
                               "training_regime": "BC-only", "train_ids": train_ids,
                               "checkpoint": bc_checkpoint.name, "checkpoint_sha256": sha(bc_checkpoint),
                               "state_dict_sha256": state_digest, "warm_start": record["warm_start"],
                               "demonstration_receipt_sha256": demo_sha,
                               "demonstration_transition_count": demonstration_count,
                               "elapsed_s": time.perf_counter() - started,
                               "demonstration_preparation_s_charged": demo_elapsed,
                               "online_rl_updates": 0}
                    bc_controls[seed] = control
                    report["controls"].append(control)
                    write(results_dir / f"bc_{seed}_only.json", control)
                elif bc_controls[seed]["state_dict_sha256"] != state_digest:
                    raise RuntimeError("BC initialization differs across matched algorithms")
                record.update(bc_control_checkpoint=bc_controls[seed]["checkpoint"],
                              bc_control_checkpoint_sha256=bc_controls[seed]["checkpoint_sha256"],
                              bc_state_dict_sha256=state_digest,
                              matched_bc_initialization_verified=True)
                persist()
                for update in range(r["updates"]):
                    if time.perf_counter() - started + demo_elapsed >= r["resource_limits"]["train_wall_s_per_algorithm_seed"]:
                        raise TimeoutError("train_wall_limit")
                    episodes = []
                    for i in range(r["episodes_per_update"]):
                        remaining = r["resource_limits"]["train_wall_s_per_algorithm_seed"] - demo_elapsed - (time.perf_counter() - started)
                        if remaining <= 0:
                            raise TimeoutError("train_wall_limit")
                        map_id = train_ids[(update * r["episodes_per_update"] + i) % len(train_ids)]
                        episode = run_episode(cases[map_id], model, stochastic=True, deadline=remaining,
                                              max_steps=r["resource_limits"]["max_episode_steps"])
                        episode["map"] = map_id
                        episodes.append(episode)
                    batch = [e for e in episodes if e["transitions"]]
                    next_transitions = total_transitions + sum(len(e["transitions"]) for e in episodes)
                    if next_transitions > r["resource_limits"]["max_transitions_per_run"]:
                        raise RuntimeError("transition_limit")
                    total_transitions = next_transitions
                    stats = ({"skipped_no_transitions": True} if not batch else
                             ppo_update(model, optimizer, batch, epochs=r["training"]["ppo_epochs"],
                                        minibatch=r["training"]["ppo_minibatch"], gamma=r["training"]["gamma"],
                                        lam=r["training"]["gae_lambda"], entropy_coef=r["training"]["entropy_coef"],
                                        max_grad=r["training"]["max_grad"], rng=random.Random(seed * 1000 + update)) if algorithm == "PPO" else
                             a2c_update(model, optimizer, batch, gamma=r["training"]["gamma"],
                                        lam=r["training"]["gae_lambda"], entropy_coef=r["training"]["entropy_coef"],
                                        max_grad=r["training"]["max_grad"]) if algorithm == "A2C" else
                             reinforce_update(model, optimizer, batch, gamma=r["training"]["gamma"],
                                              entropy_coef=r["training"]["entropy_coef"], max_grad=r["training"]["max_grad"]))
                    entry = {"update": update, "episodes": [{k: v for k, v in e.items() if k != "transitions"}
                                                               for e in episodes], "stats": stats,
                             "elapsed_s": time.perf_counter() - started, "total_transitions": total_transitions}
                    history.append(entry)
                    torch.save({"state_dict": model.state_dict(), "global_dim": WeatherFullMapEnv.global_dim,
                                "candidate_dim": WeatherFullMapEnv.candidate_dim, "hidden_dim": model.hidden_dim,
                                "algorithm": algorithm, "seed": seed, "training_regime": f"BC+{algorithm}",
                                "demonstration_receipt_sha256": demo_sha,
                                "bc_state_dict_sha256": state_digest, "last_completed_update": update,
                                "frozen_settings": record["frozen_settings"]}, checkpoint)
                    record.update(history=history, total_transitions=total_transitions,
                                  last_completed_update=update, checkpoint=checkpoint.name,
                                  checkpoint_sha256=sha(checkpoint), elapsed_s=time.perf_counter() - started)
                    replace_json(record_path, record)
                    append_jsonl(results_dir / "TRAINING_UPDATES.jsonl", {"algorithm": algorithm, "seed": seed, "training_regime": f"BC+{algorithm}",
                                                                        "demonstration_receipt_sha256": demo_sha, **entry})
                    persist()
                if total_transitions == 0:
                    raise RuntimeError("no_trainable_transitions")
                if time.perf_counter() - started + demo_elapsed > r["resource_limits"]["train_wall_s_per_algorithm_seed"]:
                    raise TimeoutError("train_wall_limit")
                record["status"] = "ok"
            except BaseException as error:
                record.update(status="training_failed", error=f"{type(error).__name__}: {error}")
            record.update(elapsed_s=time.perf_counter() - started,
                          charged_training_wall_s=time.perf_counter() - started + demo_elapsed,
                          history=history, total_transitions=total_transitions)
            report["training"].append(record)
            replace_json(record_path, record)
            append_jsonl(results_dir / "TRAINING_FINAL.jsonl", record)
            persist()
    for row in material["slots"]:
        if row["split"] == "train":
            continue
        name = row["id"]
        if name not in cases:
            report["comparisons"].append({"map": name, "status": "anchor_or_generation_failed"})
            continue
        for budget in r["budgets_s"]:
            methods = [("physical_greedy", None), ("physical_beam_optional", "beam")] + [(f"BC-only_{t['seed']}", t) for t in report["controls"]] + [(f"BC+{t['algorithm']}_{t['seed']}", t) for t in report["training"]]
            for method, trained in methods:
                started = time.perf_counter()
                anchor = None
                fallback_ready_s = None
                try:
                    case = load_case(out / name)
                    solution = read(out / name / "author/solution.json")
                    verified_anchor = replay_weather_solution(*case[:3], solution, weather_cost_cap=case[3])
                    if not verified_anchor["admissible"]:
                        raise ValueError("independent author fallback replay failed")
                    if json.loads(json.dumps(verified_anchor, allow_nan=False)) != read(out / name / "weather_anchor.json")["author_weather_replay"]:
                        raise ValueError("independent author fallback replay differs from receipt")
                    anchor = verified_anchor
                    fallback_ready_s = time.perf_counter() - started
                    model = None
                    if trained == "beam":
                        remaining = budget - (time.perf_counter() - started)
                        episode = beam_episode(case, max(0, remaining), r["resource_limits"]["max_episode_steps"])
                    elif trained:
                        if trained["status"] != "ok":
                            raise RuntimeError("training_failed")
                        if sha(results_dir / trained["checkpoint"]) != trained["checkpoint_sha256"]:
                            raise RuntimeError("checkpoint_hash_mismatch")
                        ckpt = torch.load(results_dir / trained["checkpoint"], map_location="cpu", weights_only=True)
                        model = WeatherPointerActorCritic(global_dim=ckpt["global_dim"],
                                                         candidate_dim=ckpt["candidate_dim"], hidden_dim=ckpt["hidden_dim"])
                        model.load_state_dict(ckpt["state_dict"], strict=True)
                        remaining = budget - (time.perf_counter() - started)
                        episode = run_episode(case, model, deadline=max(0, remaining),
                                              max_steps=r["resource_limits"]["max_episode_steps"])
                    else:
                        remaining = budget - (time.perf_counter() - started)
                        episode = run_episode(case, model, deadline=max(0, remaining),
                                              max_steps=r["resource_limits"]["max_episode_steps"])
                    episode.pop("transitions")
                except Exception as error:
                    episode = {"complete": False, "failure": f"{type(error).__name__}: {error}", "events": []}
                total = time.perf_counter() - started
                if total > budget:
                    episode.update(complete=False, failure="deadline", result=None)
                selection = select_timed_result(episode, anchor, total, budget)
                comparison = {"map": name, "split": row["split"], "budget_s": budget,
                    "method": method,
                    "training_regime": trained.get("training_regime") if isinstance(trained, dict) else "nonRL",
                    "demonstration_receipt_sha256": trained.get("demonstration_receipt_sha256") if isinstance(trained, dict) else None,
                    "demonstration_transition_count": trained.get("demonstration_transition_count") if isinstance(trained, dict) else 0,
                    "checkpoint_sha256": trained.get("checkpoint_sha256") if isinstance(trained, dict) else None,
                    "elapsed_total_s": total, "anchor": anchor,
                    "fallback_ready_s": fallback_ready_s, "candidate": episode, **selection}
                report["comparisons"].append(comparison)
                append_jsonl(results_dir / "COMPARISONS.jsonl", comparison)
                persist()
    report["status"] = "completed"
    write(results_dir / "RESULTS.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("register"); p.add_argument("--registration", required=True); p.add_argument("--namespace", required=True)
    p.add_argument("--updates", type=int, default=4); p.add_argument("--episodes", type=int, default=2)
    p = sub.add_parser("amend"); p.add_argument("--registration", required=True); p.add_argument("--namespace", required=True)
    p.add_argument("--updates", type=int, default=4); p.add_argument("--episodes", type=int, default=2)
    p.add_argument("--legacy-registration", required=True); p.add_argument("--legacy-materialization", required=True)
    p.add_argument("--legacy-bundle", required=True)
    p = sub.add_parser("import-anchors")
    p.add_argument("--registration", required=True); p.add_argument("--out", required=True)
    p.add_argument("--source-registration", required=True); p.add_argument("--source-out", required=True)
    p.add_argument("--expected-source-registration-sha256", required=True)
    p.add_argument("--expected-source-anchors-sha256", required=True)
    for name in ("materialize", "anchors", "experiment"):
        p = sub.add_parser(name); p.add_argument("--registration", required=True); p.add_argument("--out", required=True)
        if name == "anchors":
            p.add_argument("--java-home", required=True); p.add_argument("--build-dir", required=True)
    a = parser.parse_args()
    if a.command == "register": register(a.registration, a.namespace, a.updates, a.episodes)
    elif a.command == "amend": amend(a.registration, a.namespace, a.updates, a.episodes,
                                      a.legacy_registration, a.legacy_materialization, a.legacy_bundle)
    elif a.command == "import-anchors": import_anchors(a.registration, a.out, a.source_registration, a.source_out,
                                                         a.expected_source_registration_sha256,
                                                         a.expected_source_anchors_sha256)
    elif a.command == "materialize": materialize(a.registration, a.out)
    elif a.command == "anchors": anchors(a.registration, a.out, a.java_home, a.build_dir)
    else: experiment(a.registration, a.out)


if __name__ == "__main__":
    main()
