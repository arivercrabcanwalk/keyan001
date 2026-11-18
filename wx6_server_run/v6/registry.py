"""Policy registry for v6 (wraps wx2.evaljob.get_pol):
  S:<name>            shift-shielded variant of any policy (v6/shield.py)
  RL6:<npz>           RL6 token-scoring policy (v6/net6.py), greedy; RL6 always runs with its shield unless :noshield
  RL6:<npz>:noshield  ablation
  RL6R_<ms>ms:<npz>   RL6 as base of a fair twin-weather rollout with an in-sim deadline (equal-latency class 100 ms)
  N4fd_<M>_<ms>ms     fair rollout over the dev-selected strongest rule (extra.base)
  everything else     wx2.evaljob.get_pol (A1, A2, N1_240, N6_H_theta, R_/Rfc_/Rfc600e15_ re-optimisation, RL5 ...)
"""
from wx2 import evaljob as EJ, twin as TW
from . import shield as SH


def get_policy(name, extra=None):
    extra = dict(extra or {})
    if name.startswith("S:"):
        return SH.shielded(get_policy(name[2:], extra))
    if extra.get("policy") and not name.startswith(("RL6", "N4fd")):
        return get_policy(extra["policy"], {k: v for k, v in extra.items() if k != "policy"})
    if name.startswith("RL6R_"):
        from . import net6 as N6
        dms = float(name.split("_")[1].split(":")[0].replace("ms", ""))
        base = N6.make_policy(N6.load(extra["ckpt"]), shield=True)
        return TW.make_rollout_v3(M=int(extra.get("M", 32)), base=base, seed=extra.get("seed", 0), deadline_ms=dms, fair=True)
    if name.startswith("RL6"):
        from . import net6 as N6
        ck = extra.get("ckpt") or name.split(":", 1)[1].split(":noshield")[0]
        ns = extra.get("noshield", False) or name.endswith(":noshield")
        return N6.make_policy(N6.load(ck), shield=not ns, fmask=extra.get("fmask"))
    if name.startswith("N4fd_") and "base" in extra and extra["base"].startswith("S:"):
        parts = name.split("_"); M = int(parts[1]); dms = float(parts[2].replace("ms", ""))
        return TW.make_rollout_v3(M=M, base=get_policy(extra["base"]), seed=extra.get("seed", 0), deadline_ms=dms, fair=True)
    return EJ.get_pol(name, extra)
