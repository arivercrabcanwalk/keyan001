"""rlv3 training: behaviour cloning from the strongest non-RL teacher -> POMO-style multi-rollout policy gradient
with common random numbers (same map + same weather/request day for all N rollouts of a group, shared mean baseline;
Kwon et al. 2020).  Paper A uses per-station returns (stations are independent under weather-only scenarios -> exact
credit assignment); paper B uses the map return (stations interact through emergency requests).
Reward = -J (true objective only).  The sketch's eta-shaping (head/tailwind bonus) is available ONLY as an ablation
(--shaping eta) because it is not potential-based and can change the optimal policy (Ng et al. 1999).
dev selection includes the BC checkpoint; only checkpoints with 100 % strict completion on every dev episode qualify.
Resumable: state.pt is written after every eval."""
import os, sys, json, time, argparse, math, random
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rlcore.common import load_plans, progress, device, seed_all
from rlcore.scen import make_env, DEV_DAYS, TRAIN_DAY0
from rlcore import policies as PO
from rlcore.feat import featurize
from rlcore.agent import RLPolicy, ablate

_W = {}


def _winit():
    import torch
    torch.set_num_threads(1)


def _model_from(path, ver):
    import torch
    from rlcore.model import Policy
    if _W.get("ver") != ver:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        m = Policy(**ck.get("arch", {})); m.load_state_dict(ck["model"]); m.eval()
        _W["m"], _W["ver"], _W["fa"], _W["base"] = m, ver, ck.get("feat_ablate", "none"), ck.get("base", "none")
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
        if mask[k]:
            self.buf.append((tok.astype(np.float16), ctx, mask, k))
        return a


def job_teacher(args):
    row, day, scen, teacher, fa, show = args
    env = make_env(row, day, scen)
    rec = Recorder(PO.make(teacher), fa, show)
    res = PO.run_episode(env, rec)
    return rec.buf, res["J"]


def job_rollouts(args):
    row, day, scen, wpath, ver, n, temp, seed, shaping, lam_s = args
    m, fa, base = _model_from(wpath, ver)
    out = []
    for k in range(n):
        env = make_env(row, day, scen)
        pol = RLPolicy(m, fa, greedy=False, temp=temp, rng=np.random.default_rng(seed * 1000 + k), collect=True, base=base)
        res = PO.run_episode(env, pol)
        dec = [(b[0].astype(np.float16), b[1], b[2], b[3], b[4]) for b in pol.buf]
        perst = dict(res["per_st_J"])
        if shaping == "eta":     # ablation: sketch 8.4 head/tailwind shaping (tailwind reward = lower J)
            for b in pol.buf:
                perst[b[4]] = perst.get(b[4], 0.0) - lam_s * b[5]
        Jsh = res["J"] - (lam_s * sum(b[5] for b in pol.buf) if shaping == "eta" else 0.0)
        out.append(dict(dec=dec, J=res["J"], Jsh=Jsh, perst=perst, ok=res["complete_strict"], fb=res["fallback"]))
    return out


def job_ri(args):
    """Rollout-improvement labels (approximate policy iteration with the base heuristic, Bertsekas et al. 1997;
    Secomandi 2001; Goodson et al. 2017).  The episode is driven by the CURRENT greedy network (DAgger states, Ross et
    al. 2011).  At a random subset of decisions the simulator state is snapshotted (common random numbers) and the
    teacher's action plus the network's top-(K-1) alternatives are each completed with the teacher heuristic; the label
    is the action with the lowest completed J (teacher's action unless another one is better by > tol).
    Each candidate is evaluated on R futures re-sampled from the generative model conditioned on the current state
    (Env.resample_future), shared by all candidates (CRN).  A first version used the realised future (hindsight labels)
    and in the local pilot it learned risky moves (more storm incidents); resampling removes that information leak."""
    import copy, torch
    from rlcore.model import collate
    row, day, scen, wpath, ver, teacher, p_pick, K, seed, tol, R = args
    m, fa, base = _model_from(wpath, ver)
    show = base != "none"
    rng = np.random.default_rng(seed)
    env = make_env(row, day, scen)
    sh = PO.make(teacher); sh.reset(env)
    out = []; n_dec = 0; n_imp = 0
    while True:
        cur = env.next_decision()
        if cur is None:
            break
        n_dec += 1
        pick = rng.random() < p_pick
        snap = copy.deepcopy((env, cur, sh)) if pick else None
        sug = sh.act(env, cur)
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
            fseeds = [int(rng.integers(1 << 30)) for _ in range(R)] if R > 0 else [0]
            Js = {kc: [] for kc in cand}
            for kc in cand:
                for fs in fseeds:                   # same R sampled futures for every candidate (common random numbers)
                    e2, c2, s2 = copy.deepcopy(snap)
                    if R > 0:
                        e2.resample_future(fs)      # unobserved future redrawn -> no hindsight information in the label
                    s2.act(e2, c2)                  # same internal update the teacher made at this decision
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
            out.append((tok.astype(np.float16), ctx, mask, lab))
        env.step(acts[k_pol])
    res = env.result()
    return out, dict(J=res["J"], ok=res["complete_strict"], n_dec=n_dec, n_lab=len(out), n_imp=n_imp)


def job_eval(args):
    row, day, scen, wpath, ver = args
    m, fa, base = _model_from(wpath, ver)
    env = make_env(row, day, scen)
    res = PO.run_episode(env, RLPolicy(m, fa, greedy=True, base=base))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scen", required=True); ap.add_argument("--plans", required=True); ap.add_argument("--dev_plans", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--teacher", default="auto"); ap.add_argument("--bc_episodes", type=int, default=400)
    ap.add_argument("--bc_epochs", type=int, default=8); ap.add_argument("--rl_iters", type=int, default=2000)
    ap.add_argument("--rl_hours", type=float, default=6.0); ap.add_argument("--batch_maps", type=int, default=8)
    ap.add_argument("--rollouts", type=int, default=8); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--ent", type=float, default=0.01); ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--dev_days", type=int, default=10); ap.add_argument("--dev_maps", type=int, default=20)
    ap.add_argument("--eval_every", type=int, default=50)
    ap.add_argument("--feat_ablate", default="none"); ap.add_argument("--shaping", default="none")
    ap.add_argument("--lam_shape", type=float, default=2.0); ap.add_argument("--no_bc", action="store_true")
    ap.add_argument("--smooth", type=float, default=0.1, help="BC label smoothing (keeps exploration for the RL stage)")
    ap.add_argument("--ri_hours", type=float, default=0.0, help="rollout-improvement (API/DAgger) stage hours, before PG")
    ap.add_argument("--ri_iters", type=int, default=100000); ap.add_argument("--ri_maps", type=int, default=32)
    ap.add_argument("--ri_pick", type=float, default=0.08, help="fraction of decisions that get rollout labels")
    ap.add_argument("--ri_R", type=int, default=3, help="sampled futures per label (0 = realised future = hindsight)")
    ap.add_argument("--ri_K", type=int, default=4); ap.add_argument("--ri_tol", type=float, default=1.0)
    ap.add_argument("--ri_epochs", type=int, default=2); ap.add_argument("--ri_buffer", type=int, default=150000)
    ap.add_argument("--ri_bc_keep", type=int, default=40000, help="BC samples kept and replayed in every RI fit (anti-forgetting)")
    ap.add_argument("--no_base", action="store_true", help="pure end-to-end ablation: do not show the teacher's choice")
    ap.add_argument("--d", type=int, default=128); ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    import torch
    import multiprocessing as mp
    from rlcore.model import Policy, collate
    seed_all(a.seed)
    os.makedirs(a.out, exist_ok=True)
    dev = device(a.device)
    rows = load_plans(a.plans); drows = load_plans(a.dev_plans)[:a.dev_maps]
    ddays = DEV_DAYS[:a.dev_days]
    arch = dict(d=a.d, layers=a.layers)
    model = Policy(**arch).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    curve = open(os.path.join(a.out, "curve.jsonl"), "a")
    st_path = os.path.join(a.out, "state.pt")
    wpath = os.path.join(a.out, "_w.pt")
    pool = mp.get_context("spawn").Pool(a.workers, initializer=_winit)
    rng = random.Random(a.seed)

    def save_w(ver):
        torch.save(dict(model={k: v.detach().cpu() for k, v in model.state_dict().items()}, arch=arch, feat_ablate=a.feat_ablate,
                        base=state.get("base", "none")), wpath + ".tmp")
        os.replace(wpath + ".tmp", wpath)

    def ckpt(path, extra):
        torch.save(dict(model={k: v.detach().cpu() for k, v in model.state_dict().items()}, arch=arch,
                        feat_ablate=a.feat_ablate, scen=a.scen, base=state.get("base", "none"), **extra), path + ".tmp")
        os.replace(path + ".tmp", path)

    def dev_eval(ver, tag):
        save_w(ver)
        jobs = [(r, dd, a.scen, wpath, ver) for r in drows for dd in ddays]
        res = pool.map(job_eval, jobs, chunksize=1)
        J = float(np.mean([x["J"] for x in res])); ok = all(x["complete_strict"] for x in res)
        fb = float(np.mean([x["fallback"] for x in res]))
        rec = dict(tag=tag, devJ=J, strict_all=ok, fallback=fb, cost=float(np.mean([x["cost"] for x in res])),
                   inc=float(np.mean([x["inc_cell"] + x["inc_land"] for x in res])), t=time.time())
        curve.write(json.dumps(rec) + "\n"); curve.flush()
        return rec

    def fit(data, epochs, tag):
        idx = np.arange(len(data)); out = None
        for ep in range(epochs):
            np.random.shuffle(idx); tot = 0.0; acc = 0; n = 0
            model.train()
            for b in range(0, len(idx), 512):
                bs = [data[i] for i in idx[b:b + 512]]
                t, c, m = collate([(x[0].astype(np.float32), x[1], x[2]) for x in bs], dev)
                y = torch.tensor([x[3] for x in bs], device=dev)
                lg = model(t, c, m)
                logp = torch.log_softmax(lg, -1)
                nll = -logp.gather(1, y[:, None]).squeeze(1)
                smooth = -(logp.masked_fill(~m, 0.0)).sum(-1) / m.sum(-1).clamp(min=1)   # smoothing over LEGAL actions only
                loss = ((1 - a.smooth) * nll + a.smooth * smooth).mean()
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
                tot += float(loss.detach()) * len(bs); acc += int((lg.argmax(1) == y).sum()); n += len(bs)
            model.eval()
            out = dict(tag=f"{tag}{ep}", loss=tot / max(1, n), acc=acc / max(1, n), n=n)
            if tag == "bc":
                print(f"[train] BC epoch {ep} loss={out['loss']:.4f} acc={out['acc']:.3f}", flush=True)
            curve.write(json.dumps(out) + "\n"); curve.flush()
        return out

    state = dict(stage="bc", it=0, best=None, ver=0, t_rl=0.0, ri_it=0, t_ri=0.0)
    if os.path.exists(st_path):
        ck = torch.load(st_path, map_location="cpu", weights_only=False)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); state = ck["state"]
        print(f"[train] resumed {state['stage']} it={state['it']} best={state['best']}", flush=True)

    def save_state():
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), state=state), st_path + ".tmp")
        os.replace(st_path + ".tmp", st_path)

    # ---------------- teacher selection (on TRAIN maps only; dev/test untouched) -------------
    if state["stage"] == "bc":
        teacher = a.teacher
        if teacher == "auto":
            cands = ["A1", "REOPT"]
            probe = [(rows[i % len(rows)], TRAIN_DAY0 + 777000 + i, a.scen, c, a.feat_ablate, False) for i in range(min(24, len(rows))) for c in cands]
            rs = pool.map(job_teacher, probe, chunksize=1)
            sc = {c: float(np.mean([rs[k][1] for k in range(len(rs)) if probe[k][3] == c])) for c in cands}
            teacher = min(sc, key=sc.get)
            print(f"[train] teacher probe J={sc} -> {teacher}", flush=True)
        state["teacher"] = teacher
        state["base"] = "none" if a.no_base else teacher
        if not a.no_bc:
            jobs = [(rows[rng.randrange(len(rows))], TRAIN_DAY0 + rng.randrange(10 ** 6), a.scen, teacher, a.feat_ablate, not a.no_base)
                    for _ in range(a.bc_episodes)]
            data = []
            for buf, _ in pool.imap_unordered(job_teacher, jobs, chunksize=2):
                data.extend(buf)
            print(f"[train] BC samples={len(data)} teacher={teacher}", flush=True)
            fit(data, a.bc_epochs, "bc")
            keep = random.Random(a.seed).sample(range(len(data)), min(len(data), a.ri_bc_keep))
            torch.save([data[i] for i in keep], os.path.join(a.out, "bc_keep.pt"))
            del data
        state["ver"] += 1
        rec = dev_eval(state["ver"], "bc")
        print(f"[train] dev(BC) {rec}", flush=True)
        if rec["strict_all"]:
            state["best"] = dict(devJ=rec["devJ"], tag="bc", it=0)
            ckpt(os.path.join(a.out, "best.pt"), dict(dev=rec, tag="bc"))
        ckpt(os.path.join(a.out, "bc.pt"), dict(dev=rec, tag="bc"))
        state["stage"] = "ri"; save_state()

    def consider(rec, tag, it):
        if rec["strict_all"] and (state["best"] is None or rec["devJ"] < state["best"]["devJ"]):
            state["best"] = dict(devJ=rec["devJ"], tag=tag, it=it)
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
            res = pool.map(job_ri, jobs, chunksize=1)
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
        state["stage"] = "rl"; save_state()

    # ---------------- RL fine-tuning -------------
    t_start = time.time() - state.get("t_rl", 0.0)
    while state["it"] < a.rl_iters and (time.time() - t_start) < a.rl_hours * 3600:
        state["ver"] += 1; save_w(state["ver"])
        jobs = [(rows[rng.randrange(len(rows))], TRAIN_DAY0 + rng.randrange(10 ** 6), a.scen, wpath, state["ver"], a.rollouts,
                 a.temp, a.seed * 10 ** 7 + state["it"] * 100 + g, a.shaping, a.lam_shape) for g in range(a.batch_maps)]
        groups = pool.map(job_rollouts, jobs, chunksize=1)
        samples, advs = [], []
        per_station = a.scen.startswith("weather") or a.scen == "nowind"
        for grp in groups:
            if per_station:
                keys = set(k for r in grp for k in r["perst"])
                base = {k: np.mean([r["perst"].get(k, 0.0) for r in grp]) for k in keys}
                sd = max(1.0, float(np.std([r["Jsh"] for r in grp])))
                for r in grp:
                    for (tk, cx, mk, ak, s) in r["dec"]:
                        samples.append((tk.astype(np.float32), cx, mk, ak)); advs.append(-(r["perst"][s] - base[s]) / sd)
            else:
                Js = np.array([r["Jsh"] for r in grp]); b = Js.mean(); sd = max(1.0, Js.std())
                for r, J in zip(grp, Js):
                    for (tk, cx, mk, ak, s) in r["dec"]:
                        samples.append((tk.astype(np.float32), cx, mk, ak)); advs.append(-(J - b) / sd)
        model.train()
        opt.zero_grad()
        n = len(samples); tot_ent = 0.0
        for b in range(0, n, 1024):
            bs = samples[b:b + 1024]
            t, c, m = collate([(x[0], x[1], x[2]) for x in bs], dev)
            y = torch.tensor([x[3] for x in bs], device=dev)
            A = torch.tensor(advs[b:b + 1024], device=dev, dtype=torch.float32)
            lg = model(t, c, m)
            logp = torch.log_softmax(lg, -1)
            lp = logp.gather(1, y[:, None]).squeeze(1)
            p = logp.exp()
            ent = -(p * logp.masked_fill(~m, 0)).sum(-1)
            loss = (-(A * lp) - a.ent * ent).sum() / n
            loss.backward(); tot_ent += float(ent.detach().sum())
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        model.eval()
        state["it"] += 1; state["t_rl"] = time.time() - t_start
        Jm = float(np.mean([r["J"] for g in groups for r in g]))
        okr = float(np.mean([r["ok"] for g in groups for r in g]))
        curve.write(json.dumps(dict(tag="rl", it=state["it"], trainJ=Jm, strict=okr, ent=tot_ent / max(1, n), n_dec=n)) + "\n"); curve.flush()
        if state["it"] % 10 == 0:
            print(f"[train] it={state['it']} trainJ={Jm:.2f} strict={okr:.3f} ent={tot_ent / max(1, n):.3f} n={n}", flush=True)
        if state["it"] % a.eval_every == 0:
            state["ver"] += 1
            rec = dev_eval(state["ver"], f"it{state['it']}")
            print(f"[train] dev it={state['it']} {rec}", flush=True)
            if rec["strict_all"] and (state["best"] is None or rec["devJ"] < state["best"]["devJ"]):
                state["best"] = dict(devJ=rec["devJ"], tag=f"it{state['it']}", it=state["it"])
                ckpt(os.path.join(a.out, "best.pt"), dict(dev=rec, tag=f"it{state['it']}"))
            ckpt(os.path.join(a.out, "last.pt"), dict(dev=rec, tag=f"it{state['it']}"))
            save_state()
    save_state()
    pool.close()
    if state["best"] is None:
        print("[train] WARNING: no checkpoint reached 100% strict completion on dev", flush=True)
        sys.exit(3)
    json.dump(dict(best=state["best"], teacher=state.get("teacher"), iters=state["it"], hours=state["t_rl"] / 3600),
              open(os.path.join(a.out, "done.json"), "w"))
    print(f"[train] done best={state['best']}", flush=True)


if __name__ == "__main__":
    main()
