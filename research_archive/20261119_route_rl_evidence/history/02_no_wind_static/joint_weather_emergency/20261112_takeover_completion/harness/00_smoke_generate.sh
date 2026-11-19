#!/bin/bash
# 00_smoke_generate.sh — generate one fresh map and prove the identity machinery works.
set -euo pipefail
R=<EXECUTION_PATH>
GEN=$R/code/route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>
export PYTHONHASHSEED=0
cd "$R"
python3 harness/gen_maps.py --namespace takeover-20261112-g3-v1 \
  --partition opportunity --out "$R/g3_smoke" --families 3x10 --ordinals 1 \
  --generator-dir "$GEN"
echo "--- files ---"
ls -la "$R/g3_smoke/maps"
head -3 "$R"/g3_smoke/maps/*.txt
python3 - <<'PY'
import json, pathlib
d = json.load(open('<EXECUTION_PATH>'))
print(json.dumps(d['maps'][0], indent=1)[:1200])
PY
