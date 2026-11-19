#!/bin/bash
# 01_smoke_author.sh - compile accepted J1b profile and run one author anchor.
set -euo pipefail
R=<EXECUTION_PATH>
C=$R/code
AB=$C/route_rl_research/20261103/return_makespan/g23/author_baseline
export PYTHONHASHSEED=0
cd $AB
INSTANCE=$R/g3_smoke/maps/3x10_o1.txt
NAMESPACE=takeover-20261112-g3-author-seed-v1
SHA=$(sha256sum $INSTANCE | cut -d' ' -f1)
echo instance_sha256=$SHA
COMMON="--source-root $C/reproduction/reviewer_package_semfix --scorer-path $C/route_rl_research/20261103/return_makespan/scorer.py --java-home $R/runtime/jdk17 --build-dir $R/author_build"
python3 author_runner.py prepare --profile J1b $COMMON
echo '--- prepare done ---'
SEED=$(python3 author_runner.py derive-seed --input-sha256 $SHA --seed-namespace $NAMESPACE | tr -d '[:space:]')
if [ -z "$SEED" ]; then SEED=0; fi
echo seed=$SEED
python3 author_runner.py plan --profile J1b --instance $INSTANCE --seed $SEED $COMMON --out $R/g3_smoke/author/3x10_o1 --timeout 600
echo '--- plan done ---'
T0=$(date +%s%N)
python3 author_runner.py run --profile J1b --instance $INSTANCE --seed $SEED $COMMON --out $R/g3_smoke/author/3x10_o1 --timeout 600 2>&1 | tail -30
T1=$(date +%s%N)
echo wall_ms=$(( (T1-T0)/1000000 ))
echo '--- run done ---'
ls -la $R/g3_smoke/author/3x10_o1
python3 - <<'PY'
import json, pathlib
d = pathlib.Path('<EXECUTION_PATH>')
for name in ('RUN.json','reference.json','return_score.json','independent_audit.json'):
    p = d / name
    print('==', name, 'exists' if p.exists() else 'MISSING')
    if p.exists():
        print(json.dumps(json.loads(p.read_text()), indent=1)[:1600])
PY