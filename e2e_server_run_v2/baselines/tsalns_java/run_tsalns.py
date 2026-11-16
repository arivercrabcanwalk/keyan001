"""Run the author's TSALNS (Java, patched only for budgets/IO) on a set of instances with a wall-clock budget and
write official-format plan rows (data/plans format). Usage:
  python baselines/tsalns_java/run_tsalns.py --inst 'data/instances/test/*.txt' --secs 10 --out data/plans/test_ts10.jsonl --workers 40"""
import os, sys, json, glob, argparse, subprocess, time
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
    path, secs, java, cp, reserve = args
    ins = read_instance(os.path.join(ROOT, path))
    t0 = time.time()
    import resource
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    # REVIEW FIX (R-tsjvm): one JVM per core -> serial GC + limited JIT threads, so 38 concurrent JVMs do not
    # oversubscribe the CPU (which would silently cripple the baseline); CPU seconds are recorded.
    out = subprocess.run([java, "-XX:+UseSerialGC", "-XX:CICompilerCount=2", f"-Dsecs={secs}", f"-Dreserve={reserve}", "-Diters=100000000", "-cp", cp, "test1.Main", os.path.join(ROOT, path)],
                         capture_output=True, text=True, timeout=max(120, 20 * secs))
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_s = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    sol = convert(ins, out.stdout)
    ev = evaluate(ins, sol)
    return dict(path=path, method="tsalns" + (f"_r{reserve}" if reserve else ""), sec=secs, reserve=reserve, wall=time.time() - t0, cpu_s=cpu_s, plan_obj=ev["cost"], cost=ev["cost"],
                feasible=ev["feasible"], issues=ev["issues"][:5], solution=sol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--secs", type=float, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--java", default=os.environ.get("JAVA", "java"))  # REVIEW: use --workers <= physical cores; ap.add_argument("--reserve", type=float, default=0.0)
    a = ap.parse_args()
    cp = os.path.join(HERE, "build", "classes")
    files = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, a.inst)))
    done = {json.loads(l)["path"] for l in open(a.out)} if os.path.exists(a.out) else set()
    todo = [(p, a.secs, a.java, cp, a.reserve) for p in files if p not in done]
    from multiprocessing import Pool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with Pool(a.workers) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(one, todo):
            f.write(json.dumps(r) + "\n"); f.flush()
            print(f"[tsalns] {r['path']} {a.secs}s cost={r['cost']:.2f} feas={r['feasible']}", flush=True)


if __name__ == "__main__":
    main()
