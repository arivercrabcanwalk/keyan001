#!/usr/bin/env python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lrphsd import fidelity_ops_v5 as ops
from lrphsd.problem import read_instance
from lrphsd.greedy import build as greedy_build, station_set
from lrphsd.evaluator import evaluate
from carl.kernel import CAEngine

INST = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"

def norm(sol):
    return (
        tuple(sol["station_types"]),
        tuple(tuple(tuple(tuple(tr) for tr in drone) for drone in station)
              for station in sol["routes"]),
    )

def main():
    paths = sorted(INST.glob("*.txt"))
    assert len(paths) == 120, len(paths)
    exact = 0
    failures = []
    for ix, path in enumerate(paths, 1):
        ins = read_instance(path)
        ops.prepare(ins)
        types = station_set(ins)
        py_sol = greedy_build(ins, types)
        eng = CAEngine(ins)
        try:
            eng.load(0, py_sol)
            rc = eng.rebuild_official_greedy(0)
            if rc != 1:
                failures.append((path.stem, "native_rc", rc))
                continue
            c_sol = eng.export(0)
            if norm(c_sol) != norm(py_sol):
                failures.append((path.stem, "route_mismatch",
                                 norm(py_sol), norm(c_sol)))
                continue
            audit = evaluate(ins, c_sol)
            if not audit["feasible"]:
                failures.append((path.stem, "infeasible", audit["issues"][:5]))
                continue
            exact += 1
        finally:
            eng.free()
        if ix % 20 == 0:
            print(f"[greedy-diff] {ix}/120 exact={exact} failures={len(failures)}",
                  flush=True)
    print(f"RESULT exact={exact}/120 failures={len(failures)}")
    for item in failures[:20]:
        print("FAIL", item)
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
