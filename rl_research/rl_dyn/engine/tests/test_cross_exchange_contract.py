
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lrphsd import fidelity_ops_v5 as ops
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
from carl.core import Coverage, Mirror
from carl.kernel import CAEngine
from carl.neighborhood import Context, _route_cross_exchange, apply_move

INST = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


def verify(instance, mode):
    ins = read_instance(INST / (instance + ".txt"))
    ops.prepare(ins)
    sol = build(ins)
    eng = CAEngine(ins)
    try:
        eng.load(0, sol)
        ctx = Context(ins, eng, Mirror(ins, sol), Coverage(ins), random.Random(0))
        for seed in range(1000):
            ctx.rng = random.Random(seed)
            move = _route_cross_exchange(ctx, 0)
            if move is None or move.swap_mode != mode:
                continue
            new_types = apply_move(eng, move, sol["station_types"], ins)
            if new_types is None:
                continue
            candidate = eng.export(1)
            audit = evaluate(ins, candidate)
            assert audit["feasible"], audit["issues"][:5]
            assert new_types == sol["station_types"]
            assert candidate["routes"] != sol["routes"]
            before = sorted(n for st in sol["routes"] for dr in st for tr in dr for n in tr)
            after = sorted(n for st in candidate["routes"] for dr in st for tr in dr for n in tr)
            assert before == after
            return move.tag, move.swap_pairs, audit["cost"]
        raise AssertionError(f"no feasible exchange found: {instance} mode={mode}")
    finally:
        eng.free()


if __name__ == "__main__":
    print("PASS", "cross_drone", verify("3_10_1", 1), flush=True)
    print("PASS", "cross_trip", verify("3_10_3", 2), flush=True)
