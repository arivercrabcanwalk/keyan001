"""Load Liu instances and frozen ALNS/TSALNS plans (read-only from rl_dyn)."""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import sys, os, json, hashlib
import numpy as np

_ENGINE = os.path.join(WX_ROOT, 'vendor')
_RLDYN = os.path.join(WX_ROOT, 'vendor')
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)
if _RLDYN not in sys.path:
    sys.path.insert(0, _RLDYN)

from lrphsd.problem import read_instance
from lrphsd.evaluator import evaluate

PLAN_DIR = os.path.join(WX_ROOT, "data", "plans")
_INS = {}
_PLANS = {}



def _resolve_inst(path):
    if path and os.path.isfile(path):
        return path
    cand = path
    if path and not os.path.isabs(path):
        cand = os.path.join(WX_ROOT, path)
        if os.path.isfile(cand):
            return cand
    name = os.path.basename(path) if path else ""
    for sub in ("data/instances/train", "data/instances/dev", "data/instances/test",
                "data/instances"):
        q = os.path.join(WX_ROOT, sub, name)
        if os.path.isfile(q):
            return q
    return path


def load_ins(path):
    path = _resolve_inst(path)
    if path not in _INS:
        _INS[path] = read_instance(path)
    return _INS[path]


def load_plans(name):
    """name: train_ours | dev_ours | test_ours | dev_ts | test_ts"""
    if name not in _PLANS:
        fn = os.path.join(PLAN_DIR, name + ".jsonl")
        rows = [json.loads(l) for l in open(fn)]
        for r in rows:
            if "path" in r:
                r["path"] = _resolve_inst(r["path"])
        _PLANS[name] = rows
    return _PLANS[name]


def bbox_of(ins, pad=2000.0):
    nodes = list(ins.nodes.values()) if isinstance(ins.nodes, dict) else list(ins.nodes)
    xs = [n.x for n in nodes]
    ys = [n.y for n in nodes]
    return (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)


def targets_xy(ins):
    return np.array([[n.x, n.y] for n in ins.targets], dtype=float)


def node_by_id(ins):
    if isinstance(ins.nodes, dict):
        return ins.nodes
    return {n.id: n for n in ins.nodes}


def inst_key(path):
    return os.path.basename(path)


def open_drones(ins, sol):
    """Materialise drones and planned trips from a static solution.

    Returns (fixed_cost, stations, drones) where
      stations[sid] = dict(x,y,R,kind,si)
      drones[i] = dict(sid, x, y, R, cap, large, duty_max,
                       trips=[list of node-id lists], ...)
    """
    p = ins.params
    fixed = 0.0
    stations = []
    drones = []
    nodes = node_by_id(ins)
    for si, kind in enumerate(sol["station_types"]):
        if not kind:
            continue
        if kind == 1:
            fixed += p.small_station_cost + p.small_drone_cost
        else:
            fixed += p.large_station_cost + p.small_drone_cost + p.large_drone_cost
        s = ins.stations[si]
        R = ins.radius(kind)
        sid = len(stations)
        stations.append(dict(x=s.x, y=s.y, R=R, kind=kind, si=si, sx=s.x, sy=s.y))
        routes = sol["routes"][si]
        for di, trips in enumerate(routes):
            if kind == 1 and di == 0:
                continue  # no large drone at SABS
            cap = p.large_battery if (di == 0 and kind == 2) else p.small_battery
            large = int(di == 0 and kind == 2)
            duty_max = p.large_duration if large else p.small_duration
            trip_list = [list(tr) for tr in trips if tr]
            if kind == 1 and di == 0:
                continue
            drones.append(dict(
                sid=sid, x=s.x, y=s.y, R=R, cap=cap, large=large,
                duty_max=duty_max, trips=trip_list, si=si, di=di,
            ))
    return fixed, stations, drones


def plan_nom_metrics(ins, sol):
    ev = evaluate(ins, sol)
    return ev
