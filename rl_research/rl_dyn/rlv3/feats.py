"""Pre-repair candidate features (cheap, computed from the Python mirror)."""
import math
import numpy as np
from carl.actions import N_OPERATORS

N_LOCAL = 24
N_GLOBAL = 10
N_FEAT = N_OPERATORS + 3 + N_LOCAL + N_GLOBAL

class StepCache:
    """Per-step lazily computed per-target info."""
    def __init__(self, ctx):
        self.ctx = ctx; self.sav = {}; self.trip = {}; self.oth = {}
        ins = ctx.ins
        self.scale = 15000.0
        self.btl = ctx.btl
        nodes = [s.id for s in ins.stations]
        self.st_ids = nodes
        self.max_trip = None
    def trip_len(self, si, di, ti):
        key = (si, di, ti)
        v = self.trip.get(key)
        if v is None:
            ctx = self.ctx; d = ctx.ins.dist; dep = self.st_ids[si]
            tr = ctx.mirror.routes[si][di][ti]
            v = 0.0; prev = dep
            for n in tr:
                v += d[prev, n]; prev = n
            v += d[prev, dep]
            self.trip[key] = v
        return v
    def other(self, nid, own):
        key = (nid, own)
        v = self.oth.get(key)
        if v is None:
            ctx = self.ctx; d = ctx.ins.dist; best = math.inf
            for s in ctx.open_stations:
                if s != own:
                    dd = d[self.st_ids[s], nid]
                    if dd < best: best = dd
            v = best if best < math.inf else self.scale
            self.oth[key] = v
        return v
    def saving(self, nid):
        v = self.sav.get(nid)
        if v is None:
            ctx = self.ctx; d = ctx.ins.dist
            si, di, ti, pi = ctx.mirror.pos[nid]
            tr = ctx.mirror.routes[si][di][ti]; dep = self.st_ids[si]
            a = tr[pi-1] if pi > 0 else dep
            b = tr[pi+1] if pi + 1 < len(tr) else dep
            v = d[a, nid] + d[nid, b] - d[a, b]
            self.sav[nid] = v
        return v

def _mean(a):
    return sum(a) / len(a)

def move_ids(m):
    ids = list(m.ids)
    for st in m.stages:
        ids.extend(st[0])
    for a, b in m.swap_pairs:
        ids.extend((a, b))
    return ids

def cand_feats(cache, m, op, it, glob):
    ctx = cache.ctx; ins = ctx.ins; nt = len(ins.targets); nst = ctx.nst
    f = np.zeros(N_FEAT, dtype=np.float32)
    f[op] = 1.0; f[N_OPERATORS + it] = 1.0
    o = N_OPERATORS + 3
    ids = [n for n in move_ids(m) if n in ctx.mirror.pos]
    btl = cache.btl
    if ids:
        n = len(ids)
        pos = [ctx.mirror.pos[x] for x in ids]
        sav = [cache.saving(x) for x in ids]
        tl = [cache.trip_len(p[0], p[1], p[2]) for p in pos]
        own = [ins.dist[cache.st_ids[p[0]], x] for x, p in zip(ids, pos)]
        oth = [cache.other(x, p[0]) for x, p in zip(ids, pos)]
        xs = [ins.dist[x, ids[0]] for x in ids]
        srcs = set(p[0] for p in pos)
        f[o+0] = n / nt
        f[o+1] = sum(1 for p in pos if btl and p[0] == btl[0] and p[1] == btl[1]) / n
        f[o+2] = sum(1 for p in pos if btl and p[0] == btl[0]) / n
        f[o+3] = _mean(sav) / 1000.0
        f[o+4] = max(sav) / 1000.0
        f[o+5] = sum(sav) / max(ctx.route_cost, 1e-9) * 10
        f[o+6] = _mean(own) / cache.scale * 4
        f[o+7] = _mean(oth) / cache.scale * 4
        f[o+8] = _mean(xs) / cache.scale * 4
        f[o+9] = len(srcs) / nst
        f[o+10] = _mean([ctx.load[s] for s in srcs])
        f[o+11] = _mean([ctx.slack[s] for s in srcs])
        f[o+12] = _mean(tl) / 10000.0
        f[o+13] = max(tl) / 10000.0
        f[o+14] = _mean([len(ctx.mirror.routes[p[0]][p[1]][p[2]]) for p in pos]) / 10.0
        f[o+15] = _mean([own_i - oth_i for own_i, oth_i in zip(own, oth)]) / cache.scale * 4
    if m.kinds:
        f[o+16] = len(m.kinds) / nst
        cur = ctx.mirror.types
        f[o+17] = sum(1 for s, k in m.kinds if cur[s] == 0 and k > 0)
        f[o+18] = sum(1 for s, k in m.kinds if cur[s] > 0 and k == 0)
        f[o+19] = sum((ins.fixed(k) if k else 0.0) - (ins.fixed(cur[s]) if cur[s] else 0.0) for s, k in m.kinds) / max(ctx.cost, 1e-9) * 10
        f[o+20] = 1.0 if any(btl and s == btl[0] for s, k in m.kinds) else 0.0
    rm = m.station_mask
    if rm:
        rec = [s for s in range(nst) if (rm >> s) & 1]
        f[o+21] = len(rec) / nst
        f[o+22] = _mean([ctx.load[s] for s in rec])
        f[o+23] = 1.0 if (btl and btl[0] in rec) else 0.0
    g = N_OPERATORS + 3 + N_LOCAL
    f[g:g+len(glob)] = glob
    return f
