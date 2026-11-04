#!/bin/bash
cd /workspace/rl_v3; P=/workspace/rlproj/venv/bin/python; export SET=dev
B=/workspace/rl_v3/models/bc_s0.pt
for m in norl:4 norl:2 norl:1 rl:$B:8:4 rl:$B:6:4 rl:$B:6:3 rl:$B:4:2 rl:$B:8:2; do
  tag=$(echo $m | sed 's#/workspace/rl_v3/models/##; s#[:/]#_#g')
  $P rlv3/bench.py $m results/dev/$tag.jsonl 0,1,2 0 1,2 6 8 > results/dev/$tag.log 2>&1
done
echo done > results/dev/sweep.done
