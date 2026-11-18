"""pi_route-J5: J5-aware fine-tuning of pi_route (bi-level: plan quality is measured by EXECUTING the plan with the
execution policy in the WX5 simulator, not by the static objective alone).

REINFORCE with a per-map shared baseline over m sampled plans (POMO-style; Kwon et al. 2020) on common random
weather (the m plans of one map are executed on the SAME K training days -> paired, low-variance advantages).
  adv = -(J5 - mean J5)/std  +  w_static * ( -(cost - mean cost)/std )        (static anchor keeps routing quality)
Sitings: S* = MinCov on generated maps (the regime of the main comparison). Exec policy: --exec (dyn_eval spec;
v3:<pi_exec best.pt> in the pipeline). Dev selection: dev maps x dev days (pomo plan -> J5 with the same exec).
Test-time: plan_v3 --mode pomo (or j5rr: rerank the policy's top-k candidates by simulated J5 on TRAINING days)."""
import os, sys, json, time, argparse
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, seed_all, gen, size_scale, read_instance, from_instance, JsonlLog, progress, atomic_save
from e2e.route_env import Batch
from e2e.route_model import rollout, replay_grad, load_route, save_route
from e2e import coverage as CV

SIZES = [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]
SMOKE_SIZES = [(3, 10), (4, 14)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--init", required=True, help="pi_route checkpoint (same seed)")
    ap.add_argument("--exec", required=True); ap.add_argument("--dev_inst", default="data/instances/dev/*.txt")
    ap.add_argument("--dev_days", default="16000-16003"); ap.add_argument("--B", type=int, default=8)
    ap.add_argument("--m", type=int, default=8); ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5); ap.add_argument("--w_static", type=float, default=0.3)
    ap.add_argument("--hours", type=float, default=3.0); ap.add_argument("--max_iters", type=int, default=10 ** 9)
    ap.add_argument("--val_every", type=int, default=20); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true"); ap.add_argument("--adapt", default=None)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    import glob
    from multiprocessing import get_context
    from e2e import dyn_eval as DE
    os.makedirs(a.out, exist_ok=True); dev = device(); seed_all(a.seed)
    last = os.path.join(a.out, "last.pt")
    pol, ck = load_route(last if os.path.exists(last) else a.init, dev)
    st_ = ck.get("state") or dict(it=0, elapsed=0.0, best=None, init=os.path.abspath(a.init), exec=a.exec)
    opt = torch.optim.AdamW(pol.parameters(), lr=a.lr, weight_decay=1e-6)
    pool = get_context("spawn").Pool(a.workers, maxtasksperchild=100)
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    sizes = SMOKE_SIZES if a.smoke else SIZES
    rng = np.random.default_rng(a.seed + 7919 * (st_["it"] + 1))
    devf = sorted(glob.glob(os.path.join(ROOT, a.dev_inst)))[: (2 if a.smoke else 10 ** 9)]
    devI = []
    for p in devf:
        ins = read_instance(p); tg, st, tid, sid = from_instance(ins); P, cS, cD = CV.for_instance(ins, ROOT)
        devI.append((tg, st, np.asarray(CV.min_cover(cS, cD))))
    ddays = DE.parse_days(a.dev_days)

    def j5(items, days):
        res = pool.map(DE.j5_job, [dict(tg=tg, st=st, types=ty, acts=ac, exec=a.exec, days=days, adapt=a.adapt) for tg, st, ty, ac in items], chunksize=1)
        return np.array([np.mean([m["J"] for m in r]) + (0 if all(m["complete_strict"] for m in r) else 1e3) if r else 1e5 for r in res])

    def dev_eval():
        from e2e.route_infer import solve_routes
        pol.eval(); items = []; sc = []
        for tg, st, ty in devI:
            c, acts = solve_routes(pol, tg, st, ty, mode="pomo", dev=dev); items.append((tg, st, ty, np.array(acts))); sc.append(c)
        pol.train()
        return float(np.mean(j5(items, ddays))), float(np.mean(sc))

    if st_["best"] is None:
        J0, c0 = dev_eval(); st_["best"] = J0; st_["dev0"] = dict(J=J0, cost=c0)
        save_route(pol, os.path.join(a.out, "best.pt"), state=dict(st_), val=J0)
        log.write(it=0, dev_J=J0, dev_cost=c0); print(json.dumps(dict(it=0, dev_J=J0, dev_cost=c0)), flush=True)
    t0 = time.time() - st_["elapsed"]; pol.train()
    while st_["it"] < a.max_iters and time.time() - t0 < a.hours * 3600:
        ns, n = sizes[int(rng.integers(len(sizes)))]
        tgs, sts, tys = [], [], []
        for _ in range(a.B):
            tg, st = gen(n, ns, rng, scale=size_scale(n, ns)); P, cS, cD = CV.support(tg, st)
            tgs.append(tg); sts.append(st); tys.append(np.asarray(CV.min_cover(cS, cD)))
        m = min(a.m, n)
        bt = Batch(np.stack(tgs), np.stack(sts), np.stack(tys), N=m, dev=dev)
        starts = np.stack([rng.permutation(n)[:m] for _ in range(a.B)])
        force = torch.as_tensor(starts.reshape(-1), device=dev)
        o = rollout(pol, bt, force=force)
        acts = o["acts"].cpu().numpy(); fail = o["fail"].cpu().numpy(); cost = o["cost"].cpu().numpy()
        days0 = 5_700_000 + 1000 * st_["it"] + 100_000 * a.seed
        items = [(tgs[b], sts[b], tys[b], acts[b * m + k]) for b in range(a.B) for k in range(m)]
        J = j5(items, list(range(days0, days0 + a.K)))
        J = np.where(fail, 1e5, J).reshape(a.B, m); C = np.where(fail, cost + 1e3, cost).reshape(a.B, m)
        adv = -(J - J.mean(1, keepdims=True)) / np.maximum(J.std(1, keepdims=True), 1.0) \
              - a.w_static * (C - C.mean(1, keepdims=True)) / np.maximum(C.std(1, keepdims=True), 1e-3)
        opt.zero_grad(set_to_none=True)
        h = pol.encode(bt); hd = h.detach().float().requires_grad_(True)
        replay_grad(pol, bt, o["acts"], torch.as_tensor(adv.reshape(-1), dtype=torch.float32, device=dev), force=force, hd=hd, chunk=16)
        h.float().backward(hd.grad); torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0); opt.step()
        st_["it"] += 1; st_["elapsed"] = time.time() - t0
        rec = dict(it=st_["it"], ns=ns, n=n, J=float(J[J < 1e4].mean()) if (J < 1e4).any() else None, cost=float(C.mean()), fail=float(fail.mean()))
        if st_["it"] % a.val_every == 0:
            Jd, cd = dev_eval(); rec.update(dev_J=Jd, dev_cost=cd)
            if Jd < st_["best"]:
                st_["best"] = Jd; save_route(pol, os.path.join(a.out, "best.pt"), state=dict(st_), val=Jd)
        save_route(pol, last, state=dict(st_)); log.write(**rec); print(json.dumps(rec), flush=True)
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(st_))
    progress(f"route_j5 {a.out} done it={st_['it']} best_dev_J={st_['best']} dev0={st_.get('dev0')}")


if __name__ == "__main__":
    main()
