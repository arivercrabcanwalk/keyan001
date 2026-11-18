"""Run the author's TSALNS (Java, patched only for budgets/IO) on a set of instances with a wall-clock budget and
write official-format plan rows (data/plans format). Usage:
  python baselines/tsalns_java/run_tsalns.py --inst 'data/instances/test/*.txt' --secs 10 --out data/plans/test_ts10.jsonl --workers 40"""
import os, sys, json, glob, argparse, subprocess, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from e2e.common import read_instance, evaluate, to_solution


def convert(ins, text):
    """TRIP a b t: ids  (a = station index in file order, b = drone slot, t = station type) -> official solution."""
    S = len(ins.stations); sids = {s.id for s in ins.stations}
    types = [0] * S; routes = [[[], []] for _ in range(S)]
    for l in text.splitlines():
        if not l.startswith("TRIP"):
            continue
        h, ids = l.split(":"); _, a, b, t = h.split(); a, b, t = int(a), int(b), int(t)
        if t == 0:
            continue
        types[a] = t
        tg = [int(x) for x in ids.split() if int(x) not in sids and int(x) != 0]
        if not tg:
            continue
        di = 1 if t == 1 else (0 if b == 0 else 1)
        routes[a][di].append(tg)
    return to_solution(ins, types, routes)


def one(args):
    path, secs, java, cp, reserve, cov, fix, tag = args
    ins = read_instance(os.path.join(ROOT, path))
    extra = []
    if cov or fix:
        from e2e import coverage as CV
        P, cS, cD = CV.for_instance(ins, ROOT)
    if cov:
        import tempfile
        fd, cf = tempfile.mkstemp(suffix=".cov", prefix=ins.name + "_"); os.close(fd)
        np.savetxt(cf, P, fmt="%.4f")
        extra.append(f"-Dcovfile={cf}")
    if fix:
        types = fix if isinstance(fix, list) else CV.min_cover(cS, cD)
        extra.append("-Dfixtypes=" + ",".join(str(int(t)) for t in types))
    t0 = time.time()
    import resource
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    # REVIEW FIX (R-tsjvm): one JVM per core -> serial GC + limited JIT threads, so 38 concurrent JVMs do not
    # oversubscribe the CPU (which would silently cripple the baseline); CPU seconds are recorded.
    out = subprocess.run([java, "-XX:+UseSerialGC", "-XX:CICompilerCount=2", f"-Dsecs={secs}", f"-Dreserve={reserve}", "-Diters=100000000"] + extra + ["-cp", cp, "test1.Main", os.path.join(ROOT, path)],
                         capture_output=True, text=True, timeout=max(120, 20 * secs))
    if cov:
        os.unlink(cf)
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_s = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    sol = convert(ins, out.stdout)
    n_restored = 0
    # v3: TRIP lines only list stations that carry trips, so an opened-but-unused station is lost in conversion.
    # Restore the siting the author's search actually held (fixed types / coverage-repaired types); its fixed cost
    # is charged by the official evaluator below (upgrades only -> never cheaper than the Java objective).
    if fix:
        ft = [int(t) for t in types]
        n_restored = sum(1 for a, b in zip(sol["station_types"], ft) if a != b)
        sol["station_types"] = [max(int(a), b) for a, b in zip(sol["station_types"], ft)]
    if cov and not CV.feasible(sol["station_types"], cS, cD):
        rt = [int(t) for t in CV.repair(sol["station_types"], cS, cD)]
        n_restored = sum(1 for a, b in zip(sol["station_types"], rt) if a != b); sol["station_types"] = rt
    ev = evaluate(ins, sol)
    row = dict(path=path, method="tsalns" + (f"_r{reserve}" if reserve else "") + (f"_{tag}" if tag else ""), sec=secs, reserve=reserve, wall=time.time() - t0, cpu_s=cpu_s, plan_obj=ev["cost"], cost=ev["cost"],
                feasible=ev["feasible"], issues=ev["issues"][:5], solution=sol)
    if cov or fix:
        row["cov_feasible"] = CV.feasible(sol["station_types"], cS, cD); row["n_dabs"] = int(sum(1 for t in sol["station_types"] if t == 2))
        row["fixed_cost"] = CV.fixed_cost(sol["station_types"]); row["n_restored"] = n_restored
        if fix and list(sol["station_types"]) != [int(t) for t in (fix if isinstance(fix, list) else CV.min_cover(cS, cD))]:
            row["fix_violated"] = True
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--secs", type=float, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--java", default=os.environ.get("JAVA", "java"))  # REVIEW: use --workers <= physical cores
    ap.add_argument("--reserve", type=float, default=0.0)   # v3: fixes the v2 bug (argument was inside a comment; server patch P1)
    ap.add_argument("--cov", type=int, default=0, help="v3 TS-CC: hard emergency-coverage constraint (e2e/coverage.py support set)")
    ap.add_argument("--fix", default="", help="v3 TS-FIX: siting fixed. 'mincov' (exact min-cost cover) or a plan jsonl whose station_types are used")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    cp = os.path.join(HERE, "build", "classes")
    files = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, a.inst)))
    done = {json.loads(l)["path"] for l in open(a.out)} if os.path.exists(a.out) else set()
    fixmap = {}
    if a.fix and a.fix != "mincov":
        for l in open(a.fix if os.path.isabs(a.fix) else os.path.join(ROOT, a.fix)):
            r = json.loads(l); fixmap[r["path"]] = r["solution"]["station_types"]
    todo = [(p, a.secs, a.java, cp, a.reserve, a.cov, (fixmap.get(p) if fixmap else ("mincov" if a.fix == "mincov" else "")), a.tag)
            for p in files if p not in done]
    if fixmap:
        todo = [t for t in todo if t[6]]
    from multiprocessing import Pool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with Pool(a.workers) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(one, todo):
            f.write(json.dumps(r) + "\n"); f.flush()
            print(f"[tsalns] {r['path']} {a.secs}s cost={r['cost']:.2f} feas={r['feasible']} cov={r.get('cov_feasible')} types={r['solution']['station_types']}", flush=True)


if __name__ == "__main__":
    main()
