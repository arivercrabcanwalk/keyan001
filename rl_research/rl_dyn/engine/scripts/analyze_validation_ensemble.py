#!/usr/bin/env python
"""Aggregate validation policy seeds and solver seeds at the instance level.

The instance is the inferential unit. Training seeds and solver seeds are
averaged within each map before paired inference; no run is treated as an
independent map.
"""
import argparse
import json
from pathlib import Path

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from carl.stats import bootstrap_ci, holm, wilcoxon_signed_rank

RESULTS = ROOT / "results"


def load_run(directory, expected_method, budget):
    directory = Path(directory)
    files = sorted(directory.glob("*__s*.json"))
    errors = sorted(directory.glob("*.error.json"))
    if errors:
        raise RuntimeError(f"{directory}: {len(errors)} error files")
    records = {}
    for path in files:
        row = json.loads(path.read_text())
        if row.get("status") != "ok":
            raise RuntimeError(f"{path}: status={row.get('status')}")
        if row.get("method") != expected_method:
            continue
        if not row.get("feasible"):
            raise RuntimeError(f"{path}: infeasible output")
        if abs(float(row.get("seconds", -1)) - budget) > 1e-9:
            raise RuntimeError(f"{path}: budget mismatch")
        key = (row["instance"], int(row["seed"]))
        if key in records:
            raise RuntimeError(f"{directory}: duplicate {key}")
        records[key] = float(row["cost"])
    return records


def paired_stats(ref, method, seed):
    names = sorted(ref)
    x = np.asarray([method[k] for k in names], dtype=float)
    y = np.asarray([ref[k] for k in names], dtype=float)
    d = x - y
    pct_x = 100.0 * x / y
    pct_y = np.full_like(pct_x, 100.0)
    stat = wilcoxon_signed_rank(x, y)
    ci_d = bootstrap_ci(x, y, n_boot=20000, seed=seed)
    ci_pct = bootstrap_ci(pct_x, pct_y, n_boot=20000, seed=seed + 1)
    return {
        "n_maps": int(len(d)),
        "mean_ref_cost": float(y.mean()),
        "mean_method_cost": float(x.mean()),
        "mean_delta_cost": float(d.mean()),
        "median_delta_cost": float(np.median(d)),
        "mean_delta_percent": float(pct_x.mean() - 100.0),
        "median_delta_percent": float(np.median(pct_x - 100.0)),
        "wins": int((d < -1e-9).sum()),
        "losses": int((d > 1e-9).sum()),
        "ties": int((np.abs(d) <= 1e-9).sum()),
        "wilcoxon_p_raw": float(stat["p_value"]),
        "wilcoxon_method": stat["method"],
        "wilcoxon_n_nonzero": stat["n"],
        "rank_biserial_model_worse_positive": float(stat["rank_biserial"]),
        "bootstrap95_delta_cost": [float(ci_d["lo"]), float(ci_d["hi"])],
        "bootstrap95_delta_percent": [float(ci_pct["lo"]), float(ci_pct["hi"])],
    }



def analyze_budget(budget, rng_seed):
    base = load_run(RESULTS / f"validation_{budget}s_baselines",
                    "m1d_noxchg", budget)
    if not base:
        raise RuntimeError(f"{budget}s: no reference records")
    instances = sorted({k[0] for k in base})
    solver_seeds = sorted({k[1] for k in base})
    if len(instances) != 24:
        raise RuntimeError(f"{budget}s: expected 24 maps, got {len(instances)}")
    ref_by_map = {}
    for name in instances:
        vals = [base[(name, seed)] for seed in solver_seeds]
        ref_by_map[name] = float(np.mean(vals))

    outputs = {}
    method_by_map = {}
    for family in ("bc", "ppo"):
        pooled = {}
        for model_seed in (11, 23, 37):
            method = f"m6_{family}_s{model_seed}"
            run = load_run(RESULTS / f"validation_{budget}s_{method}",
                           method, budget)
            if set(run) != set(base):
                raise RuntimeError(
                    f"{budget}s {method}: run keys differ from reference "
                    f"({len(run)} vs {len(base)})"
                )
            for key, value in run.items():
                pooled.setdefault(key, []).append(value)
        if any(len(v) != 3 for v in pooled.values()):
            raise RuntimeError(f"{budget}s {family}: expected 3 model seeds")
        by_map = {}
        for name in instances:
            vals = []
            for seed in solver_seeds:
                vals.extend(pooled[(name, seed)])
            by_map[name] = float(np.mean(vals))
        method_by_map[family] = by_map
        ref_map = {name: ref_by_map[name] for name in instances}
        ref_flat = {name: ref_by_map[name] for name in instances}
        method_flat = {name: by_map[name] for name in instances}
        outputs[family] = paired_stats(ref_flat, method_flat, rng_seed + budget * 100 + (0 if family == "bc" else 10))

    outputs["ppo_vs_bc"] = paired_stats(method_by_map["bc"],
                                         method_by_map["ppo"], rng_seed + budget * 100 + 20)
    return {
        "budget_seconds": budget,
        "n_maps": len(instances),
        "solver_seeds": solver_seeds,
        "training_seeds": [11, 23, 37],
        "reference": "m1d_noxchg",
        "reference_mean_cost": float(np.mean(list(ref_by_map.values()))),
        "results": outputs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="2,6,12")
    ap.add_argument("--seed", type=int, default=20261031)
    args = ap.parse_args()
    budgets = [int(x) for x in args.budgets.split(",")]
    results = [analyze_budget(b, args.seed) for b in budgets]

    # Confirmatory comparisons are only the 6s and 12s validation budgets.
    confirm = []
    labels = []
    for item in results:
        if item["budget_seconds"] in (6, 12):
            for family in ("bc", "ppo"):
                confirm.append(item["results"][family]["wilcoxon_p_raw"])
                labels.append(f'{item["budget_seconds"]}s {family} vs m1d_noxchg')
    adjusted = holm(confirm) if confirm else []
    for label, p in zip(labels, adjusted):
        print(f"HOLM {label}: {p:.6g}")

    out_json = RESULTS / "validation_ensemble_analysis.json"
    out_md = RESULTS / "validation_ensemble_analysis.md"
    out_json.write_text(json.dumps({
        "protocol": "validation ensemble analysis v1",
        "statistical_unit": "map; solver and model seeds averaged within map",
        "bootstrap_replicates": 20000,
        "bootstrap_seed": args.seed,
        "holm_family": labels,
        "holm_adjusted_p": [float(x) for x in adjusted],
        "budgets": results,
    }, indent=2) + "\n")

    lines = [
        "# Validation ensemble analysis",
        "",
        "Statistical unit: map. For each map, average the three solver seeds and three model-training seeds before paired inference. This avoids treating repeated seeds as independent maps.",
        "",
        "| Budget | Family | Reference mean | Policy mean | Mean delta | Mean delta % | Wins/Losses/Ties | Wilcoxon p | Holm p | Bootstrap 95% CI (%) |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    holm_map = dict(zip(labels, adjusted))
    for item in results:
        b = item["budget_seconds"]
        for family in ("bc", "ppo"):
            x = item["results"][family]
            hp = holm_map.get(f"{b}s {family} vs m1d_noxchg", float("nan"))
            ci = x["bootstrap95_delta_percent"]
            lines.append(
                f'| {b}s | {family.upper()} | {x["mean_ref_cost"]:.4f} | '
                f'{x["mean_method_cost"]:.4f} | {x["mean_delta_cost"]:+.4f} | '
                f'{x["mean_delta_percent"]:+.4f}% | '
                f'{x["wins"]}/{x["losses"]}/{x["ties"]} | '
                f'{x["wilcoxon_p_raw"]:.4g} | {hp:.4g} | '
                f'[{ci[0]:+.4f}, {ci[1]:+.4f}] |'
            )
        x = item["results"]["ppo_vs_bc"]
        ci = x["bootstrap95_delta_percent"]
        lines.append(
            f'| {b}s | PPO vs BC | {x["mean_ref_cost"]:.4f} | '
            f'{x["mean_method_cost"]:.4f} | {x["mean_delta_cost"]:+.4f} | '
            f'{x["mean_delta_percent"]:+.4f}% | '
            f'{x["wins"]}/{x["losses"]}/{x["ties"]} | '
            f'{x["wilcoxon_p_raw"]:.4g} | — | '
            f'[{ci[0]:+.4f}, {ci[1]:+.4f}] |'
        )
    lines += [
        "",
        "2-second results are a one-solver-seed screening run and are descriptive only. The 6- and 12-second comparisons use three solver seeds and are the validation evidence. Positive deltas mean higher (worse) cost than the reference.",
    ]
    out_md.write_text("\n".join(lines) + "\n")
    print(out_md.read_text())


if __name__ == "__main__":
    main()
