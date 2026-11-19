"""Development-only BC -> optional qualified RI -> IID REINFORCE with a
leave-one-out baseline. The policy emits physical task / RETURN / WAIT actions.

J is an explicit failure-penalized proxy, not the weather M_return/cap or emergency
high-priority on-time primary endpoint. All rollout failures remain in the loss.
RI is blocked unless a public-observation conditional sampler is independently
verified. There are no forced first actions and no POMO multi-start claim.
"""
import os, sys, json, time, argparse, math, random, hashlib
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rlcore.common import load_plans, progress, device, seed_all
from rlcore.scen import make_env, DEV_DAYS, TRAIN_DAY0
from rlcore import policies as PO
from rlcore.feat import featurize
from rlcore.agent import RLPolicy, ablate, action_log_probs, LEARNING_SCHEMA, ABLATIONS

_W = {}
_POOL = None
_FAILURE_SAVE = None


class PGDeadlineReached(TimeoutError):
    """The continuous PG phase window ended; finalize the last full update."""


class TotalBudgetExceeded(TimeoutError):
    """The all-stage budget ended; this run must fail."""


def remaining_budget(total_deadline, pg_deadline=None, now=None):
    """Check the hard budget first, including when both deadlines coincide."""
    now = time.monotonic() if now is None else now
    if now >= total_deadline:
        raise TotalBudgetExceeded("all-stage training wall budget exhausted")
    if pg_deadline is not None and now >= pg_deadline:
        raise PGDeadlineReached("continuous PG phase wall budget exhausted")
    return min(total_deadline, pg_deadline if pg_deadline is not None else total_deadline) - now


def dispatch_jobs(pool, fun, jobs, check, on_result=None, on_event=None):
    """Retain completed attempts while enforcing deadlines on pending work.

    AsyncResult.wait does not propagate a worker's own TimeoutError. A ready
    result is retrieved separately, so any worker exception remains a failure.
    """
    handles, results = {}, [None] * len(jobs)
    workers = list(getattr(pool, "_pool", ()))
    completed = 0

    def harvest():
        nonlocal completed
        if any(worker.exitcode is not None for worker in workers):
            raise RuntimeError("rollout worker process exited before dispatch completion")
        failure = None
        for index in list(handles):
            handle = handles[index]
            if not handle.ready():
                continue
            try:
                result = handle.get()
            except Exception as exc:
                if on_event:
                    on_event(dict(status="worker_error", job=index, error_type=type(exc).__name__, error=str(exc)))
                del handles[index]
                failure = failure or exc
                continue
            results[index] = result
            del handles[index]
            completed += 1
            if on_result:
                on_result(index, result)
        if failure is not None:
            raise failure

    try:
        for index, job in enumerate(jobs):
            check()
            handles[index] = pool.apply_async(fun, (job,))
        while handles:
            harvest()
            remaining = check()  # also reject results completing beyond the window
            if handles:
                next(iter(handles.values())).wait(timeout=min(remaining, 0.05))
        check()
    except (PGDeadlineReached, TotalBudgetExceeded) as exc:
        # A ready worker failure must not be relabelled as an ordinary deadline.
        harvest()
        if on_event:
            on_event(dict(status="deadline", budget="pg" if isinstance(exc, PGDeadlineReached) else "total",
                          completed=completed, issued=completed + len(handles), pending=sorted(handles)))
        raise
    return results


def commit_pg_update(check, step, rollback):
    """Only retain an optimizer update that fully finishes before both caps."""
    check()
    try:
        step()
        check()
    except BaseException:
        rollback()
        raise


def checkpoint_source(tag):
    if tag == "bc":
        return "bc"
    if tag == "init":
        return "initialization"
    if str(tag).startswith("ri"):
        return "ri"
    return "pg"


def is_fixed_weather(scen):
    return scen == "nowind" or scen.startswith("fixed_")


def development_days(scen, days):
    # Fixed weather has no stochastic day realization: count each map once.
    return list(days[:1] if is_fixed_weather(scen) else days)


def _attempt_summary(result):
    if isinstance(result, tuple) and len(result) == 2:
        return dict(n_labels=len(result[0]), result=result[1])
    if isinstance(result, list):
        return [dict({k: v for k, v in r.items() if k not in ("dec", "perst")},
                     n_decisions=len(r.get("dec", ()))) for r in result]
    return result


def _shutdown_pool():
    global _POOL
    if _POOL is not None:
        pool, _POOL = _POOL, None
        pool.terminate()
        pool.join()


def eligible_result(result, scen=None):
    physical = bool(np.isfinite(result.get("J", np.nan)) and result.get("physically_feasible")
                    and result.get("all_returned") and not result.get("failed"))
    if scen and scen.startswith("emerg_"):
        # The simulator horizon can leave urgent requests unserved. Keep every
        # release in the primary denominator; require full routine work/return.
        total, done = result.get("routine_total", 0), result.get("routine_done", -1)
        return physical and total > 0 and total == done
    complete = physical and bool(result.get("complete_strict")) and not result.get("timeout")
    if scen and is_fixed_weather(scen):
        cost, cap = result.get("cost", np.nan), result.get("author_cost_cap", np.nan)
        return bool(complete and np.isfinite(result.get("M_return", np.nan))
                    and isinstance(cap, (int, float, np.integer, np.floating))
                    and np.isfinite(cost) and np.isfinite(cap) and cap >= 0 and cost <= cap + 1e-7)
    return complete


def development_score(results, scen):
    """Minimized selector: fixed A uses M_return; B pools all urgent releases."""
    if scen.startswith("emerg_"):
        denominator = sum(r["high_total"] for r in results)
        if not denominator:
            return None
        return -sum(r["high_on_time"] for r in results) / denominator
    return float(np.mean([r["M_return"] if is_fixed_weather(scen) else r["J"] for r in results]))


def loo_advantages(costs, scale=1000.0):
    """Detached cost advantages for IID policies sharing exogenous randomness.

    Other trajectories' mean is independent of this trajectory's policy draws,
    conditional on the common scenario. No realized sample standard deviation.
    """
    x = np.asarray(costs, dtype=np.float64)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("LOO requires >=2 finite rollout costs")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("reward_scale must be finite and positive")
    return -(x - (x.sum() - x) / (len(x) - 1)) / scale


def pg_samples(groups, scale):
    samples, advs = [], []
    episodes = sum(len(g) for g in groups)
    for group in groups:
        advantages = loo_advantages([r["Jsh"] for r in group], scale)
        for r, adv in zip(group, advantages):
            for tk, cx, mk, ak, _station in r["dec"]:
                samples.append((tk, cx, mk, ak)); advs.append(float(adv))
    return samples, advs, episodes


def require_public_sampler(env, R):
    if R < 1:
        raise ValueError("RI requires independent public-information futures; ri_R must be >=1")
    if getattr(env, "public_future_sampler_verified", False) is not True:
        raise ValueError("RI blocked: public-observation conditional future sampler is unverified")


def training_contract(a):
    ignored = {"out", "workers", "device"}
    contract = {k: v for k, v in vars(a).items() if k not in ignored}
    for name in ("plans", "dev_plans"):
        from rlcore.common import rel
        p = rel(getattr(a, name))
        with open(p, "rb") as stream:
            payload = stream.read()
        raw_rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
        if any("error" in row for row in raw_rows):
            raise ValueError("training manifests contain failed author rows; no silent exclusion")
        contract[name] = dict(path=os.path.abspath(p), sha256=hashlib.sha256(payload).hexdigest())
    import glob
    contract["source_sha256"] = {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest()
                                for p in sorted(glob.glob(os.path.join(HERE, "rlcore", "*.py")))}
    contract["schema"] = LEARNING_SCHEMA
    return contract


def rollout_seed(seed, iteration, group):
    return int(np.random.SeedSequence([seed, iteration, group, 0x524C]).generate_state(1, dtype=np.uint64)[0])


def capture_rng(rng):
    import torch
    return dict(driver=rng.getstate(), python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None)


def restore_rng(saved, rng):
    import torch
    rng.setstate(saved["driver"]); random.setstate(saved["python"]); np.random.set_state(saved["numpy"])
    torch.set_rng_state(saved["torch"])
    if saved["cuda"] is not None:
        if not torch.cuda.is_available():
            raise ValueError("resume requires the original CUDA RNG backend")
        torch.cuda.set_rng_state_all(saved["cuda"])


def _winit():
    import torch
    torch.set_num_threads(1)


def _model_from(path, ver):
    import torch
    from rlcore.model import Policy
    identity = (os.path.abspath(path), ver, os.stat(path).st_mtime_ns)
    if _W.get("identity") != identity:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        if ck.get("learning_schema") != LEARNING_SCHEMA:
            raise ValueError("worker checkpoint schema mismatch")
        m = Policy(**ck.get("arch", {})); m.load_state_dict(ck["model"]); m.eval()
        _W["m"], _W["ver"], _W["fa"], _W["base"] = m, ver, ck.get("feat_ablate", "none"), ck.get("base", "none")
        _W["identity"] = identity
    return _W["m"], _W["fa"], _W["base"]


class Recorder:
    def __init__(self, teacher, fa, show):
        self.t = teacher; self.fa = fa; self.buf = []; self.name = teacher.name; self.show = show

    def reset(self, env):
        self.t.reset(env)

    def act(self, env, cur):
        a = self.t.act(env, cur)
        tok, ctx, mask, acts = featurize(env, cur, a if self.show else None)
        tok, ctx = ablate(tok, ctx, self.fa)
        k = acts.index(a)
        if not mask[k]:
            raise ValueError("teacher produced an illegal physical action")
        self.buf.append((tok, ctx, mask, k))
        return a


def job_teacher(args):
    row, day, scen, teacher, fa, show = args
    env = make_env(row, day, scen)
    rec = Recorder(PO.make(teacher), fa, show)
    res = PO.run_episode(env, rec)
    res["author_cost"] = res["author_cost_cap"] = env.L.get("author_cost")
    return rec.buf, res


def job_rollouts(args):
    row, day, scen, wpath, ver, n, temp, seed, shaping, lam_s = args[:10]
    audit = args[10:]
    m, fa, base = _model_from(wpath, ver)
    out = []
    for k in range(n):
        env = make_env(row, day, scen)
        pol = RLPolicy(m, fa, greedy=False, temp=temp, rng=np.random.default_rng(np.random.SeedSequence([seed, k])), collect=True, base=base)
        res = PO.run_episode(env, pol)
        dec = [(b[0], b[1], b[2], b[3], b[4]) for b in pol.buf]
        perst = dict(res["per_st_J"])
        if shaping == "eta":     # ablation: sketch 8.4 head/tailwind shaping (tailwind reward = lower J)
            for b in pol.buf:
                perst[b[4]] = perst.get(b[4], 0.0) - lam_s * b[5]
        Jsh = res["J"] - (lam_s * sum(b[5] for b in pol.buf) if shaping == "eta" else 0.0)
        out.append(dict(dec=dec, J=res["J"], Jsh=Jsh, perst=perst, ok=res["complete_strict"], fb=res["fallback"],
                        failed=res.get("failed", 0), termination_reason=res.get("termination_reason")))
        if audit:
            path, iteration, group = audit
            # Preserve every finished trajectory even when a later trajectory
            # or another worker is cancelled at the phase deadline.
            payload = json.dumps(dict(_attempt_summary([out[-1]])[0], iteration=iteration, group=group,
                                      rollout=k, path=row["path"], day=day, status="completed")) + "\n"
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, payload.encode("utf-8"))
            finally:
                os.close(fd)
    return out


def job_ri(args):
    """Optional approximate policy iteration, gated on a verified public sampler.

    Hidden-latent resampling is not an observation posterior and does not qualify.
    Paired seeds alone do not make a stochastic teacher wall-time deterministic.
    """
    import copy, torch
    from rlcore.model import collate
    row, day, scen, wpath, ver, teacher, p_pick, K, seed, tol, R = args
    m, fa, base = _model_from(wpath, ver)
    if base not in ("none", teacher):
        raise ValueError("RI teacher must match the checkpoint suggestion source")
    show = base != "none"
    rng = np.random.default_rng(seed)
    env = make_env(row, day, scen)
    require_public_sampler(env, R)
    sh = PO.make(teacher); sh.reset(env)
    out = []; n_dec = 0; n_imp = 0
    while True:
        cur = env.next_decision()
        if cur is None:
            break
        n_dec += 1
        pick = rng.random() < p_pick
        sug = sh.act(env, cur)
        snap = copy.deepcopy((env, cur, sh)) if pick else None
        tok, ctx, mask, acts = featurize(env, cur, sug if show else None)
        tok, ctx = ablate(tok, ctx, fa)
        t, c, mm = collate([(tok, ctx, mask)])
        with torch.no_grad():
            lg = m(t, c, mm)[0].numpy().astype(np.float64)
        lg = np.where(mask, lg, -1e18)
        k_pol = int(np.argmax(lg))
        if pick and sug in acts and mask.sum() >= 2:
            k_sug = acts.index(sug)
            legal = np.flatnonzero(mask)
            order = [int(x) for x in legal[np.argsort(-lg[legal])] if int(x) != k_sug]
            cand = [k_sug] + order[:K - 1]
            fseeds = [int(rng.integers(1 << 30)) for _ in range(R)]
            Js = {kc: [] for kc in cand}
            for kc in cand:
                for fs in fseeds:                   # same R sampled futures for every candidate (common random numbers)
                    e2, c2, s2 = copy.deepcopy(snap)
                    e2.resample_future(fs)
                    # Current public state and shield must survive the conditional draw.
                    tk2, cx2, mk2, ac2 = featurize(e2, c2, sug if show else None)
                    tk2, cx2 = ablate(tk2, cx2, fa)
                    if ac2 != acts or not all(np.array_equal(x, y) for x, y in ((tk2, tok), (cx2, ctx), (mk2, mask))):
                        raise ValueError("future sampler changed current public information")
                    seed_all(fs)
                    e2.step(acts[kc])
                    while True:
                        cc = e2.next_decision()
                        if cc is None:
                            break
                        e2.step(s2.act(e2, cc))
                    r = e2.result()
                    Js[kc].append(r["J"] + (0.0 if r["complete_strict"] else 1e6))
            # conservative acceptance: the alternative must beat the teacher's action by >= tol in EVERY sampled
            # future (paired, CRN) -> label noise from lucky futures is filtered out
            js = np.array(Js[k_sug]); lab = k_sug; best_gain = 0.0
            for kc in cand[1:]:
                d = js - np.array(Js[kc])
                if d.min() >= tol and d.mean() > best_gain:
                    lab, best_gain = kc, float(d.mean())
            n_imp += int(lab != k_sug)
            out.append((tok, ctx, mask, lab))
        env.step(acts[k_pol])
    res = env.result()
    return out, dict(J=res["J"], ok=res["complete_strict"], n_dec=n_dec, n_lab=len(out), n_imp=n_imp)


def job_eval(args):
    row, day, scen, wpath, ver = args
    m, fa, base = _model_from(wpath, ver)
    env = make_env(row, day, scen)
    res = PO.run_episode(env, RLPolicy(m, fa, greedy=True, base=base))
    res["author_cost"] = res["author_cost_cap"] = env.L.get("author_cost")
    return res


def _main():
    global _POOL, _FAILURE_SAVE
    ap = argparse.ArgumentParser()
    ap.add_argument("--scen", required=True); ap.add_argument("--plans", required=True); ap.add_argument("--dev_plans", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--teacher", default="auto"); ap.add_argument("--bc_episodes", type=int, default=400)
    ap.add_argument("--bc_epochs", type=int, default=8); ap.add_argument("--rl_iters", type=int, default=2000)
    ap.add_argument("--rl_hours", type=float, default=6.0, help="continuous PG phase wall window, including in-phase dev/checkpoints; never restarted")
    ap.add_argument("--batch_maps", type=int, default=8)
    ap.add_argument("--rollouts", type=int, default=8); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--ent", type=float, default=0.0); ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--reward_scale", type=float, default=1000.0, help="fixed preregistered cost scale; no sample-dependent standardization")
    ap.add_argument("--total_hours", type=float, default=12.0, help="all-stage wall cap including BC, teacher probes and dev selection")
    ap.add_argument("--dev_days", type=int, default=10); ap.add_argument("--dev_maps", type=int, default=20)
    ap.add_argument("--eval_every", type=int, default=50)
    ap.add_argument("--feat_ablate", default="none"); ap.add_argument("--shaping", default="none")
    ap.add_argument("--lam_shape", type=float, default=2.0); ap.add_argument("--no_bc", action="store_true")
    ap.add_argument("--smooth", type=float, default=0.1, help="BC label smoothing (keeps exploration for the RL stage)")
    ap.add_argument("--ri_hours", type=float, default=0.0, help="rollout-improvement (API/DAgger) stage hours, before PG")
    ap.add_argument("--ri_iters", type=int, default=100000); ap.add_argument("--ri_maps", type=int, default=32)
    ap.add_argument("--ri_pick", type=float, default=0.08, help="fraction of decisions that get rollout labels")
    ap.add_argument("--ri_R", type=int, default=3, help="independent public-observation futures per label; must be >=1")
    ap.add_argument("--ri_K", type=int, default=4); ap.add_argument("--ri_tol", type=float, default=1.0)
    ap.add_argument("--ri_epochs", type=int, default=2); ap.add_argument("--ri_buffer", type=int, default=150000)
    ap.add_argument("--ri_bc_keep", type=int, default=40000, help="BC samples kept and replayed in every RI fit (anti-forgetting)")
    ap.add_argument("--no_base", action="store_true", help="remove online teacher-choice hint; author-plan columns require --feat_ablate noplan")
    ap.add_argument("--no_ri", action="store_true", help="explicit BC/standard REINFORCE control without rollout-improvement")
    ap.add_argument("--teacher_candidates", default="A1,GREEDY,REOPT", help="train-only teacher probe candidates; not a strongest-method claim")
    ap.add_argument("--d", type=int, default=128); ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    if a.no_ri or a.ri_iters == 0:
        a.ri_hours = 0.0
    if a.ri_hours > 0:
        ap.error("RI qualification missing: the current sampler conditions on hidden simulator state; use --no_ri")
    if a.feat_ablate not in ABLATIONS or a.shaping not in ("none", "eta"):
        ap.error("unknown feature/reward ablation")
    positive = (a.total_hours, a.temp, a.reward_scale, a.lr)
    if not all(np.isfinite(x) and x > 0 for x in positive) or not (0 <= a.smooth < 1):
        ap.error("invalid positive budget/temperature/scale/lr or label smoothing")
    if a.rollouts < 2 or min(a.workers, a.batch_maps, a.dev_days, a.dev_maps, a.eval_every) < 1:
        ap.error("rollouts must be >=2; workers/maps/dev/eval counts must be positive")
    if a.seed < 0:
        ap.error("seed must be nonnegative")
    if not all(np.isfinite(x) for x in (a.rl_hours, a.ri_hours, a.ent)) or min(a.bc_episodes, a.bc_epochs, a.rl_iters, a.ri_iters, a.rl_hours, a.ri_hours, a.ent) < 0:
        ap.error("stage counts, hours and entropy coefficient must be nonnegative")
    if not a.no_bc and min(a.bc_episodes, a.bc_epochs) < 1:
        ap.error("BC requires positive episode and epoch counts; use --no_bc to disable it")
    if a.dev_days > len(DEV_DAYS):
        ap.error("dev_days exceeds the registered development day pool")
    run_started = time.monotonic()
    import torch
    import multiprocessing as mp
    from rlcore.model import Policy, collate
    seed_all(a.seed)
    os.makedirs(a.out, exist_ok=True)
    if not os.path.exists(os.path.join(a.out, "state.pt")):
        artifacts = ("best.pt", "last.pt", "bc.pt", "init.pt", "_w.pt", "bc_keep.pt", "done.json", "curve.jsonl")
        if any(os.path.exists(os.path.join(a.out, name)) for name in artifacts):
            raise ValueError("output directory contains prior learning artifacts without a resume state")
    dev = device(a.device)
    rows = load_plans(a.plans); drows = load_plans(a.dev_plans)[:a.dev_maps]
    if not rows or not drows:
        ap.error("train/dev plan sets must be nonempty")
    if {r["path"] for r in rows} & {r["path"] for r in drows}:
        ap.error("train and dev map identities overlap")
    contract = training_contract(a)
    ddays = development_days(a.scen, DEV_DAYS[:a.dev_days])
    arch = dict(d=a.d, layers=a.layers)
    model = Policy(**arch).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    curve = open(os.path.join(a.out, "curve.jsonl"), "a")
    st_path = os.path.join(a.out, "state.pt")
    wpath = os.path.join(a.out, "_w.pt")
    pool = mp.get_context("spawn").Pool(a.workers, initializer=_winit)
    _POOL = pool
    rng = random.Random(a.seed)

    def save_w(ver):
        torch.save(dict(model={k: v.detach().cpu() for k, v in model.state_dict().items()}, arch=arch, feat_ablate=a.feat_ablate,
                        base=state.get("base", "none"), learning_schema=LEARNING_SCHEMA), wpath + ".tmp")
        os.replace(wpath + ".tmp", wpath)

    def ckpt(path, extra):
        torch.save(dict(model={k: v.detach().cpu() for k, v in model.state_dict().items()}, arch=arch,
                        feat_ablate=a.feat_ablate, scen=a.scen, base=state.get("base", "none"), learning_schema=LEARNING_SCHEMA,
                        contract=contract, role=("development_B_primary_cost_gate_pending" if a.scen.startswith("emerg_")
                                                 else "development_selected_M_return_cap" if is_fixed_weather(a.scen)
                                                 else "development_selected_J_proxy"),
                        pg_optimizer_steps=state["pg_optimizer_steps"], source=state["model_source"], **extra), path + ".tmp")
        os.replace(path + ".tmp", path)

    def dev_eval(ver, tag):
        save_w(ver)
        jobs = [(r, dd, a.scen, wpath, ver) for r in drows for dd in ddays]
        res = dispatch(job_eval, jobs)
        with open(os.path.join(a.out, "dev_attempts.jsonl"), "a") as stream:
            for job, result in zip(jobs, res):
                stream.write(json.dumps(dict(tag=tag, path=job[0]["path"], day=job[1], result=result)) + "\n")
        J = float(np.mean([x["J"] for x in res])); ok = all(eligible_result(x, a.scen) for x in res)
        score = development_score(res, a.scen)
        fb = float(np.mean([x["fallback"] for x in res]))
        rec = dict(tag=tag, devJ=J, score=score, eligible_all=bool(ok and score is not None),
                   strict_all=all(x["complete_strict"] for x in res), fallback=fb, cost=float(np.mean([x["cost"] for x in res])),
                   selector=("negative_pooled_high_on_time_rate" if a.scen.startswith("emerg_") else
                             "M_return_with_per_map_author_cost_cap" if is_fixed_weather(a.scen) else "J_proxy"),
                   n_map_days=len(jobs),
                   inc=float(np.mean([x["inc_cell"] + x["inc_land"] for x in res])), t=time.time())
        curve.write(json.dumps(rec) + "\n"); curve.flush()
        return rec

    def fit(data, epochs, tag):
        if not data:
            raise ValueError(f"{tag} has no legal decision labels; no learned checkpoint can be claimed")
        idx = np.arange(len(data)); out = None
        for ep in range(epochs):
            np.random.shuffle(idx); tot = 0.0; acc = 0; n = 0
            model.train()
            for b in range(0, len(idx), 512):
                check_budget()
                bs = [data[i] for i in idx[b:b + 512]]
                t, c, m = collate([(x[0].astype(np.float32), x[1], x[2]) for x in bs], dev)
                y = torch.tensor([x[3] for x in bs], device=dev)
                lg = model(t, c, m)
                logp = torch.log_softmax(lg, -1)
                nll = -logp.gather(1, y[:, None]).squeeze(1)
                smooth = -(logp.masked_fill(~m, 0.0)).sum(-1) / m.sum(-1).clamp(min=1)   # smoothing over LEGAL actions only
                loss = ((1 - a.smooth) * nll + a.smooth * smooth).mean()
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
                state["optimizer_steps"] += 1
                tot += float(loss.detach()) * len(bs); acc += int((lg.argmax(1) == y).sum()); n += len(bs)
            model.eval()
            out = dict(tag=f"{tag}{ep}", loss=tot / max(1, n), acc=acc / max(1, n), n=n)
            if tag == "bc":
                print(f"[train] BC epoch {ep} loss={out['loss']:.4f} acc={out['acc']:.3f}", flush=True)
            curve.write(json.dumps(out) + "\n"); curve.flush()
        return out

    state = dict(stage="bc", it=0, best=None, ver=0, t_rl=0.0, ri_it=0, t_ri=0.0, elapsed_wall=0.0,
                 objective="failure_penalized_J_proxy", optimizer_steps=0, pg_optimizer_steps=0,
                 model_source="initialization", pg_stop_reason=None)
    if os.path.exists(st_path):
        ck = torch.load(st_path, map_location="cpu", weights_only=False)
        if ck.get("contract") != contract or "rng" not in ck:
            raise ValueError("resume contract/input hashes/RNG mismatch; use a new output directory")
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); state = ck["state"]
        restore_rng(ck["rng"], rng)
        print(f"[train] resumed {state['stage']} it={state['it']} best={state['best']}", flush=True)
    done_path = os.path.join(a.out, "done.json")
    if state["stage"] == "done" and os.path.exists(done_path):
        print(f"[train] already completed PG updates={state['pg_optimizer_steps']} best={state['best']}", flush=True)
        return
    if state["stage"] == "done":
        raise ValueError("completion manifest missing; final state retained for audit, no implicit PG restart")
    if state.get("failure"):
        raise ValueError("previous attempt failed; retained state is audit evidence, not a silent retry")
    if os.path.exists(done_path):
        os.unlink(done_path)

    elapsed_before = state["elapsed_wall"]

    active_deadline = None

    def check_budget():
        return remaining_budget(run_started + a.total_hours * 3600 - elapsed_before, active_deadline)

    def dispatch(fun, jobs):
        def record(event):
            with open(os.path.join(a.out, "dispatch_attempts.jsonl"), "a") as stream:
                stream.write(json.dumps(dict(event, function=fun.__name__, iteration=state["it"],
                                             stage=state["stage"], t=time.time())) + "\n")
        def result(index, value):
            job = jobs[index]
            record(dict(status="completed", job=index, path=job[0]["path"], day=job[1],
                        result=_attempt_summary(value)))
        return dispatch_jobs(pool, fun, jobs, check_budget, result, record)

    def save_state():
        state["elapsed_wall"] = elapsed_before + time.monotonic() - run_started
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), state=state, contract=contract,
                        rng=capture_rng(rng)), st_path + ".tmp")
        os.replace(st_path + ".tmp", st_path)

    def save_failure(exc):
        state["failure"] = dict(error_type=type(exc).__name__, error=str(exc), status="failed")
        if state["stage"] == "rl" and "t_start" in locals_for_failure:
            state["t_rl"] = time.monotonic() - locals_for_failure["t_start"]
        curve.write(json.dumps(dict(tag="run_failure", **state["failure"])) + "\n"); curve.flush()
        save_state()

    locals_for_failure = {}
    _FAILURE_SAVE = save_failure

    # ---------------- teacher selection (on TRAIN maps only; dev/test untouched) -------------
    if state["stage"] == "bc":
        teacher = "none" if a.no_bc and a.no_base and a.ri_hours == 0 else a.teacher
        if teacher == "auto":
            cands = a.teacher_candidates.split(",")
            if not all(cands):
                raise ValueError("empty teacher candidate")
            probe = [(rows[i % len(rows)], TRAIN_DAY0 + 777000 + i, a.scen, c, a.feat_ablate, False) for i in range(min(24, len(rows))) for c in cands]
            rs = dispatch(job_teacher, probe)
            with open(os.path.join(a.out, "teacher_attempts.jsonl"), "a") as stream:
                for job, (_, result) in zip(probe, rs):
                    stream.write(json.dumps(dict(stage="probe", path=job[0]["path"], day=job[1], teacher=job[3], result=result)) + "\n")
            sc = {c: float(np.mean([rs[k][1]["J"] for k in range(len(rs)) if probe[k][3] == c])) for c in cands}
            scores = {c: development_score([rs[k][1] for k in range(len(rs)) if probe[k][3] == c], a.scen) for c in cands}
            eligible = [c for c in cands if scores[c] is not None and all(eligible_result(rs[k][1], a.scen)
                        for k in range(len(rs)) if probe[k][3] == c)]
            if not eligible:
                raise ValueError("no train-probe teacher meets strict completion; failures retained, no fallback")
            teacher = min(eligible, key=lambda c: (scores[c], sc[c]))
            curve.write(json.dumps(dict(tag="teacher_probe", costs=sc, scores=scores, eligible=eligible, teacher=teacher)) + "\n"); curve.flush()
            print(f"[train] teacher probe J={sc} -> {teacher}", flush=True)
        state["teacher"] = teacher
        state["base"] = "none" if a.no_base else teacher
        if not a.no_bc:
            jobs = [(rows[rng.randrange(len(rows))], TRAIN_DAY0 + rng.randrange(10 ** 6), a.scen, teacher, a.feat_ablate, not a.no_base)
                    for _ in range(a.bc_episodes)]
            data = []
            teacher_results = dispatch(job_teacher, jobs)
            with open(os.path.join(a.out, "teacher_attempts.jsonl"), "a") as stream:
                for job, (buf, result) in zip(jobs, teacher_results):
                    data.extend(buf)
                    stream.write(json.dumps(dict(stage="bc", path=job[0]["path"], day=job[1], teacher=teacher, result=result)) + "\n")
            print(f"[train] BC samples={len(data)} teacher={teacher}", flush=True)
            fit(data, a.bc_epochs, "bc")
            state["model_source"] = "bc"
            keep = random.Random(a.seed).sample(range(len(data)), min(len(data), a.ri_bc_keep))
            torch.save([data[i] for i in keep], os.path.join(a.out, "bc_keep.pt"))
            del data
        state["ver"] += 1
        initial_tag = "init" if a.no_bc else "bc"
        rec = dev_eval(state["ver"], initial_tag)
        print(f"[train] dev(BC) {rec}", flush=True)
        if rec["eligible_all"]:
            state["best"] = dict(devJ=rec["devJ"], score=rec["score"], tag=initial_tag, it=0,
                                 source=checkpoint_source(initial_tag), pg_optimizer_steps=state["pg_optimizer_steps"])
            ckpt(os.path.join(a.out, "best.pt"), dict(dev=rec, tag=initial_tag))
        ckpt(os.path.join(a.out, f"{initial_tag}.pt"), dict(dev=rec, tag=initial_tag))
        ckpt(os.path.join(a.out, "last.pt"), dict(dev=rec, tag=initial_tag))
        state["stage"] = "ri"; save_state()

    def consider(rec, tag, it):
        if rec["eligible_all"] and (state["best"] is None or rec["score"] < state["best"]["score"]):
            state["best"] = dict(devJ=rec["devJ"], score=rec["score"], tag=tag, it=it,
                                 source=checkpoint_source(tag), pg_optimizer_steps=state["pg_optimizer_steps"])
            ckpt(os.path.join(a.out, "best.pt"), dict(dev=rec, tag=tag))

    # ---------------- rollout-improvement stage (approximate policy iteration over the teacher heuristic) -------------
    if state["stage"] == "ri":
        ri_buf = []; bc_keep = None
        rb_path = os.path.join(a.out, "ri_buf.pt")
        if os.path.exists(rb_path):
            ri_buf = torch.load(rb_path, weights_only=False)
        t0 = time.time() - state.get("t_ri", 0.0)
        while a.ri_hours > 0 and state["ri_it"] < a.ri_iters and (time.time() - t0) < a.ri_hours * 3600:
            state["ver"] += 1; save_w(state["ver"])
            jobs = [(rows[rng.randrange(len(rows))], TRAIN_DAY0 + rng.randrange(10 ** 6), a.scen, wpath, state["ver"],
                     state["teacher"], a.ri_pick, a.ri_K, a.seed * 10 ** 7 + 5 * 10 ** 6 + state["ri_it"] * 1000 + g, a.ri_tol, a.ri_R)
                    for g in range(a.ri_maps)]
            res = dispatch(job_ri, jobs)
            for o, _ in res:
                ri_buf.extend(o)
            ri_buf = ri_buf[-a.ri_buffer:]
            st = [x[1] for x in res]
            if bc_keep is None:
                bkp = os.path.join(a.out, "bc_keep.pt")
                bc_keep = torch.load(bkp, weights_only=False) if os.path.exists(bkp) else []
            nb = min(len(bc_keep), 2 * len(ri_buf) + 2000)
            mix = ri_buf + (random.Random(state["ri_it"]).sample(bc_keep, nb) if nb else [])
            fr = fit(mix, a.ri_epochs, "ri")
            state["ri_it"] += 1; state["t_ri"] = time.time() - t0
            info = dict(tag="ri", it=state["ri_it"], trainJ=float(np.mean([x["J"] for x in st])),
                        strict=float(np.mean([x["ok"] for x in st])), labels=int(sum(x["n_lab"] for x in st)),
                        improved=int(sum(x["n_imp"] for x in st)), buf=len(ri_buf), fit_acc=fr["acc"] if fr else None)
            curve.write(json.dumps(info) + "\n"); curve.flush()
            print(f"[train] RI {info}", flush=True)
            if state["ri_it"] % max(1, a.eval_every // 10) == 0:
                state["ver"] += 1
                rec = dev_eval(state["ver"], f"ri{state['ri_it']}")
                print(f"[train] dev ri={state['ri_it']} {rec}", flush=True)
                consider(rec, f"ri{state['ri_it']}", -state["ri_it"])
                ckpt(os.path.join(a.out, "last.pt"), dict(dev=rec, tag=f"ri{state['ri_it']}"))
                torch.save(ri_buf, rb_path + ".tmp"); os.replace(rb_path + ".tmp", rb_path)
                save_state()
        if a.ri_hours > 0 and state["ri_it"] % max(1, a.eval_every // 10) != 0:
            state["ver"] += 1
            rec = dev_eval(state["ver"], f"ri{state['ri_it']}")
            print(f"[train] dev ri-final {rec}", flush=True)
            consider(rec, f"ri{state['ri_it']}", -state["ri_it"])
        # PG continues from the best checkpoint so far (BC or RI)
        if os.path.exists(os.path.join(a.out, "best.pt")):
            model.load_state_dict(torch.load(os.path.join(a.out, "best.pt"), map_location="cpu", weights_only=False)["model"])
            state["model_source"] = state["best"]["source"]
            # Loading another parameter snapshot invalidates the current Adam moments.
            opt = torch.optim.Adam(model.parameters(), lr=a.lr)
        state["stage"] = "rl"; save_state()

    # ---------------- RL fine-tuning -------------
    # One continuous phase window: dev/checkpoint time consumes it too.
    t_start = time.monotonic() - state.get("t_rl", 0.0)
    locals_for_failure["t_start"] = t_start
    pg_deadline = t_start + a.rl_hours * 3600
    active_deadline = pg_deadline
    phase = "before_dispatch"
    while state["it"] < a.rl_iters and time.monotonic() < pg_deadline:
        try:
            check_budget()
            phase = "rollout"
            state["ver"] += 1; save_w(state["ver"])
            jobs = [(rows[rng.randrange(len(rows))], TRAIN_DAY0 + rng.randrange(10 ** 6), a.scen, wpath, state["ver"], a.rollouts,
                     a.temp, rollout_seed(a.seed, state["it"], g), a.shaping, a.lam_shape,
                     os.path.join(a.out, "rollout_attempts.jsonl"), state["it"], g) for g in range(a.batch_maps)]
            groups = dispatch(job_rollouts, jobs)
            samples, advs, episodes = pg_samples(groups, a.reward_scale)
            model.train()
            opt.zero_grad(set_to_none=True)
            n = len(samples); tot_ent = 0.0
            if not n:
                raise ValueError("rollout batch has no policy decisions; zero PG steps are not RL training")
            phase = "gradient"
            for b in range(0, n, 1024):
                check_budget()
                bs = samples[b:b + 1024]
                t, c, m = collate([(x[0], x[1], x[2]) for x in bs], dev)
                y = torch.tensor([x[3] for x in bs], device=dev)
                A = torch.tensor(advs[b:b + 1024], device=dev, dtype=torch.float32)
                lg = model(t, c, m)
                logp = action_log_probs(lg, m, a.temp)
                lp = logp.gather(1, y[:, None]).squeeze(1)
                p = logp.exp()
                ent = -(p * logp.masked_fill(~m, 0)).sum(-1)
                # Sum every action score; average episodes, not decisions.
                loss = (-(A * lp) - a.ent * ent).sum() / episodes
                loss.backward(); tot_ent += float(ent.detach().sum())
                check_budget()
            # Backward changes only gradients. A late mutating step restores
            # parameters and Adam; no incomplete update counts as RL training.
            import copy
            check_budget()
            before_model, before_opt = copy.deepcopy(model.state_dict()), copy.deepcopy(opt.state_dict())

            def step():
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                check_budget()
                opt.step()
                if dev.type == "cuda":
                    torch.cuda.synchronize(dev)

            def rollback():
                model.load_state_dict(before_model); opt.load_state_dict(before_opt)
                opt.zero_grad(set_to_none=True)
                if dev.type == "cuda":
                    torch.cuda.synchronize(dev)

            phase = "optimizer"
            commit_pg_update(check_budget, step, rollback)
            state["optimizer_steps"] += 1; state["pg_optimizer_steps"] += 1
            state["model_source"] = "pg"
            model.eval()
            state["it"] += 1; state["t_rl"] = time.monotonic() - t_start
            Jm = float(np.mean([r["J"] for g in groups for r in g]))
            okr = float(np.mean([r["ok"] for g in groups for r in g]))
            phase = "checkpoint"
            curve.write(json.dumps(dict(tag="rl", it=state["it"], trainJ=Jm, strict=okr,
                                        ent=tot_ent / n, n_dec=n, pg_optimizer_steps=state["pg_optimizer_steps"])) + "\n"); curve.flush()
            save_state()
            if state["it"] % 10 == 0:
                print(f"[train] it={state['it']} trainJ={Jm:.2f} strict={okr:.3f} ent={tot_ent / n:.3f} n={n}", flush=True)
            if state["it"] % a.eval_every == 0:
                # Dev can finish under total after PG ends, but never shifts
                # the continuous PG deadline or authorizes another update.
                active_deadline = None
                phase = "development"
                state["ver"] += 1
                rec = dev_eval(state["ver"], f"it{state['it']}")
                consider(rec, f"it{state['it']}", state["it"])
                ckpt(os.path.join(a.out, "last.pt"), dict(dev=rec, tag=f"it{state['it']}"))
                state["last_dev_it"] = state["it"]
                save_state()
                active_deadline = pg_deadline
        except PGDeadlineReached:
            opt.zero_grad(set_to_none=True); model.eval()
            state["pg_stop_reason"] = "rl_hours_exhausted"
            state["t_rl"] = time.monotonic() - t_start
            curve.write(json.dumps(dict(tag="pg_interrupted", iteration=state["it"], phase=phase,
                                        retained_pg_updates=state["pg_optimizer_steps"],
                                        elapsed_phase_seconds=state["t_rl"],
                                        deadline_overrun_seconds=max(0.0, time.monotonic() - pg_deadline))) + "\n"); curve.flush()
            _shutdown_pool()
            active_deadline = None
            check_budget()
            # Only final dev may use new workers; no more PG work is submitted.
            pool = mp.get_context("spawn").Pool(a.workers, initializer=_winit); _POOL = pool
            break
    state["t_rl"] = time.monotonic() - t_start
    state["pg_stop_reason"] = state["pg_stop_reason"] or ("rl_iters_complete" if state["it"] >= a.rl_iters else "rl_hours_exhausted")
    active_deadline = None
    if state["it"] and state.get("last_dev_it") != state["it"]:
        state["ver"] += 1
        rec = dev_eval(state["ver"], f"it{state['it']}")
        consider(rec, f"it{state['it']}", state["it"])
        ckpt(os.path.join(a.out, "last.pt"), dict(dev=rec, tag=f"it{state['it']}"))
        state["last_dev_it"] = state["it"]
    check_budget()
    if state["best"] is None:
        raise ValueError("no checkpoint met the registered development selector and physical/routine gates")
    pool.close()
    pool.join(); _POOL = None
    check_budget()
    state["stage"] = "done"
    save_state()
    check_budget()
    with open(done_path + ".tmp", "w") as stream:
        json.dump(dict(best=state["best"], best_source=state["best"]["source"], teacher=state.get("teacher"),
                       iters=state["it"], hours=state["t_rl"] / 3600, pg_optimizer_steps=state["pg_optimizer_steps"],
                       status="completed_pg_updates" if state["pg_optimizer_steps"] else "completed_without_pg_update",
                       pg_stop_reason=state["pg_stop_reason"], elapsed_wall=state["elapsed_wall"],
                       optimizer_steps=state["optimizer_steps"], contract=contract, learning_schema=LEARNING_SCHEMA,
                       objective="failure_penalized_J_proxy", qualification="development_only_not_formal",
                       pg_clock="continuous_phase_wall_including_in_phase_development_and_checkpoints",
                       finalization_clock="all_stage_wall_only"), stream)
    check_budget()
    os.replace(done_path + ".tmp", done_path)
    try:
        check_budget()
    except TotalBudgetExceeded:
        os.unlink(done_path)
        raise
    print(f"[train] done PG updates={state['pg_optimizer_steps']} best={state['best']}", flush=True)

def main():
    global _FAILURE_SAVE
    _FAILURE_SAVE = None
    try:
        return _main()
    except BaseException as exc:
        _shutdown_pool()
        if _FAILURE_SAVE is not None:
            try:
                _FAILURE_SAVE(exc)
            except Exception as audit_error:
                print(f"[train] failure-state persistence error: {audit_error}", file=sys.stderr, flush=True)
        raise
    finally:
        _shutdown_pool()
        _FAILURE_SAVE = None


if __name__ == "__main__":
    main()
