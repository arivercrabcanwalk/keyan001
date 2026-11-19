#!/usr/bin/env python3
"""Paired map-level statistics for the G3 development + confirmation sets.

The confirmation set (ordinals 2-4) was registered before generation and is
analysed with exactly the same code path as the development set (ordinal 1).
The replication test is: same sign and a 95% CI excluding zero in the unseen
36 maps.  A difference between sets is also reported, but is not a gate.
"""
from __future__ import annotations
import json, math, pathlib, random, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = 10000
SEED = 20261112
TOL = 1e-9


def pct(d, base):
    return None if base in (None, 0) else 100.0 * d / base


def boot_ci(values, b=B, seed=SEED):
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(b)]
    means.sort()
    return [means[int(0.025 * b)], means[int(0.975 * b) - 1]]


def load_set(pop_dir):
    exact = json.loads((pop_dir / "EXACT_REASSIGN_RESULTS.json").read_text())["rows"]
    nonrl_path = pop_dir / "NONRL_RESULTS.json"
    nonrl = json.loads(nonrl_path.read_text())["rows"] if nonrl_path.exists() else []
    anchor, exact_m, methods, excluded = {}, {}, {}, []
    for r in exact:
        if r.get("status") != "OK" or not r.get("admissible"):
            excluded.append({"map": r["map"], "reason": r.get("status") or "inadmissible"})
            continue
        anchor[r["map"]] = r["anchor_M_return"]
        exact_m[r["map"]] = r["validated_M_return"]
    # Two denominators are kept on purpose.
    #   valid[key][map]  : only rows that delivered an on-time admissible answer
    #   itt[key][map]    : intent-to-treat -- a failed/timed-out run is scored as
    #                      "no better than the anchor", which is what a deployed
    #                      method would actually deliver.  Never drop a map.
    valid, itt, failures = {}, {}, {}
    for r in nonrl:
        if "method" not in r:
            continue
        key = f"{r['method']}_{int(r['budget_s'])}s"
        ok = r.get("status") == "ONTIME_VALID" and r.get("chosen_M_return") is not None
        if ok:
            valid.setdefault(key, {})[r["map"]] = r["chosen_M_return"]
        else:
            failures.setdefault(key, []).append(r["map"])
    for key, by_map in valid.items():
        itt[key] = {m: by_map.get(m, anchor[m]) for m in anchor}
    for key in failures:
        itt.setdefault(key, {m: anchor[m] for m in anchor})
    return anchor, exact_m, valid, itt, failures, excluded


def compare(name, base, cand):
    maps = sorted(set(base) & set(cand))
    deltas = [cand[m] - base[m] for m in maps]
    pcts = [pct(cand[m] - base[m], base[m]) for m in maps]
    w = sum(1 for m in maps if cand[m] - base[m] < -TOL)
    l = sum(1 for m in maps if cand[m] - base[m] > TOL)
    return {
        "comparison": name, "n_maps": len(maps),
        "mean_delta": statistics.fmean(deltas) if deltas else None,
        "mean_delta_pct": statistics.fmean(pcts) if pcts else None,
        "median_delta_pct": statistics.median(pcts) if pcts else None,
        "ci95_mean_delta_pct": boot_ci(pcts),
        "wins": w, "ties": len(maps) - w - l, "losses": l,
        "per_map_pct": {m: pct(cand[m] - base[m], base[m]) for m in maps},
    }


def sets(spec):
    out = {"schema": "takeover_g3_stats_full_v1", "bootstrap": {"B": B, "seed": SEED,
                                                              "unit": "map"},
           "sets": {}, "replication": {}}
    for label, pop_dir in spec:
        if not (pop_dir / "EXACT_REASSIGN_RESULTS.json").exists():
            continue
        anchor, exact_m, valid, itt, failures, excluded = load_set(pop_dir)
        block = {"n_maps_anchor_valid": len(anchor), "excluded": excluded,
                 "failures_by_method": {k: sorted(v) for k, v in failures.items()},
                 "reference_levels": {"anchor": anchor, "exact_cost_neutral": exact_m},
                 "comparisons": []}
        block["comparisons"].append(compare("exact_cost_neutral vs anchor", anchor, exact_m))
        for key in ("lpt_6s", "joint_minmax_6s", "joint_minmax_12s"):
            if key in itt:
                block["comparisons"].append(
                    compare(f"{key} vs anchor [ITT]", anchor, itt[key]))
                block["comparisons"].append(
                    compare(f"{key} vs exact_cost_neutral [ITT]", exact_m, itt[key]))
            if key in valid:
                block["comparisons"].append(
                    compare(f"{key} vs anchor [valid-only]", anchor, valid[key]))
                block["comparisons"].append(
                    compare(f"{key} vs exact_cost_neutral [valid-only]", exact_m,
                            valid[key]))
        out["sets"][label] = block
    dev = out["sets"].get("development")
    con = out["sets"].get("confirmation")
    if dev and con:
        key = "exact_cost_neutral vs anchor"
        d = next(c for c in dev["comparisons"] if c["comparison"] == key)
        k = next(c for c in con["comparisons"] if c["comparison"] == key)
        ci = k["ci95_mean_delta_pct"]
        out["replication"][key] = {
            "development": {"n": d["n_maps"], "mean_pct": d["mean_delta_pct"],
                            "ci95": d["ci95_mean_delta_pct"]},
            "confirmation": {"n": k["n_maps"], "mean_pct": k["mean_delta_pct"],
                             "ci95": ci},
            "same_sign": (d["mean_delta_pct"] is not None and k["mean_delta_pct"] is not None
                          and (d["mean_delta_pct"] < 0) == (k["mean_delta_pct"] < 0)),
            "confirmation_ci_excludes_zero": (ci is not None and ci[1] < 0),
            "verdict": ("REPLICATED" if (ci is not None and ci[1] < 0) else "NOT_REPLICATED"),
        }
    # pooled over the whole 48-map allocation (11 dev + 36 confirmation valid maps)
    merged_anchor, merged_exact, merged_valid, merged_itt, merged_fail = {}, {}, {}, {}, {}
    for label, pop_dir in spec:
        if not (pop_dir / "EXACT_REASSIGN_RESULTS.json").exists():
            continue
        a, e, v, i, f, _ = load_set(pop_dir)
        merged_anchor.update(a); merged_exact.update(e)
        for k, d in v.items():
            merged_valid.setdefault(k, {}).update(d)
        for k, d in i.items():
            merged_itt.setdefault(k, {}).update(d)
        for k, d in f.items():
            merged_fail.setdefault(k, []).extend(d)
    if merged_anchor:
        block = {"n_maps_anchor_valid": len(merged_anchor),
                 "failures_by_method": {k: sorted(v) for k, v in merged_fail.items()},
                 "reference_levels": {"anchor": merged_anchor,
                                      "exact_cost_neutral": merged_exact},
                 "comparisons": []}
        block["comparisons"].append(
            compare("exact_cost_neutral vs anchor", merged_anchor, merged_exact))
        for key in ("lpt_6s", "joint_minmax_6s", "joint_minmax_12s"):
            if key in merged_itt:
                block["comparisons"].append(
                    compare(f"{key} vs anchor [ITT]", merged_anchor, merged_itt[key]))
                block["comparisons"].append(
                    compare(f"{key} vs exact_cost_neutral [ITT]", merged_exact,
                            merged_itt[key]))
            if key in merged_valid:
                block["comparisons"].append(
                    compare(f"{key} vs exact_cost_neutral [valid-only]", merged_exact,
                            merged_valid[key]))
        out["sets"]["pooled_all"] = block

    dest = ROOT / "stats"
    dest.mkdir(exist_ok=True)
    (dest / "STATS.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + "\n")
    for label, block in out["sets"].items():
        print(f"\n=== {label} (n={block['n_maps_anchor_valid']}) ===")
        for c in block["comparisons"]:
            ci = c["ci95_mean_delta_pct"]
            print(f"  {c['comparison']:40s} n={c['n_maps']:2d} "
                  f"mean={c['mean_delta_pct']:8.3f}% med={c['median_delta_pct']:8.3f}% "
                  f"CI={None if ci is None else [round(x,3) for x in ci]} "
                  f"W/T/L={c['wins']}/{c['ties']}/{c['losses']}")
    if out["replication"]:
        print("\n=== replication ===")
        print(json.dumps(out["replication"], indent=1, default=str)[:2000])
    return 0


if __name__ == "__main__":
    spec = [("development", ROOT / "results/g3_pop"),
            ("confirmation", ROOT / "results/g3_confirm")]
    raise SystemExit(sets(spec))