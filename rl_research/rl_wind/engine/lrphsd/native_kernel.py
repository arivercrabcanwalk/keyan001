"""ctypes binding for the round-6 native kernel.

Coverage tables are built here with the *same* expressions the Python reference
uses, so the kernel never has to reproduce CPython's hypot rounding:

* solver table  : ``ins.dist[station,node] <= radius(kind)``
* evaluator table: ``math.hypot(dx,dy) <= radius(kind) + 1e-7``
"""
import ctypes
import math
from pathlib import Path

MAXN = 4096


class NativeUnavailable(RuntimeError):
    pass


def library_path(root=None):
    base = Path(root) if root else Path(__file__).resolve().parents[1]
    for name in ('libr6kernel.so', 'libr6kernel.dylib', 'r6kernel.dll'):
        p = base / 'native' / name
        if p.exists():
            return str(p)
    return None


class NativeEngine:
    def __init__(self, ins, lib_path=None):
        path = lib_path or library_path()
        if not path:
            raise NativeUnavailable('native kernel library not built')
        self.lib = ctypes.CDLL(path)
        self._declare()
        self.ins = ins
        p = ins.params
        self.NID = max(n.id for n in ins.nodes.values()) + 1
        self.NST = len(ins.stations)
        self.NT = len(ins.targets)
        self.STID = [s.id for s in ins.stations]
        self.TIDS = list(ins.target_ids)
        self.TIDX = {n: i for i, n in enumerate(self.TIDS)}
        dist = ins.dist
        n2 = self.NID * self.NID
        darr = (ctypes.c_double * n2)()
        for a in ins.nodes.values():
            base = a.id * self.NID
            for b in ins.nodes.values():
                darr[base + b.id] = dist[a.id, b.id]
        svc = (ctypes.c_double * self.NID)()
        enge = (ctypes.c_double * self.NID)()
        for n in ins.nodes.values():
            svc[n.id] = n.service
            enge[n.id] = n.energy
        stid = (ctypes.c_int * self.NST)(*self.STID)
        tids = (ctypes.c_int * self.NT)(*self.TIDS)
        radii = (ctypes.c_double * 3)(p.large_radius, p.small_radius, p.large_radius)
        caps = (ctypes.c_double * 6)(p.small_battery, p.small_battery,
                                     p.small_battery, p.small_battery,
                                     p.large_battery, p.small_battery)
        limits = (ctypes.c_double * 3)(p.large_duration, p.small_duration, p.large_duration)
        cover_solver = (ctypes.c_ubyte * (3 * self.NST * self.NT))()
        cover_guard = (ctypes.c_ubyte * (3 * self.NST * self.NT))()
        for kind in (1, 2):
            r = ins.radius(kind)
            for si, st in enumerate(ins.stations):
                for ti, tid in enumerate(self.TIDS):
                    node = ins.nodes[tid]
                    off = kind * self.NST * self.NT + si * self.NT + ti
                    cover_solver[off] = 1 if ins.gdist[st.id, tid] <= r else 0
                    cover_guard[off] = 1 if math.hypot(node.x - st.x, node.y - st.y) <= r + 1e-7 else 0
        ok = self.lib.r6_init(self.NID, darr, svc, enge, self.NST, stid, radii,
                              self.NT, tids, p.speed, p.flight_energy, p.time_cost,
                              caps, limits, cover_solver, cover_guard)
        if ok != 1:
            raise NativeUnavailable('r6_init rejected the instance')
        self._types = (ctypes.c_int * max(self.NST, 1))()
        self._bufsize = 4 * (self.NT + 2 * self.NST + 16)
        self._buf = (ctypes.c_int * self._bufsize)()
        self._rm = (ctypes.c_int * MAXN)()
        self._nrm = ctypes.c_int(0)
        self._seed = ctypes.c_ulonglong(0)
        self._draws = ctypes.c_int(0)

    def _declare(self):
        c = ctypes
        L = self.lib
        L.r6_init.argtypes = [c.c_int, c.POINTER(c.c_double), c.POINTER(c.c_double), c.POINTER(c.c_double),
                              c.c_int, c.POINTER(c.c_int), c.POINTER(c.c_double),
                              c.c_int, c.POINTER(c.c_int),
                              c.c_double, c.c_double, c.c_double,
                              c.POINTER(c.c_double), c.POINTER(c.c_double),
                              c.POINTER(c.c_ubyte), c.POINTER(c.c_ubyte)]
        L.r6_init.restype = c.c_int
        L.r6_free.argtypes = []
        L.r6_free.restype = None
        L.r6_clone.argtypes = [c.c_int, c.c_int]
        L.r6_clone.restype = None
        L.r6_clear.argtypes = [c.c_int]
        L.r6_clear.restype = None
        L.r6_export_size.argtypes = [c.c_int]
        L.r6_export_size.restype = c.c_int
        L.r6_export.argtypes = [c.c_int, c.POINTER(c.c_int), c.POINTER(c.c_int), c.c_int]
        L.r6_export.restype = c.c_int
        L.r6_import.argtypes = [c.c_int, c.POINTER(c.c_int), c.c_int]
        L.r6_import.restype = c.c_int
        L.r6_set_kind.argtypes = [c.c_int, c.c_int, c.c_int]
        L.r6_set_kind.restype = c.c_int
        L.r6_cost.argtypes = [c.c_int]
        L.r6_cost.restype = c.c_double
        L.r6_valid.argtypes = [c.c_int, c.c_int]
        L.r6_valid.restype = c.c_int
        L.r6_guard.argtypes = [c.c_int]
        L.r6_guard.restype = c.c_int
        L.r6_fault.argtypes = []
        L.r6_fault.restype = c.c_int
        L.r6_clear_fault.argtypes = []
        L.r6_clear_fault.restype = None
        L.r6_complete.argtypes = [c.c_int]
        L.r6_complete.restype = c.c_int
        L.r6_destroy.argtypes = [c.c_int, c.c_int, c.c_int, c.c_ulonglong,
                                 c.POINTER(c.c_ulonglong), c.POINTER(c.c_int),
                                 c.POINTER(c.c_int), c.POINTER(c.c_int)]
        L.r6_destroy.restype = c.c_int
        L.r6_repair.argtypes = [c.c_int, c.c_int, c.POINTER(c.c_int), c.c_int]
        L.r6_repair.restype = c.c_int

    # ---- solution plumbing ----
    def load(self, slot, sol):
        types = sol['station_types']
        routes = sol['routes']
        buf = []
        for si in range(self.NST):
            buf.append(types[si])
            station = routes[si]
            for di in range(2):
                trips = station[di] if di < len(station) else []
                buf.append(len(trips))
                for trip in trips:
                    buf.append(len(trip))
                    buf.extend(trip)
        arr = (ctypes.c_int * len(buf))(*buf)
        if self.lib.r6_import(slot, arr, len(buf)) != 1:
            raise ValueError('native import rejected the solution buffer (invalid kind/node id/dimension)')

    def export(self, slot):
        need = self.lib.r6_export_size(slot)
        if need > self._bufsize:
            self._bufsize = need + 32
            self._buf = (ctypes.c_int * self._bufsize)()
        n = self.lib.r6_export(slot, self._types, self._buf, self._bufsize)
        if n < 0:
            raise RuntimeError('r6_export overflow')
        types = [self._types[i] for i in range(self.NST)]
        routes = []
        pos = 0
        for si in range(self.NST):
            pos += 1  # kind
            drones = []
            for di in range(2):
                ntrips = self._buf[pos]
                pos += 1
                trips = []
                for _ in range(ntrips):
                    length = self._buf[pos]
                    pos += 1
                    trips.append([self._buf[pos + k] for k in range(length)])
                    pos += length
                drones.append(trips)
            routes.append(drones)
        return {'schema_version': 1, 'instance': self.ins.name, 'instance_sha256': self.ins.sha256,
                'station_types': types, 'routes': routes}

    # ---- operations ----
    def fault(self):
        return self.lib.r6_fault()

    def _check_fault(self):
        code = self.lib.r6_fault()
        if code:
            raise RuntimeError('native kernel fault code %d (state would be corrupted)' % code)

    def clone(self, src, dst):
        self.lib.r6_clone(src, dst)

    def cost(self, slot):
        return self.lib.r6_cost(slot)

    def valid(self, slot, time_check=True):
        return bool(self.lib.r6_valid(slot, 1 if time_check else 0))

    def guard(self, slot):
        return bool(self.lib.r6_guard(slot))

    def complete(self, slot):
        return bool(self.lib.r6_complete(slot))

    def destroy(self, src, dst, op, seed):
        self.lib.r6_destroy(src, dst, op, seed,
                            ctypes.byref(self._seed), ctypes.byref(self._draws),
                            self._rm, ctypes.byref(self._nrm))
        self._check_fault()
        removed = [self._rm[i] for i in range(self._nrm.value)]
        return removed, self._seed.value, self._draws.value

    def repair(self, slot, op, removed):
        n = len(removed)
        if n > MAXN:
            raise ValueError('removed list too long for the native ABI')
        for i, v in enumerate(removed):
            if not isinstance(v, int):
                raise TypeError('removed entries must be int')
            self._rm[i] = v
        rc = self.lib.r6_repair(slot, op, self._rm, n)
        self._check_fault()
        if rc < 0:
            raise ValueError('native repair rejected the input (op=%r, nremoved=%d)' % (op, n))
        return rc
