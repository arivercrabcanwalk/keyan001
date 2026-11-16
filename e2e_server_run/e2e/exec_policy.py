"""pi_exec: learned execution layer = RL5 architecture (global MLP + shared per-action feature head) extended with a
6th action REROUTE, plus a value head (PPO). REROUTE = re-plan all unstarted targets of this drone's station with
pi_route (single-station sub-problem, used duty as initial state, energy reserve r from the CURRENT forecast) and
launch the first new trip. Only information observable at decision time is used.
Workers run the policy in numpy (fast, no torch threads); the learner holds the torch module."""
import math, os, time, numpy as np, torch, torch.nn as nn
from .common import ROOT, TOK_LIM
import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from wx2 import feat as FT, const as C, sim as S          # noqa: E402

NG, NA, N5 = FT.NG, FT.NA, S.N_ACT
REROUTE = N5            # action index 5
NACT = N5 + 1
NIN = NG + NACT * NA


class ExecNet(nn.Module):
    def __init__(self, d=128):
        super().__init__()
        self.d = d
        self.W1 = nn.Linear(NG, d); self.W2 = nn.Linear(d, d); self.W3 = nn.Linear(d, NACT)
        self.Wa = nn.Linear(NA, 1)
        self.v = nn.Sequential(nn.Linear(NG, 256), nn.Tanh(), nn.Linear(256, 256), nn.Tanh(), nn.Linear(256, 1))

    def forward(self, X, mask):
        g = X[:, :NG]; af = X[:, NG:].view(-1, NACT, NA)
        h = torch.relu(self.W2(torch.relu(self.W1(g))))
        lg = self.W3(h) + self.Wa(af).squeeze(-1)
        lg = lg.masked_fill(~mask, -1e9)
        return lg, self.v(g).squeeze(-1)

    def load_rl5(self, npz):
        z = np.load(npz)
        with torch.no_grad():
            W1 = z["W1"]
            if W1.shape[0] < NG:
                W1 = np.vstack([W1, np.zeros((NG - W1.shape[0], W1.shape[1]))])
            self.W1.weight.copy_(torch.as_tensor(W1.T)); self.W1.bias.copy_(torch.as_tensor(z["b1"]))
            self.W2.weight.copy_(torch.as_tensor(z["W2"].T)); self.W2.bias.copy_(torch.as_tensor(z["b2"]))
            W3 = np.zeros((self.d, NACT)); W3[:, :N5] = z["W3"]
            b3 = np.zeros(NACT); b3[:N5] = z["b3"]; b3[REROUTE] = float(np.min(z["b3"])) - 3.0   # REROUTE starts rare
            self.W3.weight.copy_(torch.as_tensor(W3.T)); self.W3.bias.copy_(torch.as_tensor(b3))
            self.Wa.weight.copy_(torch.as_tensor(z["Wa"].T)); self.Wa.bias.copy_(torch.as_tensor(z["ba"]))

    def numpy_params(self):
        return {k: v.detach().cpu().double().numpy() for k, v in self.state_dict().items()}


def np_forward(P, x, mask):
    g = x[:NG]; af = x[NG:].reshape(NACT, NA)
    h = np.maximum(0, np.maximum(0, g @ P["W1.weight"].T + P["W1.bias"]) @ P["W2.weight"].T + P["W2.bias"])
    lg = h @ P["W3.weight"].T + P["W3.bias"] + (af @ P["Wa.weight"].T)[:, 0] + P["Wa.bias"][0]
    v = np.tanh(np.tanh(g @ P["v.0.weight"].T + P["v.0.bias"]) @ P["v.2.weight"].T + P["v.2.bias"]) @ P["v.4.weight"].T + P["v.4.bias"]
    lg = np.where(mask, lg, -1e9)
    lg = lg - lg.max(); p = np.exp(lg) * mask; p = p / p.sum()
    return p, float(v[0])


# ---------------- REROUTE ----------------
_ROUTER = {}


def get_router(path):
    if path not in _ROUTER:
        torch.set_num_threads(1)
        from .route_model import load_route
        _ROUTER[path] = load_route(path, "cpu")[0]
    return _ROUTER[path]


def station_drones(sim, sid):
    return [j for j, e in enumerate(sim.drones) if e["sid"] == sid]


def reroute_ok(sim, i, m5):
    d = sim.drones[i]
    if not m5[S.LAUNCH] or sim.t >= C.H:
        return False
    js = station_drones(sim, d["sid"])
    if any(sim.drones[j].get("backup") or sim.drones[j].get("handed") for j in js):
        return False
    left = sum(len(tr) for j in js for tr in sim.drones[j]["trips"]) + sum(len(sim.drones[j]["backlog"]) for j in js)
    return left >= 2


def fc_reserve(sim, i, info):
    d = sim.drones[i]
    if info is None or not info.get("nodes"):
        return 0.0
    fl, sv, sve = sim._trip_nw(d, info["nodes"])
    calm = fl * sim.p.flight_energy + sve
    return float(np.clip(info["energy"] / max(calm, 1e-6) - 1.0, 0.0, 0.5))


def do_reroute(sim, i, info, router_path, mode="greedy"):
    """Re-plan all unstarted targets at drone i's station with pi_route; updates `info` in place for the launch.
    Returns True if applied (otherwise the plan is left untouched)."""
    from .route_env import Batch
    from .route_model import rollout
    from .route_env import decode_actions
    d = sim.drones[i]; sid = d["sid"]; st = sim.st[sid]
    js = station_drones(sim, sid)
    saved = {j: ([list(t) for t in sim.drones[j]["trips"]], list(sim.drones[j]["backlog"])) for j in js}
    nids = [nid for j in js for tr in sim.drones[j]["trips"] for nid in tr] + [nid for j in js for nid in sim.drones[j]["backlog"]]
    if len(nids) < 2:
        return False
    tg = np.array([[sim.nodes[n].x, sim.nodes[n].y] for n in nids]); stxy = np.array([[st["x"], st["y"]]])
    kind = st["kind"]
    td = np.zeros(3)
    for j in js:
        e = sim.drones[j]
        busy_left = max(0.0, e["free"] - sim.t) if e["state"] in ("busy", "down") else 0.0
        tok = 0 if kind == 1 else (1 if e["large"] else 2)
        td[tok] = e["duty"] + busy_left + (TOK_LIM[tok] - e["duty_max"])
    r = fc_reserve(sim, i, info)
    pol = get_router(router_path)
    bt = Batch(tg[None], stxy[None], np.array([[kind]]), reserve=[r], tdone0=td[None], N=1, dev="cpu")
    o = rollout(pol, bt, greedy=True)
    if bool(o["fail"][0]):
        return False
    routes = decode_actions(o["acts"][0].tolist(), len(nids), 1, [kind])[0]
    for j in js:
        e = sim.drones[j]
        slot = 0 if e["large"] else 1
        e["trips"] = [[nids[k] for k in trip] for trip in routes[slot]]
        e["backlog"] = []
    new = sim.next_trip_info(i)
    ok = new is not None and d["duty"] + new["ttot"] <= d["duty_max"] + 1e-6 and new["energy"] <= d["cap"] * 1.08 + 1e-6
    if not ok:
        for j in js:
            sim.drones[j]["trips"], sim.drones[j]["backlog"] = [list(t) for t in saved[j][0]], list(saved[j][1])
        return False
    info.clear(); info.update(new)
    sim.n_reroute = getattr(sim, "n_reroute", 0) + 1
    return True


def full_features(sim, i, m5, cands, info):
    x5 = FT.features(sim, i, m5, cands, info)            # (NG + 5*NA)
    x = np.zeros(NIN, dtype=np.float32); x[:NG + N5 * NA] = x5
    if info is not None:
        js = station_drones(sim, sim.drones[i]["sid"])
        left = sum(len(tr) for j in js for tr in sim.drones[j]["trips"])
        af = x[NG + REROUTE * NA: NG + (REROUTE + 1) * NA]
        af[0] = 1.0; af[1] = fc_reserve(sim, i, info) * 2; af[2] = min(left, 30) / 15.0
        af[3] = min(info["energy"] / max(sim.drones[i]["cap"], 1e-6), 1.5); af[4] = float(info.get("clear", 1.0))
        af[5] = x5[6] if len(x5) > 7 else 0.0; af[6] = x5[7] if len(x5) > 7 else 0.0
    return x


def make_exec_policy(P, router_path=None, greedy=True, rng=None, record=None, allow_reroute=True, force_reroute=False):
    """sim policy callback. record: list to append (x, mask6, a, logp, v, t) for PPO."""
    rng = rng or np.random.default_rng(0)

    def pol(sim, i, m5, cands, info):
        mask = np.zeros(NACT, dtype=bool); mask[:N5] = m5
        if allow_reroute and router_path and info is not None and reroute_ok(sim, i, m5):
            mask[REROUTE] = True
        x = full_features(sim, i, m5, cands, info)
        p, v = np_forward(P, x, mask)
        if force_reroute and mask[REROUTE] and not m5[S.SERVE0:].any():
            a = REROUTE
        else:
            a = int(np.argmax(p)) if greedy else int(rng.choice(NACT, p=p))
        if record is not None:
            record.append([x, mask, a, float(np.log(p[a] + 1e-12)), v, sim_j_running(sim)])
        if a == REROUTE:
            if not do_reroute(sim, i, info, router_path):
                sim.n_reroute_fail = getattr(sim, "n_reroute_fail", 0) + 1
            return S.LAUNCH
        return a
    return pol


def sim_j_running(sim):
    """Running J5 accumulated so far (telescoping reward: r_k = -(J_run(k+1) - J_run(k)); final adds J_final - J_run)."""
    busy = sum(d["busy"] for d in sim.drones)
    cost = sim.fixed + C.C_BUSY * busy + getattr(sim, "backup_cost", 0.0)
    lh = sum(L[2] for L in sim.log if L[0] == 1); ln = sum(L[2] for L in sim.log if L[0] == 0)
    st_end = {}
    for d in sim.drones:
        st_end[d["sid"]] = max(st_end.get(d["sid"], 0.0), d.get("last_end", 0.0))
    ot = sum(max(0.0, v - C.H) for v in st_end.values())
    return cost + C.C_OT * ot + C.C_LATE_H * lh + C.C_LATE_N * ln + sim.P * len(sim.fail_log)
