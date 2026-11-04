"""Segment-level Dynamic Algorithm Configuration (DAC) ALNS engine (rl_ppo).
Same engine / operators / repair / evaluator as rl_v3 search4 (NoRL best-of-M, cooled SA),
but the run is split into S equal-budget segments; at each segment boundary a controller
chooses a configuration  cfg = (T_level, M, fam, inten, restart).
Budget is measured in deterministic work units:  units = steps*C_STEP + evals*C_EVAL
(calibrated to wall-clock, see calib.py) so that RL training/eval is noise-free w.r.t.
machine load and every method gets exactly the same compute; controller inference is
charged as well (C_INFER per decision)."""
import sys, math, random, time
sys.path.insert(0, '/workspace/rl_v3/engine')
import numpy as np
from lrphsd import fidelity_ops_v5 as ops
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build as greedy_build
from carl.core import Coverage, Mirror, fixed_cost
from carl.kernel import CAEngine, reset_library
from carl.neighborhood import Context, apply_move, generate
from carl.state import action_mask
from carl.controllers import ScheduledPolicy
from carl.actions import N_ACTIONS, N_OPERATORS, OPERATOR_FAMILY, OPERATOR_INTENSITIES
from carl.search import reference_point, makespan, _clone_solution

C_STEP = 1.0; C_EVAL = 1.0; C_INFER = 2.0   # overwritten by calib
T_LEVELS = (0.03, 0.01, 0.003, 0.0005)       # x init_obj, segment start; decays x0.5 within segment
M_LEVELS = (1, 2, 4, 8)
FAM = ((0.35, 0.25, 0.15, 0.25), (0.08, 0.12, 0.68, 0.12))   # struct-heavy / route-heavy (NoRL early/late)
INTEN = ((0.55, 0.30, 0.15), (0.30, 0.40, 0.30), (0.10, 0.30, 0.60))
NHEAD = (len(T_LEVELS), len(M_LEVELS), len(FAM), len(INTEN), 2)
OPW = ScheduledPolicy.OPERATOR_W

def _act(rng, mask, fam, inten):
    w = np.zeros(N_ACTIONS)
    for op in range(N_OPERATORS):
        f = OPERATOR_FAMILY[op]
        for it in OPERATOR_INTENSITIES[op]:
            a = op * 3 + it
            if mask[a]: w[a] = FAM[fam][f] * OPW[op] * INTEN[inten][it]
    s = w.sum()
    if s <= 0: return int(np.flatnonzero(mask)[0])
    return int(rng.choices(range(N_ACTIONS), weights=w.tolist(), k=1)[0])

class Static:
    """NoRL: the same cfg in every segment, or a fixed per-segment schedule list."""
    def __init__(self, cfg): self.cfg = cfg
    def __call__(self, obs, k, S):
        c = self.cfg
        return c[min(k * len(c) // S, len(c) - 1)] if isinstance(c[0], (tuple, list)) else c

NOBS = 16
def obs_vec(lam, n_t, n_s, budget, k, S, cur, best, init, seg_imp, acc_rate, imp_rate, stag, last_cfg, steps_per_unit, best_prev):
    return np.array([lam, math.log1p(lam), n_t / 100, n_s / 10, math.log(budget) / 10, k / S,
                     (cur / best - 1) * 100, (init / best - 1) * 10, seg_imp * 100, acc_rate, imp_rate * 10,
                     math.log1p(stag) / 8, last_cfg[0] / 3, last_cfg[1] / 3, (best_prev / best - 1) * 100,
                     steps_per_unit], dtype=np.float32)

def solve_dac(ins, controller, budget, seed=0, lam=0.0, reserve=0.0, S=10, Tend_frac=0.5,
              record=False, wall=None):
    """budget: work units. controller(obs, k, S) -> cfg tuple (ti, mi, fam, inten, restart).
    wall: if given (seconds), use real wall clock instead of work units (final timing check)."""
    nominal = ins
    if reserve and reserve > 0:
        from dataclasses import replace as _r
        from lrphsd.problem import Instance
        p = ins.params
        dp = _r(p, small_battery=p.small_battery / (1 + reserve), large_battery=p.large_battery / (1 + reserve))
        ins = Instance(ins.name, ins.targets, ins.stations, ins.sha256, dp)
    t0 = time.perf_counter()
    ops.prepare(ins); reset_library(); eng = CAEngine(ins)
    rng = random.Random(seed * 1000003 + 17); arng = random.Random(seed * 7919 + 3)
    sol = _clone_solution(greedy_build(ins)); eng.load(0, sol)
    a0 = evaluate(ins, sol); assert a0['feasible']
    types = list(sol['station_types'])
    init_cost = a0['cost']; init_mk = makespan(eng, 0, types)
    ref = reference_point(getattr(nominal, 'name', ''))
    mk_w = float(lam) * ((ref[0] / ref[1]) if ref else (init_cost / max(init_mk, 1e-9)))
    obj = lambda c, m: c + mk_w * m
    cur_cost, cur_mk = init_cost, init_mk; cur_obj = obj(cur_cost, cur_mk)
    init_obj = best_obj = cur_obj; best_cost = init_cost; best_mk = init_mk; best_types = list(types)
    archive = [(init_cost, init_mk)]
    eng.clone(0, 2)
    coverage = Coverage(ins); mirror = Mirror(ins, sol)
    def mkctx():
        c = Context(ins, eng, mirror, coverage, rng, cross_exchange=False)
        c.cost = cur_cost; c.best_cost = best_cost; c.route_cost = eng.cost(0); return c
    ctx = mkctx()
    used = 0.0; step = 0; evals = 0; stag = 0
    seg_len = budget / S
    last_cfg = (1, 2, 0, 1, 0); traj = []; anytime = []
    seg_best0 = best_obj; best_prev = best_obj; acc = 0; imp = 0; nst = 0
    n_t = len(ins.targets); n_s = len(ins.stations)
    def spent():
        return (time.perf_counter() - t0) * 1000.0 if wall else used
    tot = wall * 1000.0 if wall else budget
    seg_len = tot / S
    for k in range(S):
        o = obs_vec(lam, n_t, n_s, budget, k, S, cur_obj, best_obj, init_obj,
                    (seg_best0 - best_obj) / init_obj, acc / max(nst, 1), imp / max(nst, 1), stag, last_cfg,
                    nst / seg_len, best_prev)
        best_prev = seg_best0 = best_obj
        cfg = controller(o, k, S); used += C_INFER
        ti, mi, fam, inten, rst = cfg[:5]; tef = cfg[5] if len(cfg) > 5 else Tend_frac
        last_cfg = (ti if isinstance(ti, int) else 1, mi, fam, inten, rst)
        if record: traj.append((o, cfg))
        if rst and cur_obj > best_obj + 1e-9:
            eng.clone(2, 0); types = list(best_types); cur_cost, cur_mk, cur_obj = best_cost, best_mk, best_obj
            mirror.update(eng.export(0)); ctx = mkctx()
        M = M_LEVELS[mi]; Ts = (T_LEVELS[ti] if isinstance(ti, int) else ti) * init_obj; Te = Ts * tef
        seg_end = (k + 1) * seg_len; seg_start = spent()
        acc = imp = nst = 0
        while True:
            sp = spent()
            if sp >= seg_end: break
            fr = (sp - seg_start) / max(seg_end - seg_start, 1e-9)
            T = Ts * (Te / Ts) ** min(fr, 1.0)
            mask = action_mask(ctx)
            if not mask.any(): break
            a = _act(arng, mask, fam, inten); op, it = divmod(a, 3)
            bv = math.inf; bc = bm = btypes = None; nm = 0
            for g in range(M):
                mv = generate(ctx, op, it)
                if mv is None: continue
                nt_ = apply_move(eng, mv, types, ins); evals += 1; nm += 1
                if nt_ is not None and not eng.same(0, 1):
                    c = eng.cost(1) + fixed_cost(ins, nt_)
                    m_ = makespan(eng, 1, nt_) if mk_w > 0 else 0.0
                    v = obj(c, m_)
                    if v < bv:
                        bv, bc, bm, btypes = v, c, m_, nt_
                        if M > 1: eng.clone(1, 4)
            used += C_STEP + C_EVAL * nm; step += 1; nst += 1
            best_flag = False
            if btypes is not None and (bv < cur_obj or rng.random() < math.exp((cur_obj - bv) / max(T, 1e-12))):
                eng.clone(4 if M > 1 else 1, 0)
                types = btypes; cur_cost = bc; cur_mk = bm if mk_w > 0 else makespan(eng, 0, types); cur_obj = bv; acc += 1
                if not any(c <= cur_cost and m <= cur_mk for c, m in archive):
                    archive = [(c, m) for c, m in archive if not (cur_cost <= c and cur_mk <= m)]
                    archive.append((cur_cost, cur_mk))
                if bv < best_obj - 1e-9:
                    eng.clone(0, 2); best_obj = bv; best_cost = bc; best_mk = cur_mk; best_types = list(types)
                    best_flag = True; imp += 1
                mirror.update(eng.export(0)); ctx = mkctx()
            stag = 0 if best_flag else stag + 1
        anytime.append(best_obj)
    final = eng.export(2); fmk = makespan(eng, 2, final['station_types']); eng.free()
    au = evaluate(nominal, final)
    return dict(objective=best_obj, cost=au['cost'], feasible=au['feasible'], makespan=fmk, steps=step,
                evals=evals, init_obj=init_obj, mk_w=mk_w, anytime=anytime, traj=traj,
                archive=sorted(archive), wall=time.perf_counter() - t0, units=used)
