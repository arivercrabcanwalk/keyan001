#!/usr/bin/env bash
# E2E-RL v3 vs the author's TSALNS (adapted under strict 100 % completion) — full pipeline, resumable.
# Every stage writes $RUN/markers/<stage>.done ; re-running the script skips finished stages.
#   SMOKE=1 bash run_all.sh                               # ~20-40 min CPU, tiny sizes, end-to-end check
#   nohup bash run_all.sh > logs/run_all.log 2>&1 &       # full run (1 GPU + ~40 CPU cores), ETA ~35 h
# Knobs (env, defaults in brackets):
#   SEEDS ["0 1 2 3 4"]  ROUTE_H [3] per seed  ROUTE_PAR [5] route seeds trained concurrently on the GPU
#   EXIT_ROUNDS [3] EXIT_DAYS [600] ES_ITERS [300] ES_H [3]  J5_H [1.5]  SITE_H [0.75]
#   BUDGETS ["1 3 10 30 60"]  W [nproc-2]  ROUTE_INIT [""] (optional warm start, e.g. the v2 runs/route/best.pt;
#   recorded in the curve/state and must be reported) TS_REPS [3] replicate TSALNS runs (10 s) for seed variance
set -uo pipefail
cd "$(dirname "$0")"; ROOT="$(pwd)"
export E2E_ROOT="$ROOT" WX_ROOT="$ROOT" PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} MKL_NUM_THREADS=${MKL_NUM_THREADS:-1} OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}
PY="${PY:-$ROOT/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SMOKE="${SMOKE:-0}"
NCPU=$(nproc 2>/dev/null || echo 8); W="${W:-$(( NCPU > 4 ? NCPU - 2 : 2 ))}"
SEEDS="${SEEDS:-0 1 2 3 4}"; ROUTE_H="${ROUTE_H:-3}"; ROUTE_PAR="${ROUTE_PAR:-5}"
EXIT_ROUNDS="${EXIT_ROUNDS:-3}"; EXIT_DAYS="${EXIT_DAYS:-600}"; ES_ITERS="${ES_ITERS:-300}"; ES_H="${ES_H:-3}"
J5_H="${J5_H:-1.5}"; SITE_H="${SITE_H:-0.75}"; BUDGETS="${BUDGETS:-1 3 10 30 60}"; TS_REPS="${TS_REPS:-3}"
ROUTE_INIT="${ROUTE_INIT:-}"
DAYS_T="${DAYS_T:-21700-21799}"; DAYS_TS="${DAYS_TS:-21700-21719}"; DAYS_R="${DAYS_R:-22700-22749}"; DAYS_O="${DAYS_O:-22700-22719}"
DAYS_L="${DAYS_L:-23700-23749}"; DAYS_DEV="${DAYS_DEV:-26000-26019}"
RUN="${RUN:-runs_v3}"; RT_EXTRA=""; XE=""; J5E=""; SE=""; LIM=""; SOE=""
if [ "$SMOKE" = "1" ]; then
  RUN=runs_v3_smoke; SEEDS="0"; ROUTE_H=0.03; ROUTE_PAR=1; BUDGETS="10"; TS_REPS=1; W=$(( W < 6 ? W : 6 ))
  DAYS_T=21700-21701; DAYS_TS=21700-21700; DAYS_R=22700-22700; DAYS_O=22700-22700; DAYS_L=23700-23700; DAYS_DEV=26000-26001
  RT_EXTRA="--smoke --B 4 --N 4 --aug 2 --d 32 --enc 1 --dec 1 --val_every 5"
  XE="--rounds 1 --days_per_round 8 --M 2 --x_epochs 2 --es_iters 2 --es_pop 2 --es_batch 3 --es_pool 12 --val_every 1"
  J5E="--smoke --B 2 --m 2 --K 1 --max_iters 2 --val_every 1"; SE="--smoke --B 2 --m 2 --K 1 --max_iters 2 --dev_every 1 --n_dev 2 --kmax 6"
  LIM="--limit_plans 2"; SOE="--C 3 --K 1"
fi
M="$RUN/markers"; PL="$RUN/plans"; mkdir -p "$M" "$PL" logs results "$RUN"
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
progress() { echo "- $(ts) $*" >> PROGRESS_SERVER.md; echo "[run_all $(ts)] $*"; }
stage() { local name="$1"; shift; if [ -f "$M/$name.done" ]; then echo "[skip] $name"; return 0; fi
  progress "START $name"; local t0=$(date +%s)
  if "$@" >> "logs/$name.log" 2>&1; then touch "$M/$name.done"; progress "DONE $name ($(( $(date +%s) - t0 ))s)"; return 0
  else local rc=$?; progress "FAIL $name rc=$rc (see logs/$name.log)"; return $rc; fi; }
HAS_TS=0; [ -d baselines/tsalns_java/build/classes ] && HAS_TS=1
if [ "$HAS_TS" != "1" ] && [ "${ALLOW_NO_TS:-0}" != "1" ]; then
  echo "TSALNS Java not built (setup.sh, LRPHSD_DIR, javac). v3 needs it for TS-FIX/TS-CC (ALLOW_NO_TS=1: smoke without author arms)."; exit 3; fi
progress "run_all v3 start SMOKE=$SMOKE W=$W seeds=[$SEEDS] gpu=$($PY -c 'import torch;print(torch.cuda.is_available())') java=$HAS_TS"
if [ "$SMOKE" = "1" ]; then
  TEST_GLOB='data/instances/test/5_35_[12].txt'; FRESH_GLOB='data/instances/fresh/f5_35_[12].txt'; TRAIN_GLOB='data/instances/train/w5_35_1[0-3]0.txt'
  DEV_GLOB='data/instances/dev/d5_35_[12].txt'; LARGE_GLOB='data/instances/large/L12_150_1.txt'
else
  TEST_GLOB='data/instances/test/*.txt'; FRESH_GLOB='data/instances/fresh/*.txt'; TRAIN_GLOB='data/instances/train/*.txt'
  DEV_GLOB='data/instances/dev/*.txt'; LARGE_GLOB='data/instances/*large/*.txt'
fi
TSR="$PY baselines/tsalns_java/run_tsalns.py --workers $W"
RL5="RL5:models_init/es_best_p5r_s0.npz"

# ======== S0: coverage layer + G0 on the shipped author plans (documents the v2 gap) ========
stage s0_fresh $PY e2e/gen_fresh.py || exit 1
stage s0_g0_shipped $PY e2e/verify_coverage.py --sets "ts_shipped=data/plans/test_ts.jsonl" --days "base:$DAYS_T;stress:$DAYS_R" --out results/G0_shipped --workers $W --allow_fail ts_shipped

# ======== S1: author arms (Java TSALNS, compute-matched budgets) — all must pass G0 ========
if [ "$HAS_TS" = "1" ]; then
  stage s1_dev_tsfix $TSR --inst "$DEV_GLOB" --secs 10 --fix mincov --tag fix --out $PL/dev_tsfix10.jsonl || exit 1
  stage s1_dev_tscc  $TSR --inst "$DEV_GLOB" --secs 10 --cov 1 --tag cc --out $PL/dev_tscc10.jsonl || exit 1
fi
DEVP=$PL/dev_tsfix10.jsonl; [ -f $DEVP ] || DEVP=data/plans/dev_ts.jsonl

# ======== S2: pi_route, SEEDS in parallel on the GPU (author arms S1b run concurrently on the CPU) ========
route_seed() { local s=$1; stage s2_route_s$s $PY e2e/route_train.py --out $RUN/route_s$s --hours $ROUTE_H --seed $s --cfl_frac 0.6 \
    --dev_plans $DEVP${ROUTE_INIT:+ --init $ROUTE_INIT} $RT_EXTRA; }
n=0; for s in $SEEDS; do route_seed $s & n=$((n+1)); if [ $n -ge $ROUTE_PAR ]; then wait -n; n=$((n-1)); fi; done
if [ "$HAS_TS" = "1" ]; then (
  for b in $BUDGETS; do
    stage s1_test_ts$b    $TSR --inst "$TEST_GLOB" --secs $b --out $PL/test_ts$b.jsonl
    stage s1_test_tsfix$b $TSR --inst "$TEST_GLOB" --secs $b --fix mincov --tag fix --out $PL/tsfix$b.jsonl
  done
  for r in $(seq 1 $((TS_REPS-1))); do stage s1_test_tsfix10_rep$r $TSR --inst "$TEST_GLOB" --secs 10 --fix mincov --tag fix_rep$r --out $PL/tsfix10_rep$r.jsonl; done
  stage s1_test_tscc10 $TSR --inst "$TEST_GLOB" --secs 10 --cov 1 --tag cc --out $PL/tscc10.jsonl
  stage s1_test_tscc60 $TSR --inst "$TEST_GLOB" --secs 60 --cov 1 --tag cc --out $PL/tscc60.jsonl
  for b in 10 60; do
    stage s1_fresh_tsfix$b $TSR --inst "$FRESH_GLOB" --secs $b --fix mincov --tag fix --out $PL/fresh_tsfix$b.jsonl
    stage s1_large_tsfix$b $TSR --inst "$LARGE_GLOB" --secs $b --fix mincov --tag fix --out $PL/large_tsfix$b.jsonl
  done
  stage s1_large_tscc10 $TSR --inst "$LARGE_GLOB" --secs 10 --cov 1 --tag cc --out $PL/large_tscc10.jsonl
  B10=$PL/test_ts10.jsonl; [ -f $B10 ] || B10=$PL/test_ts1.jsonl
  stage s1_tscr $PY e2e/author_adapt.py --src $B10 --out $PL/tscr10.jsonl --mode cr
  stage s1_pad  $PY e2e/author_adapt.py --src $B10 --out $PL/pad10.jsonl --mode pad
  SETS="tscr10=$PL/tscr10.jsonl,pad10=$PL/pad10.jsonl,tscc10=$PL/tscc10.jsonl"; for b in $BUDGETS; do SETS="$SETS,tsfix$b=$PL/tsfix$b.jsonl"; done
  stage s1_G0 $PY e2e/verify_coverage.py --sets "$SETS" --days "base:$DAYS_T;stress:$DAYS_R" --out results/G0_author --workers $W
) > logs/s1_group.log 2>&1 &
fi
wait   # route seeds + author arms
[ -f $M/s1_G0.done ] || [ "$HAS_TS" != "1" ] || { progress "G0 FAILED for an author arm (results/G0_author.md) -> stop"; exit 4; }
for s in $SEEDS; do [ -f $M/s2_route_s$s.done ] || { progress "route seed $s failed"; exit 1; }; done

# ======== S3: our plans on TRAIN/DEV maps (pi_exec training data; S* = MinCov, pi_route pomo; no ALNS) ========
for s in $SEEDS; do
  stage s3_plans_train_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$TRAIN_GLOB" --siting mincov --mode pomo --seed $s --out $PL/train_v3_s$s.jsonl || exit 1
  stage s3_plans_dev_s$s   $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$DEV_GLOB"   --siting mincov --mode pomo --seed $s --out $PL/dev_v3_s$s.jsonl || exit 1
done

# ======== S4 (CPU) pi_exec per seed: ExIt (fair-twin search, OFFLOAD) -> ES (PID-Lagrangian OT) ;
#          S5 (GPU, concurrently) static test plans of pi_route at every budget ========
(
for s in $SEEDS; do
  for b in $BUDGETS; do stage s5_v3_${b}_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$TEST_GLOB" --siting mincov --mode anytime --budget $b --seed $s --tag v3_$b --out $PL/v3_${b}_s$s.jsonl; done
  for b in 10 60; do
    stage s5_fresh_v3_${b}_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$FRESH_GLOB" --siting mincov --mode anytime --budget $b --seed $s --out $PL/fresh_v3_${b}_s$s.jsonl
    stage s5_large_v3_${b}_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$LARGE_GLOB" --siting mincov --mode anytime --budget $b --seed $s --out $PL/large_v3_${b}_s$s.jsonl
  done
  stage s5_v3greedy_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$TEST_GLOB" --siting mincov --mode greedy --seed $s --out $PL/v3greedy_s$s.jsonl
  stage s5_v3pomo_s$s   $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$TEST_GLOB" --siting mincov --mode pomo --seed $s --out $PL/v3pomo_s$s.jsonl
done ) > logs/s5_group.log 2>&1 &
for s in $SEEDS; do
  stage s4_exec_s$s $PY e2e/exec_train_v3.py --out $RUN/exec_s$s --plans $PL/train_v3_s$s.jsonl --dev_plans $PL/dev_v3_s$s.jsonl --dev_days $DAYS_DEV \
      --seed $s --workers $W --init_rl5 models_init/es_best_p5r_s0.npz --rounds $EXIT_ROUNDS --days_per_round $EXIT_DAYS --es_iters $ES_ITERS --es_hours $ES_H $XE || exit 1
done
# ablations (seed 0): ExIt from scratch (round-0 base = N6 rule, no RL5 weights) ; ES only (no ExIt)
stage s4_abl_scratch $PY e2e/exec_train_v3.py --out $RUN/exec_scratch_s0 --plans $PL/train_v3_s0.jsonl --dev_plans $PL/dev_v3_s0.jsonl --dev_days $DAYS_DEV \
      --seed 0 --workers $W --rounds $EXIT_ROUNDS --days_per_round $EXIT_DAYS --stageP none $XE
stage s4_abl_esonly $PY e2e/exec_train_v3.py --out $RUN/exec_esonly_s0 --plans $PL/train_v3_s0.jsonl --dev_plans $PL/dev_v3_s0.jsonl --dev_days $DAYS_DEV \
      --seed 0 --workers $W --init_rl5 models_init/es_best_p5r_s0.npz --rounds 0 --es_iters $ES_ITERS --es_hours $ES_H $XE
wait

# ======== S6: pi_route-J5 (bi-level, exec = our pi_exec of the same seed) -> J5-aware test plans ========
for s in $SEEDS; do
  stage s6_routej5_s$s $PY e2e/route_j5.py --out $RUN/routej5_s$s --init $RUN/route_s$s/best.pt --exec v3:$RUN/exec_s$s/best.pt \
      --dev_inst "$DEV_GLOB" --hours $J5_H --seed $s --workers $W $J5E || exit 1
  stage s6_v3j5_s$s $PY e2e/plan_v3.py --route $RUN/routej5_s$s/best.pt --inst "$TEST_GLOB" --siting mincov --mode pomo --seed $s --tag v3j5 --out $PL/v3j5_s$s.jsonl || exit 1
done

# ======== S7: pi_site on large maps (siting freedom) + SimOpt-J5 baseline ========
for s in $SEEDS; do
  stage s7_site_s$s $PY e2e/site_v3.py --out $RUN/site_s$s --route $RUN/route_s$s/best.pt --exec v3:$RUN/exec_s$s/best.pt --hours $SITE_H --seed $s --workers $W $SE || exit 1
  stage s7_large_site_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$LARGE_GLOB" --siting site:$RUN/site_s$s/best.pt --mode anytime --budget 10 --seed $s --out $PL/large_v3site_s$s.jsonl
  stage s7_simopt_s$s $PY e2e/site_v3.py --simopt --out $PL/large_simopt_sit_s$s.jsonl --route $RUN/route_s$s/best.pt --exec v3:$RUN/exec_s$s/best.pt --inst "$LARGE_GLOB" --seed $s --workers $W $SOE
  stage s7_large_simopt_s$s $PY e2e/plan_v3.py --route $RUN/route_s$s/best.pt --inst "$LARGE_GLOB" --siting plan:$PL/large_simopt_sit_s$s.jsonl --mode anytime --budget 10 --seed $s --out $PL/large_v3simopt_s$s.jsonl
done

# ======== S8: dynamic evaluation (identical shared feasibility layer / adaptation for every arm) ========
DY="$PY e2e/dyn_eval.py --workers $W $LIM"
AUTH="$PL/tsfix10.jsonl,$PL/tscr10.jsonl,$PL/tscc10.jsonl,$PL/pad10.jsonl"
RULES="A1=A1,N6=N6_90_0.25,Rfc=Rfc_N6_90_0.25,RfcP=Rfc600e15_N6_90_0.25,RL5=$RL5,OFFN6=OFF+N6_90_0.25"
stage s8_auth_base   $DY --out results/dyn_base.jsonl   --plans "$AUTH" --methods "$RULES" --days $DAYS_T
stage s8_auth_stress $DY --out results/dyn_stress.jsonl --plans "$AUTH" --methods "N6=N6_90_0.25,Rfc=Rfc_N6_90_0.25,RL5=$RL5" --days $DAYS_R --scenario stress
stage s8_rlr $DY --out results/dyn_base.jsonl --plans $PL/tsfix10.jsonl --methods "RLR=RLR:models_init/es_best_p5r_s0.npz:100" --days $DAYS_TS
for s in $SEEDS; do
  OX="OURS_s$s=v3:$RUN/exec_s$s/best.pt,OURSnooff_s$s=v3:$RUN/exec_s$s/best.pt:nooff"
  stage s8_ours_base_s$s   $DY --out results/dyn_base.jsonl --plans "$PL/v3j5_s$s.jsonl,$PL/v3_10_s$s.jsonl,$PL/tsfix10.jsonl,$PL/tscr10.jsonl,$PL/pad10.jsonl" --methods "$OX" --days $DAYS_T
  stage s8_oursplan_rules_s$s $DY --out results/dyn_base.jsonl --plans "$PL/v3j5_s$s.jsonl,$PL/v3_10_s$s.jsonl" --methods "A1=A1,N6=N6_90_0.25,Rfc=Rfc_N6_90_0.25,RL5=$RL5" --days $DAYS_T
  stage s8_search_s$s $DY --out results/dyn_base.jsonl --plans "$PL/tsfix10.jsonl" --methods "OURSS_s$s=v3s:$RUN/exec_s$s/best.pt:100" --days $DAYS_TS
  stage s8_ours_stress_s$s $DY --out results/dyn_stress.jsonl --plans "$PL/v3j5_s$s.jsonl,$PL/tsfix10.jsonl" --methods "OURS_s$s=v3:$RUN/exec_s$s/best.pt,RL5=$RL5" --days $DAYS_R --scenario stress
  for SC in sigma15 ncbias uniform; do
    stage s8_ours_${SC}_s$s $DY --out results/dyn_$SC.jsonl --plans "$PL/v3j5_s$s.jsonl,$PL/tsfix10.jsonl" --methods "OURS_s$s=v3:$RUN/exec_s$s/best.pt,RL5=$RL5,N6=N6_90_0.25" --days $DAYS_O --scenario $SC
  done
  LP="$PL/large_v3site_s$s.jsonl,$PL/large_v3_10_s$s.jsonl,$PL/large_v3simopt_s$s.jsonl,$PL/large_tscc10.jsonl,$PL/large_tsfix10.jsonl"
  stage s8_large_s$s $DY --out results/dyn_large.jsonl --plans "$LP" --methods "OURS_s$s=v3:$RUN/exec_s$s/best.pt,RL5=$RL5" --days $DAYS_L
done
stage s8_abl $DY --out results/dyn_base.jsonl --plans "$PL/v3j5_s0.jsonl,$PL/tsfix10.jsonl" --methods "ABLscratch=v3:$RUN/exec_scratch_s0/best.pt,ABLesonly=v3:$RUN/exec_esonly_s0/best.pt" --days $DAYS_T
stage s8_large_rules $DY --out results/dyn_large.jsonl --plans "$PL/large_tscc10.jsonl,$PL/large_tsfix10.jsonl" --methods "N6=N6_90_0.25,Rfc=Rfc_N6_90_0.25" --days $DAYS_L

# ======== S9: analysis, gates, raw CSV, pack ========
rm -f $M/s9_analysis.done $M/s9_pack.done
stage s9_analysis $PY e2e/analyze_v3.py --dyn 'results/dyn_*.jsonl' --plans_dir $PL --gates gates_v3.json --seeds "$SEEDS" --static "$PL/*.jsonl" --out results/analysis_v3
stage s9_pack bash -c "tar czf results/e2e_v3_results_$(hostname)_$(date +%Y%m%d_%H%M).tgz results/analysis_v3 results/G0_* results/dyn_*.jsonl PROGRESS_SERVER.md logs/*.log $RUN/*/curve.jsonl $RUN/*/state.json $RUN/*/DONE $PL/*.jsonl $RUN/exec_s*/best.pt $RUN/site_s*/best.pt 2>/dev/null; ls -la results/*.tgz"
progress "run_all v3 finished (SMOKE=$SMOKE): results/analysis_v3/ANALYSIS_V3.md, raw CSV results/analysis_v3/raw_per_instance.csv, pack results/e2e_v3_results_*.tgz"
