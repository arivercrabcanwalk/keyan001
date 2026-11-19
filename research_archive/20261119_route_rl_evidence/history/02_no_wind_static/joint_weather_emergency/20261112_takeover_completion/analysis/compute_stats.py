#!/usr/bin/env python3
"""Paired map-level statistics for the G3 development set.

Every comparison is a paired difference on the same map.  The bootstrap
resamples maps (the independent unit), never rows, and never solver seeds.
"""
from __future__ import annotations
import json, math, pathlib, random, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POP = ROOT / "results/g3_pop"
B = 10000
SEED = 20261112
TOL = 1e-9


def load(name):
    return json.loads((POP / name).read_text())


def pct(delta, base):
    return None if base in (None, 0) else 100.0 * delta / base


def boot_ci(values, b=B, seed=SEED):
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(b):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * b)]
    hi = means[int(0.975 * b) - 1]
    return [lo, hi]


def compare(name, base_by_map, cand_by_map):
    maps = sorted(set(base_by_map) & set(cand_by_map))
    deltas, pcts, w = [], [], 0
    for m in maps:
        b = base_by_map[m]
        c = cand_by_map[m]
        d = c - b
        deltas.append(d)
        pcts.append(pct(d, b))
        if d < -TOL:
            w += 1
    losses = sum(1 for m in maps if cand_by_map[m] - base_by_map[m] > TOL)
    ties = len(maps) - w - losses
    return {
        "comparison": name, "n_maps": len(maps),
        "mean_delta": statistics.fmean(deltas),
        "mean_delta_pct": statistics.fmean(pcts),
        "median_delta_pct": statistics.median(pcts),
        "ci95_mean_delta": boot_ci(deltas),
        "ci95_mean_delta_pct": boot_ci(pcts),
        "wins": w, "ties": ties, "losses": losses,
        "per_map_pct": {m: pct(cand_by_map[m] - base_by_map[m], base_by_map[m])
                        for m in maps},
    }


def main() -> int:
    index = load("population_index.json")
    exact = load("EXACT_REASSIGN_RESULTS.json")["rows"]
    nonrl = load("NONRL_RESULTS.json")["rows"]
    anchor, exact_m, methods = {}, {}, {}
    excluded = []
    for r in exact:
        if r.get("status") != "OK":
            excluded.append({"map": r["map"], "reason": r.get("status")})
            continue
        if not r.get("admissible"):
            excluded.append({"map": r["map"], "reason": "exact_reassign_inadmissible"})
            continue
        anchor[r["map"]] = r["anchor_M_return"]
        exact_m[r["map"]] = r["validated_M_return"]
    for r in nonrl:
        if r.get("status") != "ONTIME_VALID":
            continue
        key = f"{r['method']}_{int(r['budget_s'])}s"
        methods.setdefault(key, {})[r["map"]] = r["chosen_M_return"]
    out = {
        "schema": "takeover_g3_stats_v1",
        "unit": "map",
        "bootstrap": {"B": B, "seed": SEED, "resamples": "maps_with_replacement"},
        "n_maps_anchor_valid": len(anchor),
        "excluded": excluded,
        "reference_levels": {
            "anchor": {m: anchor[m] for m in anchor},
            "exact_cost_neutral": {m: exact_m[m] for m in exact_m},
        },
        "comparisons": [],
    }
    out["comparisons"].append(compare("exact_cost_neutral vs anchor", anchor, exact_m))
    for key in ("lpt_6s", "joint_minmax_6s", "joint_minmax_12s"):
        if key in methods:
            out["comparisons"].append(compare(f"{key} vs anchor", anchor, methods[key]))
            out["comparisons"].append(
                compare(f"{key} vs exact_cost_neutral", exact_m, methods[key]))
    out["lpt_optimality_gap"] = compare("lpt_6s vs exact_cost_neutral", exact_m,
                                        methods.get("lpt_6s", {}))
    dest = ROOT / "stats"
    dest.mkdir(exist_ok=True)
    (dest / "STATS_self.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + "\n")
    for c in out["comparisons"]:
        ci = c["ci95_mean_delta_pct"]
        print(f"{c['comparison']:40s} n={c['n_maps']:2d} "
              f"mean={c['mean_delta_pct']:8.3f}% med={c['median_delta_pct']:8.3f}% "
              f"CI={None if ci is None else [round(x,3) for x in ci]} "
              f"W/T/L={c['wins']}/{c['ties']}/{c['losses']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
