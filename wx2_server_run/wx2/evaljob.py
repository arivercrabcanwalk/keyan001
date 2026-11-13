"""Shared evaluation of one (instance, day, method). Used by all runners."""
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

import os, json, time, pickle, hashlib
import numpy as np
from . import inst as I
from . import sim as S
from . import policies as P
from . import const as C
from . import planadapt as PA

CACHE = os.path.join(WX_ROOT, "data", "days")
os.makedirs(CACHE, exist_ok=True)

# process-local
_INS = {}
_DAY = {}


def _ins(path):
    if path not in _INS:
        _INS[path] = I.load_ins(path)
    return _INS[path]


def sol_fp(sol):
    types = tuple((sol or {}).get("station_types") or [])
    rh = hashlib.sha1(repr((sol or {}).get("routes")).encode("utf-8", "replace")).hexdigest()[:16]
    return types, rh


def day_key(path, weather_seed, mode="storm", margin=0.08, sol=None,
            sigma_scale=1.0, speed_bias=0.0):
    fp = ""
    if sol is not None:
        types, rh = sol_fp(sol)
        fp = f"|{types}|{rh}"
    raw = f"{path}|{weather_seed}|{mode}|{margin}|{sigma_scale}|{speed_bias}{fp}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def materialize(path, sol, weather_seed, mode="storm", margin=0.08,
                sigma_scale=1.0, speed_bias=0.0):
    k = day_key(path, weather_seed, mode, margin, sol, sigma_scale, speed_bias)
    fp = os.path.join(CACHE, k + ".pkl")
    if k in _DAY:
        return _DAY[k]
    if os.path.exists(fp):
        with open(fp, "rb") as f:
            rec = pickle.load(f)
        _DAY[k] = rec
        return rec
    ins = _ins(path)
    wx, reqs, meta = S.make_day(ins, weather_seed, mode=mode,
                                sigma_scale=sigma_scale, speed_bias=speed_bias)
    asol, leftover = PA.repack(ins, sol, wx, margin=margin, t0=0.0, relocate=2)
    rec = dict(wx=wx, reqs=reqs, meta=meta, sol=asol, leftover=leftover,
               path=path, seed=weather_seed, mode=mode)
    # atomic write
    tmp = fp + f".tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        pickle.dump(rec, f, protocol=5)
    os.replace(tmp, fp)
    _DAY[k] = rec
    return rec


def get_pol(name, extra=None):
    extra = extra or {}
    if name == "RL" or name.startswith("RL_"):
        from . import learn as L
        net = L.load_net(extra["ckpt"])
        greedy = extra.get("greedy", True)
        return L.make_policy(net, greedy=greedy, rng=np.random.default_rng(extra.get("seed", 0)))
    if name.startswith("N4d_"):
        # format N4d_M_Dms e.g. N4d_32_1ms
        parts = name.split("_")
        M = int(parts[1])
        dms = float(parts[2].replace("ms", ""))
        base = P.name_policy(extra.get("base", "N1_240"))
        return P.make_rollout(M=M, base=base, deadline_ms=dms)
    if name.startswith("N4h_"):
        # limited horizon: N4h_32_60
        parts = name.split("_")
        M = int(parts[1]); H = float(parts[2])
        return P.make_rollout(M=M, base=P.name_policy(extra.get("base", "N1_240")), horizon=H)
    if name.startswith("N4_"):
        parts = name.split("_")
        M = int(parts[1][1:]) if len(parts) > 1 and "M" in parts[1] else 32
        base = P.name_policy(extra.get("base", "N1_240"))
        return P.make_rollout(M=M, base=base, seed=extra.get("seed", 0),
                              deadline_ms=extra.get("deadline_ms"),
                              horizon=extra.get("horizon"))
    if name == "N5":
        # extra['n5_table'] is dict (storm,wbin) -> policy name
        table = {k: P.name_policy(v) for k, v in extra["n5_table"].items()}
        return P.make_N5(table)
    return P.name_policy(name)


def eval_one(job):
    """job: dict(path, sol, day, mode, method, P, extra). sol may be the ORIGINAL plan."""
    path, day, mode = job["path"], job["day"], job.get("mode", "storm")
    rec = materialize(path, job["sol"], day, mode, margin=job.get("margin", 0.08),
                      sigma_scale=job.get("sigma_scale", 1.0),
                      speed_bias=job.get("speed_bias", 0.0))
    ins = _ins(path)
    pol = get_pol(job["method"], job.get("extra"))
    t0 = time.perf_counter()
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=job.get("P", C.P_MAIN))
    m = sim.run(pol, record_time=job.get("record_time", True))
    sec = time.perf_counter() - t0
    out = dict(m)
    out.update(path=path, day=int(day), mode=mode, method=job["method"],
               wall_sec=sec, leftover=len(rec["leftover"]),
               inst=os.path.basename(path),
               day_hash=rec["meta"]["day_hash"], wx_hash=rec["meta"]["wx_hash"],
               n_storm=rec["meta"]["n_storm"], n_bg=rec["meta"]["n_bg"],
               n_swept=rec["meta"]["n_swept"],
               plan_method=job.get("plan_method", "ours"))
    return out
