# Code Map

## Liu/SEMFiX baseline

- `source/liu_semfix/lrphsd/`: problem parser, evaluator, TSALNS/SEMFiX variants, greedy and precision checks.
- `source/liu_semfix/carl/`: historical CA-RL/route controller implementation. It is included for audit and negative-result context, not as the current research direction.
- `source/liu_semfix/scripts/`: benchmark, audit, training and verification entry points.
- `source/liu_semfix/native/`: C source for the optional native kernels; compiled `.so` files are intentionally omitted.

## Direct route-RL implementation

- `source/route_rl/return_makespan/scorer.py`: independent feasibility, original cost and `M_return`/MTC scoring.
- `source/route_rl/return_makespan/g24_weather_nfz/`: weather/NFZ route environment, physical replay, author anchor adapter, route policy, RL update routines, bounded non-RL baselines and tests.
- `source/route_rl/return_makespan/g23/`: author-method adapter and constrained published-family instance generator.
- `source/route_rl/station/`: station-level engineering environment/DP diagnostics. These are not novelty claims.

## Joint weather/emergency controls

- `source/joint_weather_emergency/`: selected modules for dynamic emergency tasks, causal memory, weather policy, replay and training integration. These files are engineering sources from the development package; their reports define what was and was not scientifically admitted.

## Running the safe check

`source/run_syntax_check.sh` compiles every exported Python file. The research scripts may require NumPy, PyTorch, Java, instance files and the full original runtime; those dependencies and private data are not bundled here.
