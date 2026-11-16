#!/bin/bash
# WX5 single entry point (40 vCPU server; uses NCPU-2 workers). PREREG: wx_e/PREREG_v5.md, DESIGN: wx_e/DESIGN_v5_ZH.md
#   nohup bash run_all.sh > run_all.log 2>&1 &
#   SMOKE=1 bash run_all.sh        # tiny end-to-end dry run (minutes), NOT official
# Resume-safe: every stage writes a .done marker; every eval row / ES iteration is checkpointed. Re-running after a
# crash/reboot continues where it stopped; ES runs that did not reach ES_ITERS are relaunched (equal compute).
# Nothing is pushed anywhere.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
export WX_ROOT="$ROOT" PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
unset WX_OT
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="${PY:-python3}"; fi
jst() { TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST'; }
PROG="$ROOT/PROGRESS_SERVER.md"
progress() { printf '[%s] %s\n' "$(jst)" "$*" | tee -a "$PROG"; }
mkdir -p logs models5 wx_e/results results_final data/days
NCPU="${NCPU:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc --all 2>/dev/null || echo 8)}"; W=$((NCPU - 2)); [ "$W" -lt 2 ] && W=2
SMOKE="${SMOKE:-0}"
SEEDS="${SEEDS:-0 1 2}"
OT_BUDGET="${OT_BUDGET:-0}"            # PREREG_v5 §4: relative constraint E[ot_RL - ot_N6best] <= OT_BUDGET (=0) on the same days
VARIANTS="${VARIANTS:-main nf ne uc}"   # main | nf = no forecast features | ne = no emergency features | uc = no OT constraint
if [ "$SMOKE" = "1" ]; then
  W=$(( W < 4 ? W : 4 )); SEEDS="0 1"; VARIANTS="main nf"
  DEV_LIMIT=2; DEV_DAYS="6000"; N6GRID="N6_60_0.25,N6_90_0.25"
  ES_ITERS=2; ES_POP=2; ES_BATCH=2; ES_VALN=4; ES_VALEVERY=1
  TEST_LIMIT=2; TA_DAYS="7700"; TB_DAYS="8700"; TC_DAYS="8800"; TL_DAYS="9700"; SUB_DAYS="7700"
  STAMP="smoke"
else
  DEV_LIMIT=0; DEV_DAYS="6000-6019"
  N6GRID="N6_30_0.1,N6_30_0.25,N6_30_0.5,N6_30_1.0,N6_60_0.1,N6_60_0.25,N6_60_0.5,N6_60_1.0,N6_90_0.1,N6_90_0.25,N6_90_0.5,N6_90_1.0"
  ES_ITERS="${ES_ITERS:-250}"; ES_POP="${ES_POP:-16}"; ES_BATCH="${ES_BATCH:-16}"; ES_VALN=64; ES_VALEVERY=10
  TEST_LIMIT=0; TA_DAYS="7700-7799"; TB_DAYS="8700-8799"; TC_DAYS="8800-8899"; TL_DAYS="9700-9799"; SUB_DAYS="7700-7719"
  STAMP="official"
fi
LIM=""; [ "$TEST_LIMIT" != "0" ] && LIM="--limit-plans $TEST_LIMIT"
DLIM=""; [ "$DEV_LIMIT" != "0" ] && DLIM="--limit-plans $DEV_LIMIT"
R=wx_e/results
done_mark() { touch "logs/$1.$STAMP.done"; }
is_done() { [ -f "logs/$1.$STAMP.done" ]; }
run_stage() { # name cmd...
  local n="$1"; shift
  if is_done "$n"; then progress "skip $n (done)"; return 0; fi
  progress "START $n"
  "$@" >> "logs/$n.log" 2>&1; local rc=$?
  if [ $rc -eq 0 ]; then done_mark "$n"; progress "DONE $n"; else progress "FAIL $n rc=$rc (see logs/$n.log); continuing"; fi
  return 0
}
progress "WX5 run_all start: ncpu=$NCPU workers=$W smoke=$SMOKE seeds=[$SEEDS] variants=[$VARIANTS] es_iters=$ES_ITERS pop=$ES_POP batch=$ES_BATCH ot_budget=$OT_BUDGET python=$($PY -V 2>&1)"
$PY -c "import numpy, scipy" || { progress "numpy/scipy missing: run setup.sh"; exit 1; }

# ---- Stage 1: freeze N6 on dev (grid; min dev J5 among 100%-complete configs) ----
run_stage s1_n6grid $PY run_jobs3.py --out $R/dev_n6grid_v5.jsonl --methods N1_240,$N6GRID --plans dev_ours --days $DEV_DAYS $DLIM --workers $W
if ! [ -f wx_e/N6_FREEZE.$STAMP.json ]; then
  $PY - << PYEOF
import json, numpy as np, collections
rows=[json.loads(l) for l in open("$R/dev_n6grid_v5.jsonl") if '"error"' not in l]
by=collections.defaultdict(list); comp=collections.defaultdict(list); ot=collections.defaultdict(list)
for r in rows: by[r["method"]].append(r["J"]); comp[r["method"]].append(r.get("complete",1)); ot[r["method"]].append(r.get("ot_min",0))
c={m:float(np.mean(v)) for m,v in by.items() if m.startswith("N6_")}
ok={m:v for m,v in c.items() if np.mean(comp[m])>=1.0-1e-12} or c
best=min(ok,key=ok.get)
json.dump(dict(best=best,dev_J5=c,dev_ot={m:float(np.mean(v)) for m,v in ot.items()},dev_complete={m:float(np.mean(v)) for m,v in comp.items()},
  frozen_by="min dev mean J5 among 100%-complete N6 configs, PREREG_v5 §3"),open("wx_e/N6_FREEZE.$STAMP.json","w"),indent=1)
print("N6 best",best,c[best])
PYEOF
fi
N6BEST=$($PY -c "import json;print(json.load(open('wx_e/N6_FREEZE.$STAMP.json'))['best'])")
progress "N6 frozen: $N6BEST"

# ---- Stage 2: constrained ES (PREREG_v5 §4). All (variant, seed) runs in parallel, equal workers, FIXED iterations.
#      Relaunch loop: a run without its DONE marker is resumed from its per-iteration state (max 5 attempts). ----
NV=$(echo $VARIANTS | wc -w); NS=$(echo $SEEDS | wc -w); NR=$((NV * NS)); WS=$(( W / NR )); [ "$WS" -lt 1 ] && WS=1
progress "ES: $NR runs x $WS workers, $ES_ITERS iters, pop $ES_POP, batch $ES_BATCH"
es_args() { # variant -> extra args
  case "$1" in
    main) echo "--ot-budget $OT_BUDGET --ot-ref $N6BEST --dual-lr 0.005" ;;
    nf)   echo "--ot-budget $OT_BUDGET --ot-ref $N6BEST --dual-lr 0.005 --ablate noforecast" ;;
    ne)   echo "--ot-budget $OT_BUDGET --ot-ref $N6BEST --dual-lr 0.005 --ablate noemerg" ;;
    uc)   echo "--ot-budget -1" ;;
  esac
}
run_name() { case "$1" in main) echo "es5_s$2" ;; nf) echo "es5_s$2_noforecast" ;; ne) echo "es5_s$2_noemerg" ;; uc) echo "es5uc_s$2" ;; esac; }
for attempt in 1 2 3 4 5; do
  pids=(); n_todo=0
  for v in $VARIANTS; do for s in $SEEDS; do
    nm=$(run_name $v $s); [ -f models5/DONE_$nm ] && continue
    n_todo=$((n_todo + 1)); TAG=es5; [ "$v" = "uc" ] && TAG=es5uc
    progress "ES launch $nm (attempt $attempt)"
    $PY run_es5.py --seed $s --init models/rl_s${s}_best_pomo_v2.npz --iters $ES_ITERS --pop $ES_POP --batch $ES_BATCH \
      --sigma 0.02 --lr 0.01 --val-n $ES_VALN --val-every $ES_VALEVERY --workers $WS --tag $TAG --models models5 \
      $(es_args $v) --log logs/es_train.log >> logs/es_$nm.log 2>&1 &
    pids+=($!)
  done; done
  [ "$n_todo" = "0" ] && break
  for p in "${pids[@]}"; do wait $p; done
done
SM=""; [ "$SMOKE" = "1" ] && SM="--dev-limit $DEV_LIMIT"
for v in $VARIANTS; do for s in $SEEDS; do
  nm=$(run_name $v $s); OB=$OT_BUDGET; [ "$v" = "uc" ] && OB=-1
  run_stage s2_select_$nm $PY select_es5.py --name $nm --iters $ES_ITERS --models models5 --workers $W --dev-days $DEV_DAYS --ot-budget $OB --ot-ref $N6BEST $SM
done; done
EXTRA=$($PY - << PYEOF
import json, os
e={"N6_best": {"policy": "$N6BEST"}, "R_N6best": {"policy": "R_$N6BEST"}, "Rfc_N6best": {"policy": "Rfc_$N6BEST"}}
pref={"es5_s{s}":"RL5_s{s}","es5_s{s}_noforecast":"RL5nf_s{s}","es5_s{s}_noemerg":"RL5ne_s{s}","es5uc_s{s}":"RL5uc_s{s}"}
for s in "$SEEDS".split():
    for k,v in pref.items():
        f=f"models5/final_{k.format(s=s)}.npz"
        if os.path.exists(f): e[v.format(s=s)]={"ckpt": f}
    g=f"models/rl_s{s}_best_pomo_v2.npz"
    if os.path.exists(g): e[f"POMO_s{s}"]={"ckpt": g}
print(json.dumps(e))
PYEOF
)
export EXTRA
pick() { $PY -c "import json,os;e=json.loads(os.environ['EXTRA']);print(','.join(k for k in e if k.startswith('$1')))"; }
RLM=$(pick RL5_s); RLA=$(pick RL5nf_s),$(pick RL5ne_s),$(pick RL5uc_s); RLA=$(echo "$RLA" | sed 's/,,*/,/g;s/^,//;s/,$//'); POM=$(pick POMO_s)
progress "final policies: $RLM ; ablations: $RLA ; pomo inits: $POM"
[ -z "$RLM" ] && { progress "no final RL5 policies -> stop"; exit 2; }
EXTRA_R=$($PY -c "import json,os;e=json.loads(os.environ['EXTRA']);k=sorted(x for x in e if x.startswith('RL5_s'))[0];e['RLR_100ms']={'ckpt':e[k]['ckpt']};print(json.dumps(e))")
BASES="A1,A2,N1_240,N6_best,R_N6best,Rfc_N6best"
ALLM="$BASES,$POM,$RLM${RLA:+,$RLA}"

# ---- Stage 3: Test-A (50 maps x 100 FRESH days 7700-7799) incl. ablations + clairvoyant reference O;
#      fair rollouts (twin weather, 100 ms in-sim deadline) on a 20-day subset ----
run_stage s3_testA $PY run_jobs3.py --out $R/testA_v5.jsonl --methods $ALLM,O --plans test_ours --days $TA_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s3_testA_roll $PY run_jobs3.py --out $R/testA_v5.jsonl --methods N4fd_32_100ms,RLR_100ms --plans test_ours --days $SUB_DAYS $LIM --workers $W --extra "$EXTRA_R"
# ---- Stage 4: Test-B (author TSALNS plans), Test-C (stress), Test-L (larger maps) incl. ablations ----
run_stage s4_testB $PY run_jobs3.py --out $R/testB_v5.jsonl --methods $ALLM --plans test_ts --days $TB_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s4_testC $PY run_jobs3.py --out $R/testC_v5.jsonl --methods $ALLM --plans test_ours --days $TC_DAYS $LIM --scenario stress --workers $W --extra "$EXTRA"
run_stage s4_testL $PY run_jobs3.py --out $R/testL_v5.jsonl --methods $ALLM --plans test_large --days $TL_DAYS $LIM --workers $W --extra "$EXTRA"
# ---- Stage 5: robustness P4a (sigma x1.5), P4b (nowcast bias x1.3), P3 exploratory (uniform failures) ----
MAINM="$BASES,$POM,$RLM"
run_stage s5_p4a $PY run_jobs3.py --out $R/p4_sigma15_v5.jsonl --methods $MAINM --plans test_ours --days $TA_DAYS $LIM --scenario sigma15 --workers $W --extra "$EXTRA"
run_stage s5_p4b $PY run_jobs3.py --out $R/p4_ncbias_v5.jsonl --methods $MAINM --plans test_ours --days $TA_DAYS $LIM --scenario ncbias --workers $W --extra "$EXTRA"
run_stage s5_p3 $PY run_jobs3.py --out $R/p3_uniform_v5.jsonl --methods $MAINM --plans test_ours --days $TA_DAYS $LIM --scenario uniform --workers $W --extra "$EXTRA"
# ---- Stage 6: operational-window sensitivity (WX_OT=180 tighter / 300 looser) on the Test-A 20-day subset ----
run_stage s6_ot180 env WX_OT=180 $PY run_jobs3.py --out $R/scale_ot180_v5.jsonl --methods $MAINM --plans test_ours --days $SUB_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s6_ot300 env WX_OT=300 $PY run_jobs3.py --out $R/scale_ot300_v5.jsonl --methods $MAINM --plans test_ours --days $SUB_DAYS $LIM --workers $W --extra "$EXTRA"
# ---- Stage 7: analysis + pack ----
$PY analyze_v5.py >> logs/s7_analysis.log 2>&1 && progress "analysis written: results_final/SUMMARY_ZH.md" || progress "analysis FAILED (logs/s7_analysis.log)"
cp -f $R/*_v5.jsonl wx_e/N6_FREEZE.$STAMP.json models5/select_*.json models5/es_hist_*.jsonl models5/DONE_* results_final/ 2>/dev/null
cp -f PROGRESS_SERVER.md results_final/ 2>/dev/null
tar -czf results_out.tar.gz results_final models5/final_*.npz logs/*.log wx_e/results/*.jsonl 2>/dev/null
progress "PACKED results_out.tar.gz ($(stat -c %s results_out.tar.gz 2>/dev/null) bytes). ALL DONE."
