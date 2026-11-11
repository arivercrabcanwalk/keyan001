"""Complete physical guard with the round-4 contract and O(stations) allocation.

Identical acceptance logic to ``round4_runtime.Guard``; the only change is that
the single-station evaluator skeleton is allocated once per call and reset
between stations instead of being rebuilt for every station.
"""
from collections import Counter

from .evaluator import evaluate


class Guard:
    def __init__(self, ins, cached=False):
        self.ins = ins
        self.cached = cached
        self.calls = 0
        self.hits = 0
        self.entries = {}

    def valid(self, sol):
        self.calls += 1
        if not self.cached:
            return evaluate(self.ins, sol)['feasible']
        types = sol.get('station_types')
        routes = sol.get('routes')
        ins = self.ins
        if not isinstance(types, list) or not isinstance(routes, list) or len(types) != len(ins.stations) or len(routes) != len(types):
            return evaluate(self.ins, sol)['feasible']
        if sol.get('instance_sha256', ins.sha256) != ins.sha256:
            return False
        seen = Counter()
        entries = self.entries
        empty = {'station_types': [0] * len(types), 'routes': [[[], []] for _ in types]}
        empty_types = empty['station_types']
        empty_routes = empty['routes']
        try:
            for si, (kind, station) in enumerate(zip(types, routes)):
                if type(kind) is not int or kind not in (0, 1, 2) or len(station) != 2:
                    return evaluate(self.ins, sol)['feasible']
                key = (si, kind, tuple(tuple(tuple(t) for t in d) for d in station))
                row = entries.get(key)
                if row is not None:
                    self.hits += 1
                    valid, visits = row
                else:
                    empty_types[si] = kind
                    empty_routes[si] = station
                    audit = evaluate(ins, empty, allow_missing=True)
                    valid = audit['feasible']
                    visits = Counter(n for d in station for t in d for n in t)
                    empty_types[si] = 0
                    empty_routes[si] = [[], []]
                    if len(entries) >= 32768:
                        entries.clear()
                    entries[key] = (valid, visits)
                if not valid:
                    return False
                seen.update(visits)
        except (TypeError, KeyError):
            return evaluate(self.ins, sol)['feasible']
        return all(seen[n] == 1 for n in ins.target_ids) and all(n in ins.target_ids for n in seen)
