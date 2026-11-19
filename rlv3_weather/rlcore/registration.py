"""Engineering/pilot matrix: freeze actual inputs before any measured policy, never certify Formal."""
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile

from .common import ROOT, rel


def digest(value):
    blob = json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(path, obj):
    """Atomic write with strict JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        json.dump(obj, out, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=1)
        out.write("\n")
        tmp = out.name
    os.replace(tmp, path)


def freeze(path, body):
    sealed = {"sha256": digest(body), "body": body}
    p = Path(path)
    if p.exists():
        if read_manifest(p) != sealed:
            raise ValueError("input, source, budget, weights or methods changed; use a new run directory")
    else:
        publish(p, sealed)
    return sealed


def read_manifest(path):
    doc = json.loads(Path(path).read_text())
    if doc["sha256"] != digest(doc["body"]) or doc["body"]["schema"] != "rlv3-paired-pilot-v2":
        raise ValueError("invalid registration checksum/schema")
    return doc


def unique(values):
    return bool(values) and len(values) == len(set(values))


def make_manifest(rows, days, methods, scen, wall_s, seed_reference, scenarios, engine_hash, costs=None):
    from .scen import make_env
    if not (unique([r["path"] for r in rows]) and unique(days) and unique([n for n, _ in methods])):
        raise ValueError("empty or duplicate population, day or method")
    if not math.isfinite(wall_s) or wall_s <= 0:
        raise ValueError("positive finite wall budget required")
    if seed_reference not in dict(methods):
        raise ValueError("prespecified baseline is missing")
    kind = scenarios[scen]["kind"]
    inputs, seen = {}, set()
    if costs is not None and (set(costs) != {r["path"] for r in rows} or
            any(set(v)!={str(d) for d in days} for v in costs.values())):
        raise ValueError("cost registration must cover all map/day cells exactly")
    for row in rows:
        key = row["path"]
        maphash = file_sha(rel(key))
        if maphash in seen or maphash != row["solution"]["instance_sha256"]:
            raise ValueError("duplicate map bytes or wrong author anchor")
        seen.add(maphash)
        inputs[key] = {"map": maphash, "anchor": digest(row["solution"]), "days": {}, "caps": {}, "requirements":{}}
        fixed_wind=scen in {"nowind","fixed_e4","fixed_n8"}
        if costs is not None and fixed_wind:
            from .fixed_anchor import audit_anchor_file
            anchor_path=costs[key][str(days[0])]
            if any(v!=anchor_path for v in costs[key].values()): raise ValueError("fixed condition anchor changed across replicates")
            scored=audit_anchor_file(anchor_path,rel(key),scen)
            if (not scored["full_same_wind_author"] or
                    json.loads(Path(anchor_path).read_text())["solution"] != row["solution"]):
                raise ValueError("missing eligible same-wind author or deployed plan was substituted")
            inputs[key]["author_receipt"]=scored["audit_sha256"]
            inputs[key]["author_M_return"]=scored["metrics"]["M_return"]
        for d in days:
            env = make_env(row, d, scen)
            inputs[key]["days"][str(d)] = engine_hash(env)
            inputs[key]["requirements"][str(d)] = {"routine_total":env.n_planned,
                    "fixed":env.L["fixed"], "n_open":env.L["n_open"],"n_dabs":env.L["n_dabs"],"n_drones":len(env.dr),
                    "high_total":sum(r["prio"]==1 for r in env.requests),
                    "norm_total":sum(r["prio"]==0 for r in env.requests)}
            if costs is not None:
                c=scored["metrics"]["cost"] if fixed_wind else costs[key][str(d)]
                if not finite(c) or c<=0: raise ValueError("positive per-cell operating-cost cap required")
                inputs[key]["caps"][str(d)]=c
    types = {n: {"spec": s, "checkpoint": file_sha(rel(s[3:])) if s.startswith("rl:") else None}
             for n, s in methods}
    srcs = sorted(Path(ROOT, "rlcore").glob("*.py")) + sorted(Path(ROOT, "vendor/lrphsd").glob("*.py"))
    return dict(schema="rlv3-paired-pilot-v2", role="development_only", formal=False, scenario=scen,
                kind=kind, wall_s=wall_s, reference=seed_reference, days=days, maps=inputs, methods=types,
                day_design=("fixed_conditions" if scen in {"nowind","fixed_e4","fixed_n8"} else "independent_within_map"),
                cap_role=("NOT_REGISTERED" if costs is None else "FULL_SAME_WIND_AUTHOR" if scen in {"nowind","fixed_e4","fixed_n8"} else "EXPLICIT_OPERATIONAL_BUDGET"),
                source_sha=digest([(p.relative_to(ROOT).as_posix(), file_sha(p)) for p in srcs]))


def keys(body):
    return {(m, d, method) for m in body["maps"] for d in body["days"] for method in body["methods"]}


def index(doc, rows):
    b = doc["body"]
    if digest(b) != doc["sha256"]:
        raise ValueError("modified registration")
    indexed, problems = {}, []
    wanted = keys(b)
    if not wanted:
        raise ValueError("empty matrix")
    for num, r in enumerate(rows, 1):
        try:
            key = (r["path"], r["day"], r["method"])
            if key not in wanted or key in indexed:
                raise ValueError("extra or duplicate key")
            m, d, met = key
            if type(d) is not int or r["manifest_sha256"] != doc["sha256"] or r["scen"] != b["scenario"]:
                raise ValueError("registration or day mismatch")
            if r["spec"] != b["methods"][met]["spec"]:
                raise ValueError("method spec changed")
            if r["input_sha256"] != b["maps"][m]["days"][str(d)]:
                raise ValueError("not the registered exogenous input")
            indexed[key] = r
            if "error" in r or r.get("status") != "OK":
                problems.append(f"{key}: {r.get('status','missing status')} {r.get('error','')}")
                continue
            requirements=b["maps"][m]["requirements"][str(d)]
            if any(type(r.get(k)) not in (int,float) or r[k]!=v for k,v in requirements.items()):
                raise ValueError("reported deployment, cost or release population differs from frozen input")
            if (not finite(r["wall"]) or r["wall"] > b["wall_s"] or not finite(r["cost"])
                    or not finite(r["J"]) or not finite(r["fixed"]) or not finite(r["M_return"])
                    or r["all_returned"] != 1 or r["physically_feasible"] != 1 or r.get("failed",0)!=0
                    or not counts(r["routine_done"], r["routine_total"]) or r["routine_total"]==0
                    or r["routine_done"] != r["routine_total"]):
                raise ValueError("budget, resources, return or routine gate failed")
            cap=b["maps"][m].get("caps",{}).get(str(d))
            if cap is not None and r["cost"]>cap+(1e-7 if b["cap_role"]=="FULL_SAME_WIND_AUTHOR" else 0):
                raise ValueError("per-cell cost cap exceeded")
            if b["kind"] == "wx":
                if r["n_urgent"] != 0 or r["complete_strict"] != 1 or r.get("timeout",0)!=0:
                    raise ValueError("weather track incomplete or contains urgent work")
            else:
                if (not counts(r["high_on_time"],r["high_total"]) or not counts(r["norm_on_time"],r["norm_total"])
                        or r["high_total"]+r["norm_total"]!=r["n_urgent"]):
                    raise ValueError("invalid all-releases rate denominator")
        except (KeyError, ValueError, TypeError) as exc:
            problems.append(f"row {num}: {exc}")
    return indexed, problems, wanted - indexed.keys()


def finite(x):
    return type(x) in (int,float) and math.isfinite(x) and x >= 0


def counts(n,d):
    return type(n) is int and type(d) is int and 0 <= n <= d


def read_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for k,line in enumerate(stream,1):
            if not line.strip():
                raise ValueError(f"blank result line {k}")
            obj=json.loads(line,parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: "+x)))
            if not isinstance(obj,dict):
                raise ValueError(f"result line {k} is not an object")
            rows.append(obj)
    return rows
