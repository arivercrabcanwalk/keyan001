"""Scenario registry + seed splits (data isolation: train / dev / test seeds never overlap)."""
import hashlib
import pickle
from .common import load_ins, plan_layout, bbox
from .env import Env

TRAIN_DAY0 = 1_000_000          # train days: TRAIN_DAY0 + k (k random)
DEV_DAYS = list(range(50000, 50020))
TEST_DAYS = list(range(90000, 90100))

SCENARIOS = {
    # paper A (weather): physics wind + moving thunderstorm cells (storm day with prob 0.35)
    "weather": dict(kind="wx", mode="mix"),
    "weather_storm": dict(kind="wx", mode="storm"),     # every day a storm day (stress split)
    "weather_wind": dict(kind="wx", mode="wind"),       # wind only, no cells
    "weather_x1.3": dict(kind="wx", mode="mix", scale=1.3),   # sensitivity: 30 % windier
    "weather_paired_clear": dict(kind="wx", mode="paired", cells=False, engineering_only=True),
    "weather_paired_cells": dict(kind="wx", mode="paired", cells=True, engineering_only=True),
    "nowind": dict(kind="wx", mode="nowind"),           # sanity: exactly the author's deterministic world
    "fixed_e4": dict(kind="wx", mode="fixed", wind=(4.0, 0.0)),
    "fixed_n8": dict(kind="wx", mode="fixed", wind=(0.0, 8.0)),
    # paper B (emergency): author nominal world (no weather) + dynamic emergency inspection requests
    "emerg_low": dict(kind="urg", level="low"),
    "emerg_mid": dict(kind="urg", level="mid"),
    "emerg_high": dict(kind="urg", level="high"),
}
for _pattern in ("random", "clustered"):
    for _level in ("low", "mid", "high"):
        SCENARIOS[f"emerg_{_pattern}_{_level}"] = dict(kind="urg", level=_level, pattern=_pattern)


def scenario_input_hash(env):
    """Hash the original exogenous input, frozen before any policy action."""
    return env.scenario_input_hash


def _freeze_input(env):
    payload = (env.L, env.wx, env.requests)
    env.scenario_input_hash = hashlib.sha256(pickle.dumps(payload, protocol=4)).hexdigest()
    return env


def day_key(day, map_sha):
    """Independent synthetic stream per original map and day, invariant to file names."""
    return int.from_bytes(hashlib.sha256(f"rlv3-scen-v2|{map_sha}|{int(day)}".encode()).digest()[:16], "big")


def make_env(row, day, scen, margin=None, record=False, urgent_w=None):
    cfg = SCENARIOS[scen]
    ins = load_ins(row["path"])
    day = day_key(day, ins.sha256)
    if scen in ("nowind", "fixed_e4", "fixed_n8"):
        L = plan_layout(ins, row["solution"], fixed_scenario=scen)
    else:
        L = plan_layout(ins, row["solution"])
    if cfg["kind"] == "wx":
        from .weather import WeatherDay, FixedWeather
        if cfg["mode"] == "paired":
            from .paired_weather import make_paired_weather
            clear, cells = make_paired_weather(day, bbox(ins), cfg.get("scale", 1.0))
            wx = cells if cfg["cells"] else clear
        else:
            wx = (None if cfg["mode"] == "nowind" else
              FixedWeather(*cfg["wind"]) if cfg["mode"] == "fixed" else
              WeatherDay(day, bbox(ins), cfg["mode"], cfg.get("scale", 1.0)))
        return _freeze_input(Env(L, wx=wx, margin=margin, record=record))
    from .urgent import make_requests
    tg = [(t.id, t.x, t.y) for t in ins.targets]
    pattern = cfg.get("pattern", "clustered")
    reqs = make_requests(day, tg, cfg["level"], pattern=pattern)
    env = Env(L, wx=None, requests=reqs, margin=margin, record=record, urgent_w=urgent_w)
    env.req_gen = (tg, cfg["level"], pattern)
    return _freeze_input(env)
