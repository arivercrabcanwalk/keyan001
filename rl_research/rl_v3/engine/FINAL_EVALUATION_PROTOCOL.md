# Locked final evaluation protocol (freeze before execution)

## Test set
- Dataset: datasets/locked_v2, exactly 60 maps with constructive witnesses.
- Independent server validation: 60/60 feasible witnesses; zero instance SHA256 mismatches.
- Distribution: 8/50, 16/100, 24/200, 32/300 stations/targets × uniform/clustered/boundary × five seeds.
- This is a generated stress-test family, not a substitute for real-world data. Do not tune on it.

## Methods
Freeze M0, all three development-selected non-RL candidates (M1d, M1d_nojoint, M1d_noxchg), and each of the three seeds' BC-only and PPO checkpoints. M1d_noxchg is the primary 6/12-second reference because it has the best average development improvement across those two locked budgets. M1d_nojoint is retained because it is strongest at 12/30 seconds; M1d is retained as the full-operator reference. The exact method list, 60 instance hashes, source manifest hash and all checkpoint hashes are written to results/LOCKED_EVAL_FREEZE.json before the first locked task.

## Runs
- Budgets: 6 and 12 seconds.
- Solver seeds: 101, 102, 103 for every method/map/budget.
- Workers: 8, respecting the 12-CPU cgroup quota.
- All methods use the same instance bytes, budget, solver seeds and independent evaluator.
- PPO/BC checkpoints are frozen by SHA256; no checkpoint selection or hyperparameter change after locked evaluation begins.
- Separate cold model load, initialization, search, finalization, independent evaluation, output and end-to-end timings.

## Statistics
- Statistical unit: map; aggregate the three seeds within each map first.
- Report feasible rate and failures over the full planned task count; never success-condition the cost mean.
- Paired differences vs M1d_noxchg (primary) and separately vs M1d_nojoint and M1d; bootstrap 95% CI; Wilcoxon signed-rank; Holm correction across the predeclared comparisons. PPO must beat the strongest of the three non-RL candidates, not only M0.
- Report mean/median/std, wins/losses/ties, effect size, and per-distribution/per-scale breakdown.
- Training wall time, teacher data collection, PPO update time, checkpoint selection and inference overhead are reported separately.

## Go/no-go
A PPO claim requires PPO to improve over the strongest non-RL baseline on the locked maps with a meaningful paired effect and confidence interval, without reducing feasibility. If not, report the negative result and do not retune on locked maps.
