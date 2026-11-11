"""ctypes binding for the CA-RL kernel (r6 reproduction core + joint primitives).

The extension functions do not change the semantics of the frozen r6 path:

* ``r6_remove_ids``      remove an explicit target set, dropping empty trips;
* ``r6_repair_scoped``   repair restricted to a station bitmask / drone bitmask;
* ``r6_two_opt``         first-improvement 2-opt inside one trip;
* ``r6_station_stats``   exact work/fixed/slack statistics of one station.
"""
from pathlib import Path

import ctypes

from lrphsd.native_kernel import NativeEngine


def ca_library_path(root=None):
    base = Path(root) if root else Path(__file__).resolve().parents[1]
    for name in ("libcakernel.so", "libcakernel.dylib", "cakernel.dll"):
        p = base / "native" / name
        if p.exists():
            return str(p)
    return None


_LIB = None


def reset_library(lib_path=None):
    """Free any kernel state left by a previous engine in this process."""
    global _LIB
    path = lib_path or ca_library_path()
    if not path:
        raise RuntimeError("CA kernel library not built")
    if _LIB is None:
        _LIB = ctypes.CDLL(path)
    _LIB.r6_free()


class CAEngine(NativeEngine):
    """Native engine with joint-neighborhood primitives."""

    def __init__(self, ins, lib_path=None):
        path = lib_path or ca_library_path()
        if not path:
            raise RuntimeError("CA kernel library not built (native/libcakernel.so)")
        super().__init__(ins, path)
        self._declare_ca()

    def _declare_ca(self):
        c = ctypes
        L = self.lib
        L.r6_remove_ids.argtypes = [c.c_int, c.POINTER(c.c_int), c.c_int]
        L.r6_remove_ids.restype = c.c_int
        L.r6_same.argtypes = [c.c_int, c.c_int]
        L.r6_same.restype = c.c_int
        L.r6_swap_targets.argtypes = [c.c_int, c.c_int, c.c_int, c.c_int]
        L.r6_swap_targets.restype = c.c_int
        L.r6_repair_scoped.argtypes = [c.c_int, c.c_int, c.POINTER(c.c_int), c.c_int,
                                       c.c_ulonglong, c.c_ulonglong]
        L.r6_repair_scoped.restype = c.c_int
        L.r6_repair_joint.argtypes = [c.c_int, c.c_int, c.POINTER(c.c_int), c.c_int,
                                      c.c_ulonglong, c.c_ulonglong, c.c_int, c.c_int]
        L.r6_repair_joint.restype = c.c_int
        L.r6_two_opt.argtypes = [c.c_int, c.c_int, c.c_int, c.c_int]
        L.r6_two_opt.restype = c.c_int
        L.r6_rebuild.argtypes = [c.c_int, c.POINTER(c.c_int), c.c_int]
        L.r6_rebuild.restype = c.c_int
        L.r6_rebuild_nearest.argtypes = [c.c_int]
        L.r6_rebuild_nearest.restype = c.c_int
        L.r6_rebuild_official_greedy.argtypes = [c.c_int]
        L.r6_rebuild_official_greedy.restype = c.c_int
        L.r6_two_opt_station.argtypes = [c.c_int, c.c_int]
        L.r6_two_opt_station.restype = c.c_int
        L.r6_station_stats.argtypes = [c.c_int, c.c_int, c.POINTER(c.c_double)]
        L.r6_station_stats.restype = c.c_int
        self._stats = (c.c_double * 9)()

    # ---- joint primitives ----
    def remove_ids(self, slot, ids):
        n = len(ids)
        if n > 4096:
            raise ValueError("too many ids")
        for i, v in enumerate(ids):
            self._rm[i] = int(v)
        rc = self.lib.r6_remove_ids(slot, self._rm, n)
        self._check_fault()
        return rc

    def same(self, slot_a, slot_b):
        rc = self.lib.r6_same(int(slot_a), int(slot_b))
        self._check_fault()
        if rc < 0:
            raise ValueError("invalid slot for structural comparison")
        return bool(rc)

    def swap_targets(self, slot, nid_a, nid_b, mode):
        rc = self.lib.r6_swap_targets(slot, int(nid_a), int(nid_b), int(mode))
        self._check_fault()
        return rc

    def repair_scoped(self, slot, op, removed, station_mask=0, drone_mask=0,
                      allow_empty=0, strict_kind=0):
        n = len(removed)
        if n > 4096:
            raise ValueError("too many removed")
        for i, v in enumerate(removed):
            self._rm[i] = int(v)
        rc = self.lib.r6_repair_joint(slot, op, self._rm, n,
                                      int(station_mask), int(drone_mask),
                                      int(allow_empty), int(strict_kind))
        self._check_fault()
        return rc

    def two_opt(self, slot, si, di, ti):
        rc = self.lib.r6_two_opt(slot, si, di, ti)
        self._check_fault()
        return rc

    def free(self):
        try:
            self.lib.r6_free()
        except Exception:
            pass

    def rebuild(self, slot, order):
        n = len(order)
        if n > 4096:
            raise ValueError("too many targets")
        for i, v in enumerate(order):
            self._rm[i] = int(v)
        rc = self.lib.r6_rebuild(slot, self._rm, n)
        self._check_fault()
        return rc

    def rebuild_nearest(self, slot):
        rc = self.lib.r6_rebuild_nearest(slot)
        self._check_fault()
        return rc

    def rebuild_official_greedy(self, slot):
        rc = self.lib.r6_rebuild_official_greedy(slot)
        self._check_fault()
        return rc

    def two_opt_station(self, slot, si):
        rc = self.lib.r6_two_opt_station(slot, si)
        self._check_fault()
        return rc

    def station_stats(self, slot, si):
        ok = self.lib.r6_station_stats(slot, si, self._stats)
        if not ok:
            raise RuntimeError("station_stats failed")
        return tuple(self._stats[i] for i in range(9))
