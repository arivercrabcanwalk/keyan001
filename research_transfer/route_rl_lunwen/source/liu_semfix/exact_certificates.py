#!/usr/bin/env python3
"""Independent exact subset-DP certificates for all ten 3_10 Liu cases."""

import hashlib
import json
from pathlib import Path

from lrphsd.evaluator import evaluate
from lrphsd.exact import solve_exact
from lrphsd.problem import read_instance

root = Path(__file__).resolve().parent
inputs = root / "external" / "LRPHSD" / "data" / "Instances_Alg"
output = root / "results" / "exact_3_10_certificates"
output.mkdir(parents=True, exist_ok=True)
paths = sorted(inputs.glob("3_10_*.txt"))
assert len(paths) == 10
rows = []
for path in paths:
    instance = read_instance(path)
    solution, meta = solve_exact(instance)
    audit = evaluate(instance, solution)
    if not audit["feasible"] or abs(audit["cost"] - meta["optimal_objective"]) > 1e-7:
        raise RuntimeError(f"exact/evaluator mismatch: {path.name}")
    witness = output / (path.stem + ".solution.json")
    witness.write_text(json.dumps(solution, indent=2) + "\n")
    rows.append({"instance": path.stem,
                 "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "solution_sha256": hashlib.sha256(witness.read_bytes()).hexdigest(),
                 "optimum": audit["cost"], "feasible": audit["feasible"],
                 "elapsed_seconds": meta["elapsed_seconds"]})
(output / "summary.json").write_text(json.dumps({"method": "exact subset DP independent of TSALNS",
                                                   "count": len(rows), "rows": rows}, indent=2) + "\n")
print(f"EXACT_CERTIFICATES {len(rows)}/{len(paths)} feasible objective_match=10/10")
