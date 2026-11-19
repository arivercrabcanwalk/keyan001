"""Shared utilities for rlv3 packages: paths, Liu (EJOR 2026) parameters, instance/plan IO, official evaluator.
The RL policy never imports any ALNS/TSALNS code; TSALNS is only used to produce the author's static plans (A1)."""
import os, sys, json, time, glob, hashlib
import numpy as np

ROOT = os.environ.get("RLV3_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
VENDOR = os.path.join(ROOT, "vendor")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)
from lrphsd.problem import read_instance   # noqa: E402  official data contract
from lrphsd.evaluator import evaluate      # noqa: E402  official independent evaluator

# ---- Liu et al. (2026) parameters (identical to lrphsd.problem.Parameters) ----
SPEED = 900.0          # m/min  (15 m/s cruise airspeed)
VA_MS = 15.0
P1 = 0.018             # flight energy per minute (LD battery = 1)
P2 = 0.020             # hover energy per minute (service energy 0.2 / 10 min)
T_SVC = 10.0
CAP = {0: 1.0, 1: 0.81}            # drone slot 0 = large drone (DABS), 1 = small drone
LIMIT = {0: 600.0, 1: 480.0}       # per-drone cumulative operating time limit (author constraint)
SABS_FIX = 22.8 + 5.0
DABS_FIX = 30.4 + 8.0 + 5.0
TIME_COST = 0.5


def rel(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def stable_rng(*keys):
    h = hashlib.blake2b(digest_size=8)
    for k in keys:
        h.update(str(k).encode()); h.update(b"|")
    return np.random.default_rng(int.from_bytes(h.digest(), "little") % (2 ** 63))


_INS = {}


def load_ins(path):
    p = rel(path)
    if p not in _INS:
        _INS[p] = read_instance(p)
    return _INS[p]


def load_plans(path):
    rows = []
    seen = set()
    for l in open(rel(path), encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        if "error" in r or not isinstance(r.get("solution"), dict) or not r.get("path"):
            raise ValueError("missing/failed author anchor in plan file: " + str(r.get("path")))
        if r["path"] in seen:
            raise ValueError("duplicate plan/attempt: " + r["path"])
        seen.add(r["path"])
        rows.append(r)
    if not rows:
        raise ValueError("empty author plan population")
    return rows


def fixed_cost(types):
    return sum(SABS_FIX if t == 1 else DABS_FIX if t == 2 else 0.0 for t in types)


def plan_layout(ins, sol):
    """Materialise stations / drones / planned trips from an official solution (author TSALNS plan).
    Returns dict(stations=[...], drones=[...], assign={tid: station_index}, fixed=float, n_open=int)."""
    if sol.get("instance_sha256") != ins.sha256:
        raise ValueError("author anchor is not bound to this map")
    if any(t.service <= 0 for t in ins.targets):
        raise ValueError("the timed service model requires positive inspection duration")
    official = evaluate(ins, sol)
    if not official["feasible"]:
        raise ValueError("infeasible author anchor: " + repr(official["issues"]))
    stations, drones, assign = [], [], {}
    for si, kind in enumerate(sol["station_types"]):
        if not kind:
            continue
        s = ins.stations[si]
        k = len(stations)
        stations.append(dict(k=k, si=si, x=s.x, y=s.y, kind=int(kind), R=ins.radius(kind), drones=[]))
        for di in ((0, 1) if kind == 2 else (1,)):
            trips = [list(t) for t in sol["routes"][si][di] if t]
            d = dict(i=len(drones), st=k, di=di, cap=ins.capacity(di), limit=ins.duration(kind), trips=trips)
            stations[k]["drones"].append(d["i"])
            drones.append(d)
            for tr in trips:
                for tid in tr:
                    assign[tid] = k
    tg = {t.id: (t.x, t.y, t.service, t.energy) for t in ins.targets}
    return dict(stations=stations, drones=drones, assign=assign, targets=tg,
                fixed=official["fixed_cost"], n_open=len(stations),
                n_dabs=sum(1 for s in stations if s["kind"] == 2), types=list(sol["station_types"]))


def bbox(ins, pad=3000.0):
    xs = [n.x for n in list(ins.targets) + list(ins.stations)]
    ys = [n.y for n in list(ins.targets) + list(ins.stations)]
    return (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)


def done_keys(path, keyf):
    s = set()
    if os.path.exists(path):
        for l in open(path):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if "error" not in r:
                s.add(keyf(r))
    return s


def progress(msg):
    p = os.path.join(ROOT, "PROGRESS_SERVER.md")
    with open(p, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M:%S %Z')} {msg}\n")
    print("[progress]", msg, flush=True)


def device(pref=None):
    import torch
    pref = pref or os.environ.get("RLV3_DEVICE", "auto")
    if pref == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(pref)


def seed_all(s):
    import random, torch
    random.seed(s); np.random.seed(s); torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)


def glob_rel(pattern):
    return sorted(os.path.relpath(p, ROOT) for p in glob.glob(rel(pattern)))
