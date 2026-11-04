"""Millisecond inference path: torch encoder (once per instance), numba-compiled decoder.
Exactly the same policy / masks as rt.env + rt.model (checked by rt/check_fast.py)."""
import sys, math, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt/pylib')
import numba as nb
from .inst import SPEED, FE, E_T, S_T, TOK_KIND, SABS_FIX, DABS_FIX, TIME_COST, SR, LR, TOK_CAP, TOK_RAD, TOK_LIM, SCALE
from .env import Batch

@nb.njit(cache=True, fastmath=False)
def decode(D, n, ns, tok_st, kindk, capr, lim, cover, stime, sok, cov5, band,
           h, hk, hv, hl, gm, none, Wq, bq, Wkd, bkd, Wo, bo, wa, wl, kappa, greedy, seed):
    K = 3 * ns; d = h.shape[1]; sq = math.sqrt(d)
    if seed >= 0: np.random.seed(seed)
    visited = np.zeros(n, np.bool_); stype = np.zeros(ns, np.int64); Tdone = np.zeros(K)
    active = -1; last = 0; Lopen = 0.0; m = 0; travel = 0.0; fixed = 0.0; need_t = False
    nvis = 0; fail = False
    acts = np.full(4 * n + 10, -1, np.int64)
    V = n + K
    mask = np.zeros(V, np.bool_); x = np.zeros(3 * d + 7); att = np.zeros(V); dk = np.zeros((K, d))
    Tk = np.zeros(K); cnt = np.zeros(n, np.int64); sbad = np.zeros(ns, np.bool_)
    for step in range(4 * n + 10):
        a = active if active >= 0 else 0; has = active >= 0; stn = n + tok_st[a]
        anym = False
        # ---- target mask
        for j in range(n):
            ok = False
            if has and (not visited[j]) and cover[a, j]:
                L = Lopen + D[last, j] + D[stn, j]
                if L / SPEED * FE + E_T * (m + 1) <= capr[a] + 1e-9 and Tdone[a] + L / SPEED + S_T * (m + 1) <= lim[a] + 1e-9:
                    ok = True
            mask[j] = ok; anym = anym or ok
        # ---- token mask
        for k in range(K): Tk[k] = Tdone[k]
        if has: Tk[a] += (Lopen + D[last, stn]) / SPEED + S_T * m
        for j in range(n):
            c = 0
            if not visited[j]:
                for s in range(ns):
                    if cov5[s, j] and stype[s] != 1: c += 1
            cnt[j] = c
        for s in range(ns):
            b = False
            if stype[s] == 0:
                for j in range(n):
                    if band[s, j] and (not visited[j]) and cov5[s, j] and cnt[j] <= 1:
                        b = True; break
            sbad[s] = b
        for k in range(K):
            ok = False
            s = tok_st[k]
            if (not need_t) and (stype[s] == 0 or stype[s] == kindk[k]) and not (k % 3 == 0 and sbad[s]):
                for j in range(n):
                    if sok[k, j] and (not visited[j]) and Tk[k] + stime[k, j] <= lim[k] + 1e-9:
                        ok = True; break
            mask[n + k] = ok; anym = anym or ok
        if not anym:
            fail = True; break
        # ---- query
        for i in range(d):
            x[i] = gm[i]
            th = h[n + a, i] if has else none[i]
            x[d + i] = th
            x[2 * d + i] = h[last, i] if last < n else th
        x[3 * d] = Lopen / 10000; x[3 * d + 1] = m / 4; x[3 * d + 2] = Tdone[a] / lim[a]; x[3 * d + 3] = capr[a]
        x[3 * d + 4] = nvis / n; x[3 * d + 5] = 1.0 if has else 0.0; x[3 * d + 6] = 1.0 if need_t else 0.0
        q = Wq @ x + bq
        for k in range(K):
            s = tok_st[k]
            f0 = Tdone[k] / lim[k]; f1 = 1.0 if stype[s] == 0 else 0.0; f2 = 1.0 if stype[s] == kindk[k] else 0.0; f3 = 1.0 if active == k else 0.0
            for i in range(d):
                dk[k, i] = bkd[i] + Wkd[i, 0] * f0 + Wkd[i, 1] * f1 + Wkd[i, 2] * f2 + Wkd[i, 3] * f3
        mx = -1e30
        for j in range(V):
            if mask[j]:
                v = 0.0
                for i in range(d): v += q[i] * hk[j, i]
                if j >= n:
                    for i in range(d): v += q[i] * dk[j - n, i]
                v /= sq
                if j < n: v += wa[0] * D[last, j] / 5000.0 + wa[1] * D[stn, j] / 5000.0
                else: v += wa[2] * D[last, n + tok_st[j - n]] / 5000.0
                att[j] = v
                if v > mx: mx = v
        z = 0.0
        for j in range(V):
            if mask[j]:
                att[j] = math.exp(att[j] - mx); z += att[j]
        g = np.zeros(d)
        for j in range(V):
            if mask[j]:
                w = att[j] / z
                for i in range(d): g[i] += w * hv[j, i]
        q2 = Wo @ g + bo
        best = -1; bv = -1e30
        for j in range(V):
            if mask[j]:
                v = 0.0
                for i in range(d): v += q2[i] * hl[j, i]
                if j >= n:
                    for i in range(d): v += q2[i] * dk[j - n, i]
                v = 10.0 * math.tanh(v / sq)
                if j < n: v += wl[0] * D[last, j] / 5000.0 + wl[1] * D[stn, j] / 5000.0
                else: v += wl[2] * D[last, n + tok_st[j - n]] / 5000.0
                att[j] = v
                if v > bv: bv = v; best = j
        if not greedy:
            z = 0.0
            for j in range(V):
                if mask[j]: att[j] = math.exp(att[j] - bv); z += att[j]
            u = np.random.random() * z; acc = 0.0
            for j in range(V):
                if mask[j]:
                    acc += att[j]; best = j
                    if acc >= u: break
        act = best; acts[step] = act
        # ---- step
        if act < n:
            Lopen += D[last, act]; m += 1; last = act; visited[act] = True; nvis += 1; need_t = False
        else:
            k = act - n
            if has and m > 0:
                L = Lopen + D[last, stn]; Tdone[a] += L / SPEED + S_T * m; travel += L / SPEED
            active = k; s = tok_st[k]; last = n + s; Lopen = 0.0; m = 0; need_t = True
            if stype[s] == 0:
                stype[s] = kindk[k]; fixed += SABS_FIX if kindk[k] == 1 else DABS_FIX
        if nvis == n:
            if m > 0:
                a = active; stn = n + tok_st[a]
                L = Lopen + D[last, stn]; Tdone[a] += L / SPEED + S_T * m; travel += L / SPEED
            m = 0
            break
    cost = fixed + TIME_COST * (travel + S_T * n); mk = Tdone.max()
    F = cost + kappa * mk + (1e4 if fail else 0.0)
    return F, cost, mk, acts, fail

class Fast:
    def __init__(self, pol):
        self.pol = pol.eval(); P = lambda t: t.detach().double().numpy().copy()
        self.Wq, self.bq = P(pol.q.weight), P(pol.q.bias); self.Wkd, self.bkd = P(pol.k_dyn.weight), P(pol.k_dyn.bias)
        self.Wo, self.bo = P(pol.Wo.weight), P(pol.Wo.bias); self.none = P(pol.none); self.wa = P(pol.wa); self.wl = P(pol.wl)
    @torch.no_grad()
    def prep(self, copies, kappa, rsv):
        B = len(copies)
        bt = Batch([a for a, b in copies], [b for a, b in copies], np.full(B, kappa), np.full(B, rsv), N=1)
        self.pol.encode(bt)
        P = lambda t: t.double().numpy()
        out = []
        tok_st = bt.tok_st.numpy().astype(np.int64); kindk = TOK_KIND[bt.tok_ty.numpy()].astype(np.int64)
        lim = P(bt.tok_lim)
        for b in range(B):
            xy = np.concatenate(copies[b]).astype(np.float64)
            D = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
            n = copies[b][0].shape[0]; ns = copies[b][1].shape[0]
            dst = D[n:, :n]; dkk = dst[tok_st]
            capr = TOK_CAP[bt.tok_ty.numpy()] / (1 + rsv)
            rad = TOK_RAD[bt.tok_ty.numpy()]
            cover = dkk <= rad[:, None] + 1e-6
            stime = 2 * dkk / SPEED + S_T
            sok = cover & (2 * dkk / SPEED * FE + E_T <= capr[:, None] + 1e-9) & (stime <= lim[:, None] + 1e-9)
            cov5 = dst <= LR + 1e-6; band = cov5 & (dst > SR + 1e-6)
            out.append((D, n, ns, tok_st, kindk, capr, lim, cover, stime, sok, cov5, band,
                        P(self.pol.h[b]).copy(), P(self.pol.hk[b]).copy(), P(self.pol.hv[b]).copy(), P(self.pol.hl[b]).copy(),
                        P(self.pol.gm[b]).copy(), self.none, self.Wq, self.bq, self.Wkd, self.bkd, self.Wo, self.bo, self.wa, self.wl, float(kappa)))
        return out
    def solve(self, tg, st, kappa, rsv, mode='greedy', seed=0, deadline=None):
        """Returns (F, cost, mk, acts, fail, n_rollouts). deadline: perf_counter time to stop sampling (anytime)."""
        import time
        from .infer import _aug
        aug = mode.startswith('aug8')
        copies = _aug(tg, st) if aug else [(tg, st)]
        N = int(mode.split(':')[1]) if ':' in mode else 1
        greedy = mode in ('greedy', 'aug8')
        pre = self.prep(copies, kappa, rsv)
        best = None; cnt = 0
        for r in range(N if not greedy else 1):
            for b, args in enumerate(pre):
                F, c, mk, acts, fail = decode(*args, greedy, -1 if greedy else seed * 100003 + r * 17 + b)
                cnt += 1
                if best is None or F < best[0]: best = (F, c, mk, acts, fail)
                if deadline is not None and time.perf_counter() > deadline and best is not None: return best + (cnt,)
        return best + (cnt,)
