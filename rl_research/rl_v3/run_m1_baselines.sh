#!/bin/bash
# Milestone 1: cooled NoRL baselines on Liu's 50 test instances (skips completed runs)
cd /workspace/rl_v3
P=/workspace/rlproj/venv/bin/python
L=0,0.05,0.1,0.2,0.5,1,2
for m in norl:8 norl_m4 norl_m1; do
  t=$(echo $m | tr ':' '_')
  $P rlv3/bench.py $m results/base_${t}.jsonl $L 0 101,102,103 6 8 > results/base_${t}.log 2>&1
  $P rlv3/bench.py $m results/base_${t}_rsv.jsonl 0 0.1 101,102,103 6 8 > results/base_${t}_rsv.log 2>&1
done
echo DONE > results/base.done
