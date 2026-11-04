"""[rl_rt copy of rl_v3/rlv3/search4.py; adds init_sol (warm start) and mk_w_override]
Best-of-M candidate search engine (rl_v3).

Same engine/operators/acceptance as morl2 carl.search.solve, except:
  * each step the operator (op, intensity) is chosen by the NoRL phase schedule;
  * G candidate moves are generated for that operator; a *proposer* picks M of
    them; all M are repaired by the native kernel; the best (lowest F_lambda) one
    goes to the SA acceptance test (slot 4 keeps the running best candidate).
  * NoRL proposer = first M generated (i.e. G=M, heuristic generator only).
Wall-clock budget covers everything (generation, features, inference, repair).
"""
import math, random, time
import numpy as np
import sys; sys.path.insert(0, "/workspace/rl_v3"); sys.path.insert(0, "/workspace/rl_v3/engine")
from lrphsd import fidelity_ops_v5 as ops
from lrphsd.evaluator import evaluate
from lrphsd.greedy import build as greedy_build
from carl.core import Coverage, Mirror, fixed_cost
from carl.kernel import CAEngine, reset_library
from carl.neighborhood import Context, apply_move, generate
from carl.state import action_mask
from carl.controllers import ScheduledPolicy, IDX
from carl.actions import N_ACTIONS, N_OPERATORS, OPERATOR_FAMILY, OPERATOR_INTENSITIES
from carl.search import reference_point, makespan, bottleneck_share, _clone_solution
from rlv3.feats import StepCache, cand_feats, N_FEAT
import carl.state as _state

_FEAT_LEN = len(_state.FEATURE_NAMES) if hasattr(_state, 'FEATURE_NAMES') else 128

class Sched(ScheduledPolicy):
    pass

class FirstM:
    """NoRL proposer: the heuristic generator's own samples."""
    name = 'heur'
    needs_feats = False
    def pick(self, feats, M, glob):
        return list(range(min(M, len(feats)))), None

def solve4(ins, proposer, seed=0, seconds=6.0, M=4, G=4, lam=0.0, reserve=0.0,
           temp0_factor=0.01, temp_end_factor=1e-3, max_steps=10**7,
           log_groups=False, log_every=1, risk=0.0, vclock=None, init_sol=None, mk_w_override=None):
    nominal_ins = ins
    if reserve and reserve > 0:
        from dataclasses import replace as _r
        from lrphsd.problem import Instance
        p = ins.params
        dp = _r(p, small_battery=p.small_battery / (1 + reserve), large_battery=p.large_battery / (1 + reserve))
        ins = Instance(ins.name, ins.targets, ins.stations, ins.sha256, dp)
    clock = vclock.perf_counter if vclock else time.perf_counter
    wall0 = clock()
    ops.prepare(ins); reset_library(); eng = CAEngine(ins)
    rng = random.Random(seed * 1000003 + 17)
    sol = _clone_solution(init_sol if init_sol is not None else greedy_build(ins)); eng.load(0, sol)
    audit0 = evaluate(ins, sol)
    if not audit0['feasible']:
        raise ValueError('initial infeasible')
    types = list(sol['station_types'])
    init_cost = audit0['cost']; init_mk = makespan(eng, 0, types)
    ref = reference_point(getattr(nominal_ins, 'name', ''))
    mk_w = float(lam) * ((ref[0] / ref[1]) if ref else (init_cost / max(init_mk, 1e-9)))
    if mk_w_override is not None: mk_w = mk_w_override
    obj = lambda c, m: c + mk_w * m
    cur_cost = init_cost; cur_mk = init_mk; cur_obj = obj(init_cost, init_mk)
    init_obj = cur_obj; best_obj = cur_obj; best_cost = init_cost
    archive = [(init_cost, init_mk)]
    eng.clone(0, 2)
    coverage = Coverage(ins); mirror = Mirror(ins, sol)
    ctx = Context(ins, eng, mirror, coverage, rng, cross_exchange=False)
    ctx.cost = cur_cost; ctx.best_cost = best_cost; ctx.route_cost = eng.cost(0)
    T0 = temp0_factor * init_obj; Tend = temp_end_factor * init_obj
    ctrl = Sched(); ctrl.begin(ins, seed)
    feat = np.zeros(_FEAT_LEN, dtype=np.float32)
    stagnation = 0; step = 0; evals = 0
    groups = []
    anytime = {}
    cps = (0.05, 0.1, 0.25, 0.5, 1.0)
    while step < max_steps:
        elapsed = clock() - wall0
        if elapsed >= seconds:
            break
        frac = elapsed / seconds
        for c in cps:
            if c not in anytime and frac >= c: anytime[c] = best_obj
        T = T0 * (Tend / T0) ** frac
        if stagnation > 300:
            T = max(T, 0.01 * init_obj)
        feat[IDX['budget_used']] = frac
        mask = action_mask(ctx)
        if not mask.any():
            break
        a = ctrl.act(feat, mask, step); op, it = divmod(int(a), 3)
        cands = []
        tp = hasattr(proposer, 'step_begin')
        if tp:
            from . import tpolicy as _tp
            _tp.ACTIVE = proposer
            proposer.step_begin(ctx, op, it, frac, T, init_obj, stagnation, cur_obj, best_obj)
        cidx = []
        for g_ in range(G):
            if tp: proposer.cand_begin(g_)
            mv = generate(ctx, op, it)
            if mv is not None:
                cands.append(mv); cidx.append(g_)
        if tp: _tp.ACTIVE = None
        best_j = None; bv = math.inf; bc = bm = None; btypes = None
        vals = None; fx = None; info = None; picked = []
        if cands:
            if proposer.needs_feats or log_groups:
                cache = StepCache(ctx)
                btl_share = bottleneck_share(eng, 0, types)
                glob = np.array([lam, reserve, risk, frac, T / init_obj * 100, math.log1p(stagnation) / 8,
                                 (cur_obj / best_obj - 1) * 100, btl_share, ctx.nst / 10, len(ins.targets) / 100], dtype=np.float32)
                fx = np.stack([cand_feats(cache, mv, op, it, glob) for mv in cands])
            picked, info = proposer.pick(fx, M, None) if proposer.needs_feats else (list(range(min(M, len(cands)))), None)
            vals = []
            for j in picked:
                mv = cands[j]
                nt_ = apply_move(eng, mv, types, ins); evals += 1
                v = math.inf; c = m_ = None
                if nt_ is not None and not eng.same(0, 1):
                    c = eng.cost(1) + fixed_cost(ins, nt_)
                    m_ = makespan(eng, 1, nt_) if mk_w > 0 else 0.0
                    v = obj(c, m_)
                vals.append(v)
                if v < bv:
                    bv = v; best_j = j; bc = c; bm = m_; btypes = nt_
                    if len(picked) > 1: eng.clone(1, 4)
            if log_groups and len(picked) >= 2 and (step % log_every == 0):
                groups.append((fx[picked], np.array([x if x < math.inf else np.nan for x in vals], dtype=np.float64), cur_obj, op))
            if hasattr(proposer, 'observe') and info is not None:
                proposer.observe(info, picked, vals, cur_obj)
            if tp:
                proposer.step_end([cidx[j] for j in picked], vals, cur_obj)
        accepted = False; best_flag = False
        if best_j is not None and clock() - wall0 < seconds:
            if bv < cur_obj or rng.random() < math.exp((cur_obj - bv) / max(T, 1e-9)):
                accepted = True
        if accepted:
            if len(picked) > 1: eng.clone(4, 0)
            else: eng.clone(1, 0)
            types = btypes; cur_cost = bc; cur_mk = bm if mk_w > 0 else makespan(eng, 0, types); cur_obj = bv
            if not any(c <= cur_cost and m <= cur_mk for c, m in archive):
                archive = [(c, m) for c, m in archive if not (cur_cost <= c and cur_mk <= m)]
                archive.append((cur_cost, cur_mk))
            if bv < best_obj:
                eng.clone(0, 2); best_obj = bv; best_cost = bc; best_flag = True
            mirror.update(eng.export(0))
            ctx = Context(ins, eng, mirror, coverage, rng, cross_exchange=False)
            ctx.cost = cur_cost; ctx.best_cost = best_cost; ctx.route_cost = eng.cost(0)
        stagnation = 0 if best_flag else stagnation + 1
        step += 1
    for c in cps:
        if c not in anytime: anytime[c] = best_obj
    final = eng.export(2); final_mk = makespan(eng, 2, final['station_types']); eng.free()
    audit = evaluate(nominal_ins, final)
    return dict(objective=best_obj, cost=audit['cost'], feasible=audit['feasible'], makespan=final_mk,
                steps=step, evals=evals, archive=sorted(archive), anytime={str(k): v for k, v in anytime.items()},
                init_obj=init_obj, mk_w=mk_w, solution=final, groups=groups)
