"""pi_site v3: learned siting over the EXACT coverage-feasible set (CFL), trained by REINFORCE on simulated J5.

Why a selector over exact covers (and not a free autoregressive siting decoder as in v2): with the strict-completion
coverage constraint (Q_rho, rho = 3000 m) the feasible siting set is tiny on the paper's test maps (96 % of maps
have a unique minimum-cost cover); v2's free decoder had to "learn" feasibility and drifted to opening all DABS.
Here feasibility is guaranteed by construction (every candidate is a cover; MinCov is always a candidate) and the
policy only decides WHICH feasible cover, trading fixed cost against storm robustness/lateness -> any J5 gain of
pi_site is measured together with its fixed cost and #DABS (reported), and the 'eqcost' budget variant (only covers
of minimum fixed cost) isolates gains that cannot come from extra stations.

Candidates : enumerate_feasible(cS, cD, budget = mincost + delta, kmax)  (+ MinCov), delta=0 -> 'eqcost'.
Features   : fixed cost, #DABS/#SABS, extra cost vs MinCov, pi_route greedy route cost (batched, GPU), coverage
             redundancy, load balance, distance statistics  ->  MLP scorer -> softmax over candidates.
Training   : generated maps (sizes with siting freedom: 10_110 .. 15_200), m sampled covers per map, reward =
             -mean J5 over K training-weather days (pi_route pomo plan + exec policy, WX5 sim), shared baseline.
SimOpt-J5  : non-learned baseline: evaluate the cheapest C covers with K' days and pick the best (same simulator).
"""
import os, sys, json, time, argparse, glob
import numpy as np, torch, torch.nn as nn
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, seed_all, gen, read_instance, from_instance, JsonlLog, progress, atomic_save
from e2e import coverage as CV
from e2e.sitings import cov_mats
from e2e.route_model import load_route, rollout
from e2e.route_env import Batch

SIZES = [(10, 110), (12, 150), (13, 170), (15, 200)]
SMOKE_SIZES = [(4, 14), (5, 20)]
NF = 12


def candidates(tg, st, delta, kmax):
    P, cS, cD = CV.support(tg, st)
    t0 = np.asarray(CV.min_cover(cS, cD)); c0 = CV.fixed_cost(t0)
    F = CV.enumerate_feasible(cS, cD, budget=c0 + delta + 1e-6, kmax=kmax)
    F = [np.asarray(f) for f in F]
    if not any((f == t0).all() for f in F):
        F = [t0] + F
    F = sorted(F, key=lambda f: (CV.fixed_cost(f), -int((f == 2).sum())))[:kmax]
    return np.array(F, dtype=np.int64), t0


def route_costs(rpol, tg, st, F, dev):
    R = len(F)
    with torch.no_grad():
        bt = Batch(np.repeat(tg[None], R, 0), np.repeat(st[None], R, 0), F, N=1, dev=dev)
        o = rollout(rpol, bt, greedy=True)
    c = torch.where(o["fail"], o["cost"] + 1e4, o["cost"]).cpu().numpy()
    return c, o["acts"].cpu().numpy()


def features(tg, st, F, rc):
    _, cs, cd = cov_mats(tg, st)                      # (ns, n) bool
    n = len(tg); ns = len(st); D = np.linalg.norm(tg[:, None] - st[None], axis=-1)    # (n, ns)
    fx = np.array([CV.fixed_cost(f) for f in F]); X = np.zeros((len(F), NF), np.float32)
    for k, f in enumerate(F):
        cov = ((f == 2)[:, None] & cd) | ((f == 1)[:, None] & cs)
        red = cov.sum(0); op = np.where(f > 0)[0]
        dn = D[:, op].min(1); asg = op[np.argmin(D[:, op], 1)]; load = np.bincount(asg, minlength=ns)[op]
        X[k] = [fx[k] / 100, (f == 2).sum() / ns, (f == 1).sum() / ns, (fx[k] - fx.min()) / 50, (rc[k] - fx[k]) / 1000,
                (rc[k] - rc.min()) / 100, red.mean() / 3, (red >= 2).mean(), load.max() / n, dn.mean() / 5000,
                np.quantile(dn, 0.9) / 5000, len(op) / ns]
    return X


class SiteSel(nn.Module):
    def __init__(self, d=128):
        super().__init__(); self.cfg = dict(d=d)
        self.f = nn.Sequential(nn.Linear(2 * NF, d), nn.ReLU(), nn.Linear(d, d), nn.ReLU(), nn.Linear(d, 1))

    def forward(self, X):                             # X (C, NF) -> logits (C,)
        Xc = X - X.mean(0, keepdim=True)              # instance-relative features (permutation-invariant set)
        return self.f(torch.cat([X, Xc], -1)).squeeze(-1)


def choose(ins, ckpt, cache):
    """plan_v3 hook: greedy choice of the trained selector. Returns (types, info)."""
    if ckpt not in cache:
        dev = device(); ck = torch.load(ckpt, map_location=dev, weights_only=False)
        net = SiteSel(**ck["cfg"]).to(dev); net.load_state_dict(ck["sd"]); net.eval()
        rp = ck["route"] if os.path.isabs(ck["route"]) else os.path.join(ROOT, ck["route"])
        cache[ckpt] = (net, load_route(rp, dev)[0], ck["delta"], ck["kmax"], dev)
    net, rpol, delta, kmax, dev = cache[ckpt]
    tg, st, _, _ = from_instance(ins)
    F, t0 = candidates(tg, st, delta, kmax); rc, _ = route_costs(rpol, tg, st, F, dev)
    with torch.no_grad():
        lg = net(torch.as_tensor(features(tg, st, F, rc), device=dev))
    k = int(torch.argmax(lg))
    return F[k], dict(site_ncand=len(F), site_pick_fixed=CV.fixed_cost(F[k]), site_mincov_fixed=CV.fixed_cost(t0))


def _cand_job(job):
    try:
        tg, st = job["tg"], job["st"]
        F, t0 = candidates(tg, st, job["delta"], job["kmax"])
        return dict(F=F, t0=t0)
    except Exception as e:
        return dict(error=repr(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--route", required=True)
    ap.add_argument("--exec", default="N6_90_0.25", help="execution policy inside the J5 reward (dyn_eval spec)")
    ap.add_argument("--delta", type=float, default=90.0, help="fixed-cost budget above MinCov (0 = eqcost)")
    ap.add_argument("--kmax", type=int, default=32); ap.add_argument("--B", type=int, default=12)
    ap.add_argument("--m", type=int, default=4); ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--hours", type=float, default=2.0); ap.add_argument("--max_iters", type=int, default=10 ** 9)
    ap.add_argument("--lr", type=float, default=3e-4); ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--n_dev", type=int, default=24); ap.add_argument("--dev_every", type=int, default=10)
    ap.add_argument("--adapt", default=None)
    # SimOpt-J5 baseline
    ap.add_argument("--simopt", action="store_true"); ap.add_argument("--inst", default=""); ap.add_argument("--C", type=int, default=12)
    a = ap.parse_args()
    dev = device(); seed_all(a.seed)
    rpol, _ = load_route(a.route, dev)
    from multiprocessing import get_context
    from e2e import dyn_eval as DE
    pool = get_context("spawn").Pool(a.workers, maxtasksperchild=100)
    if a.simopt:
        return simopt(a, rpol, dev, pool, DE)
    os.makedirs(a.out, exist_ok=True)
    net = SiteSel().to(dev); opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    stf = os.path.join(a.out, "state.json"); st_ = json.load(open(stf)) if os.path.exists(stf) else dict(it=0, elapsed=0.0, best=None)
    if os.path.exists(os.path.join(a.out, "last.pt")):
        ck = torch.load(os.path.join(a.out, "last.pt"), map_location=dev, weights_only=False); net.load_state_dict(ck["sd"])
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    sizes = SMOKE_SIZES if a.smoke else SIZES
    rng = np.random.default_rng(a.seed + 1000 * st_["it"])
    drng = np.random.default_rng(424242)
    devmaps = [gen(n, ns, drng) for ns, n in [sizes[k % len(sizes)] for k in range(a.n_dev)]]
    devmaps = [(tg, st) for tg, st in devmaps]
    devc = pool.map(_cand_job, [dict(tg=tg, st=st, delta=a.delta, kmax=a.kmax) for tg, st in devmaps])

    def plan_acts(tg, st, F):
        rc, acts = route_costs(rpol, tg, st, F, dev); return rc, acts

    def j5_many(items, days):
        jobs = [dict(tg=tg, st=st, types=f, acts=ac, exec=a.exec, days=days, adapt=a.adapt) for tg, st, f, ac in items]
        res = pool.map(DE.j5_job, jobs, chunksize=1)
        return [np.mean([m["J"] for m in r]) if r and all(m["complete_strict"] for m in r) else (np.mean([m["J"] for m in r]) + 1e3 if r else 1e5) for r in res]

    def dev_eval():
        items_net, items_min = [], []
        for (tg, st), c in zip(devmaps, devc):
            F = c["F"]; rc, acts = plan_acts(tg, st, F)
            with torch.no_grad():
                k = int(torch.argmax(net(torch.as_tensor(features(tg, st, F, rc), device=dev))))
            k0 = int(next(q for q in range(len(F)) if (F[q] == c["t0"]).all()))
            items_net.append((tg, st, F[k], acts[k])); items_min.append((tg, st, F[k0], acts[k0]))
        days = list(range(8_100_000, 8_100_000 + (2 if a.smoke else 6)))
        Jn = j5_many(items_net, days); Jm = st_.get("dev_min") or j5_many(items_min, days); st_["dev_min"] = list(map(float, Jm))
        return float(np.mean(Jn)), float(np.mean(Jm)), float(np.mean([CV.fixed_cost(x[2]) for x in items_net]))

    t0 = time.time() - st_["elapsed"]
    while st_["it"] < a.max_iters and time.time() - t0 < a.hours * 3600:
        maps = [gen(n, ns, rng) for ns, n in [sizes[int(rng.integers(len(sizes)))] for _ in range(a.B)]]
        cs = pool.map(_cand_job, [dict(tg=tg, st=st, delta=a.delta, kmax=a.kmax) for tg, st in maps])
        items, meta = [], []
        for (tg, st), c in zip(maps, cs):
            if "error" in c or len(c["F"]) < 2:
                continue
            F = c["F"]; rc, acts = plan_acts(tg, st, F)
            X = torch.as_tensor(features(tg, st, F, rc), device=dev)
            p = torch.softmax(net(X), 0).detach().cpu().numpy()
            ks = rng.choice(len(F), size=a.m, replace=True, p=p)
            meta.append((X, ks))
            items += [(tg, st, F[k], acts[k]) for k in ks]
        if not meta:
            continue
        days0 = 5_500_000 + 1000 * st_["it"]
        J = np.array(j5_many(items, list(range(days0, days0 + a.K)))).reshape(len(meta), a.m)
        loss = 0.0
        for (X, ks), Jr in zip(meta, J):
            lg = net(X); lp = torch.log_softmax(lg, 0)
            adv = -(Jr - Jr.mean()) / (abs(Jr.mean()) * 0.02 + 1e-6)
            loss = loss - (torch.as_tensor(adv, dtype=torch.float32, device=dev) * lp[torch.as_tensor(ks, device=dev)]).mean() \
                - a.ent * (-(lp.exp() * lp).sum())
        loss = loss / len(meta)
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        st_["it"] += 1; st_["elapsed"] = time.time() - t0
        rec = dict(it=st_["it"], J=float(J.mean()), loss=float(loss))
        if st_["it"] % a.dev_every == 0 or st_["it"] == 1:
            jn, jm, fx = dev_eval(); rec.update(dev_J=jn, dev_J_mincov=jm, dev_fixed=fx)
            if st_["best"] is None or jn < st_["best"]:
                st_["best"] = jn
                atomic_save(dict(sd=net.state_dict(), cfg=net.cfg, route=a.route, delta=a.delta, kmax=a.kmax, it=st_["it"], dev=rec), os.path.join(a.out, "best.pt"))
        atomic_save(dict(sd=net.state_dict(), cfg=net.cfg, route=a.route, delta=a.delta, kmax=a.kmax), os.path.join(a.out, "last.pt"))
        json.dump(st_, open(stf, "w")); log.write(**rec); print(json.dumps(rec), flush=True)
    if not os.path.exists(os.path.join(a.out, "best.pt")):
        atomic_save(dict(sd=net.state_dict(), cfg=net.cfg, route=a.route, delta=a.delta, kmax=a.kmax), os.path.join(a.out, "best.pt"))
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(st_))
    progress(f"site_v3 {a.out} done it={st_['it']} best_dev={st_['best']}")


def simopt(a, rpol, dev, pool, DE):
    """SimOpt-J5 (non-learned): cheapest C covers x K training days -> best mean J5. Writes plan rows (siting only)."""
    files = sorted(glob.glob(os.path.join(ROOT, a.inst)))
    done = {json.loads(l)["path"] for l in open(a.out)} if os.path.exists(a.out) else set()
    with open(a.out, "a") as f:
        for p in files:
            rel = os.path.relpath(p, ROOT)
            if rel in done:
                continue
            ins = read_instance(p); tg, st, _, _ = from_instance(ins); t0 = time.time()
            F, tmin = candidates(tg, st, a.delta, a.C); rc, acts = route_costs(rpol, tg, st, F, dev)
            jobs = [dict(tg=tg, st=st, types=F[k], acts=acts[k], exec=a.exec, days=list(range(5_900_000, 5_900_000 + a.K)), adapt=a.adapt) for k in range(len(F))]
            res = pool.map(DE.j5_job, jobs, chunksize=1)
            J = [np.mean([m["J"] for m in r]) if r else 1e9 for r in res]; k = int(np.argmin(J))
            row = dict(path=rel, method=f"simopt_d{int(a.delta)}", solution=dict(station_types=[int(x) for x in F[k]]), n_cand=len(F),
                       J_train=float(J[k]), fixed_cost=CV.fixed_cost(F[k]), mincov_fixed=CV.fixed_cost(tmin), wall=time.time() - t0)
            f.write(json.dumps(row) + "\n"); f.flush(); print("[simopt]", rel, row["fixed_cost"], row["mincov_fixed"], flush=True)


if __name__ == "__main__":
    main()
