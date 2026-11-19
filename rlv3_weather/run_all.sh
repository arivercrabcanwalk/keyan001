#!/usr/bin/env bash
# rlv3 pipeline (rlv3_weather).  Resumable: every stage writes a marker; re-running skips finished stages.
#   SMOKE=1 bash run_all.sh      # ~10-20 min end-to-end mini run (must pass before the full run)
#   bash run_all.sh              # full experiment
# Env overrides: PY (python), W (CPU workers, default nproc-2), SEEDS ("0 1 2"), RI_H (rollout-improvement hours per seed, default 2), RL_H (policy-gradient hours per seed, default 1),
#                ABL_H (RI hours per ablation, default 1; +0.5 h PG), TS_SECS (TSALNS budget per training map, default 10), DEVICE (cuda/cpu)
set -uo pipefail
cd "$(dirname "$0")"
export RLV3_ROOT="$PWD"
PKG="rlv3_weather"
SCEN="weather"                 # training / main test scenario
EXTRA="weather_storm weather_wind weather_x1.3"               # additional test scenarios (same trained policies)
SMOKE="${SMOKE:-0}"
if [ -z "${PY:-}" ]; then if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi; fi
NP=$(nproc 2>/dev/null || echo 8)
W="${W:-$(( NP > 4 ? NP - 2 : 2 ))}"
DEVICE="${DEVICE:-auto}"
if [ "$SMOKE" = "1" ]; then
  TAG=smoke; SEEDS="${SEEDS:-0}"; TS_SECS="${TS_SECS:-1}"; TRAIN_GLOB='data/instances/train/*_[1-2].txt'; FRESH_GLOB='data/instances/fresh/*_1.txt'
  TRARGS="--bc_episodes 24 --bc_epochs 3 --ri_iters 2 --ri_hours 0.2 --ri_maps 4 --rl_iters 6 --rl_hours 0.2 --batch_maps 4 --rollouts 4 --dev_days 2 --dev_maps 4 --eval_every 3"
  ABARGS="$TRARGS"; TUNE="--days 2 --maps 4"; TMAPS="--maps 4"; TDAYS="90000:90002"; XDAYS="90000:90002"
else
  TAG=full; SEEDS="${SEEDS:-0 1 2}"; TS_SECS="${TS_SECS:-10}"; TRAIN_GLOB='data/instances/train/*.txt'; FRESH_GLOB='data/instances/fresh/*.txt'
  RI_H="${RI_H:-2}"; RL_H="${RL_H:-1}"; ABL_H="${ABL_H:-1}"
  TRARGS="--bc_episodes 600 --bc_epochs 10 --ri_hours $RI_H --ri_maps 32 --rl_iters 100000 --rl_hours $RL_H --batch_maps 32 --rollouts 8 --dev_days 10 --dev_maps 20 --eval_every 50"
  ABARGS="--bc_episodes 600 --bc_epochs 10 --ri_hours $ABL_H --ri_maps 32 --rl_iters 100000 --rl_hours 0.5 --batch_maps 32 --rollouts 8 --dev_days 10 --dev_maps 20 --eval_every 50"
  TUNE="--days 20 --maps 20"; TMAPS=""; TDAYS="test"; XDAYS="90000:90030"
fi
RUN=runs_$TAG; RES=results_$TAG; PL=data/plans; MK=.markers_$TAG
mkdir -p logs $RUN $RES $MK
progress(){ echo "- $(date '+%F %T %Z') [$PKG/$TAG] $*" | tee -a PROGRESS_SERVER.md; }
stage(){ local n="$1"; shift
  if [ -f "$MK/$n.done" ]; then echo "[skip] $n"; return 0; fi
  progress "START $n"; local t0=$(date +%s)
  "$@" > "logs/${TAG}_$n.log" 2>&1; local rc=$?
  if [ $rc -eq 0 ]; then touch "$MK/$n.done"; progress "DONE $n ($(( $(date +%s) - t0 ))s)"; return 0; fi
  progress "FAIL $n rc=$rc (see logs/${TAG}_$n.log)"; tail -20 "logs/${TAG}_$n.log"; return $rc; }
die(){ progress "STOP: $*"; exit 1; }

progress "run_all start SMOKE=$SMOKE W=$W seeds=[$SEEDS] py=$PY"
# ---------------- S0 environment + author's TSALNS ----------------
stage s0_env $PY -c "import torch,numpy,scipy;print(torch.__version__,torch.cuda.is_available())" || die "python env (run setup.sh)"
stage s0_build_tsalns bash baselines/tsalns_java/build.sh || die "TSALNS build (need javac)"
# ---------------- S1 unit tests (energy model == author at zero wind, shield, completion, no extra stations) ----------------
stage s1_tests $PY -m pytest -q tests || die "unit tests failed"
# ---------------- S2 author's TSALNS plans for TRAIN (+fresh generalisation) maps; test/dev plans are shipped ----------------
stage s2_ts_train $PY baselines/tsalns_java/run_tsalns.py --inst "$TRAIN_GLOB" --secs $TS_SECS --out $PL/train_ts_$TAG.jsonl --workers $W || die "TSALNS train plans"
stage s2_ts_fresh $PY baselines/tsalns_java/run_tsalns.py --inst "$FRESH_GLOB" --secs $TS_SECS --out $PL/fresh_ts_$TAG.jsonl --workers $W || die "TSALNS fresh plans"
# ---------------- S3 dev tuning of every non-RL baseline (risk buffer / wind-wait threshold) ----------------
stage s3_tune $PY rlcore/tune.py --plans $PL/dev_ts.jsonl --scen $SCEN $TUNE --out $RES/tuned_$SCEN.json --workers $W || die "tuning"
TEACHER=$($PY -c "import json;print(json.load(open('$RES/tuned_$SCEN.json'))['overall'])")
progress "teacher (best dev-tuned non-RL) = $TEACHER"
# ---------------- S4 RL training (BC from teacher -> multi-rollout policy gradient), seeds + ablations ----------------
for s in $SEEDS; do
  stage s4_rl_s$s $PY rlcore/train.py --scen $SCEN --plans $PL/train_ts_$TAG.jsonl --dev_plans $PL/dev_ts.jsonl --out $RUN/rl_s$s \
      --seed $s --workers $W --teacher "$TEACHER" --device $DEVICE $TRARGS || die "RL seed $s"
done
# ablations (seed 0): no physics features / sketch eta-shaping reward / pure end-to-end (no base suggestion)
stage s4_abl_nophys $PY rlcore/train.py --scen $SCEN --plans $PL/train_ts_$TAG.jsonl --dev_plans $PL/dev_ts.jsonl --out $RUN/abl_nophys --seed 0 --workers $W --teacher "$TEACHER" --device $DEVICE --feat_ablate nophys $ABARGS || progress "WARN ablation nophys failed (continuing)"
stage s4_abl_eta $PY rlcore/train.py --scen $SCEN --plans $PL/train_ts_$TAG.jsonl --dev_plans $PL/dev_ts.jsonl --out $RUN/abl_eta --seed 0 --workers $W --teacher "$TEACHER" --device $DEVICE --shaping eta $ABARGS || progress "WARN ablation eta failed (continuing)"
stage s4_abl_nobase $PY rlcore/train.py --scen $SCEN --plans $PL/train_ts_$TAG.jsonl --dev_plans $PL/dev_ts.jsonl --out $RUN/abl_nobase --seed 0 --workers $W --teacher "$TEACHER" --device $DEVICE --no_base $ABARGS || progress "WARN ablation nobase failed (continuing)"
ABLM=""; for A in nophys eta nobase; do [ -f $RUN/abl_$A/best.pt ] && ABLM="$ABLM,ABL_$A=rl:$RUN/abl_$A/best.pt"; done
# ---------------- S5 test evaluation (identical maps x days, paired) ----------------
RLM=""; for s in $SEEDS; do RLM="$RLM,RL_s$s=rl:$RUN/rl_s$s/best.pt"; done
BASE="A1=A1,tuned:$RES/tuned_$SCEN.json"
stage s5_test_$SCEN $PY rlcore/evaluate.py --plans $PL/test_ts.jsonl --scen $SCEN --days $TDAYS $TMAPS --methods "$BASE$RLM,BC_s0=rl:$RUN/rl_s0/bc.pt$ABLM" --out $RES/test_$SCEN.jsonl --workers $W || die "test eval"
for X in $EXTRA; do
  stage s5_test_$X $PY rlcore/evaluate.py --plans $PL/test_ts.jsonl --scen $X --days $XDAYS $TMAPS --methods "$BASE$RLM" --out $RES/test_$X.jsonl --workers $W || die "test $X"
done
stage s5_fresh_$SCEN $PY rlcore/evaluate.py --plans $PL/fresh_ts_$TAG.jsonl --scen $SCEN --days $XDAYS $TMAPS --methods "$BASE$RLM" --out $RES/fresh_$SCEN.jsonl --workers $W || die "fresh eval"
# ---------------- S6 analysis + packaging ----------------
rm -f $MK/s6_analyze.done
stage s6_analyze bash -c "set -e; $PY rlcore/analyze.py --res $RES/test_$SCEN.jsonl --scen $SCEN --tuned $RES/tuned_$SCEN.json --out $RES/report_$SCEN;
  for X in $EXTRA; do $PY rlcore/analyze.py --res $RES/test_\$X.jsonl --scen \$X --tuned $RES/tuned_$SCEN.json --out $RES/report_\$X; done;
  $PY rlcore/analyze.py --res $RES/fresh_$SCEN.jsonl --scen $SCEN --tuned $RES/tuned_$SCEN.json --out $RES/report_fresh_$SCEN"
tar czf ${PKG}_${TAG}_results.tar.gz $RES $RUN/*/curve.jsonl $RUN/*/done.json $RUN/*/best.pt $RUN/*/bc.pt PROGRESS_SERVER.md logs 2>/dev/null
progress "ALL DONE -> ${PKG}_${TAG}_results.tar.gz ; main report: $RES/report_$SCEN/REPORT.md"
