"""GPU-batched multi-trip routing environment for a GIVEN siting (station types fixed by pi_site).
Action space per step: [targets (n) | drone tokens (K = 3*ns)].
  token k = (station k//3, drone kind k%3): 0 SABS-small, 1 DABS-large, 2 DABS-small; only tokens of the station's
  chosen type are legal. Choosing a token closes the current trip and starts a new trip of that drone; the next
  action must be a target. Choosing a target appends it to the current trip.
Masks: coverage radius, per-trip battery incl. return (capacity/(1+reserve)), cumulative duty per drone.
POMO multi-start: optional forced first target per rollout (the first token is restricted to drones that can
serve it as a single-target trip)."""
import torch
from .common import SPEED, FE, E_T, S_T, TOK_KIND, TOK_CAP, TOK_RAD, TOK_LIM, SABS_FIX, DABS_FIX, TIME_COST

_TK = None


class Batch:
    def __init__(self, tg, st, types, reserve=None, N=1, tdone0=None, dev="cpu"):
        """tg (B,n,2), st (B,ns,2), types (B,ns) int in {0,1,2} (tensors or arrays); reserve (B,);
        tdone0 (B,K) initial used duty per drone token (re-routing mid-day)."""
        f = lambda x, dt=torch.float32: torch.as_tensor(x, dtype=dt, device=dev)
        tg = f(tg); st = f(st); types = f(types, torch.long)
        B, n, _ = tg.shape; ns = st.shape[1]; K = 3 * ns
        self.dev = dev; self.B, self.n, self.ns, self.K, self.N = B, n, ns, K, N
        self.xy = torch.cat([tg, st], 1)                                  # (B,V,2)
        self.D = torch.cdist(self.xy, self.xy)
        self.types = types
        self.reserve = f(reserve if reserve is not None else torch.zeros(B))
        self.tok_st = torch.arange(ns, device=dev).repeat_interleave(3)
        self.tok_ty = torch.arange(3, device=dev).repeat(ns)
        self.tok_kind = torch.as_tensor(TOK_KIND, device=dev)[self.tok_ty]
        self.tok_cap = torch.as_tensor(TOK_CAP, dtype=torch.float32, device=dev)[self.tok_ty]
        self.tok_rad = torch.as_tensor(TOK_RAD, dtype=torch.float32, device=dev)[self.tok_ty]
        self.tok_lim = torch.as_tensor(TOK_LIM, dtype=torch.float32, device=dev)[self.tok_ty]
        self.tok_open = types[:, self.tok_st] == self.tok_kind[None]      # (B,K) token exists under this siting
        dst = self.D[:, n:, :n]
        self.dk = dst[:, self.tok_st]                                     # (B,K,n)
        self.capr = self.tok_cap[None] / (1 + self.reserve[:, None])      # (B,K)
        self.cover = (self.dk <= self.tok_rad[None, :, None] + 1e-6) & self.tok_open[..., None]
        self.single_time = 2 * self.dk / SPEED + S_T
        self.single_ok = self.cover & (2 * self.dk / SPEED * FE + E_T <= self.capr[..., None] + 1e-9) \
            & (self.single_time <= self.tok_lim[None, :, None] + 1e-9)
        self.tdone0 = f(tdone0) if tdone0 is not None else torch.zeros(B, K, device=dev)
        self.fixed = torch.where(types == 1, torch.tensor(SABS_FIX, device=dev),
                                 torch.where(types == 2, torch.tensor(DABS_FIX, device=dev), torch.tensor(0.0, device=dev))).sum(1)
        self.coverable = self.single_ok.any(1)                            # (B,n) every target must be coverable

    def expand_idx(self):
        return torch.arange(self.B, device=self.dev).repeat_interleave(self.N)


class State:
    def __init__(self, bt, force=None):
        self.bt = bt; B, N, n, K = bt.B, bt.N, bt.n, bt.K; dev = bt.dev
        R = B * N; self.R = R
        self.inst = bt.expand_idx(); self.ar = torch.arange(R, device=dev)
        self.visited = torch.zeros(R, n, dtype=torch.bool, device=dev)
        self.active = torch.full((R,), -1, dtype=torch.long, device=dev)
        self.last = torch.zeros(R, dtype=torch.long, device=dev)
        self.Lopen = torch.zeros(R, device=dev); self.m = torch.zeros(R, device=dev)
        self.Tdone = bt.tdone0[self.inst].clone()
        self.travel = torch.zeros(R, device=dev)
        self.need_t = torch.zeros(R, dtype=torch.bool, device=dev)
        self.done = torch.zeros(R, dtype=torch.bool, device=dev)
        self.fail = ~bt.coverable[self.inst].all(1)
        self.done |= self.fail
        self.force = force                                                # (R,) forced first target or None
        self.t = 0

    def mask(self):
        bt = self.bt; n = bt.n; I = self.inst; ar = self.ar
        has = self.active >= 0
        a = self.active.clamp(min=0)
        stn = n + bt.tok_st[a]
        d_last = bt.D[I, self.last, :n]                                   # (R,n)
        d_back = bt.D[I, stn, :n]
        L = self.Lopen[:, None] + d_last + d_back
        capr = bt.capr[I, a]
        e_ok = L / SPEED * FE + E_T * (self.m[:, None] + 1) <= capr[:, None] + 1e-9
        lim = bt.tok_lim[a]
        t_ok = self.Tdone[ar, a][:, None] + L / SPEED + S_T * (self.m[:, None] + 1) <= lim[:, None] + 1e-9
        cov = bt.cover[I, a]
        mt = has[:, None] & ~self.visited & cov & e_ok & t_ok
        Tk = self.Tdone.clone()
        cur_t = (self.Lopen + bt.D[I, self.last, stn]) / SPEED + S_T * self.m
        Tk[ar, a] = Tk[ar, a] + torch.where(has, cur_t, torch.zeros_like(cur_t))
        ok_t = bt.single_ok[I] & ~self.visited[:, None, :] & (Tk[:, :, None] + bt.single_time[I] <= bt.tok_lim[None, :, None] + 1e-9)
        if self.force is not None and self.t == 0:
            ok_t = ok_t & (torch.arange(n, device=bt.dev)[None, None, :] == self.force[:, None, None])
        mk = ok_t.any(-1) & ~self.need_t[:, None]
        if self.force is not None and self.t == 1:
            mt = mt & (torch.arange(n, device=bt.dev)[None, :] == self.force[:, None])
        m = torch.cat([mt, mk], 1)
        m[self.done] = False; m[self.done, 0] = True
        return m

    def _close(self, idx):
        if idx.numel() == 0:
            return
        bt = self.bt; a = self.active[idx]; I = self.inst[idx]
        stn = bt.n + bt.tok_st[a]
        L = self.Lopen[idx] + bt.D[I, self.last[idx], stn]
        self.Tdone[idx, a] += L / SPEED + S_T * self.m[idx]
        self.travel[idx] += L / SPEED

    def step(self, act):
        bt = self.bt; n = bt.n; live = ~self.done
        it = ((act < n) & live).nonzero().squeeze(1)
        if it.numel():
            t = act[it]; I = self.inst[it]
            self.Lopen[it] += bt.D[I, self.last[it], t]
            self.m[it] += 1; self.last[it] = t; self.visited[it, t] = True; self.need_t[it] = False
        ik = ((act >= n) & live).nonzero().squeeze(1)
        if ik.numel():
            self._close(ik[(self.active[ik] >= 0) & (self.m[ik] > 0)])
            k = act[ik] - n
            self.active[ik] = k; self.last[ik] = n + bt.tok_st[k]; self.Lopen[ik] = 0; self.m[ik] = 0; self.need_t[ik] = True
        fin = live & self.visited.all(1)
        fi = fin.nonzero().squeeze(1)
        self._close(fi[self.m[fi] > 0]); self.m[fi] = 0
        self.done |= fin
        self.t += 1

    def finish_fail(self, stuck):
        self.fail |= stuck; self.done |= stuck

    def objective(self, kappa=0.0, fail_pen=1e4):
        """route cost (flight+service time cost), full plan cost (incl. fixed), makespan proxy (max drone duty)."""
        bt = self.bt; I = self.inst
        route = TIME_COST * (self.travel + S_T * bt.n)
        cost = bt.fixed[I] + route
        mk = (self.Tdone - bt.tdone0[I]).max(1).values
        F = route + kappa * mk + self.fail.float() * fail_pen
        return F, cost, mk


def decode_actions(acts, n, ns, types):
    """acts: list of ints (-1 = padding). Returns routes[s] = [[large trips],[small trips]] as target indices."""
    routes = [[[], []] for _ in range(ns)]
    cur = None
    for a in acts:
        a = int(a)
        if a < 0:
            break
        if a < n:
            cur.append(a)
        else:
            k = a - n; s, ty = divmod(k, 3)
            cur = []; routes[s][0 if ty == 1 else 1].append(cur)      # DABS-large -> drone slot 0, small drones -> slot 1
    for s in range(ns):
        for d in range(2):
            routes[s][d] = [t for t in routes[s][d] if t]
    return routes
