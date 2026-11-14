"""Frozen WX-Storm v1 constants. Synthetic wind-error parameters are labelled as such."""

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

H = 480.0                 # minutes
DT = 5.0                  # weather update (min)
DT_FLY = 0.5              # flight integration step (min)
VA_MS = 15.0              # airspeed m/s
VA = 900.0                # airspeed m/min (= Liu speed)
# --- synthetic forecast-error parameters (NOT fitted to ERA5/CRA-40) ---
SIGMA0 = 1.0              # m/s, labelled SYNTHETIC
KAPPA = 0.5               # m/s per hour of lead, labelled SYNTHETIC
FC_AR1 = 0.7
FC_PERIOD = 60.0
# --- penalties / objective (P=100 is the main report) ---
P_MAIN = 100.0
P_SET = (50.0, 100.0, 200.0)
C_BUSY = 0.5
C_MK = 0.5
C_LATE_H = 30.0           # per late minute, high priority
C_LATE_N = 10.0           # per late minute, normal
DL = {1: 20.0, 0: 45.0}  # deadlines (min after release)
P_HIGH_FRAC = 0.40
U_SERVICE = 2.0           # urgent inspection time (min)
U_ENERGY = 0.05           # urgent inspection energy
FAIL_GROUND = 60.0        # grounded after a failure (min)
BUFFER = 1000.0           # 1 km detour buffer (m)
FRONT_KM = 2000.0
# --- cells (pre-registered) ---
STORM_PROB = 0.50
CELL_WINDOW = (30.0, 300.0)
LAM_RANGE = (1.0, 3.0)    # cells per hour on a storm day
PF_RANGE = (0.2, 0.4)
AXIS_RANGE = (1500.0, 4000.0)
LIFE_RANGE = (40.0, 100.0)
CELL_SPEED_RANGE = (8.0, 15.0)   # m/s
DELTA_DEG = 30.0
SIG_V = 1.5               # m/s OU on cell velocity
TAU_V = 20.0              # min
FRONT_ADD = (5.0, 8.0)    # m/s
# --- wind ---
W0_RANGE = (4.0, 10.0)    # m/s
DW_RANGE = (0.0, 3.0)     # m/s linear rise
OU_TAU_RANGE = (30.0, 90.0)
OU_SIG_RANGE = (1.0, 3.0)
ELL_RANGE = (5000.0, 20000.0)
GUST_DWELL = (30.0, 60.0)
GUST_AMP = (3.0, 6.0)
N_FOURIER = 16
# --- background urgents ---
BG_RATE_DIV = 6.0         # expected n_targets / 6
BG_JITTER = 500.0
# --- unserved lateness floor (pre-registered) ---
UNSERVED_FLOOR = 60.0
# --- seeds (must not overlap previous E-line exposed seeds) ---
TRAIN_WX_MIN = 10 ** 6
DEV_DAYS = list(range(6000, 6010))
TEST_DAYS = list(range(7000, 7030))
TEST_SUBSET = list(range(7000, 7010))   # slow methods
# WX-C non-overlapping
WXC_TRAIN_WX_MIN = 2 * 10 ** 6
WXC_DEV_DAYS = list(range(6100, 6150))
WXC_TEST_DAYS = list(range(7100, 7130))
