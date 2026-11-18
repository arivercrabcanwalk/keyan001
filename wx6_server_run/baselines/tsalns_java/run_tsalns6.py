"""Run the author's TSALNS (Java) on instances with a wall-clock budget; write plan rows.
  --cov     WX-E6 TSALNS-Cov: Omega (wx2/omega.py) passed with -Dcov, i.e. coverage inside the author's feasibility test.
            A deterministic exact MILP repair (v6/cover.py) is applied afterwards ONLY if the returned plan still leaves
            Omega uncovered (never expected; counted in 'cover_info.repaired' and reported by the gate).
  --reserve r  battery reserve (robust author variant, e2e_v2 TSr10/TSr20)
Usage: python baselines/tsalns_java/run_tsalns6.py --inst 'data/instances/test/*.txt' --secs 10 --out data/plans/x.jsonl --workers 38 [--cov]"""
import os, sys, json, glob, argparse, subprocess, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); os.environ.setdefault("WX_ROOT", ROOT)
from v6.common import read_instance, evaluate, to_solution, fixed_cost
from v6 import cover as CV
from wx2 import omega as OM


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
    # stations opened without any trip line (possible under -Dcov) are recovered from the RESULT/station print
    for l in text.splitlines():
        if l.startswith("Station ") and "(" in l and l.rstrip().endswith(")"):
            try:
                a = int(l.split()[1].rstrip(":")); t = int(l.rsplit("(", 1)[1].rstrip(")"))
                if 0 <= a < S and t in (1, 2):
                    types[a] = max(types[a], t) if types[a] else t
            except Exception:
                pass
    return to_solution(ins, types, routes)


def one(args):
    path, secs, java, cp, reserve, cov, tag = args
    ins = read_instance(os.path.join(ROOT, path))
    t0 = time.time()
    import resource
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    extra = []
    covf = None
    if cov:
        fd, covf = tempfile.mkstemp(suffix=".cov.txt"); os.close(fd)
        OM.write_cov_file(ins, covf); extra = [f"-Dcov={covf}"]
    out = subprocess.run([java, "-XX:+UseSerialGC", "-XX:CICompilerCount=2", f"-Dsecs={secs}", f"-Dreserve={reserve}",
                          "-Diters=100000000", *extra, "-cp", cp, "test1.Main", os.path.join(ROOT, path)],
                         capture_output=True, text=True, timeout=max(180, 20 * secs))
    if covf:
        os.remove(covf)
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_s = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    sol = convert(ins, out.stdout)
    unc0 = CV.n_uncovered(ins, sol["station_types"])
    info = dict(repaired=0, added_fixed=0.0, changed=[])
    if cov and unc0 > 0:
        sol, info = CV.repair(ins, sol)
    ev = evaluate(ins, sol)
    res = [l for l in out.stdout.splitlines() if l.startswith("RESULT")]
    return dict(path=path, method=tag, sec=secs, reserve=reserve, cov=int(cov), wall=time.time() - t0, cpu_s=cpu_s,
                plan_obj=ev["cost"], cost=ev["cost"], feasible=ev["feasible"], issues=ev["issues"][:5],
                uncovered_before_repair=unc0, uncovered=CV.n_uncovered(ins, sol["station_types"]), cover_info=info,
                n_dabs=sum(1 for t in sol["station_types"] if t == 2), n_open=sum(1 for t in sol["station_types"] if t > 0),
                fixed_cost=fixed_cost(sol["station_types"]), java_result=res[-1] if res else "", rc=out.returncode,
                solution=sol)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--secs", type=float, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--java", default=os.environ.get("JAVA", "java"))
    ap.add_argument("--reserve", type=float, default=0.0)
    ap.add_argument("--cov", action="store_true")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    tag = a.tag or ("tsalns" + ("_cov" if a.cov else "") + (f"_r{a.reserve}" if a.reserve else ""))
    cp = os.path.join(HERE, "build", "classes")
    if not os.path.exists(os.path.join(cp, "test1", "Main.class")):
        print("[tsalns] not built: run baselines/tsalns_java/build.sh"); return 4
    files = sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, a.inst)))
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try:
                done.add(json.loads(l)["path"])
            except Exception:
                pass
    todo = [(p, a.secs, a.java, cp, a.reserve, a.cov, tag) for p in files if p not in done]
    from multiprocessing import Pool
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    nerr = 0
    with Pool(max(1, a.workers)) as pool, open(a.out, "a") as f:
        for r in pool.imap_unordered(one, todo):
            ok = r["feasible"] and (r["uncovered"] == 0 or not a.cov)
            nerr += (not ok)
            f.write(json.dumps(r) + "\n"); f.flush()
            print(f"[tsalns] {r['path']} {a.secs}s cost={r['cost']:.2f} feas={r['feasible']} unc0={r['uncovered_before_repair']} "
                  f"rep={r['cover_info'].get('repaired',0)} ndabs={r['n_dabs']}", flush=True)
    return 0 if nerr == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
