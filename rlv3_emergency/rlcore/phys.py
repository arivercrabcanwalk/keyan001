"""Physics energy model (rlv3 'physics AI', design section 8.1 revised).

Rotary-wing propulsion power vs. AIRSPEED V (Zeng, Xu & Zhang 2019, IEEE TWC 18(4):2329-2345,
doi:10.1109/TWC.2019.2902559):
    P(V) = P0 (1 + 3V^2/U_tip^2) + Pi ( sqrt(1 + V^4/(4 v0^4)) - V^2/(2 v0^2) )^(1/2) + 1/2 d0 rho s A V^3
blade-profile + induced + parasite power.  Shape constants are Zeng's defaults; two scale factors are fitted so that
    P(0)   = p2 = 0.020 /min  (author hover rate)      and
    P(15)  = p1 = 0.018 /min  (author cruise rate at v = 15 m/s)
=> at zero wind every flight/hover energy equals Liu et al. (2026) EXACTLY (unit-tested).

Wind enters through kinematics (the drone keeps airspeed v_a and crabs into the wind):
    eta = (w . u)/v_a  (along-track, + = tailwind),  xi = (w x u)/v_a  (cross-track)
    v_g = v_a (eta + sqrt(1 - xi^2))                 ground speed
    c_ij^wind = P(v_a) * d_ij / v_g                  energy of leg i->j
    hover energy during inspection = P(|w|) * t_f    (station keeping = flying at airspeed |w|)
Singularities: v_g -> 0 (headwind ~ v_a) or |xi| >= 1  ->  leg physically infeasible (masked); we additionally require
v_g >= VG_MIN and |w| <= W_LIMIT (manufacturer wind-resistance limit, DJI M350 RTK / Mavic 3E: 12 m/s).

Why not the formula in the user's sketch,  c = d/v_a [P0(1+k v_w^2) + W^2/(v_a (v_a - v_rel))]?
 (i) it divides by AIRSPEED, so wind never changes flight time (wrong kinematics: time = d / v_g);
 (ii) with v_rel = v_w cos(theta_ij - theta_w) (+ = tailwind) the term W^2/(v_a(v_a - v_rel)) makes a TAILWIND more
      expensive and diverges at v_rel -> v_a (a tailwind equal to airspeed!) - sign error;
 (iii) P0(1+k v_w^2) applies the blade-profile term to wind speed instead of airspeed.
 `sketch_cost` reproduces it for the unit test that documents (ii).
"""
import math
import numpy as np
from .common import P1, P2, VA_MS

# Zeng et al. (2019) Table I default rotor constants (shape only; scales fitted below)
_P0, _PI, _UTIP, _V0, _D0, _RHO, _S, _A = 79.86, 88.63, 120.0, 4.03, 0.6, 1.225, 0.05, 0.503
VG_MIN = 4.0          # m/s minimum admissible ground speed (operational; avoids the v_g -> 0 singularity)
W_LIMIT = 12.0        # m/s max wind resistance (DJI M350 RTK spec)


def _blade_induced(V):
    V = np.asarray(V, dtype=float)
    ind = np.sqrt(np.maximum(np.sqrt(1.0 + V ** 4 / (4 * _V0 ** 4)) - V ** 2 / (2 * _V0 ** 2), 0.0))
    return _P0 * (1 + 3 * V ** 2 / _UTIP ** 2) + _PI * ind


def _parasite(V):
    V = np.asarray(V, dtype=float)
    return 0.5 * _D0 * _RHO * _S * _A * V ** 3


# closed-form calibration: alpha * S(0) = P2 ; alpha * (BI(15) + beta * PAR(15)) = P1
ALPHA = P2 / float(_blade_induced(0.0))
BETA = (P1 / ALPHA - float(_blade_induced(VA_MS))) / float(_parasite(VA_MS))


def power(V):
    """Energy per minute (battery units, LD battery = 1) at airspeed V (m/s)."""
    V = np.asarray(V, dtype=float)
    return ALPHA * (_blade_induced(V) + BETA * _parasite(V))


P_CRUISE = float(power(VA_MS))     # == P1 up to float rounding
P_HOVER0 = float(power(0.0))       # == P2


def p_cruise(va=VA_MS):
    return P1 if va == VA_MS else float(power(va))


def p_hover(wspeed):
    """hover (station-keeping) power in wind of speed |w| m/s."""
    if wspeed <= 1e-9:
        return P2
    return float(power(wspeed))


def eta_xi(wx, wy, ux, uy, va=VA_MS):
    """physics feature eta (design 8.2, sign: + tailwind) and cross ratio xi."""
    return (wx * ux + wy * uy) / va, (wx * uy - wy * ux) / va


def ground_speed(wx, wy, ux, uy, va=VA_MS):
    """m/s; returns 0.0 if the heading cannot be held (|xi|>=1) or v_g<=0."""
    eta, xi = eta_xi(wx, wy, ux, uy, va)
    disc = 1.0 - xi * xi
    if disc <= 0.0:
        return 0.0
    vg = va * (eta + math.sqrt(disc))
    return vg if vg > 0.0 else 0.0


def leg_cost(x1, y1, x2, y2, wx, wy, va=VA_MS):
    """Energy, minutes, feasible-flag for a straight leg under constant wind (wx,wy) m/s (design 8.1 revised)."""
    d = math.hypot(x2 - x1, y2 - y1)
    if d < 1e-6:
        return 0.0, 0.0, True
    if wx == 0.0 and wy == 0.0 and va == VA_MS:
        t = d / (va * 60.0)
        return P1 * t, t, True
    ux, uy = (x2 - x1) / d, (y2 - y1) / d
    vg = ground_speed(wx, wy, ux, uy, va)
    ok = vg >= VG_MIN
    vg_eff = max(vg, 0.5)
    t = d / (vg_eff * 60.0)
    return p_cruise(va) * t, t, ok


def maxrange_airspeed(w_par, w_perp, vmin=8.0, vmax=23.0, n=61):
    """Airspeed minimising energy per ground metre P(V)/v_g(V) (optional sensitivity, not default)."""
    Vs = np.linspace(vmin, vmax, n)
    disc = Vs ** 2 - w_perp ** 2
    vg = np.where(disc > 0, w_par + np.sqrt(np.maximum(disc, 0)), -1)
    cost = np.where(vg > VG_MIN, power(Vs) / np.maximum(vg, 1e-6), np.inf)
    return float(Vs[int(np.argmin(cost))])


def sketch_cost(d, vw, theta_ij, theta_w, P0=None, kappa=0.0, W2=None, va=VA_MS):
    """The user's sketch formula, reproduced verbatim for documentation/unit test only (NOT used by the simulator)."""
    P0 = P_HOVER0 if P0 is None else P0
    W2 = 1.0 if W2 is None else W2
    v_rel = vw * math.cos(theta_ij - theta_w)
    den = va * (va - v_rel)
    if den <= 0:
        return float("inf")
    return d / va * (P0 * (1 + kappa * vw ** 2) + W2 / den)
