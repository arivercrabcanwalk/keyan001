#!/usr/bin/env python3
"""Emit the per-map markdown table used by G3_DEV_REPORT.md."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
POP = ROOT / "results/g3_pop"
exact = {r["map"]: r for r in json.loads((POP/"EXACT_REASSIGN_RESULTS.json").read_text())["rows"]}
nonrl = json.loads((POP/"NONRL_RESULTS.json").read_text())["rows"]
m = {}
for r in nonrl:
    if r.get("status") == "ONTIME_VALID":
        m.setdefault(r["map"], {})[f'{r["method"]}_{int(r["budget_s"])}'] = r["chosen_M_return"]
rows = []
for name in sorted(exact, key=lambda k: exact[k].get("anchor_M_return") or 0):
    e = exact[name]
    if e.get("status") != "OK":
        continue
    a = e["anchor_M_return"]; x = e["validated_M_return"]; l = m.get(name, {}).get("lpt_6")
    j = m.get(name, {}).get("joint_minmax_12", m.get(name, {}).get("joint_minmax_6"))
    def f(v): return "TIMEOUT" if v is None else f"{v:.3f}"
    def p(v): return "—" if v is None else f"{100*(v-a)/a:+.2f}%"
    rows.append((name, a, f(x), p(x), f(l), p(l), f(j), p(j),
                 100*(l-x)/x if l else None))
print("| map | anchor | exact cost-neutral | vs anchor | LPT 6s | vs anchor | best route search | vs anchor | LPT gap to exact |")
print("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    g = "—" if r[8] is None else f"{r[8]:+.2f}%"
    print(f"| {r[0]} | {r[1]:.3f} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {g} |")
