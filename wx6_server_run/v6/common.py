"""v6 shared helpers (no torch): official instance IO, independent evaluator, Liu-style generator, plan IO."""
import os, sys, json, math, time
import numpy as np

ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
VENDOR = os.path.join(ROOT, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)
from lrphsd.problem import read_instance, Instance, Node, Parameters   # noqa: E402,F401
from lrphsd.evaluator import evaluate                                   # noqa: E402,F401

E_T = 0.2; S_T = 10.0
SABS_FIX = 22.8 + 5.0; DABS_FIX = 30.4 + 8.0 + 5.0
SCALE = 15000.0


def gen(n, ns, rng, scale=SCALE, rad=4750.0):
    """Liu-style generator: stations uniform in [0,scale]^2, targets uniform but within `rad` m of some station."""
    st = rng.uniform(0, scale, (ns, 2))
    tg = np.zeros((0, 2))
    while len(tg) < n:
        c = rng.uniform(0, scale, (4 * n, 2))
        d = np.sqrt(((c[:, None, :] - st[None]) ** 2).sum(-1)).min(1)
        tg = np.concatenate([tg, c[d <= rad]])
    return tg[:n], st


def size_scale(n, ns):
    return SCALE * max(1.0, math.sqrt(ns / 10.0))


def write_instance(path, tg, st):
    lines = ["CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME"]
    k = 1
    for x, y in tg:
        lines.append(f"{k}\t{x:.4f}\t{y:.4f}\t{E_T:.4f}\t{S_T:.4f}"); k += 1
    for x, y in st:
        lines.append(f"{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000"); k += 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def to_solution(ins, types, routes):
    return {"schema_version": 1, "instance": ins.name, "instance_sha256": ins.sha256,
            "station_types": [int(t) for t in types], "routes": routes}


def fixed_cost(types):
    return sum(SABS_FIX if t == 1 else DABS_FIX if t == 2 else 0.0 for t in types)


def load_plans(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def parse_days(s):
    out = []
    for part in str(s).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def progress(msg):
    p = os.path.join(ROOT, "PROGRESS_SERVER.md")
    with open(p, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M:%S %Z')} {msg}\n")
    print("[progress]", msg, flush=True)
