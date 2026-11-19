#!/bin/bash
# 10_gen_pop.sh - generate the frozen new population (all 12 families).
set -euo pipefail
R=<EXECUTION_PATH>
GEN=$R/code/route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>
export PYTHONHASHSEED=0
python3 $R/harness/gen_maps.py --namespace takeover-20261112-g3-v1   --partition opportunity --out $R/g3_pop --ordinals 1 --generator-dir $GEN
echo "--- generated ---"
ls $R/g3_pop/maps | wc -l
