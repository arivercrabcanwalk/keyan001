"""E2E diag D2: online (event-time) wind-aware router replacing the static TSALNS routes inside the WX5 sim.
Stations/types/assignment come from the plan (as in the eventual E2E design they would come from the siting policy);
ROUTES are rebuilt online at every decision of a drone from the pool of its unstarted targets (and, for the 'S'
variant, the unstarted targets of all drones at the same station). Only observable info: forecast issued now.
variants:
  g  : pure greedy online construction (farthest-seed + nearest insertion; forecast energy <= SPLIT_E*cap*ALPHA)
  r  : plan-repair (keep plan next trip; drop its farthest targets until forecast-feasible instead of splitting all,
       then greedily append nearest pool targets while forecast-feasible)
The rest of the queue is packed by calm energy (<=0.9 cap) for the shared time/duty rules."""
import math
from . import sim as S
from . import const as C

ALPHA = 0.97


class OnlineSim(S.Sim):
    variant = "g"
    station_pool = False

    def next_trip_info(self, i):
        d = self.drones[i]
        if d.get("_onl_t") != self.t and self.t <= self.t_horizon and (d["trips"] or d["backlog"]):
            d["_onl_t"] = self.t
            self._route(i)
        return super().next_trip_info(i)

    # ---- helpers
    def _xy(self, nid):
        n = self.nodes[nid]; return n.x, n.y

    def _calm_ok(self, d, tr):
        fl, sv, sve = self._trip_nw(d, tr)
        return fl * self.p.flight_energy + sve <= 0.9 * d["cap"]

    def _fc_ok(self, d, tr):
        return self._fc_energy(d, tr, self.t) <= C.SPLIT_E * ALPHA * d["cap"]

    def _duty_ok(self, d, tr):
        fl, sv, _ = self._trip_nw(d, tr)
        return d["duty"] + (fl + sv) * 1.15 <= d["duty_max"]

    def _greedy_trip(self, d, pool, ok):
        st = self._station(d); sx, sy = st["x"], st["y"]
        if not pool:
            return []
        seed = max(pool, key=lambda n: math.hypot(self._xy(n)[0] - sx, self._xy(n)[1] - sy))
        trip = [seed]
        rest = [n for n in pool if n != seed]
        while rest:
            px, py = self._xy(trip[-1])
            rest.sort(key=lambda n: math.hypot(self._xy(n)[0] - px, self._xy(n)[1] - py))
            added = False
            for n in rest[:4]:
                cand = trip + [n]
                # cheaper ordering: insert n at the best position
                best = None
                for k in range(len(trip) + 1):
                    c2 = trip[:k] + [n] + trip[k:]
                    fl, _, _ = self._trip_nw(d, c2)
                    if best is None or fl < best[0]:
                        best = (fl, c2)
                cand = best[1]
                if ok(d, cand):
                    trip = cand; rest.remove(n); added = True
                    break
            if not added:
                break
        return trip

    def _pack_rest(self, d, pool):
        out = []
        pool = list(pool)
        while pool:
            tr = self._greedy_trip(d, pool, self._calm_ok)
            if not tr:
                break
            out.append(tr)
            pool = [n for n in pool if n not in tr]
        return out

    def _route(self, i):
        d = self.drones[i]
        own = [n for tr in d["trips"] for n in tr] + list(d["backlog"])
        donors = []
        if self.station_pool:
            for j, e in enumerate(self.drones):
                if j != i and e["sid"] == d["sid"] and not e.get("handed"):
                    donors.append(j)
        pool = list(own) + [n for j in donors for tr in self.drones[j]["trips"] for n in tr]
        # only targets this drone can reach (own targets always reachable by construction)
        st = self._station(d)
        pool = [n for n in pool if n in own or math.hypot(self._xy(n)[0] - st["x"], self._xy(n)[1] - st["y"]) <= d["R"] + 1e-6]
        ok = lambda dd, tr: self._calm_ok(dd, tr) and self._duty_ok(dd, tr) and self._fc_ok(dd, tr)
        if self.variant == "r" and d["trips"]:
            nxt = list(d["trips"][0])
            while len(nxt) > 1 and not self._fc_ok(d, nxt):
                far = max(nxt, key=lambda n: math.hypot(self._xy(n)[0] - st["x"], self._xy(n)[1] - st["y"]))
                nxt.remove(far)
            rest_pool = [n for n in pool if n not in nxt]
            # greedy append nearest
            while True:
                px, py = self._xy(nxt[-1])
                cs = sorted(rest_pool, key=lambda n: math.hypot(self._xy(n)[0] - px, self._xy(n)[1] - py))[:3]
                added = False
                for n in cs:
                    if math.hypot(self._xy(n)[0] - px, self._xy(n)[1] - py) > 2.0 * math.hypot(px - st["x"], py - st["y"]) + 1:
                        continue
                    c2 = nxt + [n]
                    if ok(d, c2):
                        nxt = c2; rest_pool.remove(n); added = True; break
                if not added:
                    break
            trip = nxt
        else:
            trip = self._greedy_trip(d, pool, ok)
            if not trip:
                trip = [max(pool, key=lambda n: math.hypot(self._xy(n)[0] - st["x"], self._xy(n)[1] - st["y"]))]
        taken = set(trip)
        # remove taken targets from donors
        for j in donors:
            e = self.drones[j]
            e["trips"] = [[n for n in tr if n not in taken] for tr in e["trips"]]
            e["trips"] = [tr for tr in e["trips"] if tr]
        own_rest = [n for n in own if n not in taken]
        if self.variant == "r":
            # keep plan order for the remaining own trips (minus taken)
            rest = [[n for n in tr if n not in taken] for tr in d["trips"][1:]]
            rest = [tr for tr in rest if tr]
            bl = [n for n in d["backlog"] if n not in taken]
            dropped = [n for n in (d["trips"][0] if d["trips"] else []) if n not in taken]
            d["trips"] = [trip] + rest
            d["backlog"] = bl + dropped
        else:
            d["trips"] = [trip] + self._pack_rest(d, own_rest)
            d["backlog"] = []


def make(variant="g", station_pool=False):
    cls = type(f"OnlineSim_{variant}{'S' if station_pool else ''}", (OnlineSim,),
               dict(variant=variant, station_pool=station_pool))
    return cls
