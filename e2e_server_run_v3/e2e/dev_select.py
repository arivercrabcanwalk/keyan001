"""REVIEW FIX (R-primary): pre-registered selection of the STRONGEST non-RL baseline on DEV maps x DEV days
(never on test). Reads dyn_eval rows of TSALNS dev plans (reserve 0/10/20 %) x execution rules (A1/N6/Rfc) and
writes the winning arm name (mapped to its test-arm name) to --out. Ties broken by fewer fails."""
import json, argparse, collections, numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--map", default="", help="comma list plans:method=TEST_ARM_NAME")
    a = ap.parse_args()
    mp = dict(x.split("=", 1) for x in a.map.split(",") if x)
    R = collections.defaultdict(dict)
    for l in open(a.rows):
        r = json.loads(l)
        if "error" in r:
            continue
        R[f"{r['plans']}:{r['method']}"][(r["inst"], r["day"])] = r
    keys = [k for k in mp if R.get(k)]
    common = set.intersection(*[set(R[k]) for k in keys])
    score = {k: (float(np.mean([R[k][c]["J"] for c in common])), float(np.mean([R[k][c]["fails"] for c in common])),
                 float(np.mean([R[k][c].get("complete_strict", R[k][c]["complete"]) for c in common]))) for k in keys}
    ok = [k for k in keys if score[k][2] >= 1.0] or keys            # completion first (hard requirement)
    best = min(ok, key=lambda k: score[k][:2])
    json.dump(dict(scores={mp[k]: score[k] for k in keys}, n=len(common), primary=mp[best]),
              open(a.out.replace(".txt", ".json"), "w"), indent=1)
    open(a.out, "w").write(mp[best] + "\n")
    print("[dev_select]", {mp[k]: round(score[k][0], 1) for k in keys}, "->", mp[best])


if __name__ == "__main__":
    main()
