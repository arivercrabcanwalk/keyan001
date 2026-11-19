import sys, json, math, pathlib
R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
RM = C / "route_rl_research/20261103/return_makespan"
sys.path.insert(0, str(RM)); sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix/lrphsd"))
sys.path.insert(0, str(RM / "g23/nonrl_baseline"))
import problem, scorer

def durations(inst, si, trip):
    st = inst.stations[si]
    seq = [st] + [inst.nodes[n] for n in trip] + [st]
    length = sum(math.hypot(a.x-b.x, a.y-b.y) for a, b in zip(seq, seq[1:]))
    return length/inst.params.speed + sum(inst.nodes[n].service for n in trip)

def lpt(inst, sol, official_limit):
    out = {"station_types": list(sol["station_types"]), "routes": [[[], []] for _ in inst.stations],
           "schema_version": sol.get("schema_version", 1), "instance": sol.get("instance"),
           "instance_sha256": sol.get("instance_sha256")}
    for si, kind in enumerate(sol["station_types"]):
        trips = [list(t) for slot in sol["routes"][si] for t in slot if t]
        if not trips:
            continue
        slots = (1,) if kind == 1 else ((0, 1) if kind == 2 else ())
        loads = {s: 0.0 for s in slots}
        rebuilt = {s: [] for s in slots}
        order = sorted(trips, key=lambda t: (-durations(inst, si, t), tuple(t)))
        ok = True
        for t in order:
            d = durations(inst, si, t)
            cands = []
            for s in sorted(slots, key=lambda x: (loads[x], x)):
                cap = inst.params.large_battery if s == 0 else inst.params.small_battery
                st = inst.stations[si]
                seq = [st] + [inst.nodes[n] for n in t] + [st]
                length = sum(math.hypot(a.x-b.x, a.y-b.y) for a, b in zip(seq, seq[1:]))
                energy = length/inst.params.speed*inst.params.flight_energy + sum(inst.nodes[n].energy for n in t)
                if official_limit:
                    lim = inst.params.small_duration if kind == 1 else inst.params.large_duration
                else:
                    lim = (inst.params.large_duration if kind == 2 and s == 0 else inst.params.small_duration)
                if energy <= cap + 1e-7 and loads[s] + d <= lim + 1e-7:
                    cands.append(s)
            if not cands:
                ok = False
                break
            s = cands[0]
            rebuilt[s].append(t)
            loads[s] += d
        if not ok:
            return None
        for s in slots:
            out["routes"][si][s] = rebuilt[s]
    return out

rows = []
for pop in ("g3_pop", "g3_confirm"):
    d = R / pop
    idx = json.loads((d / "population_index.json").read_text())
    for m in idx["maps"]:
        if m["status"] != "generated":
            continue
        rj = d / "author" / m["name"] / "RUN.json"
        if not rj.exists() or not json.loads(rj.read_text()).get("anchor_eligible"):
            continue
        inst = problem.read_instance(pathlib.Path(m["path"]))
        sol = json.loads((d / "author" / m["name"] / "solution.json").read_text())
        anchor = scorer.CostAnchor.from_solution(inst, sol)
        a_off = lpt(inst, sol, True)
        a_old = lpt(inst, sol, False)
        mo = scorer.score_solution(inst, a_off)["M_return"] if a_off else None
        mm = scorer.score_solution(inst, a_old)["M_return"] if a_old else None
        rows.append({"pop": pop, "map": m["name"], "anchor": anchor.makespan,
                     "lpt_official_limits": mo, "lpt_old_limits": mm})
out = pathlib.Path("<EXECUTION_PATH>")
out.write_text(json.dumps({"schema": "lpt_duty_limit_probe_v1", "rows": rows}, indent=2, sort_keys=True) + "\n")
diff = [r for r in rows if r["lpt_official_limits"] is not None and r["lpt_old_limits"] is not None
        and abs(r["lpt_official_limits"] - r["lpt_old_limits"]) > 1e-9]
print("maps", len(rows), "differ", len(diff))
for r in diff[:10]:
    print(r["pop"], r["map"], "anchor", round(r["anchor"],6),
          "official", round(r["lpt_official_limits"],6), "old", round(r["lpt_old_limits"],6))
