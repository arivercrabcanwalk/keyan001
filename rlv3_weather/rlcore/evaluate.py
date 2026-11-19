"""Evaluate methods on (plan rows x days) of one scenario.  Resumable: one jsonl row per (path, day, method).
methods: comma list of NAME=SPEC, SPEC = A1 | A1@m | GREEDY@m | REOPT@m | REOPT-W<theta>@m | rl:<ckpt.pt>
'tuned:<json>' expands baseline specs from the dev-tuning file (results/tuned_<scen>.json)."""
import os, sys, json, time, argparse
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rlcore.common import load_plans, done_keys, rel
from rlcore.scen import make_env, DEV_DAYS, TEST_DAYS
from rlcore import policies as PO


def _winit():
    import torch
    torch.set_num_threads(1)


def one(args):
    row, day, scen, name, spec = args
    t0 = time.time()
    try:
        env = make_env(row, day, scen)
        if spec.startswith("rl:"):
            from rlcore.agent import load_policy, RLPolicy
            m, fa, base = load_policy(rel(spec[3:]))
            pol = RLPolicy(m, fa, greedy=True, base=base)
        else:
            pol = PO.make(spec)
        res = PO.run_episode(env, pol)
        res.pop("per_st_J", None)
        res.update(path=row["path"], day=day, scen=scen, method=name, spec=spec, wall=time.time() - t0)
        return res
    except Exception as e:  # never silently drop: error rows are written and reported by analyze
        import traceback
        return dict(path=row["path"], day=day, scen=scen, method=name, spec=spec, error=repr(e), tb=traceback.format_exc()[-800:])


def parse_days(s):
    if s == "dev":
        return DEV_DAYS
    if s == "test":
        return TEST_DAYS
    if ":" in s:
        a, b = s.split(":"); return list(range(int(a), int(b)))
    return [int(x) for x in s.split(",")]


def expand(methods, scen):
    out = []
    for tok in methods.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("tuned:"):
            tj = json.load(open(rel(tok[6:])))
            for k, v in tj["best"].items():
                out.append((k, v))
            continue
        name, _, spec = tok.partition("=")
        out.append((name, spec or name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", required=True); ap.add_argument("--scen", required=True)
    ap.add_argument("--days", default="test"); ap.add_argument("--methods", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--maps", type=int, default=0)
    a = ap.parse_args()
    rows = load_plans(a.plans)
    if a.maps:
        rows = rows[:a.maps]
    days = parse_days(a.days)
    meths = expand(a.methods, a.scen)
    done = done_keys(a.out, lambda r: (r["path"], r["day"], r["method"], r["scen"]))
    jobs = [(r, d, a.scen, n, s) for (n, s) in meths for r in rows for d in days if (r["path"], d, n, a.scen) not in done]
    print(f"[eval] {a.scen} methods={[m[0] for m in meths]} jobs={len(jobs)} (done {len(done)})", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    import multiprocessing as mp
    nerr = 0
    with mp.get_context("spawn").Pool(a.workers, initializer=_winit) as pool, open(a.out, "a") as f:
        for k, r in enumerate(pool.imap_unordered(one, jobs, chunksize=4)):
            f.write(json.dumps(r) + "\n")
            if "error" in r:
                nerr += 1; print("[eval] ERROR", r["path"], r["day"], r["method"], r["error"], flush=True)
            if (k + 1) % 500 == 0:
                f.flush(); print(f"[eval] {k + 1}/{len(jobs)}", flush=True)
    print(f"[eval] done errors={nerr}", flush=True)
    sys.exit(1 if nerr else 0)


if __name__ == "__main__":
    main()
