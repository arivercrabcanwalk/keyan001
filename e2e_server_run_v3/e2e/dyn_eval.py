"""Dynamic evaluation in the WX5 simulator (shared feasibility layer: 100 % completion rules, backup drone, latest
departure, urgent guarantee). Plans: official-format solutions (ours or the author's TSALNS). Execution methods:
  A1 (author-style: execute plan, no hold) | N6_90_0.25 | Rfc_N6_90_0.25 (event-triggered TSALNS-style re-opt)
  RL5:<npz> (v5 ES layer) | ppo:<ckpt>[:noreroute|:always]   (ours: PPO exec + learned REROUTE)
Resumable CLI: one jsonl row per (plan_set, inst, method, day, scenario)."""
import os, sys, json, time, argparse, traceback, hashlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, Instance, Node, Parameters, read_instance, to_solution
os.environ.setdefault("WX_ROOT", ROOT)
from wx2 import sim as S, planadapt as PA, const as C, evaljob as EJ   # noqa: E402

SCEN = {"base": dict(mode="storm"), "uniform": dict(mode="uniform"), "sigma15": dict(mode="storm", sigma_scale=1.5),
        "ncbias": dict(mode="storm", nc_bias=0.3), "stress": dict(mode="storm", lam=3.5, p_f=0.5)}
_PPO = {}


def build_ins(tg, st, name="gen"):
    tgt = tuple(Node(k + 1, float(x), float(y), 0.2, 10.0) for k, (x, y) in enumerate(tg))
    sts = tuple(Node(len(tg) + k + 1, float(x), float(y), 0.0, 0.0) for k, (x, y) in enumerate(st))
    h = hashlib.sha256(np.ascontiguousarray(np.concatenate([tg, st])).tobytes()).hexdigest()
    return Instance(name, tgt, sts, h, Parameters())


def sol_from_acts(ins, types, acts):
    from e2e.route_env import decode_actions
    n = len(ins.targets); ns = len(ins.stations); tid = [t.id for t in ins.targets]
    routes = decode_actions(acts, n, ns, types)
    return to_solution(ins, list(types), [[[[tid[j] for j in trip] for trip in dr] for dr in s] for s in routes])


def get_policy(spec, router=None):
    # ---- v3 specs ----
    if spec.startswith("OFF+"):                       # non-RL rule counterpart: offload-when-beneficial + inner policy
        from e2e import exec_v3 as X3
        return X3.make_rule_off(get_policy(spec[4:], router))
    if spec.startswith(("v3:", "v3s:")):
        from e2e import exec_v3 as X3
        parts = spec.split(":")
        path = parts[1] if os.path.isabs(parts[1]) else os.path.join(ROOT, parts[1])
        if path not in _PPO:
            import torch
            _PPO[path] = (torch.load(path, map_location="cpu", weights_only=False)["P"], None)
        P = _PPO[path][0]
        opts = parts[2:]
        allow_off = "nooff" not in opts
        if spec.startswith("v3s:"):                    # v3s:<ckpt>:<deadline ms>[:M<k>]
            ms = float(opts[0]) if opts and opts[0].replace(".", "").isdigit() else 100.0
            M = next((int(o[1:]) for o in opts if o.startswith("M")), 32)
            return X3.make_search_policy(P, M=M, deadline_ms=ms, allow_off=allow_off)
        return X3.make_policy(P, greedy=True, allow_off=allow_off)
    if spec.startswith("RLR:"):                        # v5 RL5 + the same fair rollout search (compute-matched)
        from wx2 import twin as TW, qnet as QN
        _, ck, ms = spec.split(":")
        base = QN.make_policy_any(QN.load_any(ck if os.path.isabs(ck) else os.path.join(ROOT, ck)), greedy=True)
        return TW.make_rollout_v3(M=32, base=base, deadline_ms=float(ms), fair=True)
    if spec.startswith("N4fd:"):                       # N4fd:<M>:<ms>:<base rule>  fair rollout over a rule base
        from wx2 import twin as TW, policies as PL
        _, M, ms, bname = spec.split(":", 3)
        return TW.make_rollout_v3(M=int(M), base=PL.name_policy(bname), deadline_ms=float(ms), fair=True)
    if spec.startswith("ppo:"):
        parts = spec.split(":")
        path = parts[1]; opt = parts[2] if len(parts) > 2 else ""
        from e2e import exec_policy as EP
        if path not in _PPO:
            import torch
            ck = torch.load(path, map_location="cpu", weights_only=False)
            _PPO[path] = (ck["P"], ck.get("router"))
        P, rpath = _PPO[path]
        rpath = router or rpath
        if rpath and not os.path.isabs(rpath):
            rpath = os.path.join(ROOT, rpath)
        return EP.make_exec_policy(P, router_path=rpath, greedy=True, allow_reroute=(opt != "noreroute"), force_reroute=(opt == "always"))
    if spec.startswith("RL5:"):
        return EJ.get_pol("RL5", dict(ckpt=spec.split(":", 1)[1]))
    return EJ.get_pol(spec)


def run_day(ins, sol, day, spec, scenario="base", router=None, P=C.P_MAIN, adapt=None):
    """adapt: None/'heur' = shared heuristic repack (relocate=2, as in v5) | 'heur0' | 'rl:<router>' (REVIEW FIX R-repack)."""
    from e2e import rl_adapt as RA
    kw = SCEN[scenario]
    wx, reqs, meta = S.make_day(ins, day, **kw)
    asol, left, astats = RA.adapt(ins, sol, wx, adapt)
    pol = get_policy(spec, router)
    sim = S.Sim(ins, asol, wx, reqs, P=P)
    t0 = time.perf_counter()
    m = sim.run(pol)
    m["wall_sec"] = time.perf_counter() - t0
    m["n_reroute"] = int(getattr(sim, "n_reroute", 0)); m["n_reroute_fail"] = int(getattr(sim, "n_reroute_fail", 0))
    m["day_hash"] = meta["day_hash"]
    m["n_offload"] = int(getattr(sim, "n_offload", 0))
    m.update(astats)
    # REVIEW FIX (R-G3): plan-independent completion (siting is now a learned decision, so requests made unservable
    # by NOT opening a station must count against the method)
    m["n_unservable_all"] = RA.n_unservable_all(ins, reqs)
    m["complete_strict"] = int(m["unfinished"] == 0 and m["unserved"] - m["n_unservable_all"] <= 0)
    return m


def j5_job(job):
    """site_train J5 reward: one siting -> pi_route plan -> mean J5 over K days with the exec policy."""
    try:
        if job.get("fail"):
            return []
        ins = build_ins(job["tg"], job["st"])
        sol = sol_from_acts(ins, job["types"], job["acts"])
        return [run_day(ins, sol, d, job["exec"], adapt=job.get("adapt")) for d in job["days"]]
    except Exception:
        traceback.print_exc()
        return []


class _DayTimeout(Exception):
    pass


def _alarm(*_):
    raise _DayTimeout("day exceeded DYN_DAY_TIMEOUT")


def _job(j):
    import signal
    signal.signal(signal.SIGALRM, _alarm); signal.alarm(int(os.environ.get("DYN_DAY_TIMEOUT", "600")))
    try:
        ins = read_instance(os.path.join(ROOT, j["path"]))
        m = run_day(ins, j["sol"], j["day"], j["method"], j["scenario"], adapt=j.get("adapt"))
        signal.alarm(0)
        out = {k: v for k, v in m.items() if not isinstance(v, (list, dict))}
        out.update(plans=j["plans"], inst=ins.name, method=j["method_name"], day=j["day"], scenario=j["scenario"])
        return out
    except Exception as e:
        return dict(plans=j["plans"], inst=os.path.basename(j["path"]), method=j["method_name"], day=j["day"],
                    scenario=j["scenario"], error=repr(e), tb=traceback.format_exc()[-1500:])


def parse_days(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--plans", required=True, help="comma list of plan jsonl files (data/plans/X.jsonl or paths)")
    ap.add_argument("--methods", required=True, help="comma list; alias=spec allowed, e.g. OURS=ppo:runs/exec/best.pt")
    ap.add_argument("--days", required=True)
    ap.add_argument("--scenario", default="base")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--limit_plans", type=int, default=0)
    ap.add_argument("--adapt", default=None, help="morning plan adaptation: heur (default, v5) | heur0 | rl:<router.pt>")
    a = ap.parse_args()
    from multiprocessing import get_context
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                r = json.loads(l)
                if "error" not in r:
                    done.add((r["plans"], r["inst"], r["method"], r["day"], r["scenario"]))
            except Exception:
                pass
    jobs = []
    for pf in a.plans.split(","):
        p = pf if os.path.exists(pf) else os.path.join(ROOT, "data", "plans", pf + ".jsonl")
        pname = os.path.basename(p).replace(".jsonl", "")
        plans = [json.loads(l) for l in open(p)]
        if a.limit_plans:
            plans = plans[:a.limit_plans]
        for spec in a.methods.split(","):
            name, sp = (spec.split("=", 1) if "=" in spec else (spec, spec))
            for pl in plans:
                inst = os.path.basename(pl["path"]).replace(".txt", "")
                for d in parse_days(a.days):
                    if (pname, inst, name, d, a.scenario) in done:
                        continue
                    jobs.append(dict(path=pl["path"], sol=pl["solution"], day=d, method=sp, method_name=name,
                                     scenario=a.scenario, plans=pname, adapt=a.adapt))
    print(f"[dyn_eval] {a.out}: todo {len(jobs)} done {len(done)}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time(); n = 0; ne = 0
    with get_context("spawn").Pool(a.workers, maxtasksperchild=200) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(_job, jobs, chunksize=2):
            f.write(json.dumps(r) + "\n"); f.flush(); n += 1; ne += "error" in r
            if n % 200 == 0 or n == len(jobs):
                print(f"[dyn_eval] {n}/{len(jobs)} err={ne} {time.time()-t0:.0f}s", flush=True)
    sys.exit(0 if ne == 0 else 2)


if __name__ == "__main__":
    main()
