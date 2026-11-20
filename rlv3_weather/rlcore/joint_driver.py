"""Supervised paired development round. No pilot outcomes or production approvals created."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import signal
import sys
import time
import traceback


def write_json(path, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    tmp = path.with_name("." + path.name + ".tmp")
    with tmp.open("x") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def read_limit(ticket):
    cfg = json.loads(ticket.read_bytes()).get("joint_training")
    if not isinstance(cfg, dict):
        raise ValueError("approved joint_training block required (not a template or legacy ticket)")
    value = cfg["config"]["wall_seconds"]
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("ticket wall_seconds must be positive and finite")
    expiry = datetime.fromisoformat(cfg["valid_until"].replace("Z", "+00:00"))
    if expiry.tzinfo is None:
        raise ValueError("expiry must include timezone")
    return min(float(value), (expiry-datetime.now(timezone.utc)).total_seconds())


def consume(ledger_dir, ticket_id, receipt):
    ledger_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = hashlib.sha256(ticket_id.encode()).hexdigest()+".json"
    path = ledger_dir / name
    # The lease is per approved ticket and persists across output dirs and checkouts.
    # O_EXCL + no auto retry is intentional, including on an interrupted write.
    with path.open("x") as f:
        f.write(json.dumps(receipt, sort_keys=True, allow_nan=False)+"\n")
        f.flush()
        os.fsync(f.fileno())
    return path


def inputs_for_smoke(out):
    from .common import load_ins
    from .fixed_anchor import audit_fixed_anchor
    groups = []
    for phase, coords in (("train", [(880,75),(1440,-120),(-930,130),(-1400,-80)]),
                          ("val", [(800,-110),(1220,370),(-790,310),(-1540,-240)])):
        path = out / (phase+"_manual.txt")
        path.write_text("CUST_NO X Y ENERGY SERVICE\n" +
                        "".join(f"{i} {x} {y} .2 10\n" for i,(x,y) in enumerate(coords,1)) +
                        "99 0 0 0 0\n")
        ins = load_ins(str(path))
        sol = dict(instance=ins.name, instance_sha256=ins.sha256, schema_version=1,
                   station_types=[2], routes=[[[[1,2]],[[3,4]]]])
        audit = audit_fixed_anchor(ins, sol, wind="fixed_e4", map_path=str(path))
        if not audit["physical_feasible"] or audit["scientific_eligible"]:
            raise RuntimeError("invalid manual engineering fixture")
        groups.append([({"path":str(path), "solution":sol}, "fixed_e4", audit["metrics"]["cost"])])
    return groups[0], groups[1], dict(scenario="fixed_e4", role="HANDWRITTEN_ENGINEERING_ONLY", formal=False,
                         config=dict(seed=0, bc_epochs=1, pg_steps=1, rollouts=2, lr=0.001,
                                     device="cpu", wall_seconds=120))


def paired_rows(matrix):
    """Every registered case × arm, including failures; only paired eligible M deltas."""
    def index(summary):
        rows = {}
        for r in summary["validation"]:
            key = (r["case_id"], r["arm"])
            if key in rows:
                raise ValueError("duplicate validation endpoint")
            rows[key] = r["result"]
        return rows
    j, s = index(matrix["joint"]), index(matrix["serial"])
    if not j or j.keys() != s.keys():
        raise ValueError("joint/serial validation population mismatch")
    table = []
    for case, arm in sorted(j):
        a, b = j[case,arm], s[case,arm]
        paired = bool(a.get("eligible") and b.get("eligible"))
        table.append(dict(case_id=case, arm=arm, joint_eligible=bool(a.get("eligible")),
                          serial_eligible=bool(b.get("eligible")), joint_cost=a.get("cost"),
                          serial_cost=b.get("cost"), joint_M=a.get("M_return"), serial_M=b.get("M_return"),
                          joint_minus_serial_min=(a["M_return"]-b["M_return"]) if paired else None))
    return table


def worker(kind, ticket, expected_sha, out, deadline, expected_frozen=None):
    try:
        import numpy, torch
        from .joint_learning import run_round
        if kind == "joint-smoke":
            train, val, meta = inputs_for_smoke(out)
        else:
            from .joint_inputs import prepare
            if hashlib.sha256(ticket.read_bytes()).hexdigest()!=expected_sha:
                raise ValueError("ticket changed after outer timing started")
            train, val, meta = prepare(str(ticket))
            if meta["ticket_sha256"]!=expected_sha:
                raise ValueError("changed ticket at admission")
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        meta["software"] = dict(torch=str(torch.__version__),numpy=numpy.__version__,
                              python=sys.version,platform=platform.platform(),cuda=torch.version.cuda)
        if expected_frozen is not None and expected_frozen != meta:
            raise ValueError("approved inputs/code/software changed after preflight")
        write_json(out/"INPUTS.json", meta)
        if meta["config"]["bc_epochs"] < 1 or meta["config"]["rollouts"] < 2:
            raise ValueError("paired development requires fitted BC and at least two independent LOO rollouts")
        if kind == "joint-preflight":
            write_json(out/"RESULT.json", dict(status="PREFLIGHT_OK",training_started=False,formal=False))
            return
        cfg = dict(meta["config"])
        if kind != "joint-smoke":
            if time.monotonic()>=deadline:
                raise TimeoutError("expired during input validation")
            ledger = Path.home()/".local/state/rlv3/joint_ticket_attempts"
            consume(ledger, meta["ticket_id"], dict(ticket_id=meta["ticket_id"], registered=iso_now(),
                    output=str(out),ticket_sha256=meta["ticket_sha256"],status="CONSUMED_NO_AUTO_RETRY"))
        cfg.pop("wall_seconds")
        write_json(out/"RUNTIME.json",dict(torch=torch.__version__,numpy=numpy.__version__,
            python=sys.version,device=cfg["device"],cuda_available=torch.cuda.is_available(),
            platform=platform.platform(),started=iso_now()))
        matrix = {}
        for structure in ("joint","serial"):
            matrix[structure] = run_round(train,val,out=out/structure,deadline=deadline,
                                          mode=structure,**cfg)
            if time.monotonic()>=deadline:
                raise TimeoutError("round ended after the shared cutoff")
            round_result = matrix[structure]
            if any(f.get("termination_reason") == "exception" for f in round_result["failures"]):
                raise RuntimeError(f"{structure}: execution exception recorded; see retained summary")
            if round_result["status"] != "completed_fixed_endpoints" or not round_result["fixed_endpoints_complete"]:
                raise RuntimeError(f"{structure}: registered endpoints incomplete; see retained summary")
            counts = round_result["counts"]
            expected = (cfg["bc_epochs"], cfg["pg_steps"], cfg["pg_steps"])
            if tuple(counts[key] for key in ("bc_updates","pg_j_updates","pg_m_updates")) != expected:
                raise RuntimeError(f"{structure}: registered optimizer counts differ")
            if counts["pg_episodes"] != 2 * cfg["pg_steps"] * cfg["rollouts"]:
                raise RuntimeError(f"{structure}: registered rollout counts differ")
            if any(a["cases"] != len(val) for a in round_result["arms"].values()):
                raise RuntimeError(f"{structure}: validation denominator changed")
        table = paired_rows(matrix)
        write_json(out/"PAIRED_VALIDATION.json", table)
        write_json(out/"RESULT.json",dict(status="ENGINEERING_ONLY" if kind=="joint-smoke" else "DEVELOPMENT_COMPLETE",
                structures=matrix,formal=False,pilot_executed=False,performance_claim=False,
                role=kind,ended=iso_now()))
    except BaseException as e:
        write_json(out/"FAILURE.json", dict(status="FAILED",reason=type(e).__name__+": "+str(e),
                  recorded=iso_now(),formal=False))
        traceback.print_exc()
        sys.exit(1)


def run(kind,out,ticket=None,preflight=None):
    from .campaign import resource_lock
    if not out.is_absolute():
        raise ValueError("OUT must be an absolute new directory")
    out=out.resolve()
    if kind not in ("joint-smoke","joint-preflight","joint-train"): raise ValueError("bad mode")
    start=time.monotonic()
    if kind=="joint-smoke":
        budget,expected_sha=120,None
        if ticket or preflight: raise ValueError("smoke accepts no tickets, maps or checkpoints")
    else:
        if not ticket or not ticket.is_absolute():raise ValueError("absolute TICKET required")
        first=ticket.read_bytes()
        expected_sha=hashlib.sha256(first).hexdigest()
        budget=read_limit(ticket)
        if budget<=0:raise ValueError("ticket expired")
    frozen=None
    if kind=="joint-train":
        if not preflight or not preflight.is_absolute():raise ValueError("absolute PREFLIGHT required")
        if (json.loads((preflight/"RESULT.json").read_bytes()).get("status")!="PREFLIGHT_OK" or
                json.loads((preflight/"SUPERVISOR.json").read_bytes()).get("exit_status")!=0):
            raise ValueError("successful completed preflight required")
        frozen=json.loads((preflight/"INPUTS.json").read_bytes())
        if frozen.get("ticket_sha256")!=expected_sha:raise ValueError("preflight ticket mismatch")
    deadline=start+budget
    with resource_lock():
        out.mkdir(mode=0o700,parents=True,exist_ok=False)
        write_json(out/"INTENT.json",dict(mode=kind,ticket_sha256=expected_sha,start=iso_now(),
                   max_wall_seconds=budget,formal=False,one_worker=True))
        ctx=mp.get_context("spawn")
        proc=ctx.Process(target=worker,args=(kind,ticket,expected_sha,out,deadline,frozen))
        proc.start()
        timeout=False
        def stop(_signum,_frame): raise KeyboardInterrupt
        originals={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
        try:
            proc.join(max(0,deadline-time.monotonic()))
            timeout=proc.is_alive() or time.monotonic()>deadline
        finally:
            for s in originals:signal.signal(s,originals[s])
            if proc.is_alive():proc.kill()
            proc.join()
            wall=time.monotonic()-start
            status=124 if timeout or wall>budget else (proc.exitcode if proc.exitcode is not None else 1)
            write_json(out/"SUPERVISOR.json",dict(exit_status=status,child_exit=proc.exitcode,
                       wall_seconds=wall,late_or_timeout=timeout or wall>budget,ended=iso_now()))
        if status:
            raise RuntimeError(f"{kind} failed (rc={status}); retained: {out}")
        if not (out/"RESULT.json").is_file(): raise RuntimeError("missing final result")
        print(kind, json.loads((out/"RESULT.json").read_bytes())["status"], out, flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=["joint-smoke","joint-preflight","joint-train"])
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--ticket",type=Path)
    ap.add_argument("--preflight",type=Path)
    a=ap.parse_args()
    run(a.mode,a.out,a.ticket,a.preflight)


if __name__=="__main__":
    main()
