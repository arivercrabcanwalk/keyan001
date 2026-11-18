"""v3 shared COVERAGE-FEASIBILITY LAYER (CFL) -- used identically by EVERY method (author adaptations and ours).

Why (v2 post-mortem, ANALYSIS_E2E_V2_ZH.md section 2): complete_strict counts an emergency request as
"must-serve" whenever SOME candidate station opened as DABS could reach it. Background requests are jittered
N(0, BG_JITTER=500 m) around targets, so a siting that covers only the targets (the author's LRPHSD constraint)
misses requests near the edge of the candidate region -> TSALNS plans are capped at 84.7 % strict completion.

Definition (pre-registered in PREREG_E2E_V3.md):
  Q_rho = ({targets} + disc(rho)) intersect U,  U = union of the candidate DABS discs (r = large radius)
  rho = 3000 m = 6 sigma of the background jitter (P(|jitter| > 6 sigma) = exp(-18) ~ 1.5e-8 per request).
  Q_rho is discretised by rings every STEP m (angular spacing <= STEP m) around every target.
  A siting (types in {0 closed, 1 SABS, 2 DABS}) is COVERAGE-FEASIBLE iff every point of Q_rho lies within
  radius(type) of an opened station (and its calm round trip fits the battery, never binding here).
Coverage-feasibility is a property of the siting only, so the same check is applied to every arm and verified
on all test days (verify_coverage.py) BEFORE any arm is reported.

Utilities: support set, exact min-cost cover (MILP, scipy/HiGHS; exact enumeration for <= 11 stations),
min-cost REPAIR of a given siting (upgrades only), enumeration of all feasible sitings with cost <= budget."""
import os, json, math, itertools, hashlib
import numpy as np

R_L, R_S = 5000.0, 4000.0
FIX_S = 22.8 + 5.0            # SABS station + small drone
FIX_D = 30.4 + 8.0 + 5.0      # DABS station + large + small drone
RHO = float(os.environ.get("CFL_RHO", "3000"))
STEP = float(os.environ.get("CFL_STEP", "250"))
FE, VA, U_E = 0.018, 900.0, 0.05
CAP = {1: 0.81, 2: 1.0}


def _reach(d, kind):
    rad = R_L if kind == 2 else R_S
    return (d <= rad + 1e-6) & (2 * d / VA * FE + U_E <= CAP[kind] + 1e-9)


def support(tg, st, rho=RHO, step=STEP):
    """Return (P, covS, covD): support points of Q_rho and boolean coverage matrices (ns, |P|) for SABS / DABS,
    de-duplicated by coverage signature (exactness of the cover is unaffected)."""
    tg = np.asarray(tg, float); st = np.asarray(st, float)
    P = [tg]
    r = step
    while r <= rho + 1e-9:
        k = max(12, int(math.ceil(2 * math.pi * r / step)))
        a = np.linspace(0, 2 * np.pi, k, endpoint=False)
        P.append((tg[:, None, :] + r * np.stack([np.cos(a), np.sin(a)], -1)[None]).reshape(-1, 2))
        r += step
    P = np.concatenate(P)
    d = np.sqrt(((P[:, None, :] - st[None]) ** 2).sum(-1))           # (|P|, ns)
    inU = _reach(d, 2).any(1)
    P, d = P[inU], d[inU]
    cS = _reach(d, 1).T; cD = _reach(d, 2).T
    sig = np.concatenate([cS, cD], 0).T
    _, idx = np.unique(sig, axis=0, return_index=True)
    idx = np.sort(idx)
    return P[idx], cS[:, idx], cD[:, idx]


def feasible(types, cS, cD):
    t = np.asarray(types)
    cov = ((t == 1)[:, None] & cS).any(0) | ((t == 2)[:, None] & cD).any(0)
    return bool(cov.all())


def n_uncovered(types, cS, cD):
    t = np.asarray(types)
    cov = ((t == 1)[:, None] & cS).any(0) | ((t == 2)[:, None] & cD).any(0)
    return int((~cov).sum())


def fixed_cost(types):
    return float(sum(FIX_S if t == 1 else FIX_D if t == 2 else 0.0 for t in types))


def _milp(cS, cD, lb_types=None, budget=None, exclude=(), obj="cost"):
    """min sum cost s.t. cover; variables xS_s, xD_s binary, xS+xD<=1; lb_types: upgrades only (repair)."""
    from scipy.optimize import milp, LinearConstraint, Bounds
    ns = cS.shape[0]
    c = np.concatenate([np.full(ns, FIX_S), np.full(ns, FIX_D)])
    if obj == "ndabs":
        c = np.concatenate([np.full(ns, 1.0), np.full(ns, 1.0 + 1e-3)])
    A = [np.concatenate([cS.T.astype(float), cD.T.astype(float)], 1)]; lo = [np.ones(cS.shape[1])]; hi = [np.full(cS.shape[1], np.inf)]
    A.append(np.concatenate([np.eye(ns), np.eye(ns)], 1)); lo.append(np.zeros(ns)); hi.append(np.ones(ns))
    lbv = np.zeros(2 * ns)
    if lb_types is not None:
        for s, t in enumerate(lb_types):
            if t == 2:
                lbv[ns + s] = 1
            elif t == 1:   # SABS may stay SABS or be upgraded to DABS: xS+xD >= 1
                row = np.zeros(2 * ns); row[s] = 1; row[ns + s] = 1
                A.append(row[None]); lo.append(np.ones(1)); hi.append(np.full(1, np.inf))
    if budget is not None:
        A.append(np.concatenate([np.full(ns, FIX_S), np.full(ns, FIX_D)])[None]); lo.append(np.full(1, -np.inf)); hi.append(np.full(1, budget + 1e-6))
    for ty in exclude:   # no-good cut on an exact type vector
        row = np.zeros(2 * ns); rhs = 0.0
        for s, t in enumerate(ty):
            if t == 1:
                row[s] = 1; rhs += 1
            elif t == 2:
                row[ns + s] = 1; rhs += 1
            else:
                row[s] = -1; row[ns + s] = -1
        # sum over chosen literals <= |chosen|-1  (with closed literals negated)
        A.append(row[None]); lo.append(np.full(1, -np.inf)); hi.append(np.full(1, rhs - 1))
    res = milp(c, constraints=LinearConstraint(np.concatenate(A, 0), np.concatenate(lo), np.concatenate(hi)),
               integrality=np.ones(2 * ns), bounds=Bounds(lbv, np.ones(2 * ns)))
    if res.status != 0 or res.x is None:
        return None
    x = np.round(res.x).astype(int)
    return [2 if x[ns + s] else 1 if x[s] else 0 for s in range(ns)]


def min_cover(cS, cD, obj="cost"):
    """Exact minimum-fixed-cost coverage-feasible siting (ties -> more DABS, then lowest index)."""
    ns = cS.shape[0]
    if ns <= 11:
        F = enumerate_feasible(cS, cD)
        cost = np.array([fixed_cost(t) for t in F]); nd = np.array([(np.array(t) == 2).sum() for t in F])
        key = cost - 1e-3 * nd if obj == "cost" else nd + 1e-4 * cost
        return list(map(int, F[int(np.argmin(key))]))
    return _milp(cS, cD, obj=obj)


def repair(types, cS, cD):
    """Minimum-cost UPGRADE of a given siting (closed->SABS/DABS, SABS->DABS; never downgrade) to coverage feasibility.
    Used for the author-adaptation arm TS-CR (TSALNS plan + coverage repair, routes unchanged)."""
    if feasible(types, cS, cD):
        return list(types)
    return _milp(cS, cD, lb_types=list(types))


def enumerate_feasible(cS, cD, budget=None, kmax=4096):
    """All coverage-feasible sitings (exact). ns <= 11: vectorised enumeration of 3^ns; else MILP + no-good cuts."""
    ns = cS.shape[0]
    if ns <= 11:
        out = []
        cfg = np.array(list(itertools.product((0, 1, 2), repeat=ns)), dtype=np.int8)
        for c in np.array_split(cfg, max(1, len(cfg) // 4000)):
            cov = ((c == 2)[:, :, None] & cD[None]).any(1) | ((c == 1)[:, :, None] & cS[None]).any(1)
            ok = cov.all(1)
            if budget is not None:
                ok &= ((c == 2).sum(1) * FIX_D + (c == 1).sum(1) * FIX_S) <= budget + 1e-6
            out.append(c[ok])
        F = np.concatenate(out)
        return F[:kmax]
    F = []
    while len(F) < kmax:
        t = _milp(cS, cD, budget=budget, exclude=F)
        if t is None:
            break
        F.append(t)
    return np.array(F, dtype=np.int8).reshape(-1, ns)


# ---------------- per-instance cache ----------------
_CACHE = {}


def for_instance(ins, root=None):
    """Cached (P, cS, cD) for an official Instance (keyed by sha256 + rho + step)."""
    key = (ins.sha256, RHO, STEP)
    if key in _CACHE:
        return _CACHE[key]
    tg = np.array([[t.x, t.y] for t in ins.targets]); st = np.array([[s.x, s.y] for s in ins.stations])
    root = root or os.environ.get("E2E_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    f = os.path.join(root, "data", "coverage", f"{ins.name}_{ins.sha256[:12]}_r{int(RHO)}_s{int(STEP)}.npz")
    if os.path.exists(f):
        z = np.load(f); out = (z["P"], z["cS"], z["cD"])
    else:
        out = support(tg, st)
        try:
            os.makedirs(os.path.dirname(f), exist_ok=True); np.savez_compressed(f, P=out[0], cS=out[1], cD=out[2])
        except OSError:
            pass
    _CACHE[key] = out
    return out


def for_arrays(tg, st):
    return support(tg, st)


def request_gap(ins, types, reqs):
    """# requests (of one day) reachable from SOME candidate DABS but not from the opened stations (plan-only bound
    on complete_strict: a day with gap > 0 can never be strictly complete)."""
    n = 0
    for (t0, x, y, pri, kind, tid) in reqs:
        d = np.array([math.hypot(x - s.x, y - s.y) for s in ins.stations])
        if not _reach(d, 2).any():
            continue
        ok = any((types[k] == 2 and _reach(d[k:k + 1], 2)[0]) or (types[k] == 1 and _reach(d[k:k + 1], 1)[0]) for k in range(len(d)))
        n += (not ok)
    return n
