#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rivermind-data/ca_rl_completion_v5_staging/code
cd "$ROOT"
PY=/opt/conda/bin/python
WORKERS=8
BASELINE_METHOD=$("$PY" - <<'PY'
from pathlib import Path
p=Path("results/v5_final_nonppo_baseline.txt")
xs=[x.strip() for x in p.read_text().splitlines() if x.strip() and not x.lstrip().startswith("#")]
if len(xs)!=1: raise SystemExit("selected non-PPO baseline must be exactly one method")
print(xs[0])
PY
)
for budget in 6 12; do
  baseline_dir="results/v5_global_repair_finalists_10seed_${budget}s"
  expected_code_hash=$("$PY" - "$baseline_dir" "$BASELINE_METHOD" <<'PY'
import glob,json,sys
from pathlib import Path
d,method=sys.argv[1:]
rows=[]
for p in glob.glob(d+"/*__s*.json"):
    r=json.load(open(p))
    if r.get("method")==method and int(r.get("seed",-1)) in range(101,110):
        rows.append(r)
if len(rows)!=216:
    raise SystemExit(f"expected 216 selected baseline rows, got {len(rows)}")
hashes={(r.get("provenance") or {}).get("code_sha256") for r in rows}
if len(hashes)!=1 or None in hashes:
    raise SystemExit(f"selected baseline has mixed/missing code hashes: {hashes}")
print(next(iter(hashes)))
PY
)
  for controller in bc ppo a2c; do
    for model_seed in 11 23 37; do
      case "$model_seed" in
        11) solver_seeds=101,102,103 ;;
        23) solver_seeds=104,105,106 ;;
        37) solver_seeds=107,108,109 ;;
      esac
      case "$controller" in
        bc) model="../training_runs_v5_final72/BC_seed${model_seed}/bc.pt" ;;
        ppo) model="../training_runs_v5_final72/PPO_seed${model_seed}/best.pt" ;;
        a2c) model="../training_runs_v5_a2c_final72/A2C_seed${model_seed}/best.pt" ;;
      esac
      [ -f "$model" ] || { echo "missing model: $model" >&2; exit 20; }
      for scope in local global; do
        if [ "$scope" = local ]; then method=m6_local_scope; else method=m6_global_asg; fi
        out="results/v5_rl_global_transfer_${budget}s_${controller}_s${model_seed}_${scope}"
        if [ -e "$out" ]; then
          if "$PY" - "$out" "$budget" "$method" "$solver_seeds" "$model" "$expected_code_hash" <<'PY'
import glob,json,sys,hashlib
from pathlib import Path
d,b,m,seeds,model,expected_hash=sys.argv[1:]
p=Path(d)/"manifest.json"
if not p.is_file(): raise SystemExit("no manifest")
manifest=json.loads(p.read_text())
expected_seeds=[int(x) for x in seeds.split(",")]
if (manifest.get("finished") is None or manifest.get("errors")!=0
    or manifest.get("methods")!=[m] or manifest.get("seeds")!=expected_seeds
    or len(manifest.get("instances",[]))!=24 or manifest.get("tasks")!=72
    or float(manifest.get("seconds",-1))!=float(b)):
    raise SystemExit("manifest mismatch")
files=sorted(Path(d).glob("*__s*.json"))
if len(files)!=72 or list(Path(d).glob("*.error.json")):
    raise SystemExit("wrong result/error-file count")
expected_model=hashlib.sha256(Path(model).read_bytes()).hexdigest()
scope="global_assignment" if m=="m6_global_asg" else "local"
rows=[json.loads(x.read_text()) for x in files]
for r in rows:
    prov=r.get("provenance") or {}
    if (r.get("status")!="ok" or r.get("feasible") is not True
        or r.get("repair_scope_mode")!=scope
        or int(r.get("seed",-1)) not in expected_seeds
        or prov.get("code_sha256")!=expected_hash
        or prov.get("model_sha256")!=expected_model):
        raise SystemExit("row feasibility/scope/seed/source/model provenance mismatch")
if len({r.get("instance") for r in rows})!=24:
    raise SystemExit("wrong instance coverage")
print("VALID_COMPLETE")
PY
          then
            echo "SKIP verified complete $out"
            continue
          else
            suffix=$(date -u +%Y%m%dT%H%M%SZ)
            preserved="${out}_provenance_mismatch_preserved_${suffix}"
            echo "PRESERVE invalid existing output: $out -> $preserved" >&2
            mv "$out" "$preserved"
          fi
        fi
        echo "[RL_GLOBAL_TRANSFER] budget=$budget controller=$controller model_seed=$model_seed scope=$scope"
        "$PY" -B scripts/run_bench.py --instances val --methods "$method" \
          --seeds "$solver_seeds" --seconds "$budget" --workers "$WORKERS" \
          --ppo-model "$model" --out "$out"
      done
    done
  done
done
"$PY" -B results/experiment_script_archive/analyze_v5_rl_global_transfer.py
printf "V5_RL_GLOBAL_TRANSFER_COMPLETE\n" > results/V5_RL_GLOBAL_TRANSFER_COMPLETE
echo "V5_RL_GLOBAL_TRANSFER_COMPLETE"
