#!/bin/bash
# WX4 single entry point (40 vCPU server; uses NCPU-2 workers). PREREG: wx_e/PREREG_v4.md
#   nohup bash run_all.sh > run_all.log 2>&1 &
#   SMOKE=1 bash run_all.sh        # tiny end-to-end dry run (minutes), NOT official
# Resume-safe: every stage writes a .done marker; every eval row / ES iteration is checkpointed.
# Re-running after a crash/reboot continues where it stopped. Nothing is pushed anywhere.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
export WX_ROOT="$ROOT" PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="${PY:-python3}"; fi
jst() { TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST'; }
PROG="$ROOT/PROGRESS_SERVER.md"
progress() { printf '[%s] %s\n' "$(jst)" "$*" | tee -a "$PROG"; }
mkdir -p logs models4 wx_e/results results_final data/days
# NB: plain `nproc` honours OMP_NUM_THREADS (=1 above) and would report 1 core
NCPU="${NCPU:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc --all 2>/dev/null || echo 8)}"; W=$((NCPU - 2)); [ "$W" -lt 2 ] && W=2
SMOKE="${SMOKE:-0}"
SEEDS="${SEEDS:-0 1 2}"   # ES seed s warm-starts from pomo_v2 seed s
if [ "$SMOKE" = "1" ]; then
  W=$(( W < 4 ? W : 4 )); SEEDS="0 1"
  DEV_LIMIT=2; DEV_DAYS="6000"; N6GRID="N6_60_0.25,N6_30_0.1"
  ES_ITERS=2; ES_POP=2; ES_BATCH=2; ES_VALN=4; ES_VALEVERY=1; LAMS="1:10:0,1:10:0.25"
  TEST_LIMIT=2; TA_DAYS="7200"; TB_DAYS="8200"; TC_DAYS="8300"; TL_DAYS="9200"; N4_DAYS="7200"; SUB_DAYS="7200"; M_BIG=2
  STAMP="smoke"
else
  DEV_LIMIT=0; DEV_DAYS="6000-6019"
  N6GRID="N6_30_0.1,N6_30_0.25,N6_30_0.5,N6_30_1.0,N6_60_0.1,N6_60_0.25,N6_60_0.5,N6_60_1.0,N6_90_0.1,N6_90_0.25,N6_90_0.5,N6_90_1.0"
  ES_ITERS="${ES_ITERS:-500}"; ES_POP="${ES_POP:-24}"; ES_BATCH="${ES_BATCH:-24}"; ES_VALN=64; ES_VALEVERY=10
  LAMS="${LAMS:-1:10:0,1:10:0.25}"  # lam_h (late-min high prio) : lam_c (cvar_h) : lam_m (makespan) -- PREREG_v4 §4
  TEST_LIMIT=0; TA_DAYS="7200-7299"; TB_DAYS="8200-8299"; TC_DAYS="8300-8399"; TL_DAYS="9200-9299"
  N4_DAYS="7200-7203"; SUB_DAYS="7200-7219"; M_BIG=32
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
progress "WX4 run_all start: ncpu=$NCPU workers=$W smoke=$SMOKE seeds=[$SEEDS] lams=[$LAMS] es_iters=$ES_ITERS python=$($PY -V 2>&1)"
$PY -c "import numpy, scipy" || { progress "numpy/scipy missing: run setup.sh"; exit 1; }

# ---- Stage 1: freeze literature baseline N6 on dev (grid, dev only; under the shared completion layer) ----
run_stage s1_n6grid $PY run_jobs3.py --out $R/dev_n6grid_v4.jsonl --methods N1_240,$N6GRID --plans dev_ours --days $DEV_DAYS $DLIM --workers $W
if ! [ -f wx_e/N6_FREEZE.$STAMP.json ]; then
  $PY - << PYEOF
import json, numpy as np, collections
rows=[json.loads(l) for l in open("$R/dev_n6grid_v4.jsonl") if '"error"' not in l]
by=collections.defaultdict(list); comp=collections.defaultdict(list)
for r in rows: by[r["method"]].append(r["J"]); comp[r["method"]].append(r.get("complete",1))
c={m:float(np.mean(v)) for m,v in by.items() if m.startswith("N6_")}
ok={m:v for m,v in c.items() if np.mean(comp[m])>=1.0-1e-12} or c
best=min(ok,key=ok.get)
json.dump(dict(best=best,dev_J=c,dev_complete={m:float(np.mean(v)) for m,v in comp.items()},frozen_by="min dev mean J among 100%-complete N6 configs, PREREG_v4 §3"),open("wx_e/N6_FREEZE.$STAMP.json","w"),indent=1)
print("N6 best",best,c[best])
PYEOF
fi
N6BEST=$($PY -c "import json;print(json.load(open('wx_e/N6_FREEZE.$STAMP.json'))['best'])")
progress "N6 frozen: $N6BEST"

# ---- Stage 2: ES-RL training (PREREG_v4 §4): ALL (seed, lambda) runs in parallel with EQUAL workers and a FIXED
#      iteration count (no wall-clock cap) -> genuinely equal compute. Trained inside the completion layer with
#      PI_TRAIN=1000 per unfinished target / missed urgent request. Resume-safe per iteration. ----
NL=$(echo ${LAMS//,/ } | wc -w); NS=$(echo $SEEDS | wc -w); NR=$((NL * NS)); WS=$(( W / NR )); [ "$WS" -lt 1 ] && WS=1
progress "ES: $NR runs x $WS workers, $ES_ITERS iters, pop $ES_POP, batch $ES_BATCH"
pids=()
for s in $SEEDS; do
  for lam in ${LAMS//,/ }; do
    IFS=: read -r LH LC LM <<< "$lam"; LM="${LM:-0}"
    run_stage s2_es_s${s}_${LH}_${LC}_${LM} $PY run_es.py --seed $s --init models/rl_s${s}_best_pomo_v2.npz --iters $ES_ITERS \
      --pop $ES_POP --batch $ES_BATCH --sigma 0.02 --lr 0.003 --val-n $ES_VALN --val-every $ES_VALEVERY --workers $WS \
      --lam_h $LH --lam_c $LC --lam_m $LM --pi-train 1000 --tag es --models models4 --log logs/es_train.log &
    pids+=($!)
  done
done
for p in "${pids[@]}"; do wait $p; done
SM=""; [ "$SMOKE" = "1" ] && SM="--dev-limit $DEV_LIMIT"
for s in $SEEDS; do
  run_stage s2_select_s$s $PY select_es.py --seed $s --lams $LAMS --tag es --models models4 --workers $W --dev-days $DEV_DAYS --bases N1_240,A1,A2,$N6BEST $SM
done
EXTRA=$($PY - << PYEOF
import json, os
e={"N6_best": {"policy": "$N6BEST"}}
for s in "$SEEDS".split():
    f=f"models4/final_es_s{s}.npz"
    if os.path.exists(f): e[f"RL4_s{s}"]={"ckpt": f}
    g=f"models/rl_s{s}_best_pomo_v2.npz"
    if os.path.exists(g): e[f"POMO_s{s}"]={"ckpt": g}
e["*"]={}
print(json.dumps(e))
PYEOF
)
export EXTRA
RLM=$($PY -c "import json,os;e=json.loads(os.environ['EXTRA']);print(','.join(k for k in e if k.startswith('RL4_')))")
POM=$($PY -c "import json,os;e=json.loads(os.environ['EXTRA']);print(','.join(k for k in e if k.startswith('POMO_')))")
progress "final policies: $RLM ; pomo inits: $POM"
[ -z "$RLM" ] && { progress "no final policies -> stop"; exit 2; }
EXTRA_R=$($PY -c "import json,os;e=json.loads(os.environ['EXTRA']);k=sorted(x for x in e if x.startswith('RL4_'))[0];c=e[k]['ckpt'];e['RLR_100ms']={'ckpt':c};e['RLR_1000ms']={'ckpt':c};print(json.dumps(e))")
BASES="N1_240,A1,A2,N6_best"

# ---- Stage 3: Test-A (official, 50 maps x 100 fresh weather days). N4fd = fair twin rollout (N1 base),
#      in-simulation decision deadline (PREREG_v4 §6). 1000 ms tier on a 20-day subset (cost). ----
run_stage s3_testA $PY run_jobs3.py --out $R/testA_v4.jsonl --methods $BASES,O,$POM,$RLM,N4fd_32_100ms --plans test_ours --days $TA_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s3_testA_1000 $PY run_jobs3.py --out $R/testA_v4.jsonl --methods N4fd_32_1000ms --plans test_ours --days $SUB_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s3_testA_N4big $PY run_jobs3.py --out $R/testA_v4.jsonl --methods N4f_M$M_BIG,N4p_M$M_BIG --plans test_ours --days $N4_DAYS $LIM --workers $W --extra "$EXTRA"
# ---- Stage 4: Test-B (author TSALNS plans), Test-C (stress), Test-L (larger maps 12x150 / 15x200) ----
run_stage s4_testB $PY run_jobs3.py --out $R/testB_v4.jsonl --methods $BASES,$POM,$RLM --plans test_ts --days $TB_DAYS $LIM --workers $W --extra "$EXTRA"
run_stage s4_testC $PY run_jobs3.py --out $R/testC_v4.jsonl --methods $BASES,$POM,$RLM --plans test_ours --days $TC_DAYS $LIM --scenario stress --workers $W --extra "$EXTRA"
run_stage s4_testL $PY run_jobs3.py --out $R/testL_v4.jsonl --methods $BASES,$POM,$RLM --plans test_large --days $TL_DAYS $LIM --workers $W --extra "$EXTRA"
# ---- Stage 5: P4 robustness (sigma x1.5; nowcast velocity bias x1.3) + P3 exploratory ----
run_stage s5_p4a $PY run_jobs3.py --out $R/p4_sigma15_v4.jsonl --methods $BASES,$POM,$RLM --plans test_ours --days $TA_DAYS $LIM --scenario sigma15 --workers $W --extra "$EXTRA"
run_stage s5_p4b $PY run_jobs3.py --out $R/p4_ncbias_v4.jsonl --methods $BASES,$POM,$RLM --plans test_ours --days $TA_DAYS $LIM --scenario ncbias --workers $W --extra "$EXTRA"
run_stage s5_p3 $PY run_jobs3.py --out $R/p3_uniform_v4.jsonl --methods N1_240,$POM,$RLM --plans test_ours --days $TA_DAYS $LIM --scenario uniform --workers $W --extra "$EXTRA"
# ---- Stage 6: WX-H latency Pareto on dev (fast RL vs fair rollouts 100/1000 ms; RL base + lookahead). 10 ms tier dropped. ----
run_stage s6_wxh $PY run_jobs3.py --out $R/wxh_v4.jsonl --methods N1_240,$RLM,N4fd_32_100ms,N4fd_32_1000ms,RLR_100ms,RLR_1000ms --plans dev_ours --days $DEV_DAYS $DLIM --workers $W --extra "$EXTRA_R"
# ---- Stage 7: analysis + pack ----
$PY analyze_v4.py >> logs/s7_analysis.log 2>&1 && progress "analysis written: results_final/SUMMARY_ZH.md" || progress "analysis FAILED (logs/s7_analysis.log)"
cp -f $R/*_v4.jsonl wx_e/N6_FREEZE.$STAMP.json models4/select_es_s*.json models4/es_hist_*.jsonl results_final/ 2>/dev/null
cp -f PROGRESS_SERVER.md results_final/ 2>/dev/null
tar -czf results_out.tar.gz results_final models4/final_*.npz logs/*.log wx_e/results/*.jsonl 2>/dev/null
progress "PACKED results_out.tar.gz ($(stat -c %s results_out.tar.gz 2>/dev/null) bytes). ALL DONE."
