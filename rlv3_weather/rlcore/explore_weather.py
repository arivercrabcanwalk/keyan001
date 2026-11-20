"""Reproducible, non-formal fixed-wind route-learning exploration.

Run from ``rlv3_weather`` with::

    python -m rlcore.explore_weather --out /absolute/new/run --seed 103 --device cpu --profile quick

The population is freshly generated and split by base map, before both paired
wind conditions are attached. No emergency jobs or historical instance files
enter this experiment. References are a published-parameter, same-wind feasible
singleton heuristic implemented here, NOT an original-author solve. Their costs
are exploratory caps; neither these data nor this CLI change project G0/G3 gates.
Joint/serial BC and terminal PG reuse the existing physical action implementation.
Validation and test never supply gradients or select checkpoints/hyperparameters.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import random
import sys
import time
import traceback


SCHEMA = "rlv3-exploratory-fixed-wind-v1"
SCENARIOS = ("fixed_e4", "fixed_n8")
REFERENCE_SOURCE = "fresh_same_wind_singleton_load_balance_v1_not_original_author"
CORPUS_SEED = 20261120  # Fixed across independent policy-training seeds.


@dataclass(frozen=True)
class Profile:
    train_maps: int
    val_maps: int
    test_maps: int
    station_types: tuple[int, ...]
    targets_per_station: tuple[int, int]
    bc_epochs: int
    pg_steps: int
    rollouts: int
    lr: float
    wall_seconds: int


# Fixed before data generation; no outcome-driven size or optimizer adjustment.
PROFILES = {
    "quick": Profile(6, 2, 4, (2, 1, 2), (4, 6), 3, 8, 4, 0.0005, 600),
    "standard": Profile(32, 8, 16, (2, 1, 2, 1), (8, 12), 8, 48, 4, 0.0003, 7200),
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def _seed(seed, *parts):
    return int.from_bytes(sha256(_canonical([seed, *parts])).digest()[:8], "big") % (2**63 - 1)


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical(value) + b"\n")
    temporary.replace(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path, rows):
    with Path(path).open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(_canonical(row).decode("utf-8") + "\n")
    with Path(path).open(encoding="utf-8") as stream:
        reopened = [json.loads(line) for line in stream]
    if len(reopened) != len(rows):
        raise RuntimeError("persisted row denominator changed")


def _fresh_map(path, *, seed, station_types, targets_per_station):
    """Generate separated station territories with heterogeneous task demands.

    Every target is within 1600 m of its assigned station; station separation is
    at least 9000 m. This preserves a fixed target-to-station assignment without
    relying on reference visit rank or reference slot labels as policy features.
    Coordinates, loads and service times vary continuously under an isolated RNG.
    """
    rng = random.Random(seed)
    stations = [(100000 + index, 1000.0 + 10000.0 * (index % 2),
                 1000.0 + 10000.0 * (index // 2), 0.0, 0.0)
                for index in range(len(station_types))]
    rows, ownership = [], {}
    tid = 1
    for si, kind in enumerate(station_types):
        station = stations[si]
        count = rng.randint(*targets_per_station)
        for j in range(count):
            angle = rng.uniform(0, 2 * math.pi)
            radius = rng.uniform(200, 1600)
            # Some DABS jobs are LD-only; SABS jobs remain singleton-feasible.
            energy = rng.uniform(.80, .85) if kind == 2 and j == 0 else rng.uniform(.12, .24)
            rows.append((tid, station[1] + radius * math.cos(angle),
                         station[2] + radius * math.sin(angle), energy,
                         rng.uniform(6.0, 14.0)))
            ownership[tid] = si
            tid += 1
    text = "CUST_NO X Y ENERGY SERVICE\n" + "".join(
        f"{nid} {x:.6f} {y:.6f} {energy:.9f} {service:.6f}\n"
        for nid, x, y, energy, service in [*rows, *stations])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    if Path(path).read_text(encoding="utf-8") != text:
        raise RuntimeError("map bytes changed after write")
    return ownership


def _singleton_reference(path, ownership, station_types, scenario):
    """Construct and independently audit one same-wind feasible reference.

    Longest singleton-duty jobs are assigned first to the least loaded feasible
    slot at their fixed station. Every target has its own explicit returned trip;
    cumulative duty is never reset. There is no search budget or claim to author
    TSALNS parity. Both wind conditions rebuild slot assignments from scratch.
    """
    from .common import load_ins
    from .fixed_anchor import _leg, _wind, audit_fixed_anchor, ENERGY_EPS
    from lrphsd.problem import empty_solution

    instance = load_ins(str(Path(path).resolve()))
    solution = empty_solution(instance, station_types)
    _, vector = _wind(scenario)
    slots = {(si, di): 0.0 for si, kind in enumerate(station_types)
             for di in ((0, 1) if kind == 2 else (1,))}
    duties = {}
    for node in instance.targets:
        si = ownership[node.id]
        station = instance.stations[si]
        _, outbound = _leg(station, node, vector, instance.params.speed)
        _, inbound = _leg(node, station, vector, instance.params.speed)
        if outbound is None or inbound is None:
            raise ValueError("generated singleton has an unreachable wind heading")
        duties[node.id] = outbound + node.service + inbound
    for node in sorted(instance.targets, key=lambda n: (-duties[n.id], n.id)):
        si = ownership[node.id]
        station = instance.stations[si]
        _, outbound = _leg(station, node, vector, instance.params.speed)
        _, inbound = _leg(node, station, vector, instance.params.speed)
        need = node.energy + instance.params.flight_energy * (outbound + inbound)
        candidates = [(slots[si, di] + duties[node.id], di)
                      for di in ((0, 1) if station_types[si] == 2 else (1,))
                      if need <= instance.capacity(di) + ENERGY_EPS
                      and slots[si, di] + duties[node.id] <= instance.duration(station_types[si]) + 1e-7]
        if not candidates:
            raise ValueError("generated reference infeasible; failed map is retained")
        _, di = min(candidates)
        solution["routes"][si][di].append([node.id])
        slots[si, di] += duties[node.id]
    audit = audit_fixed_anchor(instance, solution, wind=scenario, map_path=path)
    if not audit["physical_feasible"]:
        raise ValueError("same-wind reference failed independent audit: " + repr(audit["issues"]))
    if audit.get("scientific_eligible"):
        raise RuntimeError("synthetic heuristic reference acquired author eligibility")
    return {"path": str(Path(path).resolve()), "solution": solution}, audit


def build_population(out, *, seed=CORPUS_SEED, profile="quick"):
    """Return ``(populations, manifest)`` with split -> (row, scenario, cap).

    ``seed`` is the corpus seed, independent of policy training. Each split also
    writes ``dataset/<split>/plans.jsonl``: one native row per map using the E4
    feasible singleton reference. ``case_records.jsonl`` includes both winds and
    caps. These rows can be reused by a separate dynamic-weather experiment.
    """
    from .joint_inputs import geometry_fingerprint

    out, cfg = Path(out), PROFILES[profile]
    split_counts = {"train": cfg.train_maps, "val": cfg.val_maps, "test": cfg.test_maps}
    populations, entries, all_geometry, all_bytes = {}, [], set(), set()
    for split, count in split_counts.items():
        cases, plans, records = [], [], []
        for index in range(count):
            map_seed = _seed(seed, "population", split, index)
            path = out / "dataset" / split / f"{split}_{index:04d}.txt"
            ownership = _fresh_map(path, seed=map_seed, station_types=cfg.station_types,
                                   targets_per_station=cfg.targets_per_station)
            file_sha = sha256(path.read_bytes()).hexdigest()
            geometry = geometry_fingerprint(path)
            if geometry in all_geometry or file_sha in all_bytes:
                raise ValueError("cross-population duplicate raw/exact-translation geometry")
            all_geometry.add(geometry)
            all_bytes.add(file_sha)
            map_id = _digest(["base_map", split, index, geometry])
            for scenario in SCENARIOS:
                row, audit = _singleton_reference(path, ownership, cfg.station_types, scenario)
                case = (row, scenario, float(audit["metrics"]["cost"]))
                cases.append(case)
                if scenario == SCENARIOS[0]:
                    plans.append(row)
                case_id = _digest([map_id, scenario])
                entry = dict(split=split, base_map_id=map_id, case_id=case_id,
                             map_index=index, map_seed=map_seed, path=str(path.resolve()),
                             map_sha256=file_sha, geometry_sha256=geometry,
                             targets=len(ownership), station_types=list(cfg.station_types),
                             scenario=scenario, reference_source=REFERENCE_SOURCE,
                             original_author_reference=False, reference=row["solution"],
                             reference_audit=audit, exploratory_cap=case[2])
                _write_json(out / "dataset" / split / f"{split}_{index:04d}_{scenario}.json", entry)
                entries.append(entry)
                records.append(dict(row=row, scenario=scenario, cap=case[2],
                                    case_id=case_id, base_map_id=map_id))
        _write_jsonl(out / "dataset" / split / "plans.jsonl", plans)
        _write_jsonl(out / "dataset" / split / "case_records.jsonl", records)
        populations[split] = cases
    manifest = dict(schema=SCHEMA, seed=seed, corpus_seed=seed, profile=profile,
                    generator="fresh_separated_multistation_v1", synthetic=True,
                    original_author_reference=False, reference_source=REFERENCE_SOURCE,
                    params_source="vendored lrphsd.problem.Parameters (Liu/EJOR values)",
                    wind_source="fixed_anchor independent constant-airspeed wind triangle; m/s flow-to",
                    scenarios=list(SCENARIOS), urgent_jobs=0, split_unit="base_map",
                    split_sizes=split_counts,
                    split_cases={key: len(value) for key, value in populations.items()},
                    paired_wind_conditions=True, unique_base_map_geometry=len(all_geometry),
                    prior_experiment_instances_used=False,
                    population_sha256=_digest([{key: value for key, value in entry.items() if key != "path"}
                                                for entry in entries]), entries=entries,
                    formal=False, project_gate_changes=False)
    return populations, _write_json(out / "population_manifest.json", manifest)


def _two_opt_episode(episode, case, *, max_passes=4):
    """A declared, non-learning route-order control, never called during PG.

    Keep every fixed station, slot and trip membership; exhaustively consider
    within-trip reversals for at most four best-improvement passes. Only strict
    travel-time reductions are accepted, then the final typed plan is audited
    independently. This is a bounded greedy+2-opt control, not a strong ALNS.
    Failed greedy prefixes remain failures and receive no reference fallback.
    """
    from copy import deepcopy
    from .common import load_ins
    from .fixed_anchor import _leg, _wind, audit_fixed_anchor

    episode = deepcopy(episode)
    result, (_, scenario, cap) = episode["result"], case
    if not result.get("eligible"):
        result["postprocess"] = dict(method="within_trip_two_opt", status="SKIPPED_INELIGIBLE",
                                      moves=0, max_passes=max_passes)
        return episode
    instance = load_ins(case[0]["path"])
    _, vector = _wind(scenario)
    solution = deepcopy(result["solution"])
    nodes = instance.nodes
    edge = {}
    def duration(start, end):
        key = (start, end)
        if key not in edge:
            _, minutes = _leg(nodes[start], nodes[end], vector, instance.params.speed)
            edge[key] = minutes if minutes is not None else math.inf
        return edge[key]
    def trip_time(si, trip):
        ids = [instance.stations[si].id, *trip, instance.stations[si].id]
        return sum(duration(a, b) for a, b in zip(ids, ids[1:]))
    changes = []
    for si, drones in enumerate(solution["routes"]):
        for di, trips in enumerate(drones):
            for ti, original in enumerate(trips):
                trip = list(original)
                for _ in range(max_passes):
                    old_time = trip_time(si, trip)
                    best_time, best = old_time, None
                    for left in range(len(trip) - 1):
                        for right in range(left + 2, len(trip) + 1):
                            candidate = trip[:left] + list(reversed(trip[left:right])) + trip[right:]
                            value = trip_time(si, candidate)
                            if value < best_time - 1e-10:
                                best_time, best = value, candidate
                    if best is None:
                        break
                    changes.append(dict(station=si, slot=di, trip=ti, before=trip,
                                        after=best, flight_minutes_saved=old_time - best_time))
                    trip = best
                trips[ti] = trip
    audit = audit_fixed_anchor(instance, solution, wind=scenario, map_path=case[0]["path"])
    physical = bool(audit["physical_feasible"])
    eligible = physical and audit["metrics"]["cost"] <= cap + 1e-7
    if not physical:
        raise RuntimeError("within-trip 2-opt violated independent resource audit")
    before = dict(cost=result["cost"], M_return=result["M_return"])
    result.update(solution=solution, audit=audit, cost=audit["metrics"]["cost"],
                  J=audit["metrics"]["cost"], M_return=audit["metrics"]["M_return"],
                  complete_strict=1, all_returned=1, physically_feasible=1, eligible=eligible)
    result["postprocess"] = dict(method="within_trip_two_opt", status="AUDITED",
                                  moves=len(changes), changes=changes, max_passes=max_passes,
                                  before=before, strong_alns=False,
                                  construction_actions_refer_to_pre_reordering_plan=True)
    return episode


def _reference_episode(case, *, restricted, deadline):
    from .joint_route import JointRoute
    from .joint_learning import json_safe, _failure

    env, actions = None, []
    try:
        row, scenario, cap = case
        env = JointRoute(row, scenario, cap)
        while not env.done:
            if time.monotonic() >= deadline:
                raise TimeoutError("exploration absolute deadline reached")
            action = env.source_slot_action() if restricted else env.teacher_action()
            if action is None:
                result = json_safe(env.result())
                result["eligible"] = False
                result["termination_reason"] = "fixed_slot_no_legal_action"
                return dict(result=result, actions=actions)
            env.step(action)
            actions.append(action)
        return dict(result=json_safe(env.result()), actions=actions)
    except Exception as exc:
        result = _failure("exception", type(exc).__name__ + ": " + str(exc))
        if env is not None:
            result["partial_result"] = json_safe(env.result())
        return dict(result=result, actions=actions)


def _aggregate(rows):
    """All failures remain in N; finite complete-only M is secondary."""
    result = {}
    for method in sorted({row["method"] for row in rows}):
        method_rows = [row for row in rows if row["method"] == method]
        eligible = [row for row in method_rows if row["result"].get("eligible")]
        def mean_all(field):
            values = [row.get(field) for row in method_rows]
            return sum(values) / len(values) if all(v is not None for v in values) else None
        result[method] = dict(cases=len(method_rows), eligible_count=len(eligible),
                              failure_count=len(method_rows) - len(eligible),
                              mean_J_all=mean_all("score_j"), mean_L_all=mean_all("score_m"),
                              mean_eligible_M=(sum(row["result"]["M_return"] for row in eligible) / len(eligible)
                                               if eligible else None))
    return result


def evaluate_test(cases, manifest, rounds, *, out, seed, device, deadline):
    """Evaluate each fixed endpoint once, only after both training runs end."""
    import torch
    from .joint_learning import JointActor, _episode, _failure, terminal_score, weight_hash

    entries = [entry for entry in manifest["entries"] if entry["split"] == "test"]
    if len(entries) != len(cases):
        raise ValueError("test manifest denominator mismatch")
    endpoints = []
    for mode, summary in rounds.items():
        endpoints.append((mode + "_greedy", mode, "greedy", None, True))
        for arm in ("frozen_bc", "pg_j", "pg_m"):
            ck = summary["checkpoints"][arm]
            checkpoint = torch.load(ck["path"], map_location="cpu", weights_only=True)
            model = JointActor().to(device)
            model.load_state_dict(checkpoint["model"])
            model.eval()
            if weight_hash(model) != ck["weight_sha256"]:
                raise RuntimeError("test checkpoint weight hash mismatch")
            for parameter in model.parameters():
                parameter.requires_grad_(False)
            endpoints.append((mode + "_" + arm, mode, arm, model, ck["endpoint_complete"]))
    endpoints.extend([("same_wind_singleton", "fixed_reference", "teacher", None, True),
                      ("fixed_slot_greedy", "fixed_reference", "fixed_slot_greedy", None, True),
                      ("joint_greedy_2opt", "joint", "greedy_2opt", None, True)])
    rows = []
    with (Path(out) / "evaluation.jsonl").open("x", encoding="utf-8") as stream:
        for method, mode, arm, model, complete in endpoints:
            model_before = weight_hash(model) if model is not None else None
            for index, (case, entry) in enumerate(zip(cases, entries)):
                if time.monotonic() >= deadline:
                    raise TimeoutError("exploration absolute deadline reached during held-out test")
                if not complete:
                    episode = dict(result=_failure("registered_endpoint_not_reached"), actions=[])
                elif mode == "fixed_reference":
                    episode = _reference_episode(case, restricted=arm == "fixed_slot_greedy", deadline=deadline)
                else:
                    with torch.no_grad():
                        episode = _episode(case, model, mode=mode,
                                           kind="greedy" if arm in ("greedy", "greedy_2opt") else "argmax",
                                           seed=_seed(seed, "heldout_test", index),
                                           device=torch.device(device), deadline=deadline)
                    if arm == "greedy_2opt":
                        episode = _two_opt_episode(episode, case)
                result = episode["result"]
                row = dict(schema=SCHEMA, split="test", method=method, mode=mode, arm=arm,
                           case_id=entry["case_id"], base_map_id=entry["base_map_id"],
                           scenario=case[1], cap=case[2], original_author_reference=False,
                           endpoint_complete=bool(complete), result=result, actions=episode["actions"])
                for objective in ("j", "m"):
                    try:
                        row["score_" + objective] = terminal_score(result, objective, case[2])
                    except ValueError:
                        row["score_" + objective] = None
                stream.write(_canonical(row).decode("utf-8") + "\n")
                stream.flush()
                rows.append(row)
            if model is not None and weight_hash(model) != model_before:
                raise RuntimeError("test evaluation changed frozen endpoint weights")
    reopened = [json.loads(line) for line in (Path(out) / "evaluation.jsonl").read_text().splitlines()]
    if len(reopened) != len(endpoints) * len(cases):
        raise RuntimeError("held-out test denominator changed")
    if _digest(rows) != _digest(reopened):
        raise RuntimeError("test output changed after persistence")
    return rows


def _paired_differences(rows):
    """Descriptive pairing, retaining failures; no independence claim for winds."""
    indexed = {(row["method"], row["case_id"]): row for row in rows}
    records = []
    for mode in ("joint", "serial"):
        for arm in ("frozen_bc", "pg_j", "pg_m"):
            method, baseline = mode + "_" + arm, "joint_greedy"
            ids = sorted(case_id for candidate, case_id in indexed if candidate == method)
            pairs = [(indexed[method, identity], indexed[baseline, identity]) for identity in ids]
            deltas = [a["score_m"] - b["score_m"] for a, b in pairs
                      if a["score_m"] is not None and b["score_m"] is not None]
            records.append(dict(method=method, baseline=baseline, case_pairs=len(pairs),
                                pairs_with_defined_L=len(deltas),
                                mean_L_difference_all=(sum(deltas) / len(deltas)
                                                       if len(deltas) == len(pairs) else None),
                                both_eligible_pairs=sum(bool(a["result"].get("eligible")) and
                                                        bool(b["result"].get("eligible")) for a, b in pairs),
                                inferential_unit="base_map_cluster; paired winds are repeated conditions",
                                interpretation="descriptive exploratory comparison; not proof of RL superiority"))
    return records


def run(*, out, seed=103, device="cpu", profile="quick"):
    """One fresh, fully recorded run; existing output directories are rejected."""
    import torch
    from .joint_learning import run_round

    out = Path(out)
    if not out.is_absolute():
        raise ValueError("--out must be an absolute new directory")
    if type(seed) is not int or seed < 0 or profile not in PROFILES:
        raise ValueError("nonnegative seed and known profile required")
    if device not in ("cpu", "cuda") or device == "cuda" and not torch.cuda.is_available():
        raise ValueError("requested cpu/cuda device must be available")
    if out.exists():
        raise FileExistsError("output directory already exists; prior runs are retained")
    out.mkdir(parents=True, exist_ok=False)
    out = out.resolve()
    cfg = PROFILES[profile]
    started = time.monotonic()
    deadline = started + cfg.wall_seconds
    source_files = [Path(__file__), Path(__file__).with_name("joint_learning.py"),
                    Path(__file__).with_name("joint_route.py"), Path(__file__).with_name("fixed_anchor.py")]
    source_hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in source_files}
    contract = dict(schema=SCHEMA, seed=seed, corpus_seed=CORPUS_SEED, device=device, profile=profile,
                    config=asdict(cfg), started_utc=datetime.now(timezone.utc).isoformat(),
                    source_sha256=source_hashes, original_author_reference=False,
                    reference_source=REFERENCE_SOURCE, urgent_jobs=0,
                    action="physical (station,drone_slot,target_or_RETURN); no operator choice",
                    endpoints="fixed BC and PG update counts, argmax test, no checkpoint selection",
                    objective="J proxy and cost-compliant return makespan L in separate PG arms",
                    test_policy="sealed base-map split, evaluated after every training endpoint is frozen",
                    formal=False, project_gate_changes=False, performance_claim=False)
    _write_json(out / "contract.json", contract)
    try:
        # Tiny variable option sets are much faster and more reproducible with a
        # single CPU thread; this is a declared resource setting, not data tuning.
        torch.set_num_threads(1)
        _write_json(out / "runtime.json", dict(python=sys.version, platform=platform.platform(),
                    torch=str(torch.__version__), cuda_available=torch.cuda.is_available(),
                    device=device, torch_threads=torch.get_num_threads()))
        population, manifest = build_population(out, seed=CORPUS_SEED, profile=profile)
        rounds = {}
        for mode in ("joint", "serial"):
            rounds[mode] = run_round(population["train"], population["val"],
                                     out=out / mode, seed=seed, bc_epochs=cfg.bc_epochs,
                                     pg_steps=cfg.pg_steps, rollouts=cfg.rollouts, lr=cfg.lr,
                                     device=device, deadline=deadline, mode=mode)
            if rounds[mode]["status"] != "completed_fixed_endpoints":
                raise RuntimeError(mode + " did not reach all fixed endpoints; retained run summary")
        _write_json(out / "training_finished.json", dict(
            status="ALL_ENDPOINTS_FROZEN", elapsed_wall_seconds=time.monotonic() - started,
            test_evaluations_so_far=0,
            endpoint_weight_sha256={mode: summary["deterministic_weight_hashes"]
                                    for mode, summary in rounds.items()}))
        test_rows = evaluate_test(population["test"], manifest, rounds, out=out, seed=seed,
                                  device=device, deadline=deadline)
        if time.monotonic() >= deadline:
            raise TimeoutError("exploration absolute deadline reached before final receipt")
        if any(sha256(path.read_bytes()).hexdigest() != source_hashes[path.name] for path in source_files):
            raise RuntimeError("implementation source changed during exploration")
        test_aggregates = _aggregate(test_rows)
        summary = dict(schema=SCHEMA, status="EXPLORATORY_RUN_COMPLETE", profile=profile,
                       seed=seed, corpus_seed=CORPUS_SEED, device=device, split_sizes=manifest["split_sizes"],
                       split_cases=manifest["split_cases"], test_rows=len(test_rows),
                       methods=sorted(test_aggregates), test_aggregates=test_aggregates,
                       method_descriptions=dict(
                           joint="actor chooses a physical station/slot/target-or-return action jointly",
                           serial="matched representation ablation: fixed cyclic slot order, learned target/return",
                           same_wind_singleton="synthetic load-balanced singleton reference, not original author",
                           fixed_slot_greedy="non-learning heuristic restricted to reference slot assignment",
                           joint_greedy_2opt="joint heuristic then bounded within-trip reordering; not strong ALNS"),
                       test_aggregates_by_wind={scenario: _aggregate([r for r in test_rows if r["scenario"] == scenario])
                                                for scenario in SCENARIOS},
                       paired_differences=_paired_differences(test_rows),
                       learning_evidence={mode: value["learning_evidence"] for mode, value in rounds.items()},
                       optimizer_counts={mode: value["counts"] for mode, value in rounds.items()},
                       round_summaries={mode: str((out / mode / "summary.json").resolve()) for mode in rounds},
                       population_sha256=manifest["population_sha256"], source_sha256=source_hashes,
                       reference_source=REFERENCE_SOURCE, original_author_reference=False,
                       validation_selected_checkpoint=False, test_used_for_training=False,
                       independent_training_replicates=1, formal=False,
                       project_gate_changes=False, performance_claim=False,
                       elapsed_wall_seconds=time.monotonic() - started,
                       limitations=["synthetic independent population with heuristic same-wind caps",
                                    "single independent training seed per invocation",
                                    "fixed station types and fixed target-to-station ownership",
                                    "not an original-author or strongest-ALNS matched-budget comparison",
                                    "paired wind conditions are not independent base-map samples"])
        _write_json(out / "summary.json", summary)
        return summary
    except BaseException as exc:
        _write_json(out / "failure.json", dict(schema=SCHEMA, status="FAILED_RETAINED",
                    error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc(),
                    elapsed_wall_seconds=time.monotonic() - started, formal=False))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=103)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--profile", choices=tuple(PROFILES), default="quick")
    args = parser.parse_args(argv)
    summary = run(out=args.out, seed=args.seed, device=args.device, profile=args.profile)
    print(json.dumps(dict(status=summary["status"], out=str(args.out.resolve()),
                          test_rows=summary["test_rows"], formal=False), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
