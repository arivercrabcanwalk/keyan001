# V3 development results: CA-RL-TSALNS controller comparison

Date: 2026-10-30. Dataset: 12 development instances (dev12), three paired seeds (101, 102, 103), 12 methods, four wall-clock budgets. Each budget contains 432 tasks (12 × 12 × 3), with zero errors and 100% independently validated feasibility.

## Primary comparison against M0

M0 is the research-budget V6 wrapper and consumes the full wall-clock budget. M0paper and M0frozen are fixed-iteration profiles (500 outer iterations) and may terminate early; they are parameter-fidelity diagnostics, not equal-budget primary controls.

| Budget | M1d | M1d_nojoint | M1d_noxchg | M2 | M2_nojoint | M2_noxchg | M3 | M4 | M5 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 s | -1.216% (p=.0171) | -1.218% (p=.0054) | **-1.293% (p=.0054)** | -0.936% (.0054) | -0.910% (.0171) | -1.084% (.0054) | -0.347% (1.0000) | -1.064% (.0146) | -0.694% (.7002) |
| 6 s | -0.584% (.0054) | -0.523% (.0054) | **-0.649% (.0054)** | -0.297% (.3296) | -0.382% (.0557) | -0.308% (.2612) | +0.333% (.4072) | -0.318% (.2612) | +0.175% (.4697) |
| 12 s | -0.547% (.0054) | **-0.606% (.0054)** | -0.585% (.0054) | -0.285% (.6108) | -0.306% (.3857) | -0.294% (.6055) | +0.340% (.6108) | -0.326% (.2549) | -0.027% (.6108) |
| 30 s | -0.486% (.0054) | **-0.587% (.0054)** | -0.565% (.0054) | -0.261% (.6108) | -0.327% (.0410) | -0.352% (.1709) | +0.254% (.6108) | -0.330% (.1709) | -0.065% (.8501) |

Numbers are relative mean cost changes vs M0; negative is better. Parentheses contain Holm-adjusted p-values from paired instance-level tests. All methods were 100% feasible. The three M1d-family controllers beat M0 significantly at every budget.

## Direct M1d ablations

| Budget | Contrast | Mean paired cost difference | Holm p | 95% bootstrap CI |
|---:|---|---:|---:|---:|
| 2 s | no-exchange vs M1d | -0.4039 | 0.5156 | [-0.9860, +0.2399] |
| 2 s | no-joint vs M1d | -0.0072 | 1.0000 | [-0.5804, +0.6968] |
| 6 s | no-exchange vs M1d | -0.3399 | 0.3125 | [-0.6828, -0.0093] |
| 6 s | no-joint vs M1d | +0.3181 | 1.0000 | [-0.2332, +1.0309] |
| 12 s | no-exchange vs M1d | -0.1986 | 0.3125 | [-0.3873, -0.0220] |
| 12 s | no-joint vs M1d | -0.3075 | 0.3281 | [-0.7174, -0.0100] |
| 30 s | no-exchange vs M1d | -0.4067 | 0.0625 | [-0.6762, -0.1578] |
| 30 s | no-joint vs M1d | -0.5215 | 0.0625 | [-0.9155, -0.1618] |

The paired ablation p-values do not cross 0.05 after Holm correction. The bootstrap intervals shown are unadjusted 95% intervals. Therefore the mean ranking is a selection signal, not proof that either ablation is statistically superior.

Across the locked-evaluation budgets (6 and 12 s), M1d_noxchg has the best simple average improvement vs M0 (-0.617%), followed by M1d (-0.5655%) and M1d_nojoint (-0.5645%). M1d_nojoint is strongest at 12 and 30 s. Preserve all three as development-selected non-RL comparators in the locked evaluation; use M1d_noxchg as the predeclared primary reference for the 6/12 s combined comparison.

## Operator diagnostics (30 s)

For full M1d, the high-volume routing exchanges have modest yield:
- cross-trip exchange: 528,638 attempts, 52.8% feasible, 5.2% improved, 4 best updates.
- cross-drone exchange: 162,143 attempts, 44.4% feasible, 4.1% improved, 3 best updates.
- relocate: 553,759 attempts, 22.8% improved, 52 best updates.
- classic routing: 774,670 attempts, 48.2% improved, 344 best updates.

Joint operators are heterogeneous:
- joint_open and joint_upgrade had zero best updates.
- joint_close had 42 best updates.
- joint_downgrade had 23 best updates.
- joint_downgrade_local had 15 best updates.

The no-exchange variant reallocates the 25% routing draw to relocate; it records 1,238,374 relocate attempts and 99 best updates. The no-joint variant still retains cross-drone and cross-trip exchanges. These counts explain why the variants are promising, but counts alone do not establish causal contribution.

## Research interpretation and next action

1. M1d-family scheduled search is the strongest current non-RL family; M2 adaptive, M4 LinUCB and M5 episode-local Q-learning do not consistently match it.
2. Do not claim that Joint or cross-exchange is harmful: the direct ablation contrasts are not Holm-significant at 0.05.
3. Use M1d, M1d_nojoint and M1d_noxchg together as non-RL comparators on the locked suite; M1d_noxchg is the primary 6/12-second reference by average development performance.
4. BC/PPO training remains a macro-neighborhood controller experiment: actions select one of four neighborhood families and one of three intensities. Candidate target insertion, station assignment and detailed route construction remain heuristic. This is not yet a learned per-waypoint flight planner.
5. The 60-map locked suite is synthetic stress testing, not real-world evidence. Do not tune after opening its results.
