import json, statistics, pathlib
ROOT = pathlib.Path(".")
def load(pop):
    ex = {r["map"]: r for r in json.loads((ROOT/"results"/pop/"EXACT_REASSIGN_RESULTS.json").read_text())["rows"]}
    rows = json.loads((ROOT/"results"/pop/"STRONG_NONRL_RESULTS.json").read_text())["rows"]
    by = {}
    for r in rows:
        by.setdefault(r["map"], {})[int(r["budget_s"])] = r
    return ex, by

allrows = []
for pop in ("g3_pop", "g3_confirm"):
    ex, by = load(pop)
    for m, b in by.items():
        e = ex.get(m)
        if not e or e.get("status") != "OK":
            continue
        v = b.get(12) or b.get(6)
        allrows.append({"pop": pop, "map": m, "anchor": e["anchor_M_return"],
                        "floor": e["validated_M_return"], "alns": v["M_return"],
                        "dfloor": 100*(v["M_return"]-e["validated_M_return"])/e["validated_M_return"],
                        "danchor": 100*(v["M_return"]-e["anchor_M_return"])/e["anchor_M_return"],
                        "dcost": v["cost_delta_vs_anchor"], "adm": v["admissible"]})
print("rows", len(allrows), "admissible", sum(1 for r in allrows if r["adm"]))
for grp in ("g3_pop", "g3_confirm"):
    sub = [r for r in allrows if r["pop"] == grp]
    d = [r["dfloor"] for r in sub]
    print(f"{grp:11s} n={len(sub):2d} vs floor mean={statistics.fmean(d):+7.3f}% median={statistics.median(d):+7.3f}% wins={sum(1 for x in d if x<-1e-9)} losses={sum(1 for x in d if x>1e-9)}")
d = [r["dfloor"] for r in allrows]
print(f"{'ALL':11s} n={len(d):2d} vs floor mean={statistics.fmean(d):+7.3f}% median={statistics.median(d):+7.3f}% wins={sum(1 for x in d if x<-1e-9)} losses={sum(1 for x in d if x>1e-9)}")
da = [r["danchor"] for r in allrows]
print(f"{'ALL':11s} vs anchor mean={statistics.fmean(da):+7.3f}% median={statistics.median(da):+7.3f}%")
print("\nlargest gains vs floor:")
for r in sorted(allrows, key=lambda x: x["dfloor"])[:12]:
    print(f"  {r['map']:11s} anchor={r['anchor']:8.3f} floor={r['floor']:8.3f} alns={r['alns']:8.3f} vsfloor={r['dfloor']:+7.2f}% dcost={r['dcost']:+.3f}")
