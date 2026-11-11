#!/usr/bin/env python3
"""Mutation checks for the independent full-solution evaluator."""

import copy
import json
import os
from dataclasses import replace
from pathlib import Path

from lrphsd.evaluator import evaluate
from lrphsd.greedy import build
from lrphsd.problem import read_instance


def first_trip(solution, want_kind=None):
    for station, kind in enumerate(solution["station_types"]):
        if want_kind is not None and kind != want_kind:
            continue
        for drone, trips in enumerate(solution["routes"][station]):
            for index, trip in enumerate(trips):
                if trip:
                    return station, drone, index
    raise RuntimeError("no nonempty trip for requested station type")


root = Path(os.environ.get("LRPHSD_ROOT", Path(__file__).resolve().parent))
instance = read_instance(root / "external" / "LRPHSD" / "data" / "Instances_Alg" / "3_10_1.txt")
valid = build(instance)
assert evaluate(instance, valid)["feasible"]
station, drone, trip_index = first_trip(valid)
target = valid["routes"][station][drone][trip_index][0]
mutants = {}

missing = copy.deepcopy(valid)
missing["routes"][station][drone][trip_index].remove(target)
mutants["missing"] = missing

duplicate = copy.deepcopy(valid)
duplicate["routes"][station][drone][trip_index].append(target)
mutants["duplicate"] = duplicate

closed = copy.deepcopy(valid)
closed["station_types"][station] = 0
mutants["closed_station"] = closed

for small_station, kind in enumerate(valid["station_types"]):
    if kind == 1 and valid["routes"][small_station][1]:
        illegal_drone = copy.deepcopy(valid)
        illegal_drone["routes"][small_station][0] = illegal_drone["routes"][small_station][1]
        illegal_drone["routes"][small_station][1] = []
        mutants["large_drone_at_small_station"] = illegal_drone
        break
else:
    raise RuntimeError("need a used SABS for drone-slot mutation")

energy = copy.deepcopy(valid)
energy["routes"][station][drone][trip_index] *= 20
mutants["energy"] = energy

coverage_instance = replace(
    instance,
    params=replace(instance.params, small_radius=1.0, large_radius=1.0),
)
duration_instance = replace(
    instance,
    params=replace(instance.params, small_duration=0.001, large_duration=0.001),
)

results = []
for expected, solution in mutants.items():
    audit = evaluate(instance, solution)
    matched = any(issue.split(":")[0] == expected for issue in audit["issues"])
    results.append({"mutation": expected, "rejected": not audit["feasible"],
                    "expected_issue_present": matched, "issues": audit["issues"][:8]})
    assert not audit["feasible"] and matched, expected
for expected, changed_instance in (("coverage", coverage_instance),
                                   ("cumulative_time", duration_instance)):
    audit = evaluate(changed_instance, valid)
    matched = any(issue.split(":")[0] == expected for issue in audit["issues"])
    results.append({"mutation": expected, "rejected": not audit["feasible"],
                    "expected_issue_present": matched, "issues": audit["issues"][:8]})
    assert not audit["feasible"] and matched, expected

out = Path(os.environ.get("REPRO_OUTPUT", root / "results" / "evaluator_mutation_contract.json"))
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"source_instance": instance.name, "results": results}, indent=2) + "\n")
print(f"EVALUATOR_MUTATIONS {len(results)}/{len(results)} rejected with expected issue")
