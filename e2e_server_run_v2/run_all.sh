#!/usr/bin/env bash
# E2E-RL vs TSALNS — full pipeline (resumable; every stage writes runs/markers/<stage>.done).
#   SMOKE=1 bash run_all.sh      # minutes, tiny sizes, end-to-end check (CPU ok)
#   nohup bash run_all.sh > logs/run_all.log 2>&1 &    # full run (1 GPU + ~40 CPU cores)
# Knobs (env): ROUTE_H (12) GATE_H (2) SITE_H (3) SITEJ5_H (2) SMALL_H (1.5) PPO_ITERS (400) EXEC_H (2) SEEDS ("0 1 2") W (nproc-2)
set -uo pipefail
cd "$(dirname "$0")"; ROOT="$(pwd)"
export E2E_ROOT="$ROOT" WX_ROOT="$ROOT" PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PY="${PY:-$ROOT/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SMOKE="${SMOKE:-0}"
NCPU=$(nproc 2>/dev/null || echo 8); W="${W:-$(( NCPU > 4 ? NCPU - 2 : 2 ))}"
SEEDS="${SEEDS:-0 1 2}"
ROUTE_H="${ROUTE_H:-12}"; GATE_H="${GATE_H:-2}"; SITE_H="${SITE_H:-3}"; SITEJ5_H="${SITEJ5_H:-2}"; SMALL_H="${SMALL_H:-1.5}"
PPO_ITERS="${PPO_ITERS:-400}"; EXEC_H="${EXEC_H:-2}"; PPO_EP="${PPO_EP:-160}"; BUDGETS="${BUDGETS:-1 3 10 30}"; PLAN_B="${PLAN_B:-10}"
DAYS_A="${DAYS_A:-11700-11799}"; DAYS_B="${DAYS_B:-12700-12749}"; DAYS_L="${DAYS_L:-13700-13749}"; DAYS_DEV="${DAYS_DEV:-16000-16019}"
RUN="${RUN:-runs}"; LIM=""; RT_EXTRA=""; ST_EXTRA=""; PG_EXTRA=""
if [ "$SMOKE" = "1" ]; then
  RUN=runs_smoke; SEEDS="0"; ROUTE_H=0.03; GATE_H=0.02; SITE_H=0.01; SITEJ5_H=0.01; SMALL_H=0.01; PPO_ITERS=2; PPO_EP=8; BUDGETS="1"; PLAN_B=2
  DAYS_A=11700-11701; DAYS_B=12700-12700; DAYS_L=13700-13700; DAYS_DEV=16000-16001; W=$(( W < 4 ? W : 4 ))
  LIM="--limit_plans 2"; RT_EXTRA="--smoke --B 4 --N 4 --aug 2 --d 32 --enc 1 --dec 1 --val_every 5"; ST_EXTRA="--smoke --B 4 --M 4 --d 32 --layers 1 --distill_every 5"
fi
case " $BUDGETS " in *" $PLAN_B "*) ;; *) BUDGETS="$BUDGETS $PLAN_B";; esac
M="$RUN/markers"; mkdir -p "$M" logs results "$RUN"
ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }
progress() { echo "- $(ts) $*" >> PROGRESS_SERVER.md; echo "[run_all $(ts)] $*"; }
stage() { local name="$1"; shift; if [ -f "$M/$name.done" ]; then echo "[skip] $name"; return 0; fi
  progress "START $name"; local t0=$(date +%s)
  if "$@" >> "logs/$name.log" 2>&1; then touch "$M/$name.done"; progress "DONE $name ($(( $(date +%s) - t0 ))s)"; return 0
  else local rc=$?; progress "FAIL $name rc=$rc (see logs/$name.log)"; return $rc; fi; }
HAS_TS=0; [ -d baselines/tsalns_java/build/classes ] && HAS_TS=1
# REVIEW FIX (R-ts-missing): a full run without the compute-matched author TSALNS is not publishable -> stop early.
if [ "$SMOKE" != "1" ] && [ "$HAS_TS" != "1" ] && [ "${ALLOW_NO_TS:-0}" != "1" ]; then
  echo "TSALNS Java not built (see setup.sh / LRPHSD_DIR). Refusing a full run without it (ALLOW_NO_TS=1 to override)."; exit 3; fi
# REVIEW FIX (R-repack): RL arms adapt their plan to the morning forecast with pi_route (RL-owned), the heuristic
# repack only as a counted safety net. Baseline (TSALNS) arms keep the shared heuristic repack (v5 behaviour).
OURS_ADAPT="${OURS_ADAPT:-rl:$RUN/route_small/best.pt}"
progress "run_all start SMOKE=$SMOKE W=$W seeds=[$SEEDS] gpu=$($PY -c 'import torch;print(torch.cuda.is_available())') java_tsalns=$HAS_TS"
[ "$SMOKE" = "1" ] && TEST_GLOB='data/instances/test/5_35_[12].txt' || TEST_GLOB='data/instances/test/*.txt'
[ "$SMOKE" = "1" ] && FRESH_GLOB='data/instances/fresh/f5_35_[12].txt' || FRESH_GLOB='data/instances/fresh/*.txt'
[ "$SMOKE" = "1" ] && TRAIN_GLOB='data/instances/train/w5_35_1[0-3]0.txt' || TRAIN_GLOB='data/instances/train/*.txt'
[ "$SMOKE" = "1" ] && DEV_GLOB='data/instances/dev/d5_35_[12].txt' || DEV_GLOB='data/instances/dev/*.txt'
[ "$SMOKE" = "1" ] && LARGE_GLOB='data/instances/large/L12_150_1.txt' || LARGE_GLOB='data/instances/large/*.txt'

# ---------------- S0: fresh test instances ----------------
stage s0_fresh $PY e2e/gen_fresh.py || exit 1

# ---------------- S1: author's TSALNS, compute-matched budgets (+ battery-reserve variants) ----------------
if [ "$HAS_TS" = "1" ]; then
  for b in $BUDGETS; do
    stage s1_ts_test_$b  $PY baselines/tsalns_java/run_tsalns.py --inst "$TEST_GLOB"  --secs $b --out data/plans/test_ts$b.jsonl  --workers $W
    stage s1_ts_fresh_$b $PY baselines/tsalns_java/run_tsalns.py --inst "$FRESH_GLOB" --secs $b --out data/plans/fresh_ts$b.jsonl --workers $W
  done
  stage s1_ts_large  $PY baselines/tsalns_java/run_tsalns.py --inst "$LARGE_GLOB" --secs $PLAN_B --out data/plans/large_ts$PLAN_B.jsonl --workers $W
  stage s1_ts_res10  $PY baselines/tsalns_java/run_tsalns.py --inst "$TEST_GLOB" --secs $PLAN_B --reserve 0.1 --out data/plans/test_ts${PLAN_B}_r10.jsonl --workers $W
  stage s1_ts_res20  $PY baselines/tsalns_java/run_tsalns.py --inst "$TEST_GLOB" --secs $PLAN_B --reserve 0.2 --out data/plans/test_ts${PLAN_B}_r20.jsonl --workers $W
  # REVIEW FIX (R-primary): TSALNS plans on DEV maps (reserve 0/10/20 %) for the dev-only choice of the strongest non-RL baseline
  for rr in 0 0.1 0.2; do tag=$(echo $rr | tr -d '.'); 
    stage s1_ts_dev_r$tag $PY baselines/tsalns_java/run_tsalns.py --inst "$DEV_GLOB" --secs $PLAN_B --reserve $rr --out data/plans/dev_ts${PLAN_B}_r$tag.jsonl --workers $W
  done
else
  progress "WARN: TSALNS Java not built -> using shipped author TSALNS 10 s plans (data/plans/test_ts.jsonl) only"
fi
TSP=data/plans/test_ts.jsonl; [ -f data/plans/test_ts$PLAN_B.jsonl ] && TSP=data/plans/test_ts$PLAN_B.jsonl

# ---------------- S2: pi_route (P1) with the 2 h learning-curve gate ----------------
RT=$RUN/route
stage s2a_route_gate_segment $PY e2e/route_train.py --out $RT --hours $GATE_H --sched_h $ROUTE_H $RT_EXTRA || exit 1
if [ "$SMOKE" != "1" ]; then
  $PY e2e/gate.py --curve $RT/curve.jsonl --target_h $ROUTE_H --out results/gate_route.json; rc=$?
  if [ $rc -eq 10 ]; then progress "GATE STOP: extrapolated route gap misses the pre-registered gate (results/gate_route.json). Stopping."; exit 10; fi
  progress "GATE pass: $(cat results/gate_route.json | tr -d '\n ')"
fi
rm -f $RT/DONE
stage s2b_route_full $PY e2e/route_train.py --out $RT --hours $ROUTE_H --sched_h $ROUTE_H $RT_EXTRA || exit 1
stage s2c_route_small $PY e2e/route_train.py --out $RUN/route_small --hours $SMALL_H --d 64 --enc 3 --dec 1 --kc 16 ${RT_EXTRA:+--smoke --B 4 --N 4 --aug 2 --val_every 5} || exit 1

# ---------------- S3: pi_site (static reward + expert iteration) ----------------
stage s3_site $PY e2e/site_train.py --out $RUN/site --route $RT/best.pt --hours $SITE_H $ST_EXTRA || exit 1

# ---------------- S4: our plans on train/dev maps (training data for pi_exec; no TSALNS/ALNS plans used) ----------------
stage s4_plans_train $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TRAIN_GLOB" --out $RUN/plans/train_full.jsonl --mode full --budget 5 || exit 1
stage s4_plans_dev   $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$DEV_GLOB" --out $RUN/plans/dev_full.jsonl --mode full --budget $PLAN_B || exit 1

# ---------------- S5: pi_exec PPO (3 seeds), S6: pi_site J5 fine-tune (A4) per seed ----------------
for s in $SEEDS; do
  stage s5_exec_s$s $PY e2e/exec_ppo.py --out $RUN/exec_s$s --plans $RUN/plans/train_full.jsonl --router $RUN/route_small/best.pt \
        --iters $PPO_ITERS --hours $EXEC_H --episodes $PPO_EP --workers $W --seed $s --dev_plans $RUN/plans/dev_full.jsonl --dev_days $DAYS_DEV --adapt "$OURS_ADAPT" || exit 1
  stage s6_sitej5_s$s $PY e2e/site_train.py --out $RUN/site_j5_s$s --route $RT/best.pt --init $RUN/site/best.pt --reward j5 \
        --exec ppo:$RUN/exec_s$s/best.pt --hours $SITEJ5_H --workers $W --seed $s --lr 5e-5 --adapt "$OURS_ADAPT" $ST_EXTRA || exit 1
done
# REVIEW FIX (R-warmstart): RL5 (models_init/es_best_p5r_s0.npz) was trained by ES on the user's ALNS plans -> an
# exec arm trained from scratch (no RL5 init) shows whether the result depends on that ALNS-derived initialisation.
stage s5_exec_scratch_s0 $PY e2e/exec_ppo.py --out $RUN/exec_scratch_s0 --plans $RUN/plans/train_full.jsonl --router $RUN/route_small/best.pt \
      --init_rl5 none --iters $PPO_ITERS --hours $EXEC_H --episodes $PPO_EP --workers $W --seed 0 --dev_plans $RUN/plans/dev_full.jsonl --dev_days $DAYS_DEV --adapt "$OURS_ADAPT"

# ---------------- S7: test plans ----------------
for s in $SEEDS; do
  stage s7_plans_test_s$s  $PY e2e/plan_gen.py --site $RUN/site_j5_s$s/best.pt --route $RT/best.pt --inst "$TEST_GLOB"  --out $RUN/plans/test_e2e_s$s.jsonl  --mode j5 --budget $PLAN_B --exec ppo:$RUN/exec_s$s/best.pt --seed $s --adapt "$OURS_ADAPT" || exit 1
  stage s7_plans_large_s$s $PY e2e/plan_gen.py --site $RUN/site_j5_s$s/best.pt --route $RT/best.pt --inst "$LARGE_GLOB" --out $RUN/plans/large_e2e_s$s.jsonl --mode j5 --budget $PLAN_B --exec ppo:$RUN/exec_s$s/best.pt --seed $s --adapt "$OURS_ADAPT" || exit 1
done
# static ablations / compute curve (seed 0 policies, static-scored siting)
for b in $BUDGETS; do
  stage s7_static_test_full_$b  $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB"  --out $RUN/plans/test_full_b$b.jsonl  --mode full --budget $b
  stage s7_static_fresh_full_$b $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$FRESH_GLOB" --out $RUN/plans/fresh_full_b$b.jsonl --mode full --budget $b
done
stage s7_static_pure   $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB" --out $RUN/plans/test_pure.jsonl   --mode pure
stage s7_static_sample $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB" --out $RUN/plans/test_sample.jsonl --mode sample
stage s7_static_noeas  $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB" --out $RUN/plans/test_noeas.jsonl  --mode full --budget $PLAN_B --no_eas
stage s7_static_lns    $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB" --out $RUN/plans/test_full_lns.jsonl --mode full --budget $PLAN_B --lns_budget 5
# REVIEW FIX (R-compute): same 10 s budget with the policy on CPU only (hardware-matched to TSALNS, 1 process)
stage s7_static_cpu env E2E_DEVICE=cpu OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$TEST_GLOB" --out $RUN/plans/test_full_cpu.jsonl --mode full --budget $PLAN_B
stage s7_static_fresh_pure $PY e2e/plan_gen.py --site $RUN/site/best.pt --route $RT/best.pt --inst "$FRESH_GLOB" --out $RUN/plans/fresh_pure.jsonl --mode pure

# ---------------- S8: static tables (author's objective) ----------------
ARMS="OURS_pure=$RUN/plans/test_pure.jsonl,OURS_sample=$RUN/plans/test_sample.jsonl,OURS_noEAS=$RUN/plans/test_noeas.jsonl,OURS_full_lns=$RUN/plans/test_full_lns.jsonl"
for b in $BUDGETS; do ARMS="$ARMS,OURS_full_${b}s=$RUN/plans/test_full_b$b.jsonl"; done
for s in $SEEDS; do ARMS="$ARMS,OURS_j5_s$s=$RUN/plans/test_e2e_s$s.jsonl"; done
ARMS="$ARMS,OURS_full_cpu_${PLAN_B}s=$RUN/plans/test_full_cpu.jsonl"
stage s8_static_test $PY e2e/static_eval.py --ref $TSP --arms "$ARMS" --out results/static_test_vs_ts.md --gate_arm OURS_full_${PLAN_B}s --inst "$TEST_GLOB"
if [ "$HAS_TS" = "1" ]; then
  for b in $BUDGETS; do
    stage s8_static_matched_$b $PY e2e/static_eval.py --ref data/plans/test_ts$b.jsonl --arms "OURS_full_${b}s=$RUN/plans/test_full_b$b.jsonl" --out results/static_test_matched_$b.md --gate_arm OURS_full_${b}s --inst "$TEST_GLOB"
    stage s8_static_fresh_$b   $PY e2e/static_eval.py --ref data/plans/fresh_ts$b.jsonl --arms "OURS_full_${b}s=$RUN/plans/fresh_full_b$b.jsonl,OURS_pure=$RUN/plans/fresh_pure.jsonl" --out results/static_fresh_matched_$b.md --gate_arm OURS_full_${b}s --inst "$FRESH_GLOB"
  done
fi

# ---------------- S9: dynamic evaluation ----------------
BASEM="TS_A1=A1,TS_N6=N6_90_0.25,TS_Rfc=Rfc_N6_90_0.25,TS_RfcP=Rfc600e15_N6_90_0.25,TS_RL5=RL5:models_init/es_best_p5r_s0.npz"
cp -f $TSP $RUN/plans/ts_test.jsonl
# ---- S8b (REVIEW FIX R-primary): strongest non-RL baseline chosen on DEV only ----
if [ "$HAS_TS" = "1" ]; then
  for tag in r0 r01 r02; do cp -f data/plans/dev_ts${PLAN_B}_$tag.jsonl $RUN/plans/devts_$tag.jsonl
    stage s8b_dev_$tag $PY e2e/dyn_eval.py --out results/dev_select.jsonl --plans $RUN/plans/devts_$tag.jsonl --methods "A1=A1,N6=N6_90_0.25,Rfc=Rfc_N6_90_0.25,RfcP=Rfc600e15_N6_90_0.25" --days $DAYS_DEV --workers $W $LIM
  done
  MAPSEL="devts_r0:A1=TS_A1,devts_r0:N6=TS_N6,devts_r0:Rfc=TS_Rfc,devts_r0:RfcP=TS_RfcP,devts_r01:RfcP=TSr10_RfcP,devts_r02:RfcP=TSr20_RfcP,devts_r01:N6=TSr10_N6,devts_r01:Rfc=TSr10_Rfc,devts_r02:N6=TSr20_N6,devts_r02:Rfc=TSr20_Rfc"
  rm -f "$M/s8b_select.done"; stage s8b_select $PY e2e/dev_select.py --rows results/dev_select.jsonl --map "$MAPSEL" --out results/primary_baseline.txt
fi
[ -f results/primary_baseline.txt ] || echo TS_Rfc > results/primary_baseline.txt
# REVIEW FIX (R-info): information-matched TSALNS baseline (per-instance J5 selection among reserve variants on training days)
if [ -f data/plans/test_ts${PLAN_B}_r10.jsonl ] && [ -f data/plans/test_ts${PLAN_B}_r20.jsonl ]; then
  stage s8c_ts_j5sel $PY e2e/ts_j5select.py --plans $TSP,data/plans/test_ts${PLAN_B}_r10.jsonl,data/plans/test_ts${PLAN_B}_r20.jsonl --exec N6_90_0.25 --out $RUN/plans/ts_test_j5sel.jsonl --workers $W
fi
for SC in base sigma15 ncbias stress uniform; do
  DAYS=$DAYS_A; [ "$SC" != "base" ] && DAYS=$DAYS_B
  OUT=results/dyn_test_$SC.jsonl
  stage s9_dyn_ts_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/ts_test.jsonl --methods "$BASEM" --days $DAYS --scenario $SC --workers $W $LIM
  for rr in 10 20; do
    [ -f data/plans/test_ts${PLAN_B}_r$rr.jsonl ] && cp -f data/plans/test_ts${PLAN_B}_r$rr.jsonl $RUN/plans/ts_test_r$rr.jsonl && \
      stage s9_dyn_tsres${rr}_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/ts_test_r$rr.jsonl --methods "TSr${rr}_Rfc=Rfc_N6_90_0.25,TSr${rr}_N6=N6_90_0.25,TSr${rr}_RfcP=Rfc600e15_N6_90_0.25" --days $DAYS --scenario $SC --workers $W $LIM
  done
  [ -f $RUN/plans/ts_test_j5sel.jsonl ] && stage s9_dyn_tsj5_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/ts_test_j5sel.jsonl --methods "TSj5_N6=N6_90_0.25,TSj5_Rfc=Rfc_N6_90_0.25" --days $DAYS --scenario $SC --workers $W $LIM
  for s in $SEEDS; do
    stage s9_dyn_ours_${SC}_s$s $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/test_e2e_s$s.jsonl --methods "OURS_s$s=ppo:$RUN/exec_s$s/best.pt" --days $DAYS --scenario $SC --workers $W $LIM --adapt "$OURS_ADAPT"
    # REVIEW FIX (R-factorial): TSALNS plan + our full execution stack, EVERY seed (isolates the plan/siting contribution)
    stage s9_dyn_tsours_${SC}_s$s $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/ts_test.jsonl --methods "TS_OURSexec_s$s=ppo:$RUN/exec_s$s/best.pt" --days $DAYS --scenario $SC --workers $W $LIM --adapt "$OURS_ADAPT"
    # REVIEW FIX (R-factorial): our plan + the baseline execution (heuristic repack + Rfc / N6), EVERY seed
    stage s9_dyn_oursbase_${SC}_s$s $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/test_e2e_s$s.jsonl --methods "ABL_Rfc_s$s=Rfc_N6_90_0.25,ABL_N6_s$s=N6_90_0.25" --days $DAYS --scenario $SC --workers $W $LIM
  done
  stage s9_dyn_abl_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/test_e2e_s0.jsonl \
     --methods "ABL_RL5=RL5:models_init/es_best_p5r_s0.npz,ABL_noRR=ppo:$RUN/exec_s0/best.pt:noreroute,ABL_B_online=ppo:$RUN/exec_s0/best.pt:always,ABL_scratch=ppo:$RUN/exec_scratch_s0/best.pt" --days $DAYS --scenario $SC --workers $W $LIM --adapt "$OURS_ADAPT"
  stage s9_dyn_ablheur_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/test_e2e_s0.jsonl --methods "ABL_heurRepack=ppo:$RUN/exec_s0/best.pt" --days $DAYS --scenario $SC --workers $W $LIM
  for pl in test_full_b$PLAN_B test_pure test_noeas; do
    stage s9_dyn_ablplan_${pl}_$SC $PY e2e/dyn_eval.py --out $OUT --plans $RUN/plans/$pl.jsonl --methods "ABLP_$pl=ppo:$RUN/exec_s0/best.pt" --days $DAYS --scenario $SC --workers $W $LIM --adapt "$OURS_ADAPT"
  done
done
# large maps
if [ -f data/plans/large_ts$PLAN_B.jsonl ]; then cp -f data/plans/large_ts$PLAN_B.jsonl $RUN/plans/ts_large.jsonl
  stage s9_dyn_ts_large $PY e2e/dyn_eval.py --out results/dyn_large.jsonl --plans $RUN/plans/ts_large.jsonl --methods "$BASEM" --days $DAYS_L --workers $W $LIM; fi
for s in $SEEDS; do
  stage s9_dyn_large_s$s $PY e2e/dyn_eval.py --out results/dyn_large.jsonl --plans $RUN/plans/large_e2e_s$s.jsonl --methods "OURS_s$s=ppo:$RUN/exec_s$s/best.pt" --days $DAYS_L --workers $W $LIM --adapt "$OURS_ADAPT"
  stage s9_dyn_large_base_s$s $PY e2e/dyn_eval.py --out results/dyn_large.jsonl --plans $RUN/plans/large_e2e_s$s.jsonl --methods "ABL_N6_s$s=N6_90_0.25" --days $DAYS_L --workers $W $LIM
done

# ---------------- S10: analysis ----------------
OURS=""; for s in $SEEDS; do OURS="$OURS${OURS:+,}OURS_s$s=test_e2e_s$s:OURS_s$s"; done
BASE="TS_A1=ts_test:TS_A1,TS_N6=ts_test:TS_N6,TS_Rfc=ts_test:TS_Rfc,TS_RfcP=ts_test:TS_RfcP,TS_RL5=ts_test:TS_RL5"
for s in $SEEDS; do BASE="$BASE,TS_OURSexec_s$s=ts_test:TS_OURSexec_s$s"; done
[ -f $RUN/plans/ts_test_j5sel.jsonl ] && BASE="$BASE,TSj5_N6=ts_test_j5sel:TSj5_N6,TSj5_Rfc=ts_test_j5sel:TSj5_Rfc"
for rr in 10 20; do [ -f $RUN/plans/ts_test_r$rr.jsonl ] && BASE="$BASE,TSr${rr}_Rfc=ts_test_r$rr:TSr${rr}_Rfc,TSr${rr}_N6=ts_test_r$rr:TSr${rr}_N6,TSr${rr}_RfcP=ts_test_r$rr:TSr${rr}_RfcP"; done
EXTRA="ABL_Rfc=test_e2e_s0:ABL_Rfc_s0,ABL_N6=test_e2e_s0:ABL_N6_s0,ABL_scratch=test_e2e_s0:ABL_scratch,ABL_heurRepack=test_e2e_s0:ABL_heurRepack,ABL_RL5=test_e2e_s0:ABL_RL5,ABL_noRR=test_e2e_s0:ABL_noRR,ABL_B_online=test_e2e_s0:ABL_B_online,ABLP_full_static=test_full_b$PLAN_B:ABLP_test_full_b$PLAN_B,ABLP_pure=test_pure:ABLP_test_pure,ABLP_noeas=test_noeas:ABLP_test_noeas"
for SC in base sigma15 ncbias stress uniform; do
  rm -f "$M/s10_an_$SC.done"
  stage s10_an_$SC $PY e2e/analyze_e2e.py --rows results/dyn_test_$SC.jsonl --scenario $SC --ours "$OURS" --base "$BASE" --extra "$EXTRA" --primary @results/primary_baseline.txt --out results/dyn_test_$SC.md
done
if [ -f results/dyn_large.jsonl ]; then rm -f "$M/s10_an_large.done"
  LB="ABL_N6_s0=large_e2e_s0:ABL_N6_s0"; [ -f $RUN/plans/ts_large.jsonl ] && LB="TS_A1=ts_large:TS_A1,TS_N6=ts_large:TS_N6,TS_Rfc=ts_large:TS_Rfc,TS_RL5=ts_large:TS_RL5"
  OL=""; for s in $SEEDS; do OL="$OL${OL:+,}OURS_s$s=large_e2e_s$s:OURS_s$s"; done
  stage s10_an_large $PY e2e/analyze_e2e.py --rows results/dyn_large.jsonl --ours "$OL" --base "$LB" --primary TS_Rfc --ot_ref TS_N6 --out results/dyn_large.md
fi
rm -f "$M/s10_pack.done"
stage s10_pack bash -c "tar czf results/e2e_results_$(hostname)_$(date +%Y%m%d_%H%M).tgz results/*.md results/*.json PROGRESS_SERVER.md logs/*.log $RUN/*/curve.jsonl $RUN/plans/*.jsonl $RUN/*/DONE 2>/dev/null; ls -la results/*.tgz"
progress "run_all finished (SMOKE=$SMOKE). Results: results/*.md ; pack: results/e2e_results_*.tgz"
