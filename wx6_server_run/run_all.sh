#!/bin/bash
# WX6 single entry point (paper 1: v5 upgrade). PREREG: PREREG_v6.md  DESIGN: DESIGN_V6_ZH.md  PROTOCOL: docs/PROTOCOL_FAIR_V6_ZH.md
#   nohup bash run_all.sh > run_all.log 2>&1 &        # official run (resume-safe: re-run the same command)
#   SMOKE=1 bash run_all.sh                            # tiny end-to-end dry run (minutes), NOT official
# Every stage writes logs/<stage>.<STAMP>.done; evaluators skip finished rows; teacher shards / ES states are resumable.
# Nothing is pushed unless PUSH=1 (then results_final + tarball are committed to wx6_server_run/results_server/).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; cd "$ROOT"
export WX_ROOT="$ROOT" PYTHONUNBUFFERED=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
unset WX_OT WX_BG_MODE
if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="${PY:-python3}"; fi
JAVA="${JAVA:-$(command -v java || echo java)}"
ts() { TZ="${TZ_REPORT:-America/Phoenix}" date '+%Y-%m-%d %H:%M:%S %Z'; }
PROG="$ROOT/PROGRESS_SERVER.md"
progress() { printf '[%s] %s\n' "$(ts)" "$*" | tee -a "$PROG"; }
mkdir -p logs models6 results results_final data/plans6 teacher
NCPU="${NCPU:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc --all 2>/dev/null || echo 8)}"; W=$((NCPU - 2)); [ "$W" -lt 2 ] && W=2
SMOKE="${SMOKE:-0}"
SHIELD="${SHIELD:-1}"
TEACHER_BASE="${TEACHER_BASE:-RL5}"          # round-0 rollout base: the v5 dispatcher (strongest 1-ms policy available)
if [ "$SMOKE" = "1" ]; then
  W=$(( W < 4 ? W : 4 )); SEEDS_MAIN="${SEEDS_MAIN:-0 1}"; SEEDS_ABL="${SEEDS_ABL:-0}"
  PSECS=2; PSECS_L=2; LIMP="--limit-plans 2"; INST_TRAIN='data/instances/train/w5_35_[13]*.txt'; INST_DEV='data/instances/dev/d5_35_[12].txt'
  INST_TEST='data/instances/test/5_35_[12].txt'; INST_G='data/instances/fresh6/g5_35_[12].txt'; INST_L='data/instances/large6/G12_150_1.txt'
  DEV_DAYS="60000"; N6GRID="N6_60_0.25,N6_90_0.25"
  T0_DAYS="3000000-3000001"; T1_DAYS="3100000-3100001"; T_M=2; T_P=0.15; T0_H=0.2; T1_H=0.2
  ES_ITERS=2; ES_POP=2; ES_BATCH=2; ES_VALN=2; ES_VALEVERY=1; ES_POOL=20
  TM_DAYS="79000"; TG_DAYS="79001"; TL_DAYS="79002"; TR_DAYS="79003"; TS_DAYS="79000"; SUB_DAYS="79000"   # smoke never touches preregistered test days
  STAMP="smoke"
else
  SEEDS_MAIN="${SEEDS_MAIN:-0 1 2 3 4}"; SEEDS_ABL="${SEEDS_ABL:-0 1 2}"
  PSECS="${PSECS:-10}"; PSECS_L="${PSECS_L:-30}"; LIMP=""
  INST_TRAIN='data/instances/train/*.txt'; INST_DEV='data/instances/dev/*.txt'; INST_TEST='data/instances/test/*.txt'
  INST_G='data/instances/fresh6/*.txt'; INST_L='data/instances/large6/*.txt'
  DEV_DAYS="60000-60029"
  N6GRID="N6_30_0.1,N6_30_0.25,N6_30_0.5,N6_30_1.0,N6_60_0.1,N6_60_0.25,N6_60_0.5,N6_60_1.0,N6_90_0.1,N6_90_0.25,N6_90_0.5,N6_90_1.0"
  T0_DAYS="3000000-3000049"; T1_DAYS="3100000-3100049"; T_M="${T_M:-8}"; T_P="${T_P:-0.5}"; T0_H="${T0_H:-2.5}"; T1_H="${T1_H:-2.5}"
  ES_ITERS="${ES_ITERS:-250}"; ES_POP="${ES_POP:-20}"; ES_BATCH="${ES_BATCH:-16}"; ES_VALN=96; ES_VALEVERY=10; ES_POOL=3000
  TM_DAYS="70000-70099"; TG_DAYS="71000-71029"; TL_DAYS="72000-72029"; TR_DAYS="73000-73049"; TS_DAYS="70000-70049"; SUB_DAYS="70000-70019"
  STAMP="official"
fi
done_mark() { touch "logs/$1.$STAMP.done"; }
is_done() { [ -f "logs/$1.$STAMP.done" ]; }
stage() { # name cmd... (failure is logged; returns rc)
  local n="$1"; shift
  if is_done "$n"; then progress "skip $n (done)"; return 0; fi
  progress "START $n"
  "$@" >> "logs/$n.log" 2>&1; local rc=$?
  if [ $rc -eq 0 ]; then done_mark "$n"; progress "DONE $n"; else progress "FAIL $n rc=$rc (see logs/$n.log)"; fi
  return $rc
}
must() { stage "$@" || { progress "STOP: required stage $1 failed"; exit 2; }; }
progress "WX6 run_all start: ncpu=$NCPU workers=$W smoke=$SMOKE seeds=[$SEEDS_MAIN]/[$SEEDS_ABL] shield=$SHIELD es=$ES_ITERS x pop $ES_POP x batch $ES_BATCH teacher=$TEACHER_BASE M=$T_M p=$T_P budget=${T0_H}h+${T1_H}h python=$($PY -V 2>&1)"
$PY -c "import numpy, scipy" || { progress "numpy/scipy missing: run setup.sh"; exit 1; }
$PY tests/test_net6.py > logs/test_net6.log 2>&1 || { progress "net6 gradient test FAILED"; exit 1; }
D=data/plans6; R=results

# ---- s0: author's TSALNS (Java) ----
if ! [ -f baselines/tsalns_java/build/classes/test1/Main.class ]; then
  must s0_build_tsalns bash baselines/tsalns_java/build.sh
fi
TS="$PY baselines/tsalns_java/run_tsalns6.py --java $JAVA --workers $W"
# ---- s1: plans. TSC = TSALNS-Cov (author algorithm, Omega in its feasibility test) = MAIN plans for ALL methods.
#      TS = TSALNS unchanged (-> TSR exact cover repair, PAD all-DABS); TSCr10 = TSALNS-Cov with 10 % battery reserve ----
must s1_tsc_train $TS --inst "$INST_TRAIN" --secs $PSECS --cov --tag TSC --out $D/train_tsc.jsonl
must s1_tsc_dev   $TS --inst "$INST_DEV"   --secs $PSECS --cov --tag TSC --out $D/dev_tsc.jsonl
must s1_tsc_test  $TS --inst "$INST_TEST"  --secs $PSECS --cov --tag TSC --out $D/test_tsc.jsonl
must s1_tsc_g     $TS --inst "$INST_G"     --secs $PSECS --cov --tag TSC --out $D/fresh6_tsc.jsonl
must s1_tsc_l     $TS --inst "$INST_L"     --secs $PSECS_L --cov --tag TSC --out $D/large6_tsc.jsonl
must s1_ts_test   $TS --inst "$INST_TEST"  --secs $PSECS --tag TS --out $D/test_ts_orig.jsonl
must s1_tscr10_test $TS --inst "$INST_TEST" --secs $PSECS --cov --reserve 0.1 --tag TSCr10 --out $D/test_tscr10.jsonl
must s1_tsr_test  $PY -m v6.cover --mode repair --inp $D/test_ts_orig.jsonl --out $D/test_tsr.jsonl --tag TSR
must s1_pad_test  $PY -m v6.cover --mode pad --inp $D/test_ts_orig.jsonl --out $D/test_pad.jsonl --tag PAD
# ---- s2: structural gate: every plan entering the dynamic evaluation covers Omega (and the original TS plans are
#      reported, they are NOT evaluated because they cannot reach strict 100 %) ----
for f in train_tsc dev_tsc test_tsc fresh6_tsc large6_tsc test_tscr10 test_tsr test_pad; do
  must s2_cover_$f $PY -m v6.cover --mode check --inp $D/$f.jsonl
done
$PY -m v6.cover --mode check --inp $D/test_ts_orig.jsonl > logs/s2_cover_ts_orig_INFO.log 2>&1
progress "author's unmodified TSALNS plans leaving Omega uncovered: $(tail -1 logs/s2_cover_ts_orig_INFO.log)"

# ---- s3: dev baselines -> author strict gate, N6 freeze, SB freeze ----
EV="$PY run_eval6.py --workers $W"
must s3_dev_rules $EV --out $R/dev_baselines.jsonl --plans $D/dev_tsc.jsonl --days $DEV_DAYS --methods "A1,A2,N1_240,S:N1_240,$N6GRID"
must s3_author_gate $PY -m v6.freeze --rows $R/dev_baselines.jsonl --what author --out $R/AUTHOR_GATE.json
must s3_n6_freeze $PY -m v6.freeze --rows $R/dev_baselines.jsonl --what n6 --out $R/N6_FREEZE.json
N6B=$($PY -c "import json;print(json.load(open('$R/N6_FREEZE.json'))['best'])")
progress "N6_best frozen: $N6B"
RL5X="{\"RL5\": {\"ckpt\": \"models/rl5_es_best_p5r_s0.npz\"}}"
must s3_dev_reopt $EV --out $R/dev_baselines.jsonl --plans $D/dev_tsc.jsonl --days $DEV_DAYS \
  --methods "S:$N6B,R_$N6B,Rfc_$N6B,Rfc600e15_$N6B,S:R_$N6B,S:Rfc_$N6B,S:Rfc600e15_$N6B,RL5" --extra "$RL5X"
must s3_sb_freeze $PY -m v6.freeze --rows $R/dev_baselines.jsonl --what sb --out $R/SB_FREEZE.json
SB=$($PY -c "import json;print(json.load(open('$R/SB_FREEZE.json'))['SB'])")
progress "SB (strongest fair non-RL baseline) frozen on dev: $SB"

# ---- s4-s7: RL6 = rollout-teacher approximate policy iteration -> distillation ----
TB_EXTRA="{}"; [ "$TEACHER_BASE" = "RL5" ] && TB_EXTRA='{"ckpt": "models/rl5_es_best_p5r_s0.npz"}'
stage s4_teacher_r0 $PY -m v6.teacher --plans $D/train_tsc.jsonl --days $T0_DAYS --outdir teacher --round 0 \
  --base "$TEACHER_BASE" --base-extra "$TB_EXTRA" --M $T_M --p-label $T_P --beta 0 --lam-ot 1.0 --shield $SHIELD --workers $W --budget-h $T0_H
must s5_distill_r0 $PY -m v6.distill --data teacher --out models6/distill_r0.npz --seed 0
stage s6_teacher_r1 $PY -m v6.teacher --plans $D/train_tsc.jsonl --days $T1_DAYS --outdir teacher --round 1 \
  --base RL6 --base-extra '{"ckpt": "models6/distill_r0.npz"}' --rollin RL6 --rollin-extra '{"ckpt": "models6/distill_r0.npz"}' \
  --M $T_M --p-label $T_P --beta 0.5 --lam-ot 1.0 --shield $SHIELD --workers $W --budget-h $T1_H
for s in $SEEDS_MAIN; do must s7_distill_main_s$s $PY -m v6.distill --data teacher --out models6/distill_main_s$s.npz --seed $s --init models6/distill_r0.npz; done
for s in $SEEDS_ABL; do
  must s7_distill_nf_s$s $PY -m v6.distill --data teacher --out models6/distill_nf_s$s.npz --seed $s --ablate noforecast
  must s7_distill_ne_s$s $PY -m v6.distill --data teacher --out models6/distill_ne_s$s.npz --seed $s --ablate noemerg
done

# ---- s8: constrained ES fine-tuning, all runs in parallel with equal workers, FIXED iterations ----
OTREF="S:$N6B"; case "$SB" in R_*|Rfc*|S:R_*|S:Rfc*) ;; *) OTREF="$SB";; esac   # cheap reference for the training-time OT constraint
RUNS=""
for s in $SEEDS_MAIN; do RUNS="$RUNS main:$s"; done
for s in $SEEDS_ABL; do RUNS="$RUNS nf:$s ne:$s uc:$s"; [ "$SHIELD" = "1" ] && RUNS="$RUNS ns:$s"; done
NR=$(echo $RUNS | wc -w); WS=$(( W / NR )); [ "$WS" -lt 1 ] && WS=1
progress "ES: $NR runs x $WS workers; OT reference for training = $OTREF (selection uses SB=$SB on dev)"
es_cmd() { # variant seed
  local v=$1 s=$2 init=models6/distill_main_s$2.npz extra="--ot-ref $OTREF --delta 0.10" ab="none" sh=$SHIELD
  case $v in nf) init=models6/distill_nf_s$s.npz; ab=noforecast;; ne) init=models6/distill_ne_s$s.npz; ab=noemerg;;
             uc) extra="";; ns) sh=0;; esac
  echo "$PY run_es6.py --seed $s --init $init --plans $D/train_tsc.jsonl --name ${v}_s$s --iters $ES_ITERS --pop $ES_POP --batch $ES_BATCH \
    --val-n $ES_VALN --val-every $ES_VALEVERY --pool-days $ES_POOL --workers $WS --ablate $ab --shield $sh $extra --log logs/es_train.log"
}
for attempt in 1 2 3 4 5; do
  pids=(); n_todo=0
  for rs in $RUNS; do v=${rs%%:*}; s=${rs##*:}; [ -f models6/DONE_${v}_s$s ] && continue
    n_todo=$((n_todo + 1)); progress "ES launch ${v}_s$s (attempt $attempt)"
    eval "$(es_cmd $v $s)" >> logs/es_${v}_s$s.log 2>&1 & pids+=($!)
  done
  [ "$n_todo" = "0" ] && break
  for p in "${pids[@]}"; do wait $p; done
done
# ---- s9: preregistered dev selection per (variant, seed) ----
for rs in $RUNS; do v=${rs%%:*}; s=${rs##*:}
  dist=models6/distill_main_s$s.npz; [ $v = nf ] && dist=models6/distill_nf_s$s.npz; [ $v = ne ] && dist=models6/distill_ne_s$s.npz
  ns=0; [ $v = ns ] && ns=1
  CANDS="$dist,models6/es_best_${v}_s$s.npz,models6/es_final_${v}_s$s.npz"
  if ! [ -f models6/DONE_${v}_s$s ]; then CANDS="$dist"; progress "WARNING ${v}_s$s ES did not reach $ES_ITERS iterations -> only the distilled net is eligible (PREREG 5.3)"; fi
  must s9_select_${v}_s$s $PY -m v6.select6 --name ${v}_s$s --cands "$CANDS" \
    --plans $D/dev_tsc.jsonl --days $DEV_DAYS --sb-freeze $R/SB_FREEZE.json --workers $W --noshield $ns
done
# ---- s10: tests ----
EXTRA=$($PY - << PYEOF
import json, os
e = {"RL5": {"ckpt": "models/rl5_es_best_p5r_s0.npz"}}
pre = {"main": "RL6", "nf": "RL6nf", "ne": "RL6ne", "uc": "RL6uc", "ns": "RL6ns"}
for rs in "$RUNS".split():
    v, s = rs.split(":")
    f = f"models6/final_{v}_s{s}.npz"
    if os.path.exists(f):
        e[f"{pre[v]}_s{s}"] = {"ckpt": f, "noshield": v == "ns"}
    if v == "main" and os.path.exists(f"models6/distill_main_s{s}.npz"):
        e[f"RL6noES_s{s}"] = {"ckpt": f"models6/distill_main_s{s}.npz"}
print(json.dumps(e))
PYEOF
)
export EXTRA
pick() { $PY -c "import json,os;e=json.loads(os.environ['EXTRA']);print(','.join(k+'=RL6' for k in e if k.startswith('$1')))"; }
RLM=$(pick RL6_s); RLA=$(echo "$(pick RL6noES_s),$(pick RL6nf_s),$(pick RL6ne_s),$(pick RL6uc_s),$(pick RL6ns_s)" | sed 's/,,*/,/g;s/^,//;s/,$//')
[ -z "$RLM" ] && { progress "no final RL6 policies -> stop"; exit 2; }
BASES="A1=A1,A2=A2,N1_240=N1_240,N6_best=$N6B,S:N6_best=S:$N6B,R_N6best=R_$N6B,Rfc_N6best=Rfc_$N6B,RfcP_N6best=Rfc600e15_$N6B,S:RfcP_N6best=S:Rfc600e15_$N6B,SB=$SB,RL5=RL5"
ALLM="$BASES,$RLM${RLA:+,$RLA}"; MAINM="$BASES,$RLM"
progress "test arms: $ALLM"
must s10_testM  $EV --out $R/testM.jsonl --plans $D/test_tsc.jsonl --days $TM_DAYS --methods "$ALLM" --extra "$EXTRA" $LIMP
must s10_testG  $EV --out $R/testG.jsonl --plans $D/fresh6_tsc.jsonl --days $TG_DAYS --methods "$MAINM" --extra "$EXTRA" $LIMP
must s10_testL  $EV --out $R/testL.jsonl --plans $D/large6_tsc.jsonl --days $TL_DAYS --methods "$MAINM" --extra "$EXTRA" $LIMP
for sc in stress sigma15 ncbias6 uniform; do
  must s10_rob_$sc $EV --out $R/rob_$sc.jsonl --plans $D/test_tsc.jsonl --days $TR_DAYS --scenario $sc --methods "$MAINM" --extra "$EXTRA" $LIMP
done
for ps in test_tsr test_pad test_tscr10; do
  must s10_site_$ps $EV --out $R/site_$ps.jsonl --plans $D/$ps.jsonl --days $TS_DAYS --methods "$MAINM" --extra "$EXTRA" $LIMP
done
for w in 180 300; do
  must s10_win_ot$w env WX_OT=$w $EV --out $R/win_ot$w.jsonl --plans $D/test_tsc.jsonl --days $SUB_DAYS --methods "$MAINM" --extra "$EXTRA" $LIMP
done
N4B="$SB"; case "$SB" in R_*|Rfc*|S:R_*|S:Rfc*) N4B="S:$N6B";; esac
K0=$(echo $SEEDS_MAIN | awk '{print $1}')
LX=$($PY -c "import json,os;e=json.loads(os.environ['EXTRA']);print(json.dumps({'RL6R_100ms':{'ckpt':e['RL6_s$K0']['ckpt']},'N4fd_100ms':{'base':'$N4B'},'RL6_s$K0':e['RL6_s$K0'],'SB':{}}))")
must s10_lookahead $EV --out $R/lookahead.jsonl --plans $D/test_tsc.jsonl --days $SUB_DAYS --methods "RL6R_100ms=RL6R_100ms,N4fd_100ms=N4fd_32_100ms,RL6_s$K0=RL6,SB=$SB,O=O" --extra "$LX" $LIMP
# ---- s11: analysis + pack (+ optional push) ----
$PY analyze_v6.py >> logs/s11_analysis.log 2>&1 && progress "analysis written: results_final/SUMMARY_ZH.md" || progress "analysis FAILED (logs/s11_analysis.log)"
cp -f $R/*.json models6/select_*.json models6/DONE_* models6/es_hist_*.jsonl PROGRESS_SERVER.md results_final/ 2>/dev/null
cp -f $D/*.jsonl results_final/ 2>/dev/null; mkdir -p results_final/models && cp -f models6/final_*.npz models6/distill_*.npz results_final/models/ 2>/dev/null
gzip -kf results_final/raw_compact.csv 2>/dev/null
tar -czf results_out.tar.gz results_final logs/*.log 2>/dev/null   # raw per-row jsonl stay in results/ (compact CSV is in results_final)
sha256sum results_out.tar.gz > results_out.sha256
progress "PACKED results_out.tar.gz ($(stat -c %s results_out.tar.gz 2>/dev/null) bytes)."
if [ "${PUSH:-0}" = "1" ]; then bash tools/push_results.sh && progress "results pushed" || progress "push FAILED (see logs/push.log); push manually"; fi
progress "ALL DONE."
