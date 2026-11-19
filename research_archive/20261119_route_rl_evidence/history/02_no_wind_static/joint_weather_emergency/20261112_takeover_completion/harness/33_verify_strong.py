import json, sys, pathlib
R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
RM = C / "route_rl_research/20261103/return_makespan"
sys.path.insert(0, str(RM)); sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix/lrphsd"))
import problem, scorer

rows = json.load(open(R / "g3_pop/STRONG_NONRL_RESULTS.json"))["rows"]
r = [x for x in rows if x["map"] == "8x80_o1" and int(x["budget_s"]) == 12][0]
inst = problem.read_instance(pathlib.Path(R / "g3_pop/maps/8x80_o1.txt"))
sol = json.loads((R / "g3_pop/author/8x80_o1/solution.json").read_text())
anchor = scorer.CostAnchor.from_solution(inst, sol)

cand = r["solution"]
sc = scorer.score_solution(inst, cand)
val = scorer.validate_candidate(inst, cand, anchor, epsilon=0.0)
print("independent rescore:")
print("  M_return      ", sc["M_return"], " stored:", r["M_return"], " match:", abs(sc["M_return"]-r["M_return"])<1e-9)
print("  cost          ", sc["cost"], " stored:", r["cost"], " match:", abs(sc["cost"]-r["cost"])<1e-9)
print("  original_feasible", sc["original_feasible"], "issues:", sc["issues"][:5])
print("  visited", sc["visited_count"], "of", len(inst.targets))
print("  admissible    ", val["admissible"], "domain_issues:", val["domain_issues"])
print("  cap satisfied ", val["cost_cap_satisfied"], " raw_cost_minus_cap:", val["raw_cost_minus_cap"])
print("  slot duties   ", [round(d["duty_min"],3) for d in sc["slot_duty"]])
print("  trips", sc["nonempty_trip_count"])
print("  energy max     ", max(t["energy"] for t in sc["trips"]))
# triangular sanity: total distance
print("  total_distance", sc["total_distance_m"])
