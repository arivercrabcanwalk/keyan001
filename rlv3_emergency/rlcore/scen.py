"""Scenario registry + seed splits (data isolation: train / dev / test seeds never overlap)."""
import os
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
    "nowind": dict(kind="wx", mode="nowind"),           # sanity: exactly the author's deterministic world
    # paper B (emergency): author nominal world (no weather) + dynamic emergency inspection requests
    "emerg_low": dict(kind="urg", level="low"),
    "emerg_mid": dict(kind="urg", level="mid"),
    "emerg_high": dict(kind="urg", level="high"),
}


def day_key(day, path):
    """(day, map) -> scenario seed: every map gets its own weather / request realisation on each day
    (otherwise all maps of one day would share the same random stream and the paired test would have far fewer
    independent samples)."""
    import zlib
    return int(day) * 1000003 + zlib.crc32(os.path.basename(path).encode()) % 1000003


def make_env(row, day, scen, margin=None, record=False, urgent_w=None):
    cfg = SCENARIOS[scen]
    day = day_key(day, row["path"])
    ins = load_ins(row["path"])
    L = plan_layout(ins, row["solution"])
    if cfg["kind"] == "wx":
        from .weather import WeatherDay
        wx = None if cfg["mode"] == "nowind" else WeatherDay(day, bbox(ins), cfg["mode"], cfg.get("scale", 1.0))
        return Env(L, wx=wx, margin=margin, record=record)
    from .urgent import make_requests
    tg = [(t.id, t.x, t.y) for t in ins.targets]
    reqs = make_requests(day, tg, cfg["level"])
    env = Env(L, wx=None, requests=reqs, margin=margin, record=record, urgent_w=urgent_w)
    env.req_gen = (tg, cfg["level"])
    return env
