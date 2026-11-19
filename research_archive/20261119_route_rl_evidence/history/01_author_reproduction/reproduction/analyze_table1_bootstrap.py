#!/usr/bin/env python3
"""Map-cluster bootstrap diagnostics against Liu Table 1 rounded summaries."""

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


def interval(values, seed):
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(20000))
    return [draws[499], draws[19499]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    published = json.loads((root / "published_table1.json").read_text())["groups"]
    profiles = ("J1", "J2", "J1b", "J2b", "P1", "P2")
    result = {"method": "20,000 map-cluster bootstrap draws; 10 maps per group, five seeds per map",
              "seed": 20261102, "profiles": {}}
    for profile in profiles:
        by_map = defaultdict(list)
        failures = []
        for path in (root / "results" / ("full_" + profile)).glob(profile + "__*.json"):
            if path.name.endswith(".reference.json"):
                continue
            row = json.loads(path.read_text())
            if row["status"] != "ok" or not row["independently_feasible"]:
                failures.append(row["task_identity"])
            else:
                by_map[row["instance"]].append(row["independent_cost"])
        if failures:
            raise SystemExit(f"{profile}: {len(failures)} failed/infeasible tasks: {failures[:5]}")
        if len(by_map) != 120 or any(len(costs) != 5 for costs in by_map.values()):
            raise SystemExit(f"{profile}: incomplete five-seed, 120-map matrix")
        groups = {}
        for index, (group, paper) in enumerate(published.items()):
            maps = sorted(name for name in by_map if name.rsplit("_", 1)[0] == group)
            if len(maps) != 10:
                raise SystemExit(f"{profile}/{group}: {len(maps)} maps, expected 10")
            map_means = [statistics.mean(by_map[name]) for name in maps]
            map_bests = [min(by_map[name]) for name in maps]
            mean_ci = interval(map_means, 20261102 + index)
            best_ci = interval(map_bests, 20261202 + index)
            groups[group] = {
                "maps": 10, "runs": 50,
                "paper_average": paper["average"], "run_average": statistics.mean(map_means),
                "run_average_bootstrap95": mean_ci,
                "paper_average_inside_bootstrap95": mean_ci[0] <= paper["average"] <= mean_ci[1],
                "average_gap_pct": 100 * (statistics.mean(map_means) - paper["average"]) / paper["average"],
                "paper_best": paper["best"], "mean_map_best": statistics.mean(map_bests),
                "mean_map_best_bootstrap95": best_ci,
                "paper_best_inside_bootstrap95": best_ci[0] <= paper["best"] <= best_ci[1],
                "best_gap_pct": 100 * (statistics.mean(map_bests) - paper["best"]) / paper["best"],
            }
        result["profiles"][profile] = {"runs": 600, "failed_or_infeasible": 0, "groups": groups}
        avg_outside = [group for group, item in groups.items() if not item["paper_average_inside_bootstrap95"]]
        best_outside = [group for group, item in groups.items() if not item["paper_best_inside_bootstrap95"]]
        print(f"TABLE1_BOOTSTRAP {profile} groups=12 runs=600 avg_outside={avg_outside} best_outside={best_outside}")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
