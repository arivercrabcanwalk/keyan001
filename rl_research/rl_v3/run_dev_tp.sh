#!/bin/bash
# usage: run_dev_tp.sh PARAMS_JSON TAG [SEEDS] [LAMS]
cd /workspace/rl_v3; export SET=dev
/workspace/rlproj/venv/bin/python rlv3/bench.py tp:$1 results/dev/tp_$2.jsonl ${4:-0,1,2} 0 ${3:-1,2} 6 8 > results/dev/tp_$2.log 2>&1
