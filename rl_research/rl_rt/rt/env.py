"""Batched autoregressive construction environment (torch).
Action space per step: [targets (n) | tokens (K=3*ns)].
 - choosing a token closes the current trip (if non-empty) and starts a new trip of that drone
   (opening its station with the token's type if needed: SABS or DABS, mutually exclusive);
 - choosing a target appends it to the current trip.
Masks enforce coverage radius, per-trip battery (with reserve r: capacity/(1+r)) incl. return,
cumulative drone working time, SABS/DABS exclusivity."""
import torch, numpy as np
from .inst import *

class Batch:
    def __init__(self, tgs, sts, kappa, reserve, N, device='cpu'):
        """tgs: list of (n,2) arrays, sts: list of (ns,2); all same n, ns. kappa, reserve: (B,) arrays."""
        B = len(tgs); n = tgs[0].shape[0]; ns = sts[0].shape[0]; K = 3 * ns; V = n + ns
        self.B, self.n, self.ns, self.K, self.V, self.N = B, n, ns, K, V, N
        xy = torch.tensor(np.stack([np.concatenate([t, s]) for t, s in zip(tgs, sts)]), dtype=torch.float32)  # (B,V,2)
        self.xy = xy
        self.D = torch.cdist(xy, xy)  # metres
        self.kappa = torch.tensor(kappa, dtype=torch.float32); self.reserve = torch.tensor(reserve, dtype=torch.float32)
        tok_st = torch.arange(ns).repeat_interleave(3); tok_ty = torch.arange(3).repeat(ns)
        self.tok_st, self.tok_ty = tok_st, tok_ty
        self.tok_cap = torch.tensor(TOK_CAP, dtype=torch.float32)[tok_ty]
        self.tok_rad = torch.tensor(TOK_RAD, dtype=torch.float32)[tok_ty]
        self.tok_lim = torch.tensor(TOK_LIM, dtype=torch.float32)[tok_ty]
        dst = self.D[:, n:, :n]  # (B,ns,n) station->target
        dk = dst[:, tok_st]       # (B,K,n)
        self.dk = dk
        capr = self.tok_cap[None, :, None] / (1 + self.reserve[:, None, None])
        self.cover = dk <= self.tok_rad[None, :, None] + 1e-6
        self.single_time = 2 * dk / SPEED + S_T
        self.single_ok = self.cover & (2 * dk / SPEED * FE + E_T <= capr + 1e-9) & (self.single_time <= self.tok_lim[None, :, None] + 1e-9)
        self.capr = (self.tok_cap[None, :] / (1 + self.reserve[:, None]))  # (B,K)
        self.cov5 = dst <= LR + 1e-6                     # (B,ns,n)
        self.band = self.cov5 & (dst > SR + 1e-6)        # targets lost if station becomes SABS

class State:
    def __init__(self, bt):
        self.bt = bt; B, N, n, K, ns = bt.B, bt.N, bt.n, bt.K, bt.ns
        R = B * N; self.R = R
        self.inst = torch.arange(B).repeat_interleave(N)
        self.visited = torch.zeros(R, n, dtype=torch.bool)
        self.active = torch.full((R,), -1, dtype=torch.long)
        self.last = torch.zeros(R, dtype=torch.long)
        self.Lopen = torch.zeros(R); self.m = torch.zeros(R)
        self.Tdone = torch.zeros(R, K)
        self.stype = torch.zeros(R, ns, dtype=torch.long)
        self.travel = torch.zeros(R); self.fixed = torch.zeros(R)
        self.need_t = torch.zeros(R, dtype=torch.bool)
        self.done = torch.zeros(R, dtype=torch.bool); self.fail = torch.zeros(R, dtype=torch.bool)
        self.ar = torch.arange(R)
    def _active_station_node(self):
        bt = self.bt; a = self.active.clamp(min=0)
        return bt.n + bt.tok_st[a]
    def mask(self):
        bt = self.bt; R = self.R; n = bt.n; ar = self.ar; I = self.inst
        a = self.active.clamp(min=0); has = self.active >= 0
        stn = self._active_station_node()
        d_last = bt.D[I, self.last, :n]          # (R,n)
        d_back = bt.D[I, stn, :n]                # (R,n)
        L = self.Lopen[:, None] + d_last + d_back
        capr = bt.capr[I, a]
        e_ok = L / SPEED * FE + E_T * (self.m[:, None] + 1) <= capr[:, None] + 1e-9
        lim = bt.tok_lim[a]
        t_ok = self.Tdone[ar, a][:, None] + L / SPEED + S_T * (self.m[:, None] + 1) <= lim[:, None] + 1e-9
        cov = bt.cover[I, a]                     # (R,n)
        mt = has[:, None] & ~self.visited & cov & e_ok & t_ok
        # tokens
        Tk = self.Tdone.clone()
        cur_t = (self.Lopen + bt.D[I, self.last, stn]) / SPEED + S_T * self.m
        Tk[ar, a] = Tk[ar, a] + torch.where(has, cur_t, torch.zeros_like(cur_t))
        ok_t = bt.single_ok[I] & ~self.visited[:, None, :] & (Tk[:, :, None] + bt.single_time[I] <= bt.tok_lim[None, :, None] + 1e-9)
        tok_any = ok_t.any(-1)                   # (R,K)
        st = self.stype[:, bt.tok_st]            # (R,K) station state
        kind = torch.tensor(TOK_KIND)[bt.tok_ty][None, :]
        compat = (st == 0) | (st == kind)
        # opening a SABS must not strand an unvisited target that only this station could still cover
        allowD = (self.stype != 1)                                    # (R,ns)
        cov5 = bt.cov5[I] & allowD[:, :, None] & ~self.visited[:, None, :]
        cnt = cov5.sum(1)                                             # (R,n)
        lose = (bt.band[I] & ~self.visited[:, None, :] & (cnt[:, None, :] <= 1) & cov5).any(-1)  # (R,ns)
        sabs_bad = lose & (self.stype == 0)
        bad_tok = torch.zeros_like(compat)
        bad_tok[:, 0::3] = sabs_bad
        mk = tok_any & compat & ~bad_tok & ~self.need_t[:, None]
        m = torch.cat([mt, mk], 1)
        m[self.done] = False; m[self.done, 0] = True  # dummy action for finished rollouts
        return m
    def _close(self, idx):
        if idx.numel() == 0: return
        bt = self.bt; a = self.active[idx]; I = self.inst[idx]
        stn = bt.n + bt.tok_st[a]
        back = bt.D[I, self.last[idx], stn]
        L = self.Lopen[idx] + back
        self.Tdone[idx, a] += L / SPEED + S_T * self.m[idx]
        self.travel[idx] += L / SPEED
    def step(self, act):
        bt = self.bt; n = bt.n; live = ~self.done
        is_t = (act < n) & live; is_k = (act >= n) & live
        # targets
        it = is_t.nonzero().squeeze(1)
        if it.numel():
            t = act[it]; I = self.inst[it]
            self.Lopen[it] += bt.D[I, self.last[it], t]
            self.m[it] += 1; self.last[it] = t; self.visited[it, t] = True; self.need_t[it] = False
        # tokens
        ik = is_k.nonzero().squeeze(1)
        if ik.numel():
            close = ik[(self.active[ik] >= 0) & (self.m[ik] > 0)]
            self._close(close)
            k = act[ik] - n
            self.active[ik] = k; self.last[ik] = n + bt.tok_st[k]; self.Lopen[ik] = 0; self.m[ik] = 0; self.need_t[ik] = True
            s = bt.tok_st[k]; kind = torch.tensor(TOK_KIND)[bt.tok_ty[k]]
            new = self.stype[ik, s] == 0
            self.stype[ik[new], s[new]] = kind[new]
            self.fixed[ik[new]] += torch.where(kind[new] == 1, torch.tensor(SABS_FIX), torch.tensor(DABS_FIX))
        fin = live & self.visited.all(1)
        fi = fin.nonzero().squeeze(1)
        self._close(fi[self.m[fi] > 0]); self.m[fi] = 0
        self.done |= fin
    def finish_fail(self, stuck):
        self.fail |= stuck; self.done |= stuck
    def objective(self):
        bt = self.bt; I = self.inst
        cost = self.fixed + TIME_COST * (self.travel + S_T * bt.n)
        mk = self.Tdone.max(1).values
        F = cost + bt.kappa[I] * mk + self.fail.float() * 1e4
        return F, cost, mk
