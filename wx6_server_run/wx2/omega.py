"""WX-E6 emergency-demand support Omega (v6 generator fix, applies to ALL methods identically).

Why: in v5 / e2e_v2 background urgent requests were drawn at target + N(0, 500 m) jitter, i.e. from a continuous,
plan-unknowable support. 3.5 % of them fell outside every candidate station's radius (structurally unservable) and a
further ~1.7 % were reachable only from stations an author plan did not open; this made strict completion depend on
siting and invited the "open every station" (PAD) exploit (ANALYSIS_E2E_V2_ZH.md, sec. 2).

v6 definition (frozen, PREREG_v6 sec. 2): every map carries a FINITE, plan-independent set of fault-prone points
  Omega = targets  U  {K_OMEGA jittered "line-span" points per target}
generated deterministically from the map content (sha256), with jitter N(0, BG_JITTER) and re-drawn (max 64 tries)
until the point lies inside the radius of at least one candidate station opened as DABS (5 km), so every point of
Omega is coverable by construction. Background urgent requests are drawn from the span points; storm faults stay at
targets. The planning stage sees Omega (asset inventory known to the utility), so a coverage constraint
"every omega in Omega within the radius of an opened station" is an ordinary, checkable plan constraint.
"""
import hashlib, math
import numpy as np
from . import const as C

K_OMEGA = 4
_CACHE = {}


def _sha(ins):
    s = getattr(ins, "sha256", None)
    if s:
        return s
    h = hashlib.sha256()
    for n in list(ins.targets) + list(ins.stations):
        h.update(f"{n.x:.4f},{n.y:.4f};".encode())
    return h.hexdigest()


def coverable_any(ins, x, y, eps=1e-6):
    R = ins.params.large_radius
    return any(math.hypot(x - s.x, y - s.y) <= R + eps for s in ins.stations)


def omega(ins):
    """Returns dict(span = array [n_targets, K, 2], points = array [M, 2] (targets first, then spans),
    n_redraw = number of jitter re-draws (diagnostic), fallback = spans that fell back to the target itself)."""
    key = _sha(ins)
    if key in _CACHE:
        return _CACHE[key]
    T = np.array([[t.x, t.y] for t in ins.targets], dtype=float)
    rng = np.random.default_rng(int(key[:15], 16) ^ 0x6A09E667)
    span = np.zeros((len(T), K_OMEGA, 2))
    nred = 0; fb = 0
    for k in range(len(T)):
        for m in range(K_OMEGA):
            ok = False
            for _ in range(64):
                xy = T[k] + rng.normal(0.0, C.BG_JITTER, 2)
                if coverable_any(ins, xy[0], xy[1]):
                    ok = True; break
                nred += 1
            if not ok:
                xy = T[k].copy(); fb += 1
            span[k, m] = xy
    pts = np.concatenate([T, span.reshape(-1, 2)], axis=0)
    out = dict(span=span, points=pts, n_redraw=nred, fallback=fb, sha=key)
    _CACHE[key] = out
    return out


def write_cov_file(ins, path):
    """Plain-text Omega for the patched TSALNS (-Dcov=path): one 'x y' per line."""
    pts = omega(ins)["points"]
    with open(path, "w") as f:
        for x, y in pts:
            f.write(f"{x:.4f} {y:.4f}\n")
    return len(pts)


def uncovered(ins, types, pts=None):
    """Indices of Omega points not within the radius of any opened station (SABS 4 km, DABS 5 km)."""
    pts = omega(ins)["points"] if pts is None else pts
    p = ins.params
    S = np.array([[s.x, s.y] for s in ins.stations])
    R = np.array([0.0 if t == 0 else (p.small_radius if t == 1 else p.large_radius) for t in types])
    D = np.sqrt(((pts[:, None, :] - S[None]) ** 2).sum(-1))
    cov = (D <= R[None] + 1e-6) & (R[None] > 0)
    return np.where(~cov.any(1))[0]
