#!/bin/bash
cd /workspace/rl_v3
./run_dev_tp.sh models/tp/s0/bc.json s0_bc
./run_dev_tp.sh models/tp/s0/it30.json s0_it30
./run_dev_tp.sh models/tp/s0/it60.json s0_it60
echo done > results/dev/gate2a.done
