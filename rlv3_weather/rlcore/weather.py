"""Synthetic weather generator for rlv3-weather (SYNTHETIC ONLY - no observed weather is used).

Every distribution parameter below is a documented scenario assumption anchored to public literature
(see DESIGN_ZH.md section 3); none is fitted to proprietary data.
  mean wind     : 10-m speed U10 ~ Weibull(k=2, c=C10)  (k~2 is the standard first-order wind-speed model)
                  lifted to flight height h with the 1/7 power law (Peterson & Hennessey 1978, JAM 17:390)
  diurnal cycle : daytime amplification, evening calm after the shift (stable boundary layer) -> completion guaranteed
  mesoscale     : spatially correlated Fourier field (wavelength 5-20 km) with OU time coefficients, std = TI * U,
                  TI in [0.10, 0.20] (IEC 61400-1 reference turbulence intensities 0.12-0.16 bracket this range)
  gust surges   : hidden two-state Markov surge, gust factor G in [1.3, 1.6] (Harper, Kepert & Ginger 2010 WMO TD-1555
                  give 1.23 at sea and larger factors over rougher land)
  forecast      : issued every 60 min, error std 1.0 + 0.5/h lead (synthetic), AR(1) across issues
  storm cells   : moving elliptical no-fly zones; lifetimes 25 min (simple) / 70 min (complex), median speed 30 km/h
                  (Goudenhoofdt & Delobbe 2013, JAMC 52:918, TITAN radar statistics); outflow winds around cells;
                  linear-extrapolation nowcast with growing uncertainty buffer (Dixon & Wiener 1993; Wilson et al. 1998).
"""
import math
import numpy as np
from .common import stable_rng

H = 480.0             # shift length (min)
T_MAX = 900.0         # simulated horizon (min)
DT = 5.0
H_FLY = 100.0         # m AGL (inspection flight height above terrain: tower 30-60 m + clearance)
SHEAR = (H_FLY / 10.0) ** (1.0 / 7.0)
C10 = 4.0             # Weibull scale at 10 m  (mean 3.5 m/s at 10 m, 4.9 m/s at flight height)
K_WEIB = 2.0
U10_MAX = 9.0
DIURNAL = (0.0, 0.3)
VEER_DEG = 30.0
TI_RANGE = (0.10, 0.20)
ELL_RANGE = (5000.0, 20000.0)
TAU_RANGE = (20.0, 60.0)
N_MODES = 12
GUST_G = (1.3, 1.6)
GUST_ON_MEAN, GUST_OFF_MEAN = 15.0, 45.0
FC_PERIOD, SIG0, KAPPA, FC_RHO = 60.0, 1.0, 0.5, 0.7
POST_TAU = 60.0
T_RELAX = 600.0       # after the 10-h working day (= env.T_DAY) the wind relaxes (evening calm); only beyond the day,
                      # where overtime is penalised, so no method can profit from it without paying overtime
# storm cells
P_STORM = 0.35
CELL_WINDOW = (60.0, 360.0)
LAM_RANGE = (1.0, 3.0)        # cells / hour on a storm day (over the map)
P_SIMPLE = 0.7
LIFE_SIMPLE, LIFE_COMPLEX = (25.0, 12.0), (70.0, 35.0)
SPD_MEDIAN = 30.0 / 3.6       # m/s
SPD_K = 2.0
AXIS_RANGE = (1500.0, 4000.0)
DELTA_DEG = 30.0
G_ACTIVE = 0.3
OUTFLOW = (4.0, 8.0)          # m/s peak outflow at the cell edge (synthetic assumption)
OUTFLOW_L = 2000.0
NC_POS_SD, NC_VEL_SD, NC_AX_SD = 200.0, 0.7, 0.10
NC_BUFFER = 1000.0
NC_GROW = 0.10                # +10 % axes per 10 min of nowcast lead


def _lognorm(rng, mean, sd, lo, hi):
    s2 = math.log(1 + (sd / mean) ** 2)
    v = rng.lognormal(math.log(mean) - s2 / 2, math.sqrt(s2))
    return float(min(max(v, lo), hi))


class WeatherDay:
    """mode: 'mix' (storm with prob P_STORM), 'storm' (forced storm day), 'wind' (no cells), 'nowind' (calm, exact author world).
    scale: multiplies all wind magnitudes (sensitivity)."""

    def __init__(self, seed, bbox, mode="mix", scale=1.0):
        self.seed, self.mode, self.bbox, self.scale = int(seed), mode, tuple(bbox), float(scale)
        rng = stable_rng("rlv3-weather", seed, mode)
        self.tg = np.arange(0.0, T_MAX + DT * 0.5, DT)
        self.NT = len(self.tg)
        self.calm = (mode == "nowind")
        if self.calm:
            self.storm = False; self.ncell = 0; self.U = 0.0
            return
        u10 = min(C10 * rng.weibull(K_WEIB), U10_MAX)
        self.U = max(0.5, u10 * SHEAR)
        self.diurnal = rng.uniform(*DIURNAL)
        self.dir0 = rng.uniform(0, 2 * math.pi)
        self.veer = math.radians(rng.uniform(-VEER_DEG, VEER_DEG))
        self.TI = rng.uniform(*TI_RANGE)
        self.gG = rng.uniform(*GUST_G)
        t = self.tg
        self.relax = np.where(t > T_RELAX, np.exp(-(t - T_RELAX) / POST_TAU), 1.0)
        spd = self.U * (1 + self.diurnal * np.sin(np.pi * np.clip(t, 0, H) / H)) * self.relax * self.scale
        ang = self.dir0 + self.veer * np.clip(t, 0, H) / H
        self.mx, self.my = spd * np.cos(ang), spd * np.sin(ang)
        self.spd = spd
        # mesoscale Fourier field
        K = N_MODES
        ell = rng.uniform(*ELL_RANGE, K); th = rng.uniform(0, 2 * math.pi, K)
        self.kx, self.ky = 2 * math.pi / ell * np.cos(th), 2 * math.pi / ell * np.sin(th)
        self.kph = rng.uniform(0, 2 * math.pi, K)
        tau = rng.uniform(*TAU_RANGE, K)
        a = np.exp(-DT / tau); self._a = a; self._sigfac = None
        coef = np.zeros((self.NT, K, 2)); x = rng.normal(0, 1, (K, 2))
        g = rng.normal(0, 1, (self.NT, K, 2))
        for i in range(self.NT):
            coef[i] = x
            x = a[:, None] * x + np.sqrt(1 - a[:, None] ** 2) * g[i]
        sig = max(0.5, self.TI * self.U) * self.scale
        self._sigfac = sig * math.sqrt(2.0 / K)
        self.coef = coef * self._sigfac * self.relax[:, None, None]
        # hidden gust surges (along the mean wind)
        on = False; gust = np.zeros(self.NT)
        for i in range(self.NT):
            p = DT / (GUST_ON_MEAN if on else GUST_OFF_MEAN)
            if rng.random() < p:
                on = not on
            gust[i] = 1.0 if on else 0.0
        self.gust = gust * (self.gG - 1.0) * spd
        self.gx, self.gy = self.gust * np.cos(ang), self.gust * np.sin(ang)
        # forecasts: one unit AR(1) error vector per issue
        n_iss = int(T_MAX // FC_PERIOD) + 1
        e = rng.normal(0, 1, 2); self.fc_err = np.zeros((n_iss, 2))
        for i in range(n_iss):
            self.fc_err[i] = e
            e = FC_RHO * e + math.sqrt(1 - FC_RHO ** 2) * rng.normal(0, 1, 2)
        # cells
        self.storm = (mode == "storm") or (mode == "mix" and rng.random() < P_STORM)
        self._cells(rng)

    # ------------------------------------------------------------------ cells
    def _cells(self, rng):
        self._build_cells(self._draw_cells(rng))

    def _draw_cells(self, rng):
        cells = []
        if self.storm:
            lam = rng.uniform(*LAM_RANGE)
            n = rng.poisson(lam * (CELL_WINDOW[1] - CELL_WINDOW[0]) / 60.0)
            delta = math.radians(rng.uniform(-DELTA_DEG, DELTA_DEG))
            x0, x1, y0, y1 = self.bbox
            for _ in range(n):
                tb = rng.uniform(*CELL_WINDOW)
                L = _lognorm(rng, *LIFE_SIMPLE, 10, 60) if rng.random() < P_SIMPLE else _lognorm(rng, *LIFE_COMPLEX, 30, 200)
                s = min(max(SPD_MEDIAN / (math.log(2) ** (1 / SPD_K)) * rng.weibull(SPD_K), 2.0), 20.0)
                d = self.dir0 + delta + math.radians(rng.uniform(-15, 15))
                vx, vy = s * math.cos(d) * 60, s * math.sin(d) * 60          # m/min
                px, py = rng.uniform(x0, x1), rng.uniform(y0, y1)           # point crossed at mid-life
                cx0, cy0 = px - vx * L / 2, py - vy * L / 2
                a = rng.uniform(*AXIS_RANGE); b = a * rng.uniform(0.5, 1.0)
                cells.append(dict(tb=tb, L=L, cx0=cx0, cy0=cy0, vx=vx, vy=vy, a=a, b=b, ang=d,
                                  uo=rng.uniform(*OUTFLOW), ou=rng.normal(0, 1, (self.NT, 2))))
        return cells

    def _build_cells(self, cells):
        self._cell_list = cells
        self.ncell = len(cells)
        NT = self.NT
        self.c_cx = np.zeros((self.ncell, NT)); self.c_cy = np.zeros((self.ncell, NT))
        self.c_g = np.zeros((self.ncell, NT)); self.c_vx = np.zeros((self.ncell, NT)); self.c_vy = np.zeros((self.ncell, NT))
        self.c_a = np.array([c["a"] for c in cells]); self.c_b = np.array([c["b"] for c in cells])
        self.c_ang = np.array([c["ang"] for c in cells]); self.c_uo = np.array([c["uo"] for c in cells])
        aou = math.exp(-DT / 20.0)
        for k, c in enumerate(cells):
            x, y = c["cx0"], c["cy0"]; dv = np.zeros(2)
            for i, t in enumerate(self.tg):
                tau = t - c["tb"]
                if tau < 0:
                    x, y = c["cx0"], c["cy0"]
                g = math.sin(math.pi * tau / c["L"]) ** 0.5 if 0 <= tau <= c["L"] else 0.0
                vx, vy = c["vx"] + dv[0] * 60, c["vy"] + dv[1] * 60
                self.c_cx[k, i], self.c_cy[k, i], self.c_g[k, i] = x, y, g
                self.c_vx[k, i], self.c_vy[k, i] = vx, vy
                if tau >= 0:
                    x += vx * DT; y += vy * DT
                dv = aou * dv + math.sqrt(1 - aou ** 2) * 1.0 * c["ou"][i]
        self.cells_meta = [dict(tb=c["tb"], L=c["L"]) for c in cells]

    def resample_future(self, t, seed):
        """Copy of this day whose UNOBSERVED future (after time t) is redrawn from the generative model, conditioned on
        the current state: turbulence OU coefficients and gust Markov chain continue from their state at t, forecast
        issues after the current one continue the AR(1) error, cells not yet born at t are redrawn (storm flag redrawn
        when no cell has been born yet).  Used by rollout-improvement labels to avoid hindsight bias."""
        import copy
        if self.calm:
            return self
        w = copy.copy(self)
        rng = stable_rng("rlv3-wx-future", self.seed, int(t * 10), seed)
        i0 = min(self.NT - 1, int(math.ceil(max(t, 0.0) / DT)))
        a = self._a
        coef = self.coef.copy()
        x = coef[i0] / (self._sigfac * self.relax[i0])
        for i in range(i0 + 1, self.NT):
            x = a[:, None] * x + np.sqrt(1 - a[:, None] ** 2) * rng.normal(0, 1, x.shape)
            coef[i] = x * self._sigfac * self.relax[i]
        w.coef = coef
        g01 = (self.gust > 0).astype(float); on = bool(g01[i0])
        for i in range(i0 + 1, self.NT):
            p = DT / (GUST_ON_MEAN if on else GUST_OFF_MEAN)
            if rng.random() < p:
                on = not on
            g01[i] = 1.0 if on else 0.0
        ang = np.arctan2(self.my, self.mx)
        w.gust = g01 * (self.gG - 1.0) * self.spd
        w.gx, w.gy = w.gust * np.cos(ang), w.gust * np.sin(ang)
        iss = int(max(t, 0.0) // FC_PERIOD); fe = self.fc_err.copy(); e = fe[min(iss, len(fe) - 1)]
        for i in range(iss + 1, len(fe)):
            e = FC_RHO * e + math.sqrt(1 - FC_RHO ** 2) * rng.normal(0, 1, 2); fe[i] = e
        w.fc_err = fe
        born = [c for c in self._cell_list if c["tb"] <= t]
        storm = self.storm
        if self.mode == "mix" and not born and t < CELL_WINDOW[1]:
            storm = rng.random() < P_STORM
        new = []
        if storm and t < CELL_WINDOW[1]:
            w.storm = True
            new = [c for c in w._draw_cells(rng) if c["tb"] > t]
        w._build_cells(born + new)
        return w

    def _ti(self, t):
        f = min(max(t, 0.0), T_MAX - 1e-9) / DT
        i = int(f)
        return i, f - i

    def _cell_state(self, k, t):
        i, w = self._ti(t)
        cx = self.c_cx[k, i] + (self.c_cx[k, i + 1] - self.c_cx[k, i]) * w
        cy = self.c_cy[k, i] + (self.c_cy[k, i + 1] - self.c_cy[k, i]) * w
        g = self.c_g[k, i] + (self.c_g[k, i + 1] - self.c_g[k, i]) * w
        return cx, cy, g

    @staticmethod
    def _ell_r(x, y, cx, cy, a, b, ang):
        dx, dy = x - cx, y - cy
        ca, sa = math.cos(ang), math.sin(ang)
        xr = (dx * ca + dy * sa) / a; yr = (-dx * sa + dy * ca) / b
        return math.sqrt(xr * xr + yr * yr)

    def in_cell(self, x, y, t):
        """TRUE no-fly zone test (thunderstorm core)."""
        for k in range(self.ncell):
            cx, cy, g = self._cell_state(k, t)
            if g < G_ACTIVE:
                continue
            if self._ell_r(x, y, cx, cy, self.c_a[k] * g, self.c_b[k] * g, self.c_ang[k]) <= 1.0:
                return True
        return False

    # ------------------------------------------------------------------ wind
    def truth_wind(self, x, y, t):
        if self.calm:
            return 0.0, 0.0
        i, w = self._ti(t)
        mx = self.mx[i] + (self.mx[i + 1] - self.mx[i]) * w + self.gx[i]
        my = self.my[i] + (self.my[i + 1] - self.my[i]) * w + self.gy[i]
        c = self.coef[i] + (self.coef[i + 1] - self.coef[i]) * w
        cs = np.cos(self.kx * x + self.ky * y + self.kph)
        mx += float(cs @ c[:, 0]); my += float(cs @ c[:, 1])
        for k in range(self.ncell):
            cx, cy, g = self._cell_state(k, t)
            if g < G_ACTIVE:
                continue
            a, b = self.c_a[k] * g, self.c_b[k] * g
            r = self._ell_r(x, y, cx, cy, a, b, self.c_ang[k])
            if r > 1.0 and (r - 1.0) * a < 3 * OUTFLOW_L:
                d = math.hypot(x - cx, y - cy) + 1e-6
                u = self.c_uo[k] * g * math.exp(-(((r - 1.0) * a) / OUTFLOW_L) ** 2) * self.scale
                mx += u * (x - cx) / d; my += u * (y - cy) / d
        return mx, my

    def forecast_wind(self, t_now, t):
        """Area forecast issued at the last FC_PERIOD boundary <= t_now, valid at t (m/s)."""
        if self.calm:
            return 0.0, 0.0
        iss = int(max(t_now, 0.0) // FC_PERIOD)
        lead_h = max(0.0, t - iss * FC_PERIOD) / 60.0
        i, w = self._ti(t)
        mx = self.mx[i] + (self.mx[i + 1] - self.mx[i]) * w
        my = self.my[i] + (self.my[i + 1] - self.my[i]) * w
        s = (SIG0 + KAPPA * lead_h) * self.scale * (self.relax[i])
        e = self.fc_err[min(iss, len(self.fc_err) - 1)]
        return mx + s * e[0], my + s * e[1]

    def nowcast(self, t):
        """Observed active cells at time t (with observation noise), for linear extrapolation."""
        out = []
        if self.ncell == 0:
            return out
        r = stable_rng("nowcast", self.seed, int(t * 10))
        for k in range(self.ncell):
            cx, cy, g = self._cell_state(k, t)
            if g < G_ACTIVE:
                continue
            i, _ = self._ti(t)
            out.append(dict(cx=cx + r.normal(0, NC_POS_SD), cy=cy + r.normal(0, NC_POS_SD),
                            vx=self.c_vx[k, i] + r.normal(0, NC_VEL_SD) * 60, vy=self.c_vy[k, i] + r.normal(0, NC_VEL_SD) * 60,
                            a=self.c_a[k] * g * (1 + r.normal(0, NC_AX_SD)), b=self.c_b[k] * g * (1 + r.normal(0, NC_AX_SD)),
                            ang=self.c_ang[k], t0=t))
        return out


def nowcast_hits(nc, x1, y1, x2, y2, t0, dur, buf=NC_BUFFER, n=8):
    """Does the straight segment flown during [t0, t0+dur] come within `buf` of any extrapolated cell?"""
    if not nc:
        return False
    for c in nc:
        for k in range(n + 1):
            s = k / n; t = t0 + s * dur
            x, y = x1 + (x2 - x1) * s, y1 + (y2 - y1) * s
            lead = max(0.0, t - c["t0"])
            grow = 1.0 + NC_GROW * lead / 10.0
            cx, cy = c["cx"] + c["vx"] * lead, c["cy"] + c["vy"] * lead
            a, b = c["a"] * grow + buf, c["b"] * grow + buf
            if WeatherDay._ell_r(x, y, cx, cy, a, b, c["ang"]) <= 1.0:
                return True
    return False


def nowcast_min_gap(nc, x, y, t0, horizon=30.0):
    """Normalised clearance (km) of point (x,y) to extrapolated cells over the next `horizon` minutes (feature)."""
    best = 20.0
    for c in nc:
        for lead in (0.0, horizon / 2, horizon):
            cx, cy = c["cx"] + c["vx"] * (t0 + lead - c["t0"]), c["cy"] + c["vy"] * (t0 + lead - c["t0"])
            d = math.hypot(x - cx, y - cy) - max(c["a"], c["b"])
            best = min(best, d / 1000.0)
    return best
