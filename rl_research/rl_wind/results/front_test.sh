cd /workspace/rl_wind; export PYTHONPATH=/workspace/rl_wind OMP_NUM_THREADS=1; P=/workspace/rlproj/venv/bin/python
$P wind/hr_front2.py results/strong_test_ts_nowind.jsonl results/front_test_tsnw.jsonl 30 7 0 plan
$P wind/hr_front2.py results/strong_test_ts_fc.jsonl results/front_test_tsfc.jsonl 30 7 0 plan
$P wind/hr_front2.py results/hr_test_strong.jsonl results/front_test_ours.jsonl 30 7 0.15 plan,static_fc,saa16,ratio1,rsaa,rl:models/front/s1.pt,oracle
$P wind/final_front.py rl:models/front/s1.pt > results/final_tables_design_c.txt 2>&1
