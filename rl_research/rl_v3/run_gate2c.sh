#!/bin/bash
cd /workspace/rl_v3; export SET=dev; P=/workspace/rlproj/venv/bin/python
$P rlv3/bench.py tp:models/tp/s0/bc.json results/dev/tpf_bc_M4.jsonl 0,1,2 0 1,2 6 8 > results/dev/tpf_bc_M4.log 2>&1
$P rlv3/bench.py tp:models/tp/s0/bc.json:M8 results/dev/tpf_bc_M8.jsonl 0,1,2 0 1,2 6 8 > results/dev/tpf_bc_M8.log 2>&1
$P rlv3/bench.py tp:models/tp/zero.json results/dev/tpf_zero_M4.jsonl 0,1,2 0 1,2 6 8 > results/dev/tpf_zero_M4.log 2>&1
$P rlv3/bench.py tp:models/tp/s0/it30.json:M8 results/dev/tpf_it30_M8.jsonl 0,1,2 0 1,2 6 8 > results/dev/tpf_it30_M8.log 2>&1
echo done > results/dev/gate2c.done
