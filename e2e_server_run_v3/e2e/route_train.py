"""Train pi_route: POMO multi-start (forced first target) x Sym-NCO dihedral augmentation x shared baseline
REINFORCE, entropy schedule, size curriculum 35->110 (+ single-station sub-problems for re-routing, + large maps),
cosine LR, bf16 autocast on CUDA, checkpoint/resume, learning-curve log for the 2 h gate.
Validation (routing quality only): on dev maps with the station set of the AUTHOR'S TSALNS plan fixed, compare the
route cost (flight+service) of pi_route vs TSALNS's own routes. (TSALNS is only a measuring stick here.)"""
import os, sys, json, time, math, argparse
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import (ROOT, device, seed_all, gen, size_scale, read_instance, from_instance, JsonlLog, progress,
                        atomic_save, fixed_cost, TIME_COST, S_T, TOK_LIM)
from e2e.route_env import Batch
from e2e.route_model import RoutePolicy, rollout, replay_grad, save_route
from e2e.sitings import random_siting, random_cfl_siting

# curriculum: (ns, n) pools per phase; phase advances with training progress fraction
CURR = [
    (0.00, [(5, 35), (6, 50), (1, 12), (1, 20)]),
    (0.15, [(5, 35), (6, 50), (7, 65), (8, 80), (1, 20), (2, 30)]),
    # REVIEW FIX (R-dist): from 40 % of the schedule (i.e. after the 2 h gate) add Liu-like maps (20 km side for 10
    # stations, 13-15 km for smaller, targets within 5000 m) so the Liu 10_110 test class is in-distribution.
    (0.40, [(6, 50), (7, 65), (8, 80), (10, 110), (1, 25), (2, 35), (10, 110, 20000.0), (7, 65, 15000.0)]),
    (0.70, [(7, 65), (8, 80), (10, 110), (12, 150), (1, 30), (3, 40), (10, 110, 20000.0), (8, 80, 15000.0)]),
]
SMOKE_CURR = [(0.0, [(3, 10), (1, 6), (2, 12)])]


def dihedral(xy, k):
    x, y = xy[..., 0], xy[..., 1]
    c = [(x, y), (y, x), (-x, y), (y, -x), (x, -y), (-y, x), (-x, -y), (-y, -x)][k]
    return np.stack(c, -1)


def make_batch_np(rng, B, ns, n, liu_scale=None, cfl_frac=0.0):
    """v3: with prob. cfl_frac the siting is a random COVERAGE-FEASIBLE (CFL, e2e/coverage.py) siting -- the
    regime every v3 method plans in (nearly all stations DABS); otherwise the v2 random target-cover siting."""
    tgs, sts, tys = [], [], []
    for _ in range(B):
        if liu_scale:
            tg, st = gen(n, ns, rng, scale=liu_scale, rad=5000.0)
        else:
            tg, st = gen(n, ns, rng, scale=size_scale(n, ns))
        tgs.append(tg); sts.append(st)
        tys.append(random_cfl_siting(tg, st, rng) if (ns >= 2 and rng.random() < cfl_frac) else random_siting(tg, st, rng))
    rs = np.where(rng.random(B) < 0.7, 0.0, rng.uniform(0.0, 0.4, B))
    td = np.zeros((B, 3 * ns))
    if ns <= 3:   # re-routing sub-problems start mid-day with used duty
        td = rng.uniform(0, 0.5, (B, 3 * ns)) * np.tile(TOK_LIM, ns)[None] * (rng.random((B, 1)) < 0.7)
    return np.stack(tgs), np.stack(sts), np.stack(tys), rs, td


def load_dev(split="dev_ts", limit=0):
    out = []
    f = split if os.path.exists(split) else os.path.join(ROOT, "data", "plans", split + ".jsonl")
    for l in open(f):
        r = json.loads(l)
        ins = read_instance(os.path.join(ROOT, r["path"]))
        tg, st, tid, sid = from_instance(ins)
        types = r["solution"]["station_types"]
        from e2e.common import evaluate
        ev = evaluate(ins, r["solution"])
        out.append(dict(ins=ins, tg=tg, st=st, tid=tid, types=np.array(types), ts_cost=ev["cost"],
                        ts_route=ev["cost"] - fixed_cost(types), name=ins.name))
    return out[:limit] if limit else out


def validate(pol, dev, devset, aug=True):
    """mean route-cost gap (%) of pi_route vs TSALNS routes on TSALNS sitings; greedy and aug8 x multistart(8)."""
    pol.eval(); g1, g8 = [], []
    for r in devset:
        tg = r["tg"][None]; st = r["st"][None]; ty = r["types"][None]
        bt = Batch(tg, st, ty, N=1, dev=dev)
        o = rollout(pol, bt, greedy=True)
        route = float(o["cost"][0]) - float(bt.fixed[0]) if not bool(o["fail"][0]) else float("inf")
        g1.append(route / r["ts_route"] - 1)
        if aug:
            n = tg.shape[1]; N = min(8, n)
            tgs = np.concatenate([dihedral(tg, k) for k in range(8)]); sts = np.concatenate([dihedral(st, k) for k in range(8)])
            bt8 = Batch(tgs, sts, np.repeat(ty, 8, 0), N=N, dev=dev)
            force = torch.as_tensor(np.tile(np.random.default_rng(0).permutation(n)[:N], 8), device=dev)
            o8 = rollout(pol, bt8, greedy=True, force=force)
            c = torch.where(o8["fail"], torch.full_like(o8["cost"], float("inf")), o8["cost"] - bt8.fixed[bt8.expand_idx()])
            g8.append(float(c.min()) / r["ts_route"] - 1)
    pol.train()
    return float(np.mean(g1) * 100), (float(np.mean(g8) * 100) if g8 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=float, default=12.0)
    ap.add_argument("--max_iters", type=int, default=10 ** 9)
    ap.add_argument("--sched_h", type=float, default=0.0, help="LR/entropy/curriculum horizon (h); default = --hours")
    ap.add_argument("--B", type=int, default=32, help="instances per iteration (before x8 augmentation)")
    ap.add_argument("--N", type=int, default=16, help="POMO starts per augmented instance")
    ap.add_argument("--aug", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--ent0", type=float, default=0.01)
    ap.add_argument("--ent1", type=float, default=0.001)
    ap.add_argument("--d", type=int, default=128)
    ap.add_argument("--enc", type=int, default=6)
    ap.add_argument("--dec", type=int, default=2)
    ap.add_argument("--kc", type=int, default=24)
    ap.add_argument("--chunk", type=int, default=16)
    ap.add_argument("--val_every", type=int, default=50)
    ap.add_argument("--ckpt_min", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--dev_limit", type=int, default=0)
    ap.add_argument("--amp", type=int, default=1)
    ap.add_argument("--cfl_frac", type=float, default=0.6, help="v3: fraction of training sitings drawn coverage-feasible")
    ap.add_argument("--init", default="", help="v3: optional warm start (route checkpoint, e.g. the v2 best.pt); recorded in curve/state")
    ap.add_argument("--dev_plans", default="dev_ts", help="v3: comma list of dev plan sets; the FIRST is the checkpoint-selection yardstick")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = device(); seed_all(a.seed)
    pol = RoutePolicy(d=a.d, enc_layers=a.enc, dec_layers=a.dec, kc=a.kc).to(dev)
    init_note = None
    if a.init and os.path.exists(a.init) and not os.path.exists(os.path.join(a.out, "last.pt")):
        ck0 = torch.load(a.init, map_location=dev, weights_only=False)
        if ck0.get("cfg") and ck0["cfg"] != pol.cfg:
            pol = RoutePolicy(**ck0["cfg"]).to(dev)
        pol.load_state_dict(ck0["sd"]); init_note = os.path.abspath(a.init)
        print(f"[route_train] warm start from {a.init} (cfg {pol.cfg})", flush=True)
    opt = torch.optim.AdamW(pol.parameters(), lr=a.lr, weight_decay=1e-6)
    state = dict(it=0, elapsed=0.0, samples=0, best=None, init=init_note, seed=a.seed, cfl_frac=a.cfl_frac)
    rng = np.random.default_rng(a.seed)
    last = os.path.join(a.out, "last.pt")
    if os.path.exists(last):
        ck = torch.load(last, map_location=dev, weights_only=False)
        pol.load_state_dict(ck["sd"]); opt.load_state_dict(ck["opt"]); state = ck["state"]
        rng = np.random.default_rng(a.seed + 1000 * state["it"])
        # REVIEW FIX (R-resume): best.pt may be newer than last.pt (ckpt every 5 min) -> never let a stale
        # state["best"] allow a worse model to overwrite best.pt after a resume.
        bp = os.path.join(a.out, "best.pt")
        if os.path.exists(bp):
            bv = torch.load(bp, map_location="cpu", weights_only=False).get("val")
            if bv is not None and (state["best"] is None or bv < state["best"]):
                state["best"] = float(bv)
        print(f"[route_train] resumed it={state['it']} elapsed={state['elapsed']/3600:.2f}h", flush=True)
    devsets = []
    for sp in [x for x in a.dev_plans.split(",") if x]:
        try:
            devsets.append((os.path.basename(sp).replace(".jsonl", ""), load_dev(sp, limit=a.dev_limit or (3 if a.smoke else 0))))
        except FileNotFoundError:
            print(f"[route_train] dev plan set {sp} missing -> skipped", flush=True)
    if not devsets:
        devsets = [("dev_ts", load_dev(limit=a.dev_limit or (3 if a.smoke else 0)))]
    devset = devsets[0][1]
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    budget = a.hours * 3600
    horizon = (a.sched_h or a.hours) * 3600
    curr = SMOKE_CURR if a.smoke else CURR
    use_amp = bool(a.amp) and dev.type == "cuda"
    t_start = time.time() - state["elapsed"]; t_ck = time.time()
    pol.train()
    while state["elapsed"] < budget and state["it"] < a.max_iters:
        frac = min(1.0, state["elapsed"] / horizon)
        pool = [p for f, p in curr if frac >= f][-1]
        entry = pool[rng.integers(len(pool))]
        ns, n = entry[0], entry[1]; liu = entry[2] if len(entry) > 2 else None
        B = max(1, int(a.B * (50 / max(n, 50)) ** 1.0)) if not a.smoke else a.B
        tg, st, ty, rs, td = make_batch_np(rng, B, ns, n, liu_scale=liu, cfl_frac=a.cfl_frac)
        A = a.aug
        tga = np.concatenate([dihedral(tg, k) for k in range(A)]); sta = np.concatenate([dihedral(st, k) for k in range(A)])
        N = min(a.N, n)
        bt = Batch(tga, sta, np.tile(ty, (A, 1)), reserve=np.tile(rs, A), N=N, tdone0=np.tile(td, (A, 1)), dev=dev)
        starts = np.stack([rng.permutation(n)[:N] for _ in range(B)])          # same starts across augmentations
        force = torch.as_tensor(np.tile(starts, (A, 1)).reshape(-1), device=dev)
        # lr / entropy schedules
        lr = a.lr * min(1.0, (state["it"] + 1) / 200) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(frac, 1.0))))
        for g in opt.param_groups:
            g["lr"] = lr
        ent = a.ent0 + (a.ent1 - a.ent0) * min(frac, 1.0)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
            o = rollout(pol, bt)
        F = o["F"].view(A, B, N).permute(1, 0, 2).reshape(B, A * N)          # group per original instance
        base = F.mean(1, keepdim=True); sd = F.std(1, keepdim=True).clamp(min=1e-3)
        adv = (-(F - base) / sd).reshape(B, A, N).permute(1, 0, 2).reshape(-1)
        opt.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
            h = pol.encode(bt)
        hd = h.detach().float().requires_grad_(True)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
            mlp, ment = replay_grad(pol, bt, o["acts"], adv.detach(), force=force, hd=hd, ent_coef=ent, chunk=a.chunk)
        h.float().backward(hd.grad)
        gn = float(torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0))
        opt.step()
        state["it"] += 1; state["samples"] += B * A * N
        state["elapsed"] = time.time() - t_start
        if state["it"] % 10 == 0:
            ok = ~o["fail"]
            rec = dict(it=state["it"], h=round(state["elapsed"] / 3600, 4), ns=ns, n=n, B=B, F=float(o["F"][ok].mean()) if ok.any() else None,
                       fail=float(o["fail"].float().mean()), ent=round(ment, 4), gn=round(gn, 3), lr=lr, samples=state["samples"])
            print(json.dumps(rec), flush=True)
        if state["it"] % a.val_every == 0 or state["elapsed"] >= budget:
            g1, g8 = validate(pol, dev, devset)
            extra_val = {}
            for nm, ds in devsets[1:]:
                e1, e8 = validate(pol, dev, ds); extra_val[f"val_{nm}_aug8"] = e8
            log.write(it=state["it"], h=state["elapsed"] / 3600, samples=state["samples"], val_greedy=g1, val_aug8=g8, val_set=devsets[0][0], **extra_val)
            score = g8 if g8 is not None else g1
            if state["best"] is None or score < state["best"]:
                state["best"] = score; save_route(pol, os.path.join(a.out, "best.pt"), it=state["it"], val=score)
            print(f"[val] it={state['it']} greedy={g1:+.2f}% aug8={g8:+.2f}% best={state['best']:+.2f}%", flush=True)
        if time.time() - t_ck > a.ckpt_min * 60:
            atomic_save(dict(sd=pol.state_dict(), opt=opt.state_dict(), state=state, cfg=pol.cfg), last); t_ck = time.time()
    atomic_save(dict(sd=pol.state_dict(), opt=opt.state_dict(), state=state, cfg=pol.cfg), last)
    save_route(pol, os.path.join(a.out, "final.pt"), it=state["it"])
    if not os.path.exists(os.path.join(a.out, "best.pt")):
        save_route(pol, os.path.join(a.out, "best.pt"), it=state["it"])
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(state))
    progress(f"route_train {a.out} done: it={state['it']} best_val={state['best']}")


if __name__ == "__main__":
    main()
