[2026-11-13 09:39:36 JST] Official run: ncpu=40 avail=38 workers/seed=19 downstream=38 hours=2.0 (pomo_v2, synthetic weather)
[2026-11-13 09:39:36 JST] ======== Phase 1: pomo_v2 seeds 1 and 2 from scratch (parallel) ========
[2026-11-13 09:39:36 JST] TRAIN seed 1 start  workers=19
[2026-11-13 09:39:36 JST] TRAIN seed 2 start  workers=19
[2026-11-13 12:56:03 JST] TRAIN seed 1 exit=0
[2026-11-13 13:01:02 JST] TRAIN seed 2 exit=0
[2026-11-13 13:01:02 JST] seeds finished rc1=0 rc2=0
[2026-11-13 13:01:03 JST] tally official_testa=1 (need >=2/3 with both G-b and G-c)
[2026-11-13 13:01:03 JST] ======== Phase 2: downstream ========
[2026-11-13 13:01:03 JST] P3 uniform retrain seed 0 start workers=19 hours=2.0
[2026-11-13 13:01:03 JST] P3 retrain launched pid=6524  (eval workers=19)
[2026-11-13 13:01:03 JST] Test-A official: gates passed
[2026-11-13 13:07:38 JST] Test-A exit=0
[2026-11-13 13:13:11 JST] P3 uniform-eval (storm-trained) exit=0
[2026-11-13 13:23:41 JST] P4 sigma exit=0  speed exit=0
[2026-11-13 13:23:41 JST] value-net ckpt=/root/keyan001/wx2_server_run/models/rl_s2_best_pomo_v2.npz
[2026-11-13 13:23:52 JST] value-net exit=0
[2026-11-13 13:48:42 JST] WX-H exit=0
[2026-11-13 16:14:02 JST] P3 uniform retrain exit=0
[2026-11-13 16:14:02 JST] P3 retrain wait exit=0 (logfile logs/p3_retrain.out)
[2026-11-13 16:14:42 JST] P3 uniform-retrain eval exit=0
[2026-11-13 16:14:42 JST] ======== Phase 3: analysis and pack ========
[2026-11-13 16:14:43 JST] analyze P3=0 P4=0 summarize=0
[2026-11-13 16:14:44 JST] packing /root/keyan001/wx2_server_run/results_out.tar.gz
