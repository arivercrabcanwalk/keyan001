cd /workspace/rl_wind; export PYTHONPATH=/workspace/rl_wind STRONG=1 OMP_NUM_THREADS=1; P=/workspace/rlproj/venv/bin/python
while pgrep -f "headroom.py test results/hr_test_type" >/dev/null; do sleep 20; done
TYPEGRID=1 $P wind/headroom.py test results/hr_test_type.jsonl 7
$P wind/resim.py results/hr_test_type.jsonl results/hr_test_type_rs.jsonl 400 777 7
TYPEGRID=2 NTRAIN=400 $P wind/headroom.py train results/hr_train_type.jsonl 7
