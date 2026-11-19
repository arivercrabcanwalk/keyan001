"""Run the author's TSALNS (Java) with a wall-clock budget on a set of instances; write official-format plan rows.
  python baselines/tsalns_java/run_tsalns.py --inst 'data/instances/train/*.txt' --secs 10 --out data/plans/train_ts.jsonl --workers 16
One JVM per worker (serial GC, 2 JIT threads) so that concurrent JVMs do not oversubscribe the CPU.  Resumable."""
import os, sys, json, glob, argparse, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from rlcore.common import read_instance, evaluate


def convert(ins, text):
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
    return {"schema_version": 1, "instance": ins.name, "instance_sha256": ins.sha256, "station_types": types, "routes": routes}


def one(args):
    path, secs, java, cp = args
    ins = read_instance(os.path.join(ROOT, path))
    t0 = time.time(); n_retry = 0
    while True:
        try:
            out = subprocess.run([java, "-XX:+UseSerialGC", "-XX:CICompilerCount=2", f"-Dsecs={secs}", "-Diters=100000000",
                                  "-cp", cp, "test1.Main", os.path.join(ROOT, path)],
                                 capture_output=True, text=True, timeout=max(60, 3 * secs + 30))
            sol = convert(ins, out.stdout)
            ev = evaluate(ins, sol)
            if ev["feasible"]:
                break
            n_retry += 1
        except subprocess.TimeoutExpired:
            n_retry += 1
        if n_retry >= 3:
            return dict(path=path, error="tsalns failed 3x", sec=secs)
    return dict(path=path, method="tsalns", sec=secs, wall=time.time() - t0, plan_obj=ev["cost"], cost=ev["cost"],
                feasible=ev["feasible"], solution=sol, n_retry=n_retry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--secs", type=float, default=10.0)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--java", default=os.environ.get("JAVA", "java")); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    cp = os.path.join(HERE, "build", "classes")
    files = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, a.inst)))
    if a.limit:
        files = files[:a.limit]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            r = json.loads(l)
            if "error" not in r:
                done.add(r["path"])
    todo = [(p, a.secs, a.java, cp) for p in files if p not in done]
    from multiprocessing import Pool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    nerr = 0
    with Pool(max(1, a.workers)) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(one, todo):
            f.write(json.dumps(r) + "\n"); f.flush()
            if "error" in r:
                nerr += 1
            print(f"[tsalns] {r['path']} {a.secs}s cost={r.get('cost')} {r.get('error', '')}", flush=True)
    sys.exit(1 if nerr else 0)


if __name__ == "__main__":
    main()
