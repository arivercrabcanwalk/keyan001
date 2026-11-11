#!/usr/bin/env python
"""Aggregate benchmark results and run paired statistics.

Reads every ``<instance>__<method>__s<seed>.json`` in a run directory,
aggregates runs per (method, instance) and compares methods with paired
Wilcoxon signed-rank tests, bootstrap CIs and Holm correction.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carl.stats import bootstrap_ci, holm, paired_summary, wilcoxon_signed_rank  # noqa: E402


def load_runs(run_dir):
    """Fail closed against each run manifest; never analyze partial matrices."""
    runs = {}
    budgets = set()
    manifests = []
    code_hashes = set()
    instance_hashes = {}
    resource_protocols = set()
    for d in str(run_dir).split(","):
        root = Path(d)
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text())
        resource_protocols.add((manifest.get("workers"), manifest.get("cpu_quota")))
        if manifest.get("finished") is None or manifest.get("errors") != 0:
            raise ValueError(f"unfinished/failed manifest: {manifest_path}")
        methods = manifest.get("methods", [])
        seeds = [int(x) for x in manifest.get("seeds", [])]
        instances = [Path(x).stem for x in manifest.get("instances", [])]
        if (not methods or len(methods) != len(set(methods)) or
                not seeds or len(seeds) != len(set(seeds)) or
                not instances or len(instances) != len(set(instances))):
            raise ValueError(f"invalid task design in {manifest_path}")
        expected = {(m, i, seed) for m in methods for i in instances for seed in seeds}
        if manifest.get("tasks") != len(expected):
            raise ValueError(f"manifest task count mismatch: {manifest_path}")
        paths = sorted(root.glob("*__s*.json"))
        if len(paths) != len(expected):
            raise ValueError(f"record count mismatch in {root}: {len(paths)} != {len(expected)}")
        actual = set()
        for p in paths:
            try:
                data = json.loads(p.read_text())
            except (ValueError, OSError) as exc:
                raise ValueError(f"unreadable run: {p}") from exc
            if data.get("status") != "ok" or data.get("feasible") is not True:
                raise ValueError(f"failed/invalid run requires audit: {p}")
            cost = data.get("cost")
            budget = data.get("seconds")
            if not isinstance(cost, (int, float)) or not math.isfinite(cost):
                raise ValueError(f"nonfinite/missing cost: {p}")
            if not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
                raise ValueError(f"invalid/missing budget: {p}")
            if abs(float(budget) - float(manifest["seconds"])) > 1e-12:
                raise ValueError(f"record/manifest budget mismatch: {p}")
            key = (data["method"], data["instance"], int(data["seed"]))
            if key not in expected:
                raise ValueError(f"unexpected task identity: {key}")
            if key in actual or key in runs:
                raise ValueError(f"duplicate run identity: {key}")
            if not data.get("task_identity") or not data.get("provenance"):
                raise ValueError(f"missing task provenance: {p}")
            provenance = data["provenance"]
            code_hash = provenance.get("code_sha256")
            instance_hash = provenance.get("instance_sha256")
            if not code_hash or not instance_hash:
                raise ValueError(f"missing source/instance hash: {p}")
            code_hashes.add(code_hash)
            old_hash = instance_hashes.setdefault(data["instance"], instance_hash)
            if old_hash != instance_hash:
                raise ValueError(f"instance bytes differ across methods: {data['instance']}")
            actual.add(key)
            runs[key] = data
            budgets.add(float(budget))
        if actual != expected:
            missing = sorted(expected - actual)
            raise ValueError(f"incomplete task matrix in {root}: {missing[:20]}")
        manifests.append({"directory": str(root), "tasks": len(expected),
                          "workers": manifest.get("workers"),
                          "seconds": manifest["seconds"],
                          "methods": methods, "instances": len(instances),
                          "seeds": seeds, "cpu_quota": manifest.get("cpu_quota")})
    if len(budgets) != 1:
        raise ValueError(f"mixed wall-clock budgets: {sorted(budgets)}")
    if len(code_hashes) != 1:
        raise ValueError(f"mixed source code hashes: {sorted(code_hashes)}")
    if len(resource_protocols) != 1:
        raise ValueError(f"mixed worker/cgroup resource protocol: {sorted(resource_protocols)}")
    return runs, manifests


def _load_runs_single(run_dir):
    return load_runs(run_dir)[0]


def method_instance_means(runs):
    acc = defaultdict(list)
    for (m, inst, seed), d in runs.items():
        if d.get("cost") is not None and d.get("feasible", False):
            acc[(m, inst)].append(float(d["cost"]))
    return {k: float(np.mean(v)) for k, v in acc.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--reference", default="m1")
    ap.add_argument("--baseline", default="m0")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    runs, run_manifests = load_runs(args.run)
    if not runs:
        raise SystemExit("no runs found")
    means = method_instance_means(runs)
    methods = sorted({m for (m, _) in means})
    instances = sorted({i for (_, i) in means})
    # Refuse silent pairwise deletion: every method must cover every instance.
    missing = [(m, i) for m in methods for i in instances if (m, i) not in means]
    if missing:
        raise SystemExit(f"incomplete method-instance matrix: {missing[:20]} (n={len(missing)})")
    seed_sets = {}
    for (m, i, seed), d in runs.items():
        seed_sets.setdefault((m, i), set()).add(seed)
    if seed_sets:
        expected = None
        for key, values in seed_sets.items():
            if expected is None:
                expected = values
            elif values != expected:
                raise SystemExit(f"unpaired seed design at {key}: {sorted(values)} != {sorted(expected)}")
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    table = {m: {i: means.get((m, i)) for i in instances} for m in methods}
    with open(outdir / "paired_table.csv", "w") as f:
        f.write("method," + ",".join(instances) + ",mean\n")
        for m in methods:
            row = [table[m][i] for i in instances]
            vals = [v for v in row if v is not None]
            f.write(m + "," + ",".join("" if v is None else f"{v:.6f}" for v in row)
                    + f",{np.mean(vals):.6f}\n")

    ref = args.reference
    if ref not in methods:
        raise SystemExit(f"missing reference method: {ref}")
    comparisons = []
    for m in methods:
        if m == ref:
            continue
        pairs = [(table[m][i], table[ref][i]) for i in instances
                 if table[m][i] is not None and table[ref][i] is not None]
        if len(pairs) < 3:
            continue
        x = [p[0] for p in pairs]
        y = [p[1] for p in pairs]
        comparisons.append({"method": m, "ref": ref,
                            **paired_summary(x, y),
                            "wilcoxon": wilcoxon_signed_rank(x, y),
                            "bootstrap": bootstrap_ci(x, y)})
    if comparisons:
        adj = holm([c["wilcoxon"]["p_value"] for c in comparisons])
        for c, a in zip(comparisons, adj):
            c["p_holm"] = a
            c["significant"] = bool(a < 0.05)

    # per-size descriptive comparison vs reference
    groups = {}
    for i in instances:
        key = "_".join(i.split("_")[:2])
        groups.setdefault(key, []).append(i)
    per_size = {}
    for m in methods:
        if m == ref:
            continue
        per_size[m] = {}
        for key, insts in groups.items():
            diffs = []
            for i in insts:
                if table[m][i] is not None and table[ref][i] not in (None, 0):
                    diffs.append(100.0 * (table[m][i] - table[ref][i]) / table[ref][i])
            if diffs:
                per_size[m][key] = float(np.mean(diffs))

    # feasibility and runtime
    feasibility = {}
    runtime = {}
    runtime_measure = {}
    steps = {}
    outer_iterations = {}
    for m in methods:
        rs = [d for (mm, _, _), d in runs.items() if mm == m]
        feasibility[m] = float(np.mean([1.0 if d.get("feasible") else 0.0 for d in rs]))
        solver_vals = [d.get("solver_seconds") for d in rs if d.get("solver_seconds") is not None]
        if len(solver_vals) == len(rs):
            runtime[m] = float(np.mean(solver_vals))
            runtime_measure[m] = "solver_seconds"
        else:
            legacy_vals = [d.get("elapsed_seconds") or d.get("wall_seconds") or 0 for d in rs]
            runtime[m] = float(np.mean(legacy_vals))
            runtime_measure[m] = "legacy_elapsed_seconds (evaluation included or timing boundary unknown)"
        step_vals = [d.get("steps") for d in rs if isinstance(d.get("steps"), (int, float))]
        steps[m] = float(np.mean(step_vals)) if step_vals else None
        outer_vals = []
        for d in rs:
            value = d.get("outer_iterations_attempted")
            if value is None:
                value = (d.get("meta") or {}).get("outer_iterations_attempted")
            if isinstance(value, (int, float)):
                outer_vals.append(value)
        outer_iterations[m] = float(np.mean(outer_vals)) if outer_vals else None

    # anytime curve on common checkpoints
    anytime = defaultdict(lambda: defaultdict(list))
    for (m, inst, seed), d in runs.items():
        for cp, val in (d.get("anytime") or {}).items():
            if val is not None:
                anytime[m][cp].append(float(val))
    anytime_summary = {m: {cp: float(np.mean(v)) for cp, v in sorted(d.items())}
                       for m, d in anytime.items()}

    report = {"run": str(args.run), "n_runs": len(runs), "methods": methods,
              "instances": instances, "reference": ref, "baseline": args.baseline,
              "feasibility": feasibility, "mean_runtime_seconds": runtime, "runtime_measure": runtime_measure,
              "mean_initialization_seconds": {m: float(np.mean([d.get("initialization_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "mean_search_seconds": {m: float(np.mean([d.get("search_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "mean_controller_load_seconds": {m: float(np.mean([d.get("controller_load_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "mean_evaluation_seconds": {m: float(np.mean([d.get("evaluation_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "mean_end_to_end_seconds": {m: float(np.mean([d.get("end_to_end_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "mean_budget_overrun_seconds": {m: float(np.mean([d.get("budget_overrun_seconds") or 0.0 for (mm, _, _), d in runs.items() if mm == m])) for m in methods},
              "run_manifests": run_manifests,
              "mean_steps": steps, "mean_outer_iterations": outer_iterations,
              "comparisons": comparisons,
              "anytime": anytime_summary, "per_size_pct_vs_ref": per_size,
              "means": {m: {i: table[m][i] for i in instances} for m in methods}}
    (outdir / "analysis.json").write_text(json.dumps(report, indent=1))

    lines = [f"# Benchmark analysis: {args.run}", "",
             f"Runs: {len(runs)}  Methods: {', '.join(methods)}  Reference: {ref}", "",
             "| method | mean cost | feasible | runtime s | steps | outer iters | vs ref % | wins/losses | dz | rank-biserial | p (Holm) | 95% CI |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in methods:
        vals = [table[m][i] for i in instances if table[m][i] is not None]
        mc = float(np.mean(vals)) if vals else float("nan")
        c = next((x for x in comparisons if x["method"] == m), None)
        if c:
            ci = c["bootstrap"]
            step_text = f"{steps[m]:.0f}" if steps[m] is not None else "-"
            outer_text = f"{outer_iterations[m]:.0f}" if outer_iterations[m] is not None else "-"
            lines.append(f"| {m} | {mc:.4f} | {feasibility[m]:.3f} | {runtime[m]:.2f} | "
                         f"{step_text} | {outer_text} | {c['pct_diff']:+.3f} | {c['wins']}/{c['losses']} | "
                         f"{c['cohen_dz']:+.3f} | {c['wilcoxon']['rank_biserial']:+.3f} | "
                         f"{c['p_holm']:.4f} | [{ci['lo']:+.4f}, {ci['hi']:+.4f}] |")
        else:
            step_text = f"{steps[m]:.0f}" if steps[m] is not None else "-"
            outer_text = f"{outer_iterations[m]:.0f}" if outer_iterations[m] is not None else "-"
            lines.append(f"| {m} | {mc:.4f} | {feasibility[m]:.3f} | {runtime[m]:.2f} | "
                         f"{step_text} | {outer_text} | - | - | - | - | - | - |")
    if per_size:
        keys = sorted({k for m in per_size for k in per_size[m]})
        lines += ["", "## Per-size mean % difference vs " + ref, "",
                  "| method | " + " | ".join(keys) + " |",
                  "|---|" + "---|" * len(keys)]
        for m in methods:
            if m not in per_size:
                continue
            lines.append(f"| {m} | " + " | ".join(
                (f"{per_size[m][k]:+.2f}" if k in per_size[m] else "") for k in keys) + " |")
    lines += ["", "## Anytime mean best cost", ""]
    cps = sorted({cp for m in anytime_summary for cp in anytime_summary[m]})
    lines.append("| method | " + " | ".join(cps) + " |")
    lines.append("|---|" + "---|" * len(cps))
    for m in methods:
        lines.append(f"| {m} | " + " | ".join(
            f"{anytime_summary.get(m, {}).get(cp, float('nan')):.3f}" for cp in cps) + " |")
    (outdir / "ANALYSIS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
