"""WX5 baseline R: event-triggered FULL re-optimisation of all unstarted planned work (ALNS-lite in the spirit of
TSALNS; Ulmer 2020 'reoptimisation' baseline; Pillac et al. 2013). At every event (new urgent request, failure,
hand-over/backup) and at least every EVERY minutes, all unstarted planned targets of the whole fleet are re-assigned
across in-range drones and re-sequenced into trips by destroy/repair + simulated annealing on a deterministic proxy of
J5 (flight cost + crew overtime + window/duty violation penalties). The immediate action is then chosen by an inner
rule (default N6_90_0.25, the tuned dev-best rule) so R differs from N6 only by the re-optimisation.
Uses only observable information (no wind truth; calm energy, as a static planner would)."""
import math, random, time
from . import const as C

W_WIN = 50.0     # per minute beyond the window (hard in the sim; penalised here)
W_DUTY = 50.0


class _Re:
    def __init__(self, sim):
        self.s = sim
        self.ids = [j for j, d in enumerate(sim.drones) if not d.get("handed")]
        self.lim = C.T_END - C.LD_RESERVE - sim.t
        self.wind = False
        self.cache = {}

    def elig(self, nid):
        s = self.s
        out = []
        n = s.nodes[nid]
        for j in self.ids:
            d = s.drones[j]
            st = s._station(d)
            if math.hypot(n.x - st["x"], n.y - st["y"]) > d["R"] + 1e-6:
                continue
            fl, sv, sve = s._trip_nw(d, [nid])
            if fl * s.p.flight_energy + sve <= 0.9 * d["cap"]:
                out.append(j)
        return out

    def trip_ok(self, j, tr):
        d = self.s.drones[j]
        if len(tr) == 1:
            return True
        fl, sv, sve = self.s._trip_nw(d, tr)
        if fl * self.s.p.flight_energy + sve > 0.9 * d["cap"]:
            return False
        if self.wind:      # forecast-aware packing: multi-target trips must be feasible under the current forecast
            key = (j, tuple(tr))
            if key not in self.cache:
                self.cache[key] = self.s._fc_energy(d, tr, self.s.t) <= C.SPLIT_E * d["cap"]
            return self.cache[key]
        return True

    def drone_stats(self, j, trips):
        s = self.s; d = s.drones[j]
        start = (max(s.t, d["free"]) - s.t) if d["state"] in ("busy", "down") else 0.0
        fl = sv = 0.0
        fx = getattr(self, "fixed", None)
        for tr in (([fx[1]] if fx is not None and fx[0] == j else []) + list(trips)):
            a, b, _ = s._trip_nw(d, tr)
            fl += a; sv += b
        work = (fl + sv) * (1 + C.LD_MARGIN)
        fin = start + work
        dviol = max(0.0, d["duty"] + (fl + sv) * (1 + C.LD_MARGIN) - d["duty_max"])
        return fl + sv, fin, dviol

    def cost(self, asg):
        s = self.s
        tot = 0.0
        st_fin = {}
        for j in self.ids:
            busy, fin, dv = self.drone_stats(j, asg[j])
            tot += C.C_BUSY * busy
            tot += W_WIN * max(0.0, fin - self.lim) + W_DUTY * dv
            sid = s.drones[j]["sid"]
            st_fin[sid] = max(st_fin.get(sid, 0.0), s.t + fin)
        tot += C.C_OT * sum(max(0.0, f - C.H) for f in st_fin.values())
        return tot


def _insert_best(re, asg, nid, elig):
    best = None
    s = re.s
    for j in elig:
        trips = asg[j]
        for ti, tr in enumerate(trips):
            for p in range(len(tr) + 1):
                nt = tr[:p] + [nid] + tr[p:]
                if not re.trip_ok(j, nt):
                    continue
                a0, b0, _ = s._trip_nw(s.drones[j], tr)
                a1, b1, _ = s._trip_nw(s.drones[j], nt)
                dc = (a1 + b1) - (a0 + b0)
                if best is None or dc < best[0]:
                    best = (dc, j, ti, p)
        a1, b1, _ = s._trip_nw(s.drones[j], [nid])
        if best is None or (a1 + b1) < best[0]:
            best = (a1 + b1, j, -1, 0)
    return best


def reoptimise(sim, iters=120, seed=0, fix=None, wind=False):
    """fix=(i, nodes): drone i's next trip (already evaluated by the mask) stays fixed and first."""
    re = _Re(sim)
    re.wind = wind
    if not re.ids:
        return 0
    asg = {j: [list(tr) for tr in sim.drones[j]["trips"]] + ([[n] for n in sim.drones[j]["backlog"]]) for j in re.ids}
    fixed_trip = None
    if fix is not None and fix[0] in asg and asg[fix[0]] and asg[fix[0]][0] == list(fix[1]):
        fixed_trip = asg[fix[0]].pop(0)
        re.fixed = (fix[0], fixed_trip)
    nodes = [n for j in re.ids for tr in asg[j] for n in tr]
    if len(nodes) < 2:
        return 0
    E = {n: re.elig(n) for n in nodes}
    for n in nodes:                      # a node no other drone can take stays where it is
        if not E[n]:
            E[n] = [j for j in re.ids if any(n in tr for tr in asg[j])]
    rng = random.Random(seed)
    cur = re.cost(asg); best_c = cur; best = {j: [list(t) for t in v] for j, v in asg.items()}
    T0 = max(1.0, 0.02 * cur)
    for it in range(iters):
        T = T0 * (1 - it / iters) + 1e-6
        cand = {j: [list(t) for t in v] for j, v in asg.items()}
        k = rng.randint(1, min(4, len(nodes)))
        mode = rng.random()
        if mode < 0.4:
            rem = rng.sample(nodes, k)
        elif mode < 0.7:                  # related removal (proximity)
            c = rng.choice(nodes); cx, cy = sim.nodes[c].x, sim.nodes[c].y
            rem = sorted(nodes, key=lambda n: math.hypot(sim.nodes[n].x - cx, sim.nodes[n].y - cy))[:k]
        else:                             # route removal from the latest-finishing drone
            jmax = max(re.ids, key=lambda j: re.drone_stats(j, cand[j])[1])
            pool = [n for tr in cand[jmax] for n in tr]
            if not pool:
                continue
            rem = pool[-k:]
        for j in cand:
            cand[j] = [[n for n in tr if n not in rem] for tr in cand[j]]
            cand[j] = [tr for tr in cand[j] if tr]
        rng.shuffle(rem)
        ok = True
        for n in rem:
            b = _insert_best(re, cand, n, E[n])
            if b is None:
                ok = False; break
            _, j, ti, p = b
            if ti < 0:
                cand[j].append([n])
            else:
                cand[j][ti].insert(p, n)
        if not ok:
            continue
        c = re.cost(cand)
        if c < cur or rng.random() < math.exp(-(c - cur) / T):
            asg, cur = cand, c
            if c < best_c - 1e-9:
                best_c, best = c, {j: [list(t) for t in v] for j, v in cand.items()}
    if fixed_trip is not None:
        best[fix[0]] = [fixed_trip] + best[fix[0]]
    moved = 0
    for j in re.ids:
        old = [n for tr in sim.drones[j]["trips"] for n in tr] + list(sim.drones[j]["backlog"])
        new = [n for tr in best[j] for n in tr]
        moved += len(set(new) - set(old))
        sim.drones[j]["trips"] = best[j]
        sim.drones[j]["backlog"] = []
    return moved


def make_R(inner, every=30.0, iters=120, wind=False):
    st = {"t": -1e9, "sig": None, "n": 0}

    def pol(sim, i, mask, cands, info):
        sig = (tuple(sim.pending), len(sim.fail_log), getattr(sim, "n_backup", 0),
               sum(1 for d in sim.drones if d.get("handed")))
        if sim.t <= C.T_END and (sig != st["sig"] or sim.t - st["t"] >= every):
            fix = (i, info["nodes"]) if info is not None else None
            mv = reoptimise(sim, iters=iters, seed=int(sim.t * 7 + i), fix=fix, wind=wind)
            st["t"], st["sig"] = sim.t, sig
            st["n"] += 1
            sim.n_reopt = getattr(sim, "n_reopt", 0) + 1
            sim.n_reopt_moved = getattr(sim, "n_reopt_moved", 0) + mv
        return inner(sim, i, mask, cands, info)
    return pol
