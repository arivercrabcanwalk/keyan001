cd /workspace/rl_wind; export PYTHONPATH=/workspace/rl_wind; P=/workspace/rlproj/venv/bin/python
while [ ! -f results/strong_test_ts_nowind.jsonl.done ]; do sleep 20; done
for f in strong_dev_ts_fc strong_test_ts_fc strong_test_ts_nowind; do $P wind/resim.py results/$f.jsonl results/${f}_rs.jsonl 400 777 3; done
$P wind/final_strong.py models/reserve/n600_s0.pt > results/final_tables_design_b.txt 2>&1
