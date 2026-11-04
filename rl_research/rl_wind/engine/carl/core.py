"""Solution mirror, exact costs and instance helpers for CA-RL-TSALNS.

The kernel owns the authoritative search state.  Python keeps a *mirror* of
the current solution that is refreshed from ``r6_export`` after every accepted
move; it is used only to choose where a joint move should act.  Every cost and
every feasibility verdict in the search still comes from the kernel, and the
returned solution is re-checked by the independent evaluator.
"""
from dataclasses import dataclass
from pathlib import Path

from lrphsd.problem import Parameters, read_instance
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build as greedy_build


@dataclass
class InstanceSet:
    name: str
    paths: list


def load_instance(path, params=None):
    return read_instance(path, params)


def instance_groups(inst_dir):
    """Group official instances by (n_stations, n_targets)."""
    groups = {}
    for p in sorted(Path(inst_dir).glob("*.txt")):
        stem = p.stem
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        key = (int(parts[0]), int(parts[1]))
        groups.setdefault(key, []).append(p)
    for key in groups:
        groups[key].sort(key=lambda p: int(p.stem.split("_")[2]))
    return dict(sorted(groups.items()))


def split_instances(inst_dir, train_idx=(1, 2, 3, 4, 5, 6), val_idx=(7, 8),
                    test_idx=(9, 10)):
    """Grouped split by instance geometry seed inside every size group.

    The official 120 instances are 12 size groups x 10 independent geometry
    seeds.  Splitting by seed keeps the same size coverage in every split and
    never puts two runs of the same geometry on both sides.
    """
    groups = instance_groups(inst_dir)
    splits = {"train": [], "val": [], "test": []}
    for key, paths in groups.items():
        for p in paths:
            idx = int(p.stem.split("_")[2])
            if idx in train_idx:
                splits["train"].append(p)
            elif idx in val_idx:
                splits["val"].append(p)
            elif idx in test_idx:
                splits["test"].append(p)
    return splits


class Mirror:
    """Python mirror of a kernel solution."""

    __slots__ = ("types", "routes", "pos", "station_targets", "n_targets")

    def __init__(self, ins, sol):
        self.types = []
        self.routes = []
        self.pos = {}
        self.station_targets = []
        self.n_targets = len(ins.targets)
        self.update(sol)

    def update(self, sol):
        self.types = list(sol["station_types"])
        self.routes = sol["routes"]
        pos = {}
        station_targets = []
        for si, station in enumerate(self.routes):
            ids = []
            for di, trips in enumerate(station):
                for ti, trip in enumerate(trips):
                    for pi, nid in enumerate(trip):
                        pos[nid] = (si, di, ti, pi)
                        ids.append(nid)
            station_targets.append(ids)
        self.pos = pos
        self.station_targets = station_targets

    def counts(self):
        return [len(x) for x in self.station_targets]


def fixed_cost(ins, types):
    p = ins.params
    total = 0.0
    for kind in types:
        if kind == 1:
            total += p.small_station_cost + p.small_drone_cost
        elif kind == 2:
            total += p.large_station_cost + p.large_drone_cost + p.small_drone_cost
    return total


def kernel_cost(ins, eng, slot, types):
    """Full objective: fixed station/drone cost + kernel route-set cost."""
    return eng.cost(slot) + fixed_cost(ins, types)


def independent_validate(ins, sol):
    return evaluate(ins, sol)


class Coverage:
    """Coverage tables under the two open station types (cached views)."""

    def __init__(self, ins):
        self.ins = ins
        self.stations = ins.stations
        self.targets = ins.targets
        self.tidx = {n.id: i for i, n in enumerate(ins.targets)}
        self.tlist = [n.id for n in ins.targets]
        nt = len(ins.targets)
        self.nt = nt
        self.ns = len(ins.stations)
        dist = ins.dist
        r1, r2 = ins.params.small_radius, ins.params.large_radius
        self.cover1 = [[False] * nt for _ in range(self.ns)]
        self.cover2 = [[False] * nt for _ in range(self.ns)]
        self.by1 = [[] for _ in range(self.ns)]
        self.by2 = [[] for _ in range(self.ns)]
        self.cnt_all = [0] * nt
        nearest = {}
        for si, st in enumerate(ins.stations):
            c1, c2 = self.cover1[si], self.cover2[si]
            b1, b2 = self.by1[si], self.by2[si]
            for ti, t in enumerate(ins.targets):
                d = ins.gdist[st.id, t.id]
                if d <= r1:
                    c1[ti] = True
                    b1.append(t.id)
                if d <= r2:
                    c2[ti] = True
                    b2.append(t.id)
                    self.cnt_all[ti] += 1
                if t.id not in nearest or d < nearest[t.id]:
                    nearest[t.id] = d
        self.nearest = nearest
        self.order_all = sorted(self.tlist, key=lambda n: nearest[n], reverse=True)
        self._alt_cache = {}

    def covers(self, si, nid, kind):
        ti = self.tidx[nid]
        return (self.cover1 if kind == 1 else self.cover2)[si][ti]

    def covering_stations(self, nid, kind, types, exclude=None):
        ti = self.tidx[nid]
        table = self.cover1 if kind == 1 else self.cover2
        out = []
        for si, k in enumerate(types):
            if k != kind:
                continue
            if exclude is not None and si == exclude:
                continue
            if table[si][ti]:
                out.append(si)
        return out

    def cover_count(self, nid):
        return self.cnt_all[self.tidx[nid]]

    def alt_counts(self, types):
        """Number of open stations covering each target, cached by type tuple."""
        key = tuple(types)
        cached = self._alt_cache.get(key)
        if cached is not None:
            return cached
        counts = [0] * self.nt
        for si, kind in enumerate(key):
            if not kind:
                continue
            table = self.cover1[si] if kind == 1 else self.cover2[si]
            for ti in range(self.nt):
                if table[ti]:
                    counts[ti] += 1
        if len(self._alt_cache) > 256:
            self._alt_cache.clear()
        self._alt_cache[key] = counts
        return counts
