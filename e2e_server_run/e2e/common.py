"""Shared utilities: device, Liu constants, instance generator / IO, solution format, official evaluator.
NO ALNS / TSALNS code is imported by any RL module (baselines live in baselines/ and wx2/reopt.py only)."""
import os, sys, json, math, time, hashlib, random
import numpy as np
import torch

ROOT = os.environ.get("E2E_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
VENDOR = os.path.join(ROOT, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)
from lrphsd.problem import read_instance, Instance, Node, Parameters   # noqa: E402  (official data contract)
from lrphsd.evaluator import evaluate                                   # noqa: E402  (official independent evaluator)

# ---- Liu parameters (identical to lrphsd.problem.Parameters) ----
SPEED = 900.0; FE = 0.018; E_T = 0.2; S_T = 10.0
SB, LB = 0.81, 1.0; SR, LR = 4000.0, 5000.0; SD, LD = 480.0, 600.0
SABS_FIX = 22.8 + 5.0; DABS_FIX = 30.4 + 8.0 + 5.0; TIME_COST = 0.5
SCALE = 15000.0
# drone tokens per station: 0 = SABS small drone, 1 = DABS large drone, 2 = DABS small drone
TOK_KIND = np.array([1, 2, 2]); TOK_DI = np.array([1, 0, 1])
TOK_CAP = np.array([SB, LB, SB]); TOK_RAD = np.array([SR, LR, LR]); TOK_LIM = np.array([SD, LD, LD])


def device(pref=None):
    pref = pref or os.environ.get("E2E_DEVICE", "auto")
    if pref == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(pref)


def seed_all(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)


def gen(n, ns, rng, scale=SCALE):
    """Liu-style generator: stations uniform in [0,scale]^2, targets uniform but within 4750 m of some station."""
    st = rng.uniform(0, scale, (ns, 2))
    tg = np.zeros((0, 2))
    while len(tg) < n:
        c = rng.uniform(0, scale, (4 * n, 2))
        d = np.sqrt(((c[:, None, :] - st[None]) ** 2).sum(-1)).min(1)
        tg = np.concatenate([tg, c[d <= 4750]])
    return tg[:n], st


def size_scale(n, ns):
    """Map side length grows with sqrt(#stations) for large instances (Liu: 15 km for <=10 stations)."""
    return SCALE * max(1.0, math.sqrt(ns / 10.0))


def from_instance(ins):
    tg = np.array([[t.x, t.y] for t in ins.targets]); st = np.array([[s.x, s.y] for s in ins.stations])
    return tg, st, [t.id for t in ins.targets], [s.id for s in ins.stations]


def write_instance(path, tg, st):
    """Official format (as Liu's files): targets first (energy 0.2, service 10), then stations (0, 0)."""
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
    """types: list per station (0 closed, 1 SABS, 2 DABS); routes[s] = [large-drone trips, small-drone trips] (node ids)."""
    return {"schema_version": 1, "instance": ins.name, "instance_sha256": ins.sha256,
            "station_types": [int(t) for t in types], "routes": routes}


def eval_solution(ins, sol):
    r = evaluate(ins, sol)
    return r


def fixed_cost(types):
    return sum(SABS_FIX if t == 1 else DABS_FIX if t == 2 else 0.0 for t in types)


class JsonlLog:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "a")

    def write(self, **kw):
        kw.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.f.write(json.dumps(kw) + "\n"); self.f.flush()


def done_keys(path, key):
    s = set()
    if os.path.exists(path):
        for l in open(path):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if "error" not in r:
                s.add(key(r))
    return s


def progress(msg):
    """Append a line to PROGRESS_SERVER.md (server-side progress log)."""
    p = os.path.join(ROOT, "PROGRESS_SERVER.md")
    with open(p, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M:%S %Z')} {msg}\n")
    print("[progress]", msg, flush=True)


def atomic_save(obj, path):
    tmp = path + ".tmp"
    torch.save(obj, tmp); os.replace(tmp, path)
