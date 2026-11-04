#!/bin/bash
cd /workspace/rl_v3; export SET=dev; P=/workspace/rlproj/venv/bin/python
./run_dev_tp.sh models/tp/zero.json zero
$P rlv3/bench.py norl:8 results/dev/norl_8.jsonl 0,1,2 0 1,2 6 8 > results/dev/norl_8.log 2>&1
$P rlv3/bench.py norl:6 results/dev/norl_6.jsonl 0,1,2 0 1,2 6 8 > results/dev/norl_6.log 2>&1
echo done > results/dev/gate2b.done
