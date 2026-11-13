#!/bin/bash
# Single entry point for the remaining WX-E pomo_v2 experiments.
# Usage (from this directory):
#   nohup bash run_all.sh > run_all.log 2>&1 &
# Smoke (a few minutes, tiny subsets, does not write to any other machine):
#   SMOKE=1 bash run_all.sh
#
# Does not use STOP_AUTO_TRAIN (that flag is for the original local v1 chain).
# Seeds 1 and 2 are trained from scratch (full BC + 2 DAgger rounds + 2 h POMO),
# which is pre-registration-consistent and reproducible. Seed 0 is already done
# and is shipped with this package.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export WX_ROOT="$ROOT"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Python: prefer local venv
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PY:-python3}"
fi

jst() { TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST'; }
PROG="$ROOT/PROGRESS_SERVER.md"
progress() {
  local msg="[$(jst)] $*"
  printf '%s\n' "$msg" | tee -a "$PROG"
}

mkdir -p "$ROOT/logs" "$ROOT/models" "$ROOT/wx_e/results" "$ROOT/wx_h/results" \
         "$ROOT/results_final" "$ROOT/data/days"

# ----- worker sizing: ~38 of 40 cores, leave 2 for the OS -----
NCPU="$(nproc 2>/dev/null || echo 8)"
AVAIL=$((NCPU - 2))
if [ "$AVAIL" -lt 2 ]; then AVAIL=2; fi

SMOKE="${SMOKE:-0}"
if [ "$SMOKE" = "1" ]; then
  HOURS=0.01
  MAX_ITERS=1
  BC_DAYS=1
  DAGGER_DAYS=1
  M_DAGGER=2
  B=2
  K=2
  EVAL_EVERY=1
  DEV_LIMIT=1
  DEV_DAYS="6000"
  TRAIN_LIMIT=2
  # two seeds in parallel, few workers
  W_SEED=2
  W_DOWN=2
  LIMIT_PLANS=1
  TEST_DAYS="7000"
  VALUE_NTRAIN=1
  VALUE_EPOCHS=1
  WXH_METHODS="N1_240,N4d_32_1ms,VG_1ms,RV_1ms"
  P3_HOURS=0.01
  P3_MAX_ITERS=1
  progress "SMOKE=1: tiny end-to-end dry run (not official). workers=$W_SEED ncpu=$NCPU"
else
  HOURS=2.0
  MAX_ITERS=""
  BC_DAYS=400
  DAGGER_DAYS=200
  M_DAGGER=8
  B=""          # default → pomo_v2 HP B=24
  K=8
  EVAL_EVERY=10
  DEV_LIMIT=0
  DEV_DAYS=""
  TRAIN_LIMIT=0
  # two seeds in parallel, split available cores
  W_SEED=$((AVAIL / 2))
  if [ "$W_SEED" -lt 2 ]; then W_SEED=2; fi
  W_DOWN=$AVAIL
  LIMIT_PLANS=0
  TEST_DAYS=""
  VALUE_NTRAIN=80
  VALUE_EPOCHS=12
  WXH_METHODS=""
  P3_HOURS=2.0
  P3_MAX_ITERS=""
  progress "Official run: ncpu=$NCPU avail=$AVAIL workers/seed=$W_SEED downstream=$W_DOWN hours=$HOURS (pomo_v2, synthetic weather)"
fi

# optional CLI extras assembled once
stage2_extras() {
  local extra="--variant pomo_v2 --force --workers $1"
  extra="$extra --hours $2 --bc-days $BC_DAYS --dagger-days $DAGGER_DAYS --M-dagger $M_DAGGER --K $K --eval-every $EVAL_EVERY"
  if [ -n "$B" ]; then extra="$extra --B $B"; fi
  if [ -n "$MAX_ITERS" ]; then extra="$extra --max-iters $MAX_ITERS"; fi
  if [ "$DEV_LIMIT" -gt 0 ]; then extra="$extra --dev-limit $DEV_LIMIT"; fi
  if [ -n "$DEV_DAYS" ]; then extra="$extra --dev-days $DEV_DAYS"; fi
  if [ "$TRAIN_LIMIT" -gt 0 ]; then extra="$extra --train-limit $TRAIN_LIMIT"; fi
  printf '%s' "$extra"
}

eval_limits() {
  local extra=""
  if [ "$LIMIT_PLANS" -gt 0 ]; then extra="$extra --limit-plans $LIMIT_PLANS"; fi
  if [ -n "$TEST_DAYS" ]; then extra="$extra --days $TEST_DAYS"; fi
  if [ -n "$DEV_DAYS" ] && [ "${1:-}" = "dev" ]; then extra="$extra --days $DEV_DAYS"; fi
  printf '%s' "$extra"
}

# ----- preflight -----
if ! "$PY" -c "import numpy, scipy" 2>/dev/null; then
  progress "numpy/scipy missing — running setup.sh"
  bash "$ROOT/setup.sh" || { progress "SETUP FAILED"; exit 2; }
  if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; fi
fi
"$PY" -c "import numpy, scipy; import wx2.const as C; assert C.SIGMA0==1.0 and C.KAPPA==0.5; print('preflight OK', 'numpy', __import__('numpy').__version__)"
if [ ! -f "$ROOT/wx_e/GA_FREEZE.json" ]; then
  progress "FATAL: wx_e/GA_FREEZE.json missing"
  exit 2
fi
if [ ! -f "$ROOT/models/rl_s0_best_pomo_v2.npz" ] || [ ! -f "$ROOT/wx_e/GB_s0_pomo_v2.json" ]; then
  progress "FATAL: seed 0 official checkpoint / GB file missing"
  exit 2
fi

# =============================================================================
# Phase 1: train seeds 1 and 2 in parallel, from scratch
# =============================================================================
train_seed() {
  local s="$1"
  local w="$2"
  local gb="$ROOT/wx_e/GB_s${s}_pomo_v2.json"
  if [ -f "$gb" ]; then
    progress "seed $s already has $(basename "$gb") — skip training"
    echo 0 > "$ROOT/logs/train_s${s}.exit"
    return 0
  fi
  progress "TRAIN seed $s start  workers=$w"
  set +e
  # shellcheck disable=SC2046
  "$PY" -u "$ROOT/run_stage2.py" --seed "$s" --mode storm $(stage2_extras "$w" "$HOURS") \
    > "$ROOT/logs/train_s${s}.out" 2>&1
  local rc=$?
  # (no set -e: we record exit codes and continue)
  echo "$rc" > "$ROOT/logs/train_s${s}.exit"
  progress "TRAIN seed $s exit=$rc"
  return $rc
}

progress "======== Phase 1: pomo_v2 seeds 1 and 2 from scratch (parallel) ========"
train_seed 1 "$W_SEED" &
PID1=$!
train_seed 2 "$W_SEED" &
PID2=$!
set +e
wait $PID1; RC1=$?
wait $PID2; RC2=$?
# (no set -e: we record exit codes and continue)
progress "seeds finished rc1=$RC1 rc2=$RC2"

# Tally G-b / G-c with the same formal logic already written into each GB file
"$PY" - << 'PY'
import json, os, sys
root = os.environ["WX_ROOT"]
ok = done = 0
rows = []
for s in (0, 1, 2):
    p = os.path.join(root, "wx_e", f"GB_s{s}_pomo_v2.json")
    if os.path.exists(p):
        g = json.load(open(p))
        done += 1
        gb, gc = bool(g.get("G_b")), bool(g.get("G_c"))
        if gb and gc:
            ok += 1
        rows.append(dict(seed=s, G_b=gb, G_c=gc, G_b_J=g.get("G_b_J"), G_b_ot=g.get("G_b_ot"),
                         dev_J=g.get("dev_J"), gap=g.get("gap_vs_bestN"),
                         d_ot_pp=g.get("d_ot_pp"), KL=g.get("KL"), frac_diff=g.get("frac_diff"),
                         best_ckpt=g.get("best_ckpt")))
        print(f"s{s} G_b={gb} G_c={gc} J={g.get('dev_J')} gap={g.get('gap_vs_bestN')} "
              f"frac_diff={g.get('frac_diff')} KL={g.get('KL')}")
    else:
        print(f"s{s} MISSING")
        rows.append(dict(seed=s, missing=True))
tally = dict(passed=ok, done=done, official_testa=(ok >= 2 and done >= 3), seeds=rows)
open(os.path.join(root, "wx_e", "GB_V2_TALLY.json"), "w").write(json.dumps(tally, indent=2))
print(f"passed {ok}/{done} official_testa={tally['official_testa']}")
open(os.path.join(root, "results_final", "GB_V2_TALLY.json"), "w").write(json.dumps(tally, indent=2))
PY

OFFICIAL_TESTA="$("$PY" -c "import json,os; print('1' if json.load(open(os.path.join(os.environ['WX_ROOT'],'wx_e','GB_V2_TALLY.json'))).get('official_testa') else '0')")"
progress "tally official_testa=$OFFICIAL_TESTA (need >=2/3 with both G-b and G-c)"

# =============================================================================
# Phase 2: downstream — Test-A, P3, P4, value net, WX-H
# P3 uniform retrain runs in the background so it overlaps with evals.
# =============================================================================
progress "======== Phase 2: downstream ========"

# --- 2a. P3 uniform retrain of seed 0 (pomo_v2, full protocol unless SMOKE) ---
p3_retrain() {
  local gb="$ROOT/wx_e/GB_s0_pomo_v2_uniform.json"
  if [ -f "$gb" ]; then
    progress "P3 uniform retrain already has $gb — skip"
    echo 0 > "$ROOT/logs/p3_retrain.exit"
    return 0
  fi
  local w="$1"
  progress "P3 uniform retrain seed 0 start workers=$w hours=$P3_HOURS"
  local extra
  extra="$(stage2_extras "$w" "$P3_HOURS")"
  if [ -n "$P3_MAX_ITERS" ]; then
    # stage2_extras already added --max-iters if MAX_ITERS set; for P3 use P3_MAX_ITERS
    :
  fi
  # Force tag via --mode uniform (auto tag _pomo_v2_uniform) and --variant pomo_v2
  set +e
  "$PY" -u "$ROOT/run_stage2.py" --seed 0 --mode uniform --variant pomo_v2 --force \
    --workers "$w" --hours "$P3_HOURS" \
    --bc-days "$BC_DAYS" --dagger-days "$DAGGER_DAYS" --M-dagger "$M_DAGGER" --K "$K" \
    --eval-every "$EVAL_EVERY" \
    ${B:+--B $B} \
    ${P3_MAX_ITERS:+--max-iters $P3_MAX_ITERS} \
    ${DEV_LIMIT:+--dev-limit $DEV_LIMIT} \
    ${DEV_DAYS:+--dev-days $DEV_DAYS} \
    ${TRAIN_LIMIT:+--train-limit $TRAIN_LIMIT} \
    > "$ROOT/logs/p3_retrain.out" 2>&1
  local rc=$?
  # (no set -e: we record exit codes and continue)
  echo "$rc" > "$ROOT/logs/p3_retrain.exit"
  progress "P3 uniform retrain exit=$rc"
  return $rc
}

# half the cores for P3 retrain while evals run; in SMOKE just 2 and sequential is fine
W_P3=$((W_DOWN / 2))
if [ "$W_P3" -lt 2 ]; then W_P3=2; fi
W_EV=$((W_DOWN - W_P3))
if [ "$W_EV" -lt 2 ]; then W_EV=2; fi
if [ "$SMOKE" = "1" ]; then
  W_P3=2
  W_EV=2
fi

p3_retrain "$W_P3" &
PID_P3=$!
progress "P3 retrain launched pid=$PID_P3  (eval workers=$W_EV)"

# --- 2b. Test-A (Liu-50 × 7000-7029, one shot). Official only if gates pass;
#         otherwise --force and clearly labelled unofficial. ---
testa_force=""
if [ "$OFFICIAL_TESTA" != "1" ]; then
  testa_force="--force"
  progress "Test-A will run UNOFFICIAL (--force): gates not 2/3. Labelled in STATS."
else
  progress "Test-A official: gates passed"
fi
# methods: N1_240, A1, A2, RL (all available pomo_v2 seeds)
set +e
"$PY" -u "$ROOT/run_eval_suite.py" --suite testa --methods "N1_240,A1,A2,RL" \
  --mode storm --rl-tag _pomo_v2 --workers "$W_EV" $testa_force \
  --plans test_ours $(eval_limits) \
  > "$ROOT/logs/testa.out" 2>&1
RC_TESTA=$?
# (no set -e: we record exit codes and continue)
progress "Test-A exit=$RC_TESTA"

# Prefer test results for P3/P4 if Test-A (official or not) produced a file;
# otherwise fall back to a short dev eval so analysis still has paired rows.
BASE_PLANS=test_ours
BASE_DAYS_ARGS=""
BASE_JSON="$ROOT/wx_e/results/testA.jsonl"
# In SMOKE, always restrict P3/P4 to a single day (even if testa wrote an empty file).
if [ "$SMOKE" = "1" ]; then
  if [ "$BASE_PLANS" = "test_ours" ]; then
    BASE_DAYS_ARGS="--days 7000"
  else
    BASE_DAYS_ARGS="--days 6000"
  fi
fi
P3U_JSON="$ROOT/wx_e/results/p3_uniform.jsonl"
P3S_JSON="$ROOT/wx_e/results/p3_storm.jsonl"
if [ ! -s "$BASE_JSON" ]; then
  progress "Test-A jsonl missing — fallback to dev_ours for P3/P4 pairing"
  BASE_PLANS=dev_ours
  if [ -n "$DEV_DAYS" ]; then BASE_DAYS_ARGS="--days $DEV_DAYS"; else BASE_DAYS_ARGS="--days 6000,6001,6002,6003,6004,6005,6006,6007,6008,6009"; fi
  if [ "$SMOKE" = "1" ]; then BASE_DAYS_ARGS="--days 6000"; fi
  BASE_JSON="$ROOT/wx_e/results/dev_rl.jsonl"
  "$PY" -u "$ROOT/run_eval_suite.py" --suite dev_rl --methods "N1_240,A1,RL" \
    --mode storm --rl-tag _pomo_v2 --workers "$W_EV" --force \
    --plans dev_ours $BASE_DAYS_ARGS $( [ "$LIMIT_PLANS" -gt 0 ] && echo --limit-plans $LIMIT_PLANS ) \
    > "$ROOT/logs/dev_rl.out" 2>&1 || progress "dev_rl eval failed"
fi

# Storm-mode eval used for P3 share: Test-A (or dev_rl) already has N1 + RL on storm days.
# Also run a dedicated p3 --mode storm if we are on test and want a sibling file — reuse BASE_JSON.

# --- 2c. P3 uniform eval of the *storm-trained* policy ---
set +e
"$PY" -u "$ROOT/run_eval_suite.py" --suite p3 --mode uniform --methods "N1_240,A1,RL" \
  --rl-tag _pomo_v2 --workers "$W_EV" --force \
  --plans "$BASE_PLANS" $BASE_DAYS_ARGS $( [ "$LIMIT_PLANS" -gt 0 ] && echo --limit-plans $LIMIT_PLANS ) \
  > "$ROOT/logs/p3_uniform_eval.out" 2>&1
RC_P3E=$?
# (no set -e: we record exit codes and continue)
progress "P3 uniform-eval (storm-trained) exit=$RC_P3E"

# --- 2d. P4: σ×1.5 and cell speed +30% ---
set +e
"$PY" -u "$ROOT/run_eval_suite.py" --suite p4 --sigma 1.5 --speed 0.0 \
  --methods "N1_240,A1,RL" --rl-tag _pomo_v2 --workers "$W_EV" --force \
  --plans "$BASE_PLANS" $BASE_DAYS_ARGS $( [ "$LIMIT_PLANS" -gt 0 ] && echo --limit-plans $LIMIT_PLANS ) \
  > "$ROOT/logs/p4_sigma.out" 2>&1
RC_P4S=$?
"$PY" -u "$ROOT/run_eval_suite.py" --suite p4 --sigma 1.0 --speed 0.30 \
  --methods "N1_240,A1,RL" --rl-tag _pomo_v2 --workers "$W_EV" --force \
  --plans "$BASE_PLANS" $BASE_DAYS_ARGS $( [ "$LIMIT_PLANS" -gt 0 ] && echo --limit-plans $LIMIT_PLANS ) \
  > "$ROOT/logs/p4_speed.out" 2>&1
RC_P4V=$?
# (no set -e: we record exit codes and continue)
progress "P4 sigma exit=$RC_P4S  speed exit=$RC_P4V"

# --- 2e. Value net + random-net ablation, then WX-H at 1/10/100 ms ---
# Prefer the best seed by dev J among those with a ckpt (seed 0 shipped; 1/2 after training).
VALUE_CKPT="$("$PY" - << 'PY'
import json, os
root = os.environ["WX_ROOT"]
best = None
bestJ = 1e18
for s in (0, 1, 2):
    ck = os.path.join(root, "models", f"rl_s{s}_best_pomo_v2.npz")
    gb = os.path.join(root, "wx_e", f"GB_s{s}_pomo_v2.json")
    if not os.path.exists(ck):
        continue
    J = 1e18
    if os.path.exists(gb):
        J = float(json.load(open(gb)).get("dev_J") or 1e18)
    if J < bestJ:
        bestJ, best = J, ck
print(best or "")
PY
)"
progress "value-net ckpt=$VALUE_CKPT"
VALUE_OUT="$ROOT/models/value_best_pomo_v2.npz"
set +e
VARGS=(--ckpt "$VALUE_CKPT" --out "$VALUE_OUT" --plans dev_ours --n-train "$VALUE_NTRAIN" \
       --epochs "$VALUE_EPOCHS" --workers "$W_EV" --seed 0)
if [ "$LIMIT_PLANS" -gt 0 ]; then VARGS+=(--limit-plans "$LIMIT_PLANS"); fi
if [ -n "$DEV_DAYS" ]; then VARGS+=(--days "$DEV_DAYS"); fi
"$PY" -u "$ROOT/run_value.py" "${VARGS[@]}" > "$ROOT/logs/value.out" 2>&1
RC_VAL=$?
# (no set -e: we record exit codes and continue)
progress "value-net exit=$RC_VAL"

set +e
WARGS=(--ckpt "$VALUE_CKPT" --value "$VALUE_OUT" --plans dev_ours --workers "$W_EV")
if [ "$LIMIT_PLANS" -gt 0 ]; then WARGS+=(--limit-plans "$LIMIT_PLANS"); fi
if [ -n "$DEV_DAYS" ]; then WARGS+=(--days "$DEV_DAYS"); fi
if [ -n "$WXH_METHODS" ]; then WARGS+=(--methods "$WXH_METHODS"); fi
"$PY" -u "$ROOT/run_wxh.py" "${WARGS[@]}" > "$ROOT/logs/wxh.out" 2>&1
RC_WXH=$?
# (no set -e: we record exit codes and continue)
progress "WX-H exit=$RC_WXH"

# --- 2f. wait for P3 retrain, then eval the uniform-trained policy ---
set +e
wait $PID_P3
RC_P3R=$?
# (no set -e: we record exit codes and continue)
progress "P3 retrain wait exit=$RC_P3R (logfile logs/p3_retrain.out)"

if [ -f "$ROOT/models/rl_s0_best_pomo_v2_uniform.npz" ]; then
  set +e
  "$PY" -u "$ROOT/run_eval_suite.py" --suite p3 --mode uniform --methods "RL" \
    --rl-tag _pomo_v2_uniform --workers "$W_DOWN" --force \
    --plans "$BASE_PLANS" $BASE_DAYS_ARGS $( [ "$LIMIT_PLANS" -gt 0 ] && echo --limit-plans $LIMIT_PLANS ) \
    > "$ROOT/logs/p3_uniform_retrain_eval.out" 2>&1
  RC_P3RE=$?
  # (no set -e: we record exit codes and continue)
  progress "P3 uniform-retrain eval exit=$RC_P3RE"
  # The suite writes p3_uniform.jsonl and will APPEND RL_s0_pomo_v2_uniform rows
  # into the same file if tag_out is p3_uniform. Good — analyze can pick the method.
else
  progress "P3 uniform-retrain ckpt missing — skip its eval"
fi

# =============================================================================
# Phase 3: analysis + pack
# =============================================================================
progress "======== Phase 3: analysis and pack ========"

# Storm-share uses Test-A / dev_rl (storm mode, N1 + RL)
STORM_JSON="$BASE_JSON"
# P4 files from run_eval_suite naming: p4_s{sigma}_v{speed}.jsonl
P4_SIGMA="$ROOT/wx_e/results/p4_s1.5_v0.0.jsonl"
P4_SPEED="$ROOT/wx_e/results/p4_s1.0_v0.3.jsonl"
# speed may be 0.3 or 0.30 depending on format — pick what exists
if [ ! -f "$P4_SPEED" ]; then
  P4_SPEED="$(ls "$ROOT"/wx_e/results/p4_s1.0_v*.jsonl 2>/dev/null | head -1 || true)"
fi
if [ ! -f "$P4_SIGMA" ]; then
  P4_SIGMA="$(ls "$ROOT"/wx_e/results/p4_s1.5_v*.jsonl 2>/dev/null | head -1 || true)"
fi

set +e
"$PY" -u "$ROOT/analyze_p3.py" \
  --storm-rl "$STORM_JSON" \
  --uniform-eval "$P3U_JSON" \
  --uniform-retrain "$P3U_JSON" \
  --out "$ROOT/results_final/P3_ANALYSIS.json" \
  > "$ROOT/logs/analyze_p3.out" 2>&1
RC_A3=$?
"$PY" -u "$ROOT/analyze_p4.py" \
  --baseline "$STORM_JSON" \
  --p4-sigma "${P4_SIGMA:-}" \
  --p4-speed "${P4_SPEED:-}" \
  --out "$ROOT/results_final/P4_ANALYSIS.json" \
  > "$ROOT/logs/analyze_p4.out" 2>&1
RC_A4=$?
"$PY" -u "$ROOT/summarize_final.py" > "$ROOT/logs/summarize.out" 2>&1
RC_SUM=$?
# (no set -e: we record exit codes and continue)
progress "analyze P3=$RC_A3 P4=$RC_A4 summarize=$RC_SUM"

# Copy key artefacts into results_final
cp -a "$ROOT/wx_e"/GB_s*_pomo_v2*.json "$ROOT/results_final/" 2>/dev/null || true
cp -a "$ROOT/wx_e/GB_V2_TALLY.json" "$ROOT/results_final/" 2>/dev/null || true
cp -a "$ROOT/wx_e/results/"*.json "$ROOT/results_final/" 2>/dev/null || true
mkdir -p "$ROOT/results_final/jsonl" "$ROOT/results_final/models" "$ROOT/results_final/logs" "$ROOT/results_final/wx_h"
cp -a "$ROOT/wx_e/results/"*.jsonl "$ROOT/results_final/jsonl/" 2>/dev/null || true
cp -a "$ROOT/models/"rl_s*_best_pomo_v2*.npz "$ROOT/results_final/models/" 2>/dev/null || true
cp -a "$ROOT/models/"value_*.npz* "$ROOT/results_final/models/" 2>/dev/null || true
cp -a "$ROOT/wx_h/"WXH.md "$ROOT/wx_h/"WXH_SUMMARY.json "$ROOT/results_final/wx_h/" 2>/dev/null || true
cp -a "$ROOT/wx_h/results/"*.jsonl "$ROOT/results_final/wx_h/" 2>/dev/null || true
cp -a "$ROOT/logs/"*.out "$ROOT/results_final/logs/" 2>/dev/null || true
cp -a "$PROG" "$ROOT/results_final/" 2>/dev/null || true

# Pack (exclude the days cache — it can be hundreds of MB and is regenerable)
TAR="$ROOT/results_out.tar.gz"
progress "packing $TAR"
tar -czf "$TAR" \
  --exclude='data/days/*.pkl' \
  --exclude='data/days/*.tmp.*' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='models/*_live*.npz' \
  --exclude='models/*_it*.npz' \
  -C "$ROOT" \
  results_final \
  results_out_placeholder_skip \
  wx_e/GB_s0_pomo_v2.json \
  wx_e/GB_s1_pomo_v2.json \
  wx_e/GB_s2_pomo_v2.json \
  wx_e/GB_s0_pomo_v2_uniform.json \
  wx_e/GB_V2_TALLY.json \
  wx_e/results \
  wx_h \
  models/rl_s0_best_pomo_v2.npz \
  models/rl_s1_best_pomo_v2.npz \
  models/rl_s2_best_pomo_v2.npz \
  models/rl_s0_best_pomo_v2_uniform.npz \
  models/value_best_pomo_v2.npz \
  models/value_best_pomo_v2.npz.meta.json \
  models/value_random.npz \
  models/value_random.npz.meta.json \
  logs \
  PROGRESS_SERVER.md \
  2>/dev/null || true
# tar returns 2 if some files are missing (e.g. a seed failed). That's OK.
if [ -f "$TAR" ]; then
  progress "packed $(du -h "$TAR" | awk '{print $1}')  -> $TAR"
else
  progress "WARNING: results_out.tar.gz was not created; falling back to results_final only"
  tar -czf "$TAR" -C "$ROOT" results_final logs PROGRESS_SERVER.md || true
fi

# Optional push: ONLY if the user configured their own git credentials on this
# machine and set WX_PUSH_RESULTS=1. Never uses a baked-in token. Never in SMOKE.
maybe_push() {
  if [ "$SMOKE" = "1" ]; then
    progress "SMOKE: skip git push"
    return 0
  fi
  if [ "${WX_PUSH_RESULTS:-0}" != "1" ]; then
    progress "未设置 WX_PUSH_RESULTS=1，不向 GitHub 推送。请下载 results_out.tar.gz 发回。"
    return 0
  fi
  local repo
  repo="$(cd "$ROOT" && git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "$repo" ]; then
    progress "不在 git 仓库中，跳过推送。请下载 results_out.tar.gz。"
    return 0
  fi
  if [ -n "${GITHUB_TOKEN_KEYAN:-}" ] || [ -n "${GITHUB_TOKEN:-}" ] || [ -n "${GH_TOKEN:-}" ]; then
    # Defensive: even if a token happened to be in the environment, do not use it.
    progress "检测到环境中的令牌变量；为安全起见拒绝自动推送。请用你自己在服务器上配置的 git 凭据，或下载 results_out.tar.gz。"
    return 0
  fi
  (
    cd "$repo"
    git add -- "wx2_server_run/results_final" "wx2_server_run/results_out.tar.gz" \
               "wx2_server_run/wx_e/GB_s"*_pomo_v2*.json "wx2_server_run/wx_e/GB_V2_TALLY.json" \
               "wx2_server_run/PROGRESS_SERVER.md" 2>/dev/null || true
    if git diff --cached --quiet; then
      echo "no staged result changes"
      exit 0
    fi
    git -c user.useConfigOnly=true commit -m "WX-E server results (pomo_v2 seeds, P3/P4, WX-H)" || true
    git push origin HEAD
  ) > "$ROOT/logs/git_push.out" 2>&1
  progress "git push attempted, see logs/git_push.out"
}
maybe_push

progress "======== ALL DONE ========  results: $TAR"
progress "查看汇总： results_final/SUMMARY_ZH.md  以及 PROGRESS_SERVER.md"
exit 0
