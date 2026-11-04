"""Scenario E: LRPHSD plan + online emergency (urgent) requests. Event-driven simulator.
Time unit: minute; distance: m; speed 900 m/min (Liu). Planned trips come from a static LRPHSD plan.
Urgent request u: release r_u, location, priority (high: deadline 15 min, normal: 30 min), served by a dedicated
out-and-back sortie from an opened station within its radius; urgent sorties have priority over planned trips
(a drone in flight cannot be interrupted). Decisions:
  (1) HOLD/LAUNCH: whenever a drone is at its station with planned trips left (t < H), launch the next planned trip
      or hold it in ready state for HOLD minutes (a held drone answers an urgent request immediately);
  (2) DISPATCH: on arrival of an urgent request, pick a drone (default: earliest arrival).
Cost model: J = fixed + TIME_COST*busy_time + LAM_MK*planned_makespan + sum_u pen_u  (pen = P_HIGH / P_NORM if late or
unserved). Requests no opened station can reach are 'uncovered' (outsourced, penalised like late)."""
import dyn, math, heapq, numpy as np
SPEED = 900.0
HOLD = 5.0
H = 240.0          # urgent arrival window
DL = {1: 15.0, 0: 30.0}
U_SERVICE = 2.0; U_ENERGY = 0.05
P_HIGH, P_NORM = 30.0, 10.0
LAM_MK = 0.5
class Day:
    """Exogenous urgent requests for one (instance, seed). Hidden hotspot regime."""
    def __init__(self, ins, seed, rate=None, hot=None):
        rng = np.random.default_rng(seed)
        T = np.array([[n.x, n.y] for n in ins.targets])
        nt = len(T)
        lam = rate if rate is not None else nt / 3.0 / H        # expected nt/3 urgent requests over H
        n = rng.poisson(lam * H)
        self.has_hot = (rng.random() < 0.7) if hot is None else hot
        self.center = T[rng.integers(nt)] + rng.normal(0, 300, 2)
        frac = 0.6 if self.has_hot else 0.0
        t = np.sort(rng.uniform(0, H, n))
        ish = rng.random(n) < frac
        base = T[rng.integers(nt, size=n)] + rng.normal(0, 500, (n, 2))
        hotp = self.center + rng.normal(0, 700, (n, 2))
        xy = np.where(ish[:, None], hotp, base)
        pri = (rng.random(n) < 0.4).astype(int)
        self.req = [(float(t[k]), float(xy[k, 0]), float(xy[k, 1]), int(pri[k])) for k in range(n)]
class Sim:
    def __init__(self, ins, sol, day):
        p = ins.params; self.ins = ins; self.p = p
        self.fixed = 0.0; self.drones = []; self.st = []
        for si, kind in enumerate(sol['station_types']):
            if not kind: continue
            self.fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
            s = ins.stations[si]; R = ins.radius(kind)
            self.st.append((s.x, s.y, R, kind))
            for di, trips in enumerate(sol['routes'][si]):
                if kind == 1 and di == 0 and not any(trips): continue
                cap = p.large_battery if (di == 0 and kind == 2) else p.small_battery
                q = [self._dur(s, tr) for tr in trips if tr]
                self.drones.append(dict(sid=len(self.st) - 1, x=s.x, y=s.y, R=R, cap=cap, large=int(di == 0 and kind == 2),
                                        q=q, uq=[], free=0.0, state='idle', planned_end=0.0, busy=0.0, holds=0))
        self.day = day; self.t = 0.0
        self.ev = []; self.k = 0
        for i, d in enumerate(self.drones): self._push(0.0, 0, i)        # type 0: drone free at station
        for j, r in enumerate(day.req): self._push(r[0], 1, j)            # type 1: urgent arrival
        self.log = []   # per urgent: (pri, response or None)
        self.seen = []  # released urgent (t, x, y, pri)
        self.ndec = 0
    def _dur(self, s, tr):
        ins = self.ins; seq = [s] + [ins.nodes[n] for n in tr] + [s]; t = 0.0
        for u, v in zip(seq, seq[1:]): t += math.hypot(v.x - u.x, v.y - u.y) / SPEED
        return t + sum(ins.nodes[n].service for n in tr)
    def _push(self, t, typ, i):
        self.k += 1; heapq.heappush(self.ev, (t, typ, self.k, i))
    # ---- helpers usable by policies ----
    def avail(self, i):
        d = self.drones[i]; a = max(self.t, d['free']) if d['state'] == 'busy' else self.t
        for (dd, _) in d['uq']: a += dd
        return a
    def eligible(self, x, y):
        out = []
        for i, d in enumerate(self.drones):
            dist = math.hypot(x - d['x'], y - d['y'])
            if dist <= d['R'] and 2 * dist / SPEED * self.p.flight_energy + U_ENERGY <= d['cap']:
                out.append((i, dist))
        return out
    def run(self, hold_pol, disp_pol=None):
        while self.ev:
            t, typ, _, i = heapq.heappop(self.ev); self.t = t
            if typ == 0: self._free(i, hold_pol)
            else: self._arrive(i, disp_pol)
        return self.metrics()
    def _launch_urgent(self, i, dur):
        d = self.drones[i]; d['state'] = 'busy'; d['free'] = self.t + dur; d['busy'] += dur
        self._push(d['free'], 0, i)
    def _free(self, i, hold_pol):
        d = self.drones[i]
        if d['state'] == 'busy' and self.t < d['free'] - 1e-9: return       # stale
        if d['state'] == 'hold' and self.t < d.get('hold_until', 0) - 1e-9: return
        if d['state'] == 'busy' and d.get('cur_planned'): d['planned_end'] = self.t; d['cur_planned'] = False
        d['state'] = 'idle'
        if d['uq']:
            dur, _ = d['uq'].pop(0); self._launch_urgent(i, dur); return
        if not d['q']: return
        if self.t < H and hold_pol is not None:
            self.ndec += 1
            if hold_pol(self, i):
                d['state'] = 'hold'; d['hold_until'] = self.t + HOLD; d['holds'] += 1
                self._push(self.t + HOLD, 0, i); return
        dur = d['q'].pop(0); d['state'] = 'busy'; d['free'] = self.t + dur; d['busy'] += dur; d['cur_planned'] = True
        self._push(d['free'], 0, i)
    def _arrive(self, j, disp_pol):
        t, x, y, pri = self.day.req[j]; self.seen.append((t, x, y, pri))
        el = self.eligible(x, y)
        if not el: self.log.append((pri, None, -1)); return
        if disp_pol is None: i, dist = min(el, key=lambda e: self.avail(e[0]) + e[1] / SPEED)
        else: i, dist = disp_pol(self, el, (t, x, y, pri))
        if i is None: self.log.append((pri, None, -2)); return
        d = self.drones[i]; dur = 2 * dist / SPEED + U_SERVICE
        resp = self.avail(i) + dist / SPEED - t
        self.log.append((pri, resp, i))
        if d['state'] in ('idle', 'hold'): self._launch_urgent(i, dur)
        else: d['uq'].append((dur, j))
    def metrics(self):
        mk = max([d['planned_end'] for d in self.drones] + [0.0])
        busy = sum(d['busy'] for d in self.drones)
        nh = sum(1 for l in self.log if l[0] == 1); nn = len(self.log) - nh
        late_h = sum(1 for l in self.log if l[0] == 1 and (l[1] is None or l[1] > DL[1]))
        late_n = sum(1 for l in self.log if l[0] == 0 and (l[1] is None or l[1] > DL[0]))
        unc = sum(1 for l in self.log if l[1] is None)
        resp = [l[1] for l in self.log if l[1] is not None]
        cost = self.fixed + self.p.time_cost * busy
        pen = P_HIGH * late_h + P_NORM * late_n
        return dict(J=cost + LAM_MK * mk + pen, cost=cost, mk=mk, pen=pen, n=len(self.log), nh=nh, late_h=late_h, late_n=late_n,
                    unc=unc, ontime=(1 - (late_h + late_n) / max(1, len(self.log))),
                    ontime_h=(1 - late_h / max(1, nh)), resp=float(np.mean(resp)) if resp else 0.0,
                    holds=sum(d['holds'] for d in self.drones), ndec=self.ndec)
    # ---- fast state copy for rollouts ----
    def clone(self):
        s = Sim.__new__(Sim)
        s.__dict__.update(self.__dict__)
        s.drones = [dict(d, q=list(d['q']), uq=list(d['uq'])) for d in self.drones]
        s.ev = list(self.ev); s.log = list(self.log); s.seen = self.seen
        return s
