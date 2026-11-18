"""v3 author-adaptation plan builders (non-RL, deterministic) on top of the AUTHOR's TSALNS plans:
  cr  : TS-CR  = TSALNS plan + minimum-cost coverage REPAIR (exact MILP, upgrades only); routes unchanged,
                 newly opened / upgraded stations get no planned trips (they serve emergencies and take hand-overs).
  pad : PAD    = TSALNS plan with EVERY candidate station opened as DABS; routes unchanged (v2 local control).
Rows keep the author's routes so these arms isolate "siting repair" from "route re-optimisation" (TS-FIX / TS-CC
re-run the author's Java TSALNS with the coverage constraint / fixed siting; see baselines/tsalns_java)."""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, read_instance, evaluate
from e2e import coverage as CV


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--out", required=True); ap.add_argument("--mode", choices=["cr", "pad"], required=True)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    n_bad = 0
    with open(a.out, "w") as f:
        for l in open(a.src):
            r = json.loads(l); s = r["solution"]; ins = read_instance(os.path.join(ROOT, r["path"]))
            P, cS, cD = CV.for_instance(ins, ROOT)
            t0 = list(s["station_types"])
            t1 = CV.repair(t0, cS, cD) if a.mode == "cr" else [2] * len(t0)
            # SABS -> DABS upgrade: the SABS small-drone trips move to the DABS small drone (slot 1); slot 0 empty
            s["station_types"] = [int(x) for x in t1]
            s["routes"] = [rt if rt else [[], []] for rt in s["routes"]]
            ev = evaluate(ins, s)
            ok = CV.feasible(t1, cS, cD); n_bad += (not ok) or (not ev["feasible"])
            r.update(method=f"tsalns_{a.mode}", base_types=t0, cov_feasible=ok, feasible=ev["feasible"], cost=ev["cost"],
                     n_dabs=int(sum(1 for x in t1 if x == 2)), fixed_cost=CV.fixed_cost(t1), n_upgrades=int(sum(1 for x, y in zip(t0, t1) if x != y)))
            f.write(json.dumps(r) + "\n")
            print(f"[author_adapt:{a.mode}] {r['path']} {t0} -> {t1} cost={ev['cost']:.1f} cov={ok} feas={ev['feasible']}", flush=True)
    sys.exit(1 if n_bad else 0)


if __name__ == "__main__":
    main()
