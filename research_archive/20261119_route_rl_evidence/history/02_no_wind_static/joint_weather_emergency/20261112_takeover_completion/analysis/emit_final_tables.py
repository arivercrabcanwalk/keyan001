#!/usr/bin/env python3
"""Emit FINAL_TABLES.md from the frozen result files."""
from __future__ import annotations
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
POP = ROOT / "results/g3_pop"
CON = ROOT / "results/g3_confirm"
stats = json.loads((ROOT / "stats/STATS.json").read_text())


def rows(pop):
    ex = {r["map"]: r for r in json.loads((pop / "EXACT_REASSIGN_RESULTS.json").read_text())["rows"]}
    nr = json.loads((pop / "NONRL_RESULTS.json").read_text())["rows"]
    m = {}
    for r in nr:
        if "method" not in r:
            continue
        m.setdefault(r["map"], {})[r["method"] + "_" + str(int(r["budget_s"]))] = r
    return ex, m


def table(pop, label):
    ex, m = rows(pop)
    out = ["### " + label, "",
           "| map | anchor M_return | anchor cost | exact cost-neutral | delta vs anchor | LPT 6s | delta vs exact | joint 6s | joint 12s |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name in sorted(ex, key=lambda k: (ex[k].get("anchor_M_return") or 0)):
        e = ex[name]
        if e.get("status") != "OK":
            out.append("| " + name + " | - | - | ANCHOR_NOT_ELIGIBLE | - | - | - | - | - |")
            continue
        a, x = e["anchor_M_return"], e["validated_M_return"]

        def g(key):
            r = m.get(name, {}).get(key)
            if r is None:
                return "-"
            return "TIMEOUT" if r.get("status") != "ONTIME_VALID" else format(r["chosen_M_return"], ".4f")
        lpt = m.get(name, {}).get("lpt_6")
        dlt = "-" if not lpt or lpt.get("status") != "ONTIME_VALID" else format(100*(lpt["chosen_M_return"]-x)/x, "+.3f") + "%"
        out.append("| " + name + " | " + format(a, ".4f") + " | " + format(e["anchor_cost"], ".4f")
                   + " | " + format(x, ".4f") + " | " + format(100*(x-a)/a, "+.3f") + "% | "
                   + g("lpt_6") + " | " + dlt + " | " + g("joint_minmax_6") + " | " + g("joint_minmax_12") + " |")
    return "\n".join(out)


def comps():
    out = ["### Paired statistics (unit = map, B=10000, seed=20261112)", "",
           "| set | comparison | n | mean delta % | median delta % | 95% CI | W/T/L |",
           "|---|---|---|---|---|---|---|"]
    for label in ("development", "confirmation", "pooled_all"):
        b = stats["sets"].get(label)
        if not b:
            continue
        for c in b["comparisons"]:
            ci = c["ci95_mean_delta_pct"]
            cis = ("[" + format(ci[0], "+.3f") + ", " + format(ci[1], "+.3f") + "]") if ci else "n/a"
            out.append("| " + label + " | " + c["comparison"] + " | " + str(c["n_maps"]) + " | "
                       + format(c["mean_delta_pct"], "+.3f") + " | " + format(c["median_delta_pct"], "+.3f")
                       + " | " + cis + " | " + str(c["wins"]) + "/" + str(c["ties"]) + "/" + str(c["losses"]) + " |")
    b = stats["sets"].get("pooled_all") or {}
    if b.get("failures_by_method"):
        out += ["", "### Failure denominator (ITT: a failed run is scored as falling back to the anchor)", "",
                "| method | failures | maps |", "|---|---|---|"]
        for k, v in b["failures_by_method"].items():
            out.append("| " + k + " | " + str(len(v)) + " / " + str(b["n_maps_anchor_valid"])
                       + " | " + ", ".join(sorted(v)) + " |")
    return "\n".join(out)


doc = ["# FINAL_TABLES - G3 development + confirmation (2026-11-12)", "",
       "Generated from results/g3_pop/, results/g3_confirm/ and stats/STATS.json.",
       "delta vs anchor = change in M_return from exact cost-neutral reassignment (negative is better).",
       "delta vs exact = LPT against that floor. TIMEOUT = no on-time valid output was delivered.",
       "", comps(), "", table(POP, "Development set (ordinal 1, 12 maps, 11 valid)"), "",
       table(CON, "Confirmation set (ordinals 2-4, 36 maps, 36 valid)"), ""]
(ROOT / "FINAL_TABLES.md").write_text("\n".join(doc) + "\n", encoding="utf-8")
print("wrote FINAL_TABLES.md")
