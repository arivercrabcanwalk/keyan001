# SMOKE (fresh clone, local box: 8 CPU, no GPU, openjdk 17)
`SMOKE=1 bash run_all.sh` from a fresh `git clone` (TSALNS built with `LRPHSD_DIR=... bash baselines/tsalns_java/build.sh`):
all 50 stage markers DONE (S0 G0, S1 author arms TS/TS-FIX/TS-CC/TS-CR/PAD + G0 PASS, S2 route, S3 plans, S4 exec ExIt->ES + 2 ablations,
S5 static plans, S6 route-J5, S7 site + SimOpt, S8 dyn eval, S9 analysis/CSV/pack). G3 strict completion: PASS (all smoke arms 100 %).
One transient failure seen: author Java did not return for one 10 s TS-FIX run (unseeded, non-deterministic) -> run_tsalns.py now retries
(timeout 3*secs+30 s, max 3, recorded as n_retry); the resumed run completed the stage.
Smoke numbers are NOT results (2 maps x 1-2 days, toy training budgets); gates show "missing" because n<5 pairs.
