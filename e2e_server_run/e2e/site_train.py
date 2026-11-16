"""Train pi_site with REINFORCE + POMO-style shared baseline over M sampled sitings per instance (different station
orders), entropy bonus, and optional expert iteration (imitate the result of the RL-owned station-set search).
Reward:
  --reward static : -(fixed + route cost of pi_route greedy)            (the author's objective)
  --reward j5     : -mean J5 over K synthetic weather days, executing the pi_route plan with the execution policy
                    (--exec N6_90_0.25 | ppo:<ckpt> | RL5:<npz>) in the WX5 simulator (CPU process pool)."""
import os, sys, json, time, math, argparse
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, seed_all, gen, size_scale, JsonlLog, progress, atomic_save
from e2e.site_model import SitePolicy, save_site
from e2e.route_model import load_route, rollout
from e2e.route_env import Batch
from e2e.site_search import search

SIZES = [(5, 35), (6, 50), (7, 65), (8, 80), (10, 110)]
SMOKE_SIZES = [(3, 10), (4, 14)]


def route_cost(rpol, tg, st, types, dev):
    """batched greedy routing cost for R sitings. tg/st (R,n,2)."""
    bt = Batch(tg, st, types, N=1, dev=dev)
    o = rollout(rpol, bt, greedy=True)
    return torch.where(o["fail"], o["cost"] + 1e3, o["cost"]), o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--hours", type=float, default=4.0)
    ap.add_argument("--max_iters", type=int, default=10 ** 9)
    ap.add_argument("--B", type=int, default=64)
    ap.add_argument("--M", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--distill_every", type=int, default=10)
    ap.add_argument("--distill_w", type=float, default=0.5)
    ap.add_argument("--reward", default="static", choices=["static", "j5"])
    ap.add_argument("--exec", default="N6_90_0.25")
    ap.add_argument("--K", type=int, default=4, help="weather days per siting (j5 reward)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--init", default="")
    ap.add_argument("--d", type=int, default=128)
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--ckpt_min", type=float, default=5.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = device(); seed_all(a.seed)
    rpol, _ = load_route(a.route, dev)
    for p in rpol.parameters():
        p.requires_grad_(False)
    pol = SitePolicy(d=a.d, layers=a.layers).to(dev)
    if a.init:
        ck = torch.load(a.init, map_location=dev, weights_only=False); pol = SitePolicy(**ck["cfg"]).to(dev); pol.load_state_dict(ck["sd"])
    opt = torch.optim.AdamW(pol.parameters(), lr=a.lr)
    state = dict(it=0, elapsed=0.0, best=None)
    last = os.path.join(a.out, "last.pt")
    if os.path.exists(last):
        ck = torch.load(last, map_location=dev, weights_only=False)
        pol = SitePolicy(**ck["cfg"]).to(dev); pol.load_state_dict(ck["sd"])
        opt = torch.optim.AdamW(pol.parameters(), lr=a.lr); opt.load_state_dict(ck["opt"]); state = ck["state"]
        print(f"[site_train] resumed it={state['it']}", flush=True)
    rng = np.random.default_rng(a.seed + 7919 * state["it"])
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    sizes = SMOKE_SIZES if a.smoke else SIZES
    pool = None
    if a.reward == "j5":
        from multiprocessing import get_context
        pool = get_context("spawn").Pool(a.workers)
    budget = a.hours * 3600; t_start = time.time() - state["elapsed"]; t_ck = time.time()
    day_ctr = 3_000_000 + 1000 * state["it"]          # training weather seeds (disjoint from dev/test days)
    while state["elapsed"] < budget and state["it"] < a.max_iters:
        ns, n = sizes[rng.integers(len(sizes))]
        B = a.B if a.reward == "static" else max(2, a.B // 8)
        inst = [gen(n, ns, rng, scale=size_scale(n, ns)) for _ in range(B)]
        tg = torch.as_tensor(np.stack([x for x, _ in inst]), dtype=torch.float32, device=dev)
        st = torch.as_tensor(np.stack([y for _, y in inst]), dtype=torch.float32, device=dev)
        M = a.M
        types, logp, ent = pol.run(tg, st, M=M)
        I = torch.arange(B, device=dev).repeat_interleave(M)
        with torch.no_grad():
            cost, o = route_cost(rpol, tg[I], st[I], types, dev)
        if a.reward == "static":
            R = cost
        else:
            from e2e import dyn_eval
            jobs = []
            for r in range(B * M):
                jobs.append(dict(tg=inst[r // M][0], st=inst[r // M][1], types=types[r].tolist(), acts=o["acts"][r].tolist(),
                                 days=[day_ctr + k for k in range(a.K)], exec=a.exec, fail=bool(o["fail"][r])))
            day_ctr += a.K
            res = pool.map(dyn_eval.j5_job, jobs, chunksize=1)
            R = torch.as_tensor([np.mean([m["J"] for m in rr]) if rr else 1e5 for rr in res], dtype=torch.float32, device=dev)
        Rb = R.view(B, M)
        adv = (-(Rb - Rb.mean(1, keepdim=True)) / Rb.std(1, keepdim=True).clamp(min=1e-3)).view(-1)
        loss = -(adv.detach() * logp).mean() - a.ent * ent.mean()
        dl = 0.0
        if a.reward == "static" and a.distill_every and state["it"] % a.distill_every == 0:
            k = min(4, B); tgt = []
            for b in range(k):
                j = int(torch.argmin(Rb[b])) + b * M
                tt, _, _ = search(rpol, inst[b][0], inst[b][1], types[j].cpu().numpy(), dev, max_rounds=3 if a.smoke else 20)
                tgt.append(tt)
            tgt = torch.as_tensor(np.stack(tgt), device=dev)
            _, lp_t, _ = pol.run(tg[:k], st[:k], M=1, forced=tgt, order=torch.stack([torch.randperm(ns, device=dev) for _ in range(k)]))
            dlt = -lp_t.mean(); loss = loss + a.distill_w * dlt; dl = float(dlt)
        opt.zero_grad(set_to_none=True); loss.backward()
        torch.nn.utils.clip_grad_norm_(pol.parameters(), 1.0); opt.step()
        state["it"] += 1; state["elapsed"] = time.time() - t_start
        rec = dict(it=state["it"], h=state["elapsed"] / 3600, ns=ns, n=n, R=float(R.mean()), R_best=float(Rb.min(1).values.mean()),
                   n_open=float((types > 0).float().sum(1).mean()), ent=float(ent.mean()), distill=dl)
        if state["it"] % 10 == 0:
            print(json.dumps(rec), flush=True); log.write(**rec)
        if time.time() - t_ck > a.ckpt_min * 60:
            atomic_save(dict(sd=pol.state_dict(), opt=opt.state_dict(), state=state, cfg=pol.cfg), last); t_ck = time.time()
            save_site(pol, os.path.join(a.out, "best.pt"), it=state["it"])
    atomic_save(dict(sd=pol.state_dict(), opt=opt.state_dict(), state=state, cfg=pol.cfg), last)
    save_site(pol, os.path.join(a.out, "best.pt"), it=state["it"])
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(state))
    if pool:
        pool.close()
    progress(f"site_train {a.out} ({a.reward}) done it={state['it']}")


if __name__ == "__main__":
    main()
