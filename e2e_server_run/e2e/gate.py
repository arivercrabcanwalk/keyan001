"""Early learning-curve gate (pre-registered, PREREG_E2E.md §6): after ~2 h of pi_route training, fit
gap(h) = a + b * h^(-c) (c in [0.2, 2]) to the dev aug8 route-gap curve (vs TSALNS routes on TSALNS sitings) and
extrapolate to the planned training length. Static plan gap ~= route gap * route_share + siting gap; we require the
extrapolated route gap <= ROUTE_GATE (default +1.0 %), else STOP (exit 10) and report.
Also stops if the curve is not improving at all (last third no better than first third)."""
import sys, json, argparse, numpy as np


def fit(h, g):
    best = None
    for c in np.linspace(0.2, 2.0, 37):
        X = np.stack([np.ones_like(h), h ** (-c)], 1)
        coef, res, *_ = np.linalg.lstsq(X, g, rcond=None)
        r = float(((X @ coef - g) ** 2).sum())
        if best is None or r < best[0]:
            best = (r, coef, c)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curve", required=True); ap.add_argument("--target_h", type=float, default=12.0)
    ap.add_argument("--route_gate", type=float, default=1.0); ap.add_argument("--out", default="")
    a = ap.parse_args()
    R = [json.loads(l) for l in open(a.curve)]
    R = [r for r in R if r.get("val_aug8") is not None and r["h"] > 0.05]
    if len(R) < 6:
        print(json.dumps(dict(decision="CONTINUE", reason="too few points", n=len(R)))); return 0
    h = np.array([r["h"] for r in R]); g = np.array([r["val_aug8"] for r in R])
    r, coef, c = fit(h, g)
    pred = float(coef[0] + coef[1] * a.target_h ** (-c))
    k = max(1, len(g) // 3); improving = g[-k:].mean() < g[:k].mean() - 0.1
    ok = pred <= a.route_gate and improving
    out = dict(decision="CONTINUE" if ok else "STOP", pred_gap_at_target=pred, asymptote=float(coef[0]), c=float(c),
               last=float(g[-1]), best=float(g.min()), improving=bool(improving), n=len(g), target_h=a.target_h, gate=a.route_gate)
    print(json.dumps(out))
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)
    return 0 if ok else 10


if __name__ == "__main__":
    sys.exit(main())
