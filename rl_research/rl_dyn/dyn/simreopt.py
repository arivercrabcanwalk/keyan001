"""(A3) TS-reopt: TSALNS rolling-horizon re-optimisation (authors' algorithm used as an online re-planner).
Trigger: every urgent-request arrival (variant 'ev'), optionally also every DELTA minutes (variant 'ev+periodic').
At a trigger time t we FREEZE: completed trips, trips in flight (non-interruptible), the opened stations and their
types, each drone's station (drones always return to their own station) and its ready time (max(t, end of the
current trip)). The residual problem = all not-yet-started planned targets + all not-yet-started urgent requests
(including the new one). It is re-optimised with the authors' TSALNS *routing layer* (cost-only objective
fixed + time_cost * total flight time; their swap1-4 / 2-opt local moves, 4 destroy + 4 repair operators, adaptive
weights, SA), for a wall-clock budget SEC per re-opt. Location layer is frozen (stations already built), so
mutate_location / greedy rebuild are not used. No priority, no deadline, no hold: exactly TSALNS' published logic.
Approximations (documented in PAPER_FINDINGS E8):
  (1) Ready times only matter through the order of execution; TSALNS' objective is time-independent, so a drone's
      residual trips are simply executed back-to-back from its ready time; urgent requests are ordinary targets
      (energy U_ENERGY, service U_SERVICE) inserted into trips that depart from now on.
  (2) The per-drone working-time limit (480/600 min) is checked on the residual trips only (not on elapsed time);
      it is never binding in our instances (makespan << 480).
  (3) An urgent node is first inserted by TSALNS' own min-delta repair (repair family 0) to build the incumbent;
      if no feasible insertion exists, a dedicated out-and-back trip is appended at the nearest eligible drone.
"""
import dyn, math, time, random, copy
from dyn import sim as S
from lrphsd.problem import Instance, Node
from lrphsd import tsalns as TS
UID = 100000
class SimReopt(S.Sim):
    def __init__(self, ins, sol, day, sec=1.0, delta=None, seed=0):
        super().__init__(ins, sol, day)
        self.sec = sec; self.delta = delta; self.seed = seed
        self.types = list(sol['station_types']); self.nodes = dict(ins.nodes); self.resp = {}
        k = 0; self.sd = []
        for si, kind in enumerate(sol['station_types']):
            if not kind: continue
            for di, trips in enumerate(sol['routes'][si]):
                if kind == 1 and di == 0 and not any(trips): continue
                self.drones[k]['q'] = [list(tr) for tr in trips if tr]; self.sd.append((si, di)); k += 1
        self.dmap = {sd: i for i, sd in enumerate(self.sd)}
        if delta:
            t = delta
            while t < S.H: self._push(t, 2, 0); t += delta
        self.n_re = 0; self.t_re = 0.0; self.t_re_max = 0.0; self.evals = 0
    def run(self, hold_pol=None, disp_pol=None):
        import heapq
        while self.ev:
            t, typ, _, i = heapq.heappop(self.ev); self.t = t
            if typ == 0: self._free(i)
            elif typ == 1: self._arrive(i)
            else:
                if any(d['q'] for d in self.drones): self._reopt([]); self._kick()
        return self.metrics()
    def _seq(self, d, tr):
        t = 0.0; px, py = d['x'], d['y']; arr = []
        for n in tr:
            nd = self.nodes[n]; t += math.hypot(nd.x - px, nd.y - py) / S.SPEED; arr.append(t); t += nd.service; px, py = nd.x, nd.y
        return t + math.hypot(d['x'] - px, d['y'] - py) / S.SPEED, arr
    def _free(self, i):
        d = self.drones[i]
        if d['state'] == 'busy' and self.t < d['free'] - 1e-9: return
        if d['state'] == 'busy' and d.get('cur_planned'): d['planned_end'] = self.t; d['cur_planned'] = False
        d['state'] = 'idle'
        if not d['q']: return
        tr = d['q'].pop(0); dur, arr = self._seq(d, tr)
        for n, a in zip(tr, arr):
            if n >= UID: self.resp[n - UID] = self.t + a - self.day.req[n - UID][0]
        d['state'] = 'busy'; d['free'] = self.t + dur; d['busy'] += dur; d['cur_planned'] = any(n < UID for n in tr)
        self._push(d['free'], 0, i)
    def _kick(self):
        for i, d in enumerate(self.drones):
            if d['state'] == 'idle' and d['q']: self._free(i)
    def _arrive(self, j):
        t, x, y, pri = self.day.req[j]; self.seen.append((t, x, y, pri))
        el = self.eligible(x, y)
        if not el: self.log.append((pri, None, -1)); return
        nid = UID + j; self.nodes[nid] = Node(nid, x, y, S.U_ENERGY, S.U_SERVICE)
        self.log.append((pri, j, -3)); self._reopt([nid], el); self._kick()
    def _reopt(self, new, el=None):
        t0 = time.perf_counter()
        res = [n for d in self.drones for tr in d['q'] for n in tr] + list(new)
        ins = self.ins
        rins = Instance(ins.name + '_res', tuple(self.nodes[n] for n in res), ins.stations, ins.sha256, ins.params)
        sol = {'station_types': list(self.types), 'routes': [[[], []] for _ in ins.stations]}
        for i, d in enumerate(self.drones):
            si, di = self.sd[i]; sol['routes'][si][di] = [list(tr) for tr in d['q']]
        if new and not TS.repair(rins, sol, list(new), 0):
            i, _ = min(el, key=lambda e: e[1]); si, di = self.sd[i]; sol['routes'][si][di].append(list(new))
        rng = random.Random(self.seed * 1000003 + self.n_re); bud = TS.Budget(self.sec); cfg = TS.DEFAULT
        cur = sol; cost, valid, *_ = bud.assess(rins, cur); best, bcost = copy.deepcopy(cur), (cost if valid else math.inf)
        temp = cfg['initial_temperature']
        while bud.alive() and len(res) > 1:
            cand, val = cur, cost
            for _ in range(cfg['local_iterations']):
                if not bud.alive(): break
                cand, val = TS.local_move(rins, cand, val, rng, bud)
            if bud.alive(): cand, val = TS.alns(rins, cand, rng, bud, cfg)
            val, v, *_ = bud.assess(rins, cand)
            if v and (val < cost or rng.random() < math.exp(min(0, (cost - val) / max(temp, 1e-12)))):
                cur, cost = cand, val
                if cost < bcost - 1e-9: best, bcost = copy.deepcopy(cur), cost
            temp *= cfg['cooling_rate']
        if bcost == math.inf: best = cur
        for i, d in enumerate(self.drones):
            si, di = self.sd[i]; d['q'] = [list(tr) for tr in best['routes'][si][di] if tr]
        # any trips TSALNS put on an unused (station,drone) slot -> must exist in sim; map them (DABS large drone w/o plan)
        for si, st in enumerate(best['routes']):
            for di, trips in enumerate(st):
                if (si, di) not in self.dmap and any(trips):
                    raise RuntimeError('reopt used a drone slot absent from simulation: %s' % ((si, di),))
        dt = time.perf_counter() - t0; self.n_re += 1; self.t_re += dt; self.t_re_max = max(self.t_re_max, dt); self.evals += bud.evaluations
    def metrics(self):
        self.log = [(p, (self.resp.get(j) if j is not None else None), i) for (p, j, i) in self.log]
        m = super().metrics(); m.update(n_reopt=self.n_re, reopt_s=self.t_re, reopt_max_s=self.t_re_max, evals=self.evals); return m
