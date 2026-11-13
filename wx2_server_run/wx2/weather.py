"""Synthetic WX-Storm v1 weather and demand generator.

Wind forecast-error parameters (sigma0=1 m/s, kappa=0.5 m/s/h) are SYNTHETIC,
not fitted to ERA5/GFS. Every report must label them as such.
"""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import math, hashlib
import numpy as np
from . import const as C

def _rng(seed, *extra) -> np.random.Generator:
    # stable 64-bit seed from integers / strings
    h = hashlib.blake2b(digest_size=8)
    h.update(str(int(seed)).encode())
    for e in extra:
        h.update(b"|")
        h.update(str(e).encode())
    return np.random.default_rng(int.from_bytes(h.digest(), "little") % (2 ** 63))


def ou_path(rng, n, dt, tau, sigma, dim=2, x0=None):
    """Stationary OU with Var=sigma^2, time-constant tau."""
    a = math.exp(-dt / tau)
    s = sigma * math.sqrt(max(0.0, 1.0 - a * a))
    x = rng.normal(0.0, sigma, dim) if x0 is None else np.array(x0, dtype=float)
    out = np.zeros((n, dim))
    g = rng.normal(0.0, 1.0, (n, dim))
    for i in range(n):
        out[i] = x
        x = a * x + s * g[i]
    return out


def ground_speed_mpm(wx_ms, wy_ms, ux, uy, va_mpm=C.VA):
    """Ground speed (m/min) for heading unit (ux,uy). Wind in m/s.
    vg = w·u + sqrt(va^2 - |w×u|^2). Returns 0 if heading is unsustainable.
    """
    # convert wind to m/min
    wx, wy = wx_ms * 60.0, wy_ms * 60.0
    along = wx * ux + wy * uy
    cross = wx * uy - wy * ux
    disc = va_mpm * va_mpm - cross * cross
    if disc < 0.0:
        return 0.0
    vg = along + math.sqrt(disc)
    return vg if vg > 1.0 else 0.0


def ellipse_contains(x, y, cx, cy, a, b, ang, buf=0.0):
    """Point-in-expanded-ellipse. a,b,buf in metres."""
    aa, bb = a + buf, b + buf
    if aa <= 0 or bb <= 0:
        return False
    dx, dy = x - cx, y - cy
    ca, sa = math.cos(ang), math.sin(ang)
    xr = (dx * ca + dy * sa) / aa
    yr = (-dx * sa + dy * ca) / bb
    return (xr * xr + yr * yr) <= 1.0


def segment_hits_ellipse(p1, p2, cx, cy, a, b, ang, buf=0.0, n=8):
    """Conservative segment-ellipse test by n samples + endpoints."""
    for k in range(n + 1):
        t = k / n
        x = p1[0] * (1 - t) + p2[0] * t
        y = p1[1] * (1 - t) + p2[1] * t
        if ellipse_contains(x, y, cx, cy, a, b, ang, buf):
            return True
    return False


def _around_points(cx, cy, a, b, ang, buf, n=8):
    """Waypoints on the expanded ellipse."""
    aa, bb = a + buf, b + buf
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        xr, yr = aa * math.cos(th), bb * math.sin(th)
        pts.append((cx + xr * ca - yr * sa, cy + xr * sa + yr * ca))
    return pts


class WeatherDay:
    """One fully materialised exogenous day (truth + forecasts + nowcastable cells)."""

    def __init__(self, seed, bbox, targets_xy, mode="storm", p_f=None, lam=None):
        """
        bbox: (xmin, xmax, ymin, ymax) of the instance (metres).
        targets_xy: (n,2)
        mode: 'storm' (default WX-E) or 'uniform' (P3, same expected faults, spatial uniform)
              or 'nowind' (regression: zero wind, no cells)
        """
        self.seed = int(seed)
        self.mode = mode
        self.bbox = tuple(bbox)
        self.targets_xy = np.asarray(targets_xy, dtype=float)
        rng = _rng(seed, "weather", mode)
        self.tgrid = np.arange(0.0, C.H + C.DT * 0.5, C.DT)
        self.NT = len(self.tgrid)
        self.dt = C.DT

        if mode == "nowind":
            self._zero(rng)
            return

        self.storm = bool(rng.random() < C.STORM_PROB)
        self.lam = float(lam if lam is not None else rng.uniform(*C.LAM_RANGE))
        self.p_f = float(p_f if p_f is not None else rng.uniform(*C.PF_RANGE))
        self.W0 = float(rng.uniform(*C.W0_RANGE))
        self.dir0 = float(rng.uniform(0.0, 2 * math.pi))
        self.dW = float(rng.uniform(*C.DW_RANGE))
        self.delta = float(rng.uniform(-C.DELTA_DEG, C.DELTA_DEG) * math.pi / 180.0)
        self.ou_tau = float(rng.uniform(*C.OU_TAU_RANGE))
        self.ou_sig = float(rng.uniform(*C.OU_SIG_RANGE))
        self.ell = float(rng.uniform(*C.ELL_RANGE))
        self.gust_dwell = float(rng.uniform(*C.GUST_DWELL))
        self.gust_amp = float(rng.uniform(*C.GUST_AMP))

        # background forecast F0(t): speed linear, direction constant (m/s)
        t = self.tgrid
        spd = self.W0 + self.dW * (t / C.H)
        self.F0x = spd * math.cos(self.dir0)
        self.F0y = spd * math.sin(self.dir0)

        # large-scale OU error (m/s), 2-D, used as spatially-mean field
        self.ou = ou_path(rng, self.NT, C.DT, self.ou_tau, self.ou_sig, 2)

        # hidden gust two-state Markov (unpredictable)
        self.gust = self._gust_path(rng)

        # Fourier spatial field: K modes, each with its own unit-variance OU
        self._init_fourier(rng)

        # Reference-point smooth field (for hashes / forecasts): F0 + OU.
        # Pointwise TRUTH uses F0 + spatial(std=ou_sig) + gust + front — the
        # Fourier field IS the spatially correlated OU, not an extra term.
        self.wtx = self.F0x + self.ou[:, 0] + self.gust[:, 0]
        self.wty = self.F0y + self.ou[:, 1] + self.gust[:, 1]

        # forecast updates (see _build_forecast)
        self._build_forecast(rng)

        # convective cells
        self.cells = []
        self.cell_dir = self.dir0 + self.delta  # shared motion direction
        if self.storm:
            self._spawn_cells(rng)

        # cache cell arrays for fast lookup
        self._pack_cells()

    def _zero(self, rng):
        self.storm = False
        self.lam = 0.0
        self.p_f = 0.0
        self.W0 = 0.0
        self.dir0 = 0.0
        self.dW = 0.0
        self.delta = 0.0
        self.ou_tau = 60.0
        self.ou_sig = 0.0
        self.ell = 10000.0
        self.gust_dwell = 45.0
        self.gust_amp = 0.0
        self.F0x = np.zeros(self.NT)
        self.F0y = np.zeros(self.NT)
        self.ou = np.zeros((self.NT, 2))
        self.gust = np.zeros((self.NT, 2))
        self.wtx = np.zeros(self.NT)
        self.wty = np.zeros(self.NT)
        self.issue_times = np.array([0.0])
        self.fc_now_x = np.zeros(self.NT)
        self.fc_now_y = np.zeros(self.NT)
        # fc_prof[issue, t] 
        self.fc_x = np.zeros((1, self.NT))
        self.fc_y = np.zeros((1, self.NT))
        self.kvec = np.zeros((C.N_FOURIER, 2))
        self.kphi = np.zeros(C.N_FOURIER)
        self.kxi = np.zeros((self.NT, C.N_FOURIER, 2))
        self.cells = []
        self.cell_dir = 0.0
        self._pack_cells()

    def _gust_path(self, rng):
        n = self.NT
        on = False
        # start in stationary distribution: p_on ≈ 0.5 (symmetric rates)
        dwell = self.gust_dwell
        p_switch = 1.0 - math.exp(-C.DT / dwell)
        gx = np.zeros((n, 2))
        vec = np.zeros(2)
        for i in range(n):
            if rng.random() < p_switch:
                on = not on
                if on:
                    ang = self.dir0 + rng.uniform(-0.4, 0.4)
                    vec = self.gust_amp * np.array([math.cos(ang), math.sin(ang)])
                else:
                    vec = np.zeros(2)
            gx[i] = vec
        return gx

    def _init_fourier(self, rng):
        K = C.N_FOURIER
        # wavevectors around 2π/ell
        ang = rng.uniform(0, 2 * math.pi, K)
        freq = (2 * math.pi / self.ell) * rng.uniform(0.6, 1.6, K)
        self.kvec = np.stack([freq * np.cos(ang), freq * np.sin(ang)], 1)
        self.kphi = rng.uniform(0, 2 * math.pi, K)
        # each mode: 2-D OU with variance 1, then scaled so the field has std ≈ ou_sig
        self.kxi = np.stack(
            [ou_path(rng, self.NT, C.DT, self.ou_tau, 1.0, 2) for _ in range(K)],
            axis=1,
        )  # (NT, K, 2)

    def spatial_wind(self, x, y, idx):
        """Spatially correlated OU error at (x,y). Pointwise std ≈ ou_sig.

        The large-scale `self.ou` is identified with the domain-centre value of
        this field so it is NOT added again in truth_wind.
        """
        kr = self.kvec[:, 0] * x + self.kvec[:, 1] * y + self.kphi
        c = np.cos(kr)  # (K,)
        s = math.sqrt(2.0 / C.N_FOURIER) * self.ou_sig
        return s * (self.kxi[idx, :, 0] * c).sum(), s * (self.kxi[idx, :, 1] * c).sum()

    def _build_forecast(self, rng):
        """Updated forecast every 60 min. Error std = SIGMA0 + KAPPA*lead_hours.
        Adjacent updates AR(1) 0.7. Forecast does NOT include hidden gust.
        Truth_smooth = F0 + OU (+ spatial at a later evaluation).
        """
        issues = np.arange(0.0, C.H + 0.1, C.FC_PERIOD)
        self.issue_times = issues
        ni, nt = len(issues), self.NT
        # error fields e[issue, t, 2], built sequentially with AR(1)
        e = np.zeros((ni, nt, 2))
        for i, ti in enumerate(issues):
            lead_h = np.maximum(0.0, (self.tgrid - ti) / 60.0)
            # forecasts are not issued for the past: leave 0
            std = C.SIGMA0 + C.KAPPA * lead_h  # (nt,)
            innov = rng.normal(0.0, 1.0, (nt, 2)) * std[:, None]
            if i == 0:
                e[i] = innov
            else:
                # AR(1) on the overlapping future; scale to new std
                prev_lead = np.maximum(0.0, (self.tgrid - issues[i - 1]) / 60.0)
                prev_std = C.SIGMA0 + C.KAPPA * prev_lead
                ratio = std / np.maximum(prev_std, 1e-6)
                e[i] = C.FC_AR1 * e[i - 1] * ratio[:, None] + math.sqrt(max(0.0, 1 - C.FC_AR1 ** 2)) * innov
        # smooth truth (no gust)
        smx = self.F0x + self.ou[:, 0]
        smy = self.F0y + self.ou[:, 1]
        self.fc_x = smx[None, :] + e[:, :, 0]   # (ni, nt)
        self.fc_y = smy[None, :] + e[:, :, 1]
        # "current forecast of the present" at each tgrid (lead ≈ 0 after an update,
        # growing until the next)
        self.fc_now_x = np.zeros(nt)
        self.fc_now_y = np.zeros(nt)
        for k, tk in enumerate(self.tgrid):
            i = int(np.searchsorted(issues, tk + 1e-9) - 1)
            i = max(0, min(i, ni - 1))
            self.fc_now_x[k] = self.fc_x[i, k]
            self.fc_now_y[k] = self.fc_y[i, k]

    def _idx(self, t):
        i = int(round(t / C.DT))
        return max(0, min(self.NT - 1, i))

    def issue_index(self, t):
        i = int(np.searchsorted(self.issue_times, t + 1e-9) - 1)
        return max(0, min(len(self.issue_times) - 1, i))

    def forecast_wind(self, t_now, t_future=None):
        """Latest issued forecast at t_now, for time t_future (default: now). m/s, large-scale."""
        if t_future is None:
            t_future = t_now
        i = self.issue_index(t_now)
        j = self._idx(t_future)
        return float(self.fc_x[i, j]), float(self.fc_y[i, j])

    def truth_wind_large(self, t):
        j = self._idx(t)
        return float(self.wtx[j]), float(self.wty[j])

    def truth_wind(self, x, y, t):
        """Full true wind: F0 + spatially correlated OU + hidden gust + front. m/s."""
        j = self._idx(t)
        sx, sy = self.spatial_wind(x, y, j)
        gx, gy = float(self.gust[j, 0]), float(self.gust[j, 1])
        fx, fy = self.front_wind(x, y, t)
        return float(self.F0x[j] + sx + gx + fx), float(self.F0y[j] + sy + gy + fy)

    def _spawn_cells(self, rng):
        t0, t1 = C.CELL_WINDOW
        n = rng.poisson(self.lam * (t1 - t0) / 60.0)
        xmin, xmax, ymin, ymax = self.bbox
        # pad bbox so cells can enter from outside
        pad = 8000.0
        for _ in range(int(n)):
            birth = float(rng.uniform(t0, t1))
            life = float(rng.uniform(*C.LIFE_RANGE))
            death = min(C.H, birth + life)
            a = float(rng.uniform(*C.AXIS_RANGE))
            b = float(rng.uniform(*C.AXIS_RANGE))
            ang = float(rng.uniform(0, 2 * math.pi))
            spd = float(rng.uniform(*C.CELL_SPEED_RANGE))  # m/s
            # start near / just upwind of the bbox so the cell can sweep it
            # place at a random point on the expanded bbox at birth, move along cell_dir
            cx0 = float(rng.uniform(xmin - pad, xmax + pad))
            cy0 = float(rng.uniform(ymin - pad, ymax + pad))
            front = float(rng.uniform(*C.FRONT_ADD))
            # integrate velocity: mean = spd along cell_dir, plus OU
            vu = ou_path(rng, self.NT, C.DT, C.TAU_V, C.SIG_V, 2)
            mx = spd * math.cos(self.cell_dir)
            my = spd * math.sin(self.cell_dir)
            vx = mx + vu[:, 0]
            vy = my + vu[:, 1]
            # positions (m); velocity is m/s so *60 for m/min
            cx = np.zeros(self.NT)
            cy = np.zeros(self.NT)
            # back-integrate to t=0 from birth
            ib = self._idx(birth)
            cx[ib] = cx0
            cy[ib] = cy0
            for k in range(ib + 1, self.NT):
                cx[k] = cx[k - 1] + vx[k - 1] * 60.0 * C.DT
                cy[k] = cy[k - 1] + vy[k - 1] * 60.0 * C.DT
            for k in range(ib - 1, -1, -1):
                cx[k] = cx[k + 1] - vx[k] * 60.0 * C.DT
                cy[k] = cy[k + 1] - vy[k] * 60.0 * C.DT
            # triangular intensity on [birth, death]
            mid = 0.5 * (birth + death)
            inten = np.zeros(self.NT)
            for k, tk in enumerate(self.tgrid):
                if tk < birth or tk > death:
                    inten[k] = 0.0
                elif tk <= mid:
                    inten[k] = (tk - birth) / max(1e-6, mid - birth)
                else:
                    inten[k] = (death - tk) / max(1e-6, death - mid)
            self.cells.append(dict(
                birth=birth, death=death, life=life, a=a, b=b, ang=ang,
                cx=cx, cy=cy, vx=vx, vy=vy, inten=inten, front=front,
                spd=spd,
            ))

    def _pack_cells(self):
        n = len(self.cells)
        self.ncell = n
        if n == 0:
            self.c_cx = np.zeros((0, self.NT))
            self.c_cy = np.zeros((0, self.NT))
            self.c_vx = np.zeros((0, self.NT))
            self.c_vy = np.zeros((0, self.NT))
            self.c_in = np.zeros((0, self.NT))
            self.c_a = np.zeros(0)
            self.c_b = np.zeros(0)
            self.c_ang = np.zeros(0)
            self.c_front = np.zeros(0)
            self.c_birth = np.zeros(0)
            self.c_death = np.zeros(0)
            return
        self.c_cx = np.stack([c["cx"] for c in self.cells])
        self.c_cy = np.stack([c["cy"] for c in self.cells])
        self.c_vx = np.stack([c["vx"] for c in self.cells])
        self.c_vy = np.stack([c["vy"] for c in self.cells])
        self.c_in = np.stack([c["inten"] for c in self.cells])
        self.c_a = np.array([c["a"] for c in self.cells])
        self.c_b = np.array([c["b"] for c in self.cells])
        self.c_ang = np.array([c["ang"] for c in self.cells])
        self.c_front = np.array([c["front"] for c in self.cells])
        self.c_birth = np.array([c["birth"] for c in self.cells])
        self.c_death = np.array([c["death"] for c in self.cells])

    def active_cells(self, t, min_inten=1e-6):
        if self.ncell == 0:
            return []
        j = self._idx(t)
        out = []
        for i in range(self.ncell):
            if self.tgrid[j] < self.c_birth[i] - 1e-9 or self.tgrid[j] > self.c_death[i] + 1e-9:
                continue
            if self.c_in[i, j] < min_inten:
                continue
            out.append(i)
        return out

    def in_any_cell(self, x, y, t, buf=0.0):
        for i in self.active_cells(t):
            j = self._idx(t)
            if ellipse_contains(x, y, self.c_cx[i, j], self.c_cy[i, j],
                                self.c_a[i], self.c_b[i], self.c_ang[i], buf):
                return True
        return False

    def front_wind(self, x, y, t):
        """+5–8 m/s in the 2 km front of each active cell, along cell motion."""
        if self.ncell == 0:
            return 0.0, 0.0
        j = self._idx(t)
        fx = fy = 0.0
        for i in self.active_cells(t):
            cx, cy = self.c_cx[i, j], self.c_cy[i, j]
            vx, vy = self.c_vx[i, j], self.c_vy[i, j]
            spd = math.hypot(vx, vy) + 1e-9
            ux, uy = vx / spd, vy / spd
            # "front": ahead of the ellipse along velocity, within FRONT_KM of the
            # ellipse boundary, and not inside the ellipse
            if ellipse_contains(x, y, cx, cy, self.c_a[i], self.c_b[i], self.c_ang[i], 0.0):
                continue
            # nearest point approximation: vector from center, projected
            dx, dy = x - cx, y - cy
            ahead = dx * ux + dy * uy
            if ahead <= 0:
                continue
            # distance to expanded ellipse along this ray, approx: radial
            # use "distance to boundary" ≈ max(0, r_ell - 1) * radial_len
            if ellipse_contains(x, y, cx, cy, self.c_a[i], self.c_b[i], self.c_ang[i], C.FRONT_KM):
                # only the forward half
                fx += self.c_front[i] * ux
                fy += self.c_front[i] * uy
        return fx, fy

    def nowcast_cells(self, t):
        """Observed: current polygon + velocity estimated from last 3 observations.
        No future truth. Observations at 5-min ticks (positions are visible).
        Returns list of dicts with cx,cy,a,b,ang,vx_est,vy_est,birth_obs.
        """
        out = []
        j = self._idx(t)
        for i in range(self.ncell):
            # visible if already born (even if intensity just starting)
            if self.tgrid[j] < self.c_birth[i] - 1e-9:
                continue
            if self.tgrid[j] > self.c_death[i] + C.DT:
                continue
            # last 3 observation indices at or before j, after birth
            jb = self._idx(self.c_birth[i])
            idxs = [k for k in range(max(jb, j - 2), j + 1)]
            if len(idxs) >= 2:
                i0, i1 = idxs[0], idxs[-1]
                dtmin = max(C.DT, (i1 - i0) * C.DT)
                vx = (self.c_cx[i, i1] - self.c_cx[i, i0]) / (dtmin * 60.0)  # m/s
                vy = (self.c_cy[i, i1] - self.c_cy[i, i0]) / (dtmin * 60.0)
            else:
                vx = vy = 0.0
            out.append(dict(
                i=i,
                cx=float(self.c_cx[i, j]), cy=float(self.c_cy[i, j]),
                a=float(self.c_a[i]), b=float(self.c_b[i]), ang=float(self.c_ang[i]),
                vx=float(vx), vy=float(vy),
                inten=float(self.c_in[i, j]),
                age=float(max(0.0, self.tgrid[j] - self.c_birth[i])),
            ))
        return out

    def predicted_center(self, nc, t_future):
        """Constant-velocity prediction from a nowcast dict."""
        dt = (t_future - 0.0)  # caller passes absolute; we need dt from 'now'
        # store nothing; caller should use:
        # cx + vx*60*(t_f - t_now)
        return nc  # placeholder, see pred_xy

    def pred_xy(self, nc, t_now, t_future):
        dtsec = (t_future - t_now) * 60.0
        return nc["cx"] + nc["vx"] * dtsec, nc["cy"] + nc["vy"] * dtsec

    def swept_targets(self, tid_xy):
        """For each target, list (cell_i, enter_t, leave_t) if the TRUE cell sweeps it."""
        hits = []
        if self.ncell == 0:
            return hits
        for ti, (x, y) in enumerate(tid_xy):
            for i in range(self.ncell):
                inside = False
                enter = leave = None
                jb = self._idx(self.c_birth[i])
                jd = self._idx(self.c_death[i])
                for j in range(jb, jd + 1):
                    inn = ellipse_contains(x, y, self.c_cx[i, j], self.c_cy[i, j],
                                           self.c_a[i], self.c_b[i], self.c_ang[i], 0.0)
                    if inn and not inside:
                        enter = self.tgrid[j]; inside = True
                    if inn:
                        leave = self.tgrid[j]
                    if (not inn) and inside:
                        break
                if enter is not None:
                    hits.append((ti, i, float(enter), float(leave if leave is not None else enter)))
        return hits

    def hash(self):
        """Stable fingerprint of the materialised day (for SPLITS.json)."""
        h = hashlib.sha256()
        h.update(np.asarray([self.seed, int(self.storm), self.W0, self.dir0, self.dW,
                             self.lam, self.p_f, self.delta, self.ncell], dtype=np.float64).tobytes())
        h.update(self.wtx.tobytes()); h.update(self.wty.tobytes())
        if self.ncell:
            h.update(self.c_cx.tobytes()); h.update(self.c_cy.tobytes())
        return h.hexdigest()[:16]


def make_requests(wx: WeatherDay, targets_xy, seed, mode=None, n_storm_force=None):
    """Build the urgent-request stream for one day.

    Storm faults: each swept target fails with probability p_f, alarm
    U(0,20) min AFTER the cell leaves. Background: Poisson, expected
    n_targets/6, jittered around targets. 40% high-priority.

    mode='uniform' (P3): same expected NUMBER of storm-like faults, but
    locations uniform among targets and independent of cell tracks.
    Alarm times keep the same marginal window (storm-active period) so
    the only change is spatial.
    """
    mode = mode or wx.mode
    # Always use the "storm" request stream for the canonical faults+bg, so
    # P3 uniform is a paired spatial ablation and storm-mode hashes stay frozen.
    rng = _rng(seed, "requests", "storm")
    T = np.asarray(targets_xy, dtype=float)
    nt = len(T)
    reqs = []  # (t, x, y, pri, kind, tid)
    # --- storm / uniform faults ---
    hits = wx.swept_targets(T)
    # unique targets swept (first leave time)
    swept = {}
    for ti, ci, ent, lev in hits:
        if ti not in swept or lev < swept[ti][1]:
            swept[ti] = (ent, lev, ci)
    storm_faults = []
    for ti, (ent, lev, ci) in swept.items():
        if rng.random() < wx.p_f:
            delay = float(rng.uniform(0.0, 20.0))
            alarm = min(C.H - 1e-6, lev + delay)
            pri = int(rng.random() < C.P_HIGH_FRAC)
            storm_faults.append((alarm, float(T[ti, 0]), float(T[ti, 1]), pri, "storm", int(ti)))

    # --- background (generated on the STORM rng stream, BEFORE any uniform
    # re-placement, so storm-mode days stay bit-identical to already-run
    # experiments, and P3 uniform days share the exact same background).
    bg_reqs = []
    nbg = int(rng.poisson(nt / C.BG_RATE_DIV))
    for _ in range(nbg):
        t = float(rng.uniform(0.0, C.H))
        ti = int(rng.integers(nt))
        xy = T[ti] + rng.normal(0.0, C.BG_JITTER, 2)
        pri = int(rng.random() < C.P_HIGH_FRAC)
        bg_reqs.append((t, float(xy[0]), float(xy[1]), pri, "bg", -1))

    if mode == "uniform":
        n_exp = n_storm_force if n_storm_force is not None else len(storm_faults)
        # Re-place only the storm-like faults. Use a dedicated stream so we do
        # not consume the canonical rng (already used for bg). Keep alarm
        # times and priorities when available — only (x,y,tid) change.
        rng_u = _rng(seed, "requests", "uniform_place")
        times_pool = [r[0] for r in storm_faults]
        storm_faults_u = []
        for k in range(n_exp):
            ti = int(rng_u.integers(nt))
            if k < len(times_pool):
                alarm = times_pool[k]
                pri = storm_faults[k][3]
            else:
                alarm = float(rng_u.uniform(30.0, min(C.H - 1, 400.0)))
                pri = int(rng_u.random() < C.P_HIGH_FRAC)
            storm_faults_u.append((alarm, float(T[ti, 0]), float(T[ti, 1]), pri, "uniform", int(ti)))
        storm_faults = storm_faults_u

    reqs.extend(storm_faults)
    reqs.extend(bg_reqs)

    reqs.sort(key=lambda r: r[0])
    return reqs, dict(n_storm=sum(1 for r in reqs if r[4] in ("storm", "uniform")),
                      n_bg=sum(1 for r in reqs if r[4] == "bg"),
                      n_swept=len(swept), storm=int(wx.storm), ncell=wx.ncell)


def day_hash(wx, reqs):
    h = hashlib.sha256()
    h.update(wx.hash().encode())
    if reqs:
        arr = np.array([(r[0], r[1], r[2], r[3]) for r in reqs], dtype=np.float64)
        h.update(arr.tobytes())
    return h.hexdigest()[:16]
