"""Authors' algorithm applied online ('TS-insert'): an urgent request is treated like any LRPHSD target and inserted
by TSALNS's cost-greedy repair (cheapest feasible insertion into a not-yet-started trip of an in-range drone, or a new
trip appended to its queue). No priority, no deadlines, no holding: exactly the cost-only logic of TSALNS."""
import dyn, math, heapq
from dyn import sim as S
class SimTS(S.Sim):
    def __init__(self, ins, sol, day):
        super().__init__(ins, sol, day)
        # rebuild queues as node lists
        k = 0
        for si, kind in enumerate(sol['station_types']):
            if not kind: continue
            s = ins.stations[si]
            for di, trips in enumerate(sol['routes'][si]):
                if kind == 1 and di == 0 and not any(trips): continue
                self.drones[k]['q'] = [[(ins.nodes[n].x, ins.nodes[n].y, ins.nodes[n].service, ins.nodes[n].energy, -1) for n in tr] for tr in trips if tr]
                k += 1
    def _tdur(self, d, tr):
        x0, y0 = d['x'], d['y']; t = 0.0; px, py = x0, y0; arr = []
        for (x, y, sv, e, u) in tr:
            t += math.hypot(x - px, y - py) / SPEED_; arr.append(t); t += sv; px, py = x, y
        return t + math.hypot(x0 - px, y0 - py) / SPEED_, arr
    def _energy(self, d, tr):
        dur, _ = self._tdur(d, tr); fl = dur - sum(n[2] for n in tr)
        return fl * self.p.flight_energy + sum(n[3] for n in tr)
    def _free(self, i, hold_pol):
        d = self.drones[i]
        if d['state'] == 'busy' and self.t < d['free'] - 1e-9: return
        if d['state'] == 'busy' and d.get('cur_planned'): d['planned_end'] = self.t; d['cur_planned'] = False
        d['state'] = 'idle'
        if not d['q']: return
        tr = d['q'].pop(0); dur, arr = self._tdur(d, tr)
        for (x, y, sv, e, u), a in zip(tr, arr):
            if u >= 0: self.resp[u] = self.t + a - self.day.req[u][0]
        d['state'] = 'busy'; d['free'] = self.t + dur; d['busy'] += dur
        d['cur_planned'] = any(n[4] < 0 for n in tr)
        self._push(d['free'], 0, i)
    def _arrive(self, j, disp_pol):
        t, x, y, pri = self.day.req[j]; self.seen.append((t, x, y, pri))
        if not hasattr(self, 'resp'): self.resp = {}
        el = self.eligible(x, y)
        if not el: self.log.append((pri, None, -1)); return
        node = (x, y, S.U_SERVICE, S.U_ENERGY, j); best = None
        for i, dist in el:
            d = self.drones[i]
            for ti, tr in enumerate(d['q']):
                base = self._tdur(d, tr)[0]
                for pos in range(len(tr) + 1):
                    nt = tr[:pos] + [node] + tr[pos:]
                    if self._energy(d, nt) > d['cap'] + 1e-9: continue
                    inc = self._tdur(d, nt)[0] - base
                    if best is None or inc < best[0]: best = (inc, i, ti, pos)
            inc = 2 * dist / SPEED_ + S.U_SERVICE
            if best is None or inc < best[0] - 1e-9: best = (inc, i, len(d['q']), 0)
        _, i, ti, pos = best; d = self.drones[i]
        if ti == len(d['q']): d['q'].append([node])
        else: d['q'][ti].insert(pos, node)
        self.log.append((pri, j, i))
        if d['state'] == 'idle': self._free(i, None)
    def metrics(self):
        resp = getattr(self, 'resp', {})
        self.log = [(p, (resp.get(j) if j is not None else None), i) for (p, j, i) in self.log]
        return super().metrics()
SPEED_ = S.SPEED
