#!/usr/bin/env python3
"""Reopen and independently recompute ten small-instance exact certificates."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    from lrphsd.evaluator import evaluate
    from lrphsd.exact import solve_exact
    from lrphsd.problem import read_instance

    cert_dir = root / "results" / "exact_3_10_certificates"
    summary = json.loads((cert_dir / "summary.json").read_text())
    rows = summary["rows"]
    if len(rows) != 10 or summary["count"] != 10:
        raise SystemExit("exact certificate count mismatch")
    names = {row["instance"] for row in rows}
    if names != {f"3_10_{index}" for index in range(1, 11)}:
        raise SystemExit("exact certificate instance set mismatch")
    for row in rows:
        name = row["instance"]
        path = root / "external" / "LRPHSD" / "data" / "Instances_Alg" / (name + ".txt")
        witness_path = cert_dir / (name + ".solution.json")
        if sha(path) != row["input_sha256"] or sha(witness_path) != row["solution_sha256"]:
            raise SystemExit(f"certificate hash mismatch: {name}")
        instance = read_instance(path)
        witness = json.loads(witness_path.read_text())
        audit = evaluate(instance, witness)
        exact_solution, exact_meta = solve_exact(instance)
        exact_audit = evaluate(instance, exact_solution)
        if not audit["feasible"] or not exact_audit["feasible"] or not row["feasible"]:
            raise SystemExit(f"infeasible exact certificate: {name}")
        if abs(audit["cost"] - row["optimum"]) > 1e-7 or abs(audit["cost"] - exact_meta["optimal_objective"]) > 1e-7:
            raise SystemExit(f"exact objective mismatch: {name}")
    print("EXACT_CERTIFICATES 10/10 hashes feasibility and optimum match")


if __name__ == "__main__":
    main()
