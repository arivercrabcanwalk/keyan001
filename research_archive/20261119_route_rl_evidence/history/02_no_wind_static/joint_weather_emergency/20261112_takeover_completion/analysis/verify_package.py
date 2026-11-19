import json, pathlib, re, statistics
ROOT = pathlib.Path(".")
issues = []
BT = chr(96)
idx = (ROOT/"INDEX.md").read_text()
pat = BT + r'([A-Za-z0-9_./-]+\.(?:md|json|csv|jsonl))' + BT
refs = set(re.findall(pat, idx))
missing = [r for r in sorted(refs) if not (ROOT/r).exists()]
print("INDEX refs:", len(refs), "missing:", missing)

stats = json.loads((ROOT/"stats/STATS.json").read_text())
pooled = {c["comparison"]: c for c in stats["sets"]["pooled_all"]["comparisons"]}
ex = pooled["exact_cost_neutral vs anchor"]
print("STATS pooled exact-vs-anchor: %.3f pct, CI %s, n=%d" % (ex["mean_delta_pct"], [round(x,3) for x in ex["ci95_mean_delta_pct"]], ex["n_maps"]))

tot = []
for pop in ("g3_pop","g3_confirm"):
    exr = {r["map"]: r for r in json.loads((ROOT/"results"/pop/"EXACT_REASSIGN_RESULTS.json").read_text())["rows"]}
    sr = json.loads((ROOT/"results"/pop/"STRONG_NONRL_RESULTS.json").read_text())["rows"]
    by = {}
    for x in sr: by.setdefault(x["map"],{})[int(x["budget_s"])]=x
    for m,b in by.items():
        e = exr.get(m)
        if not e or e.get("status")!="OK": continue
        v = b.get(12) or b.get(6)
        tot.append({"adm": v["admissible"], "df": 100*(v["M_return"]-e["validated_M_return"])/e["validated_M_return"],
                    "da": 100*(v["M_return"]-e["anchor_M_return"])/e["anchor_M_return"]})
d = [t["df"] for t in tot]; da = [t["da"] for t in tot]
print("STRONG n=%d adm=%d vs-floor mean=%.3f wins=%d losses=%d vs-anchor mean=%.3f" % (
  len(tot), sum(1 for t in tot if t["adm"]), statistics.fmean(d),
  sum(1 for x in d if x<-1e-9), sum(1 for x in d if x>1e-9), statistics.fmean(da)))

rz = (ROOT/"REPORT_ZH.md").read_text()
for token in ("11.412","10.951","3.041","13.928","22 ","33.706"):
    if token not in rz: issues.append("REPORT_ZH missing " + token)

man = json.loads((ROOT/"RESULTS_MANIFEST.json").read_text())
paths = {e["path"] for e in man["entries"]}
for p in ("results/g3_pop/STRONG_NONRL_RESULTS.json","results/g3_confirm/STRONG_NONRL_RESULTS.json",
          "STRONG_NONRL_REPORT.md","stats/STATS.json","G3_REPORT.md","REPORT_ZH.md"):
    if p not in paths: issues.append("manifest missing " + p)
print("manifest entries:", man["count"])
print("ISSUES:", issues if issues else "none")
