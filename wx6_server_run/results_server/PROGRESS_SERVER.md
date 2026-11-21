[2026-11-18 15:34:35 America] WX6 run_all start: ncpu=30 workers=28 smoke=0 seeds=[0 1 2 3 4]/[0 1 2] shield=1 es=250 x pop 20 x batch 16 teacher=RL5 M=8 p=0.5 budget=2.5h+2.5h python=Python 3.12.13
[2026-11-18 15:34:35 America] START s1_tsc_train
[2026-11-18 15:36:01 America] DONE s1_tsc_train
[2026-11-18 15:36:01 America] START s1_tsc_dev
[2026-11-18 15:36:12 America] DONE s1_tsc_dev
[2026-11-18 15:36:12 America] START s1_tsc_test
[2026-11-18 15:36:34 America] DONE s1_tsc_test
[2026-11-18 15:36:34 America] START s1_tsc_g
[2026-11-18 15:37:17 America] DONE s1_tsc_g
[2026-11-18 15:37:17 America] START s1_tsc_l
[2026-11-18 15:38:18 America] FAIL s1_tsc_l rc=2 (see logs/s1_tsc_l.log)
[2026-11-18 15:38:18 America] STOP: required stage s1_tsc_l failed
[2026-11-18 15:58:55 America] WX6 run_all start: ncpu=30 workers=28 smoke=0 seeds=[0 1 2 3 4]/[0 1 2] shield=1 es=250 x pop 20 x batch 16 teacher=RL5 M=8 p=0.5 budget=2.5h+2.5h python=Python 3.12.13
[2026-11-18 15:58:55 America] skip s1_tsc_train (done)
[2026-11-18 15:58:55 America] skip s1_tsc_dev (done)
[2026-11-18 15:58:55 America] skip s1_tsc_test (done)
[2026-11-18 15:58:55 America] skip s1_tsc_g (done)
[2026-11-18 15:58:55 America] START s1_tsc_l
[2026-11-18 15:58:56 America] DONE s1_tsc_l
[2026-11-18 15:58:56 America] START s1_ts_test
[2026-11-18 15:59:17 America] DONE s1_ts_test
[2026-11-18 15:59:17 America] START s1_tscr10_test
[2026-11-18 15:59:39 America] DONE s1_tscr10_test
[2026-11-18 15:59:39 America] START s1_tsr_test
[2026-11-18 15:59:40 America] DONE s1_tsr_test
[2026-11-18 15:59:40 America] START s1_pad_test
[2026-11-18 15:59:41 America] DONE s1_pad_test
[2026-11-18 15:59:41 America] START s2_cover_train_tsc
[2026-11-18 15:59:42 America] DONE s2_cover_train_tsc
[2026-11-18 15:59:42 America] START s2_cover_dev_tsc
[2026-11-18 15:59:42 America] DONE s2_cover_dev_tsc
[2026-11-18 15:59:42 America] START s2_cover_test_tsc
[2026-11-18 15:59:42 America] DONE s2_cover_test_tsc
[2026-11-18 15:59:42 America] START s2_cover_fresh6_tsc
[2026-11-18 15:59:43 America] DONE s2_cover_fresh6_tsc
[2026-11-18 15:59:43 America] START s2_cover_large6_tsc
[2026-11-18 15:59:44 America] DONE s2_cover_large6_tsc
[2026-11-18 15:59:44 America] START s2_cover_test_tscr10
[2026-11-18 15:59:45 America] DONE s2_cover_test_tscr10
[2026-11-18 15:59:45 America] START s2_cover_test_tsr
[2026-11-18 15:59:45 America] DONE s2_cover_test_tsr
[2026-11-18 15:59:45 America] START s2_cover_test_pad
[2026-11-18 15:59:46 America] DONE s2_cover_test_pad
[2026-11-18 15:59:46 America] author's unmodified TSALNS plans leaving Omega uncovered: [cover] 47/50 plans leave Omega points uncovered
[2026-11-18 15:59:46 America] START s3_dev_rules
[2026-11-18 16:01:10 America] DONE s3_dev_rules
[2026-11-18 16:01:10 America] START s3_author_gate
[2026-11-18 16:01:10 America] DONE s3_author_gate
[2026-11-18 16:01:10 America] START s3_n6_freeze
[2026-11-18 16:01:11 America] DONE s3_n6_freeze
[2026-11-18 16:01:11 America] N6_best frozen: N6_60_0.1
[2026-11-18 16:01:11 America] START s3_dev_reopt
[2026-11-18 16:12:31 America] DONE s3_dev_reopt
[2026-11-18 16:12:31 America] START s3_sb_freeze
[2026-11-18 16:12:33 America] DONE s3_sb_freeze
[2026-11-18 16:12:33 America] SB (strongest fair non-RL baseline) frozen on dev: R_N6_60_0.1
[2026-11-18 16:12:33 America] START s4_teacher_r0
[2026-11-18 18:43:08 America] DONE s4_teacher_r0
[2026-11-18 18:43:08 America] START s5_distill_r0
[2026-11-18 18:43:31 America] DONE s5_distill_r0
[2026-11-18 18:43:31 America] START s6_teacher_r1
[2026-11-18 21:15:07 America] DONE s6_teacher_r1
[2026-11-18 21:15:07 America] START s7_distill_main_s0
[2026-11-18 21:15:52 America] WX6 run_all start: ncpu=36 workers=34 smoke=0 seeds=[0 1 2 3 4]/[0 1 2] shield=1 es=250 x pop 20 x batch 16 teacher=RL5 M=8 p=0.5 budget=2.5h+2.5h python=Python 3.12.13
[2026-11-18 21:15:52 America] skip s1_tsc_train (done)
[2026-11-18 21:15:52 America] skip s1_tsc_dev (done)
[2026-11-18 21:15:52 America] skip s1_tsc_test (done)
[2026-11-18 21:15:52 America] skip s1_tsc_g (done)
[2026-11-18 21:15:52 America] skip s1_tsc_l (done)
[2026-11-18 21:15:52 America] skip s1_ts_test (done)
[2026-11-18 21:15:52 America] skip s1_tscr10_test (done)
[2026-11-18 21:15:52 America] skip s1_tsr_test (done)
[2026-11-18 21:15:52 America] skip s1_pad_test (done)
[2026-11-18 21:15:52 America] skip s2_cover_train_tsc (done)
[2026-11-18 21:15:52 America] skip s2_cover_dev_tsc (done)
[2026-11-18 21:15:52 America] skip s2_cover_test_tsc (done)
[2026-11-18 21:15:52 America] skip s2_cover_fresh6_tsc (done)
[2026-11-18 21:15:52 America] skip s2_cover_large6_tsc (done)
[2026-11-18 21:15:52 America] skip s2_cover_test_tscr10 (done)
[2026-11-18 21:15:52 America] skip s2_cover_test_tsr (done)
[2026-11-18 21:15:52 America] skip s2_cover_test_pad (done)
[2026-11-18 21:15:53 America] author's unmodified TSALNS plans leaving Omega uncovered: [cover] 47/50 plans leave Omega points uncovered
[2026-11-18 21:15:53 America] skip s3_dev_rules (done)
[2026-11-18 21:15:53 America] skip s3_author_gate (done)
[2026-11-18 21:15:53 America] skip s3_n6_freeze (done)
[2026-11-18 21:15:53 America] N6_best frozen: N6_60_0.1
[2026-11-18 21:15:53 America] skip s3_dev_reopt (done)
[2026-11-18 21:15:53 America] skip s3_sb_freeze (done)
[2026-11-18 21:15:53 America] SB (strongest fair non-RL baseline) frozen on dev: R_N6_60_0.1
[2026-11-18 21:15:53 America] skip s4_teacher_r0 (done)
[2026-11-18 21:15:53 America] skip s5_distill_r0 (done)
[2026-11-18 21:15:53 America] skip s6_teacher_r1 (done)
[2026-11-18 21:15:53 America] START s7_distill_main_s0
[2026-11-18 21:16:30 America] DONE s7_distill_main_s0
[2026-11-18 21:16:30 America] START s7_distill_main_s1
[2026-11-18 21:17:09 America] DONE s7_distill_main_s1
[2026-11-18 21:17:09 America] START s7_distill_main_s2
[2026-11-18 21:17:42 America] DONE s7_distill_main_s2
[2026-11-18 21:17:42 America] START s7_distill_main_s3
[2026-11-18 21:18:33 America] DONE s7_distill_main_s3
[2026-11-18 21:18:33 America] START s7_distill_main_s4
[2026-11-18 21:19:09 America] DONE s7_distill_main_s4
[2026-11-18 21:19:09 America] START s7_distill_nf_s0
[2026-11-18 21:20:17 America] DONE s7_distill_nf_s0
[2026-11-18 21:20:17 America] START s7_distill_ne_s0
[2026-11-18 21:20:54 America] DONE s7_distill_ne_s0
[2026-11-18 21:20:54 America] START s7_distill_nf_s1
[2026-11-18 21:22:01 America] DONE s7_distill_nf_s1
[2026-11-18 21:22:01 America] START s7_distill_ne_s1
[2026-11-18 21:22:40 America] DONE s7_distill_ne_s1
[2026-11-18 21:22:40 America] START s7_distill_nf_s2
[2026-11-18 21:23:37 America] DONE s7_distill_nf_s2
[2026-11-18 21:23:37 America] START s7_distill_ne_s2
[2026-11-18 21:24:24 America] DONE s7_distill_ne_s2
[2026-11-18 21:24:24 America] ES: 17 runs x 2 workers; OT reference for training = S:N6_60_0.1 (selection uses SB=R_N6_60_0.1 on dev)
[2026-11-18 21:24:24 America] ES launch main_s0 (attempt 1)
[2026-11-18 21:24:24 America] ES launch main_s1 (attempt 1)
[2026-11-18 21:24:24 America] ES launch main_s2 (attempt 1)
[2026-11-18 21:24:24 America] ES launch main_s3 (attempt 1)
[2026-11-18 21:24:24 America] ES launch main_s4 (attempt 1)
[2026-11-18 21:24:24 America] ES launch nf_s0 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ne_s0 (attempt 1)
[2026-11-18 21:24:24 America] ES launch uc_s0 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ns_s0 (attempt 1)
[2026-11-18 21:24:24 America] ES launch nf_s1 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ne_s1 (attempt 1)
[2026-11-18 21:24:24 America] ES launch uc_s1 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ns_s1 (attempt 1)
[2026-11-18 21:24:24 America] ES launch nf_s2 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ne_s2 (attempt 1)
[2026-11-18 21:24:24 America] ES launch uc_s2 (attempt 1)
[2026-11-18 21:24:24 America] ES launch ns_s2 (attempt 1)
[2026-11-20 08:50:35 America] START s9_select_main_s0
[2026-11-20 08:51:59 America] DONE s9_select_main_s0
[2026-11-20 08:51:59 America] START s9_select_main_s1
[2026-11-20 08:53:21 America] DONE s9_select_main_s1
[2026-11-20 08:53:21 America] START s9_select_main_s2
[2026-11-20 08:54:53 America] DONE s9_select_main_s2
[2026-11-20 08:54:53 America] START s9_select_main_s3
[2026-11-20 08:56:17 America] DONE s9_select_main_s3
[2026-11-20 08:56:17 America] START s9_select_main_s4
[2026-11-20 08:57:28 America] DONE s9_select_main_s4
[2026-11-20 08:57:28 America] START s9_select_nf_s0
[2026-11-20 08:58:45 America] DONE s9_select_nf_s0
[2026-11-20 08:58:45 America] START s9_select_ne_s0
[2026-11-20 09:00:10 America] DONE s9_select_ne_s0
[2026-11-20 09:00:10 America] START s9_select_uc_s0
[2026-11-20 09:01:42 America] DONE s9_select_uc_s0
[2026-11-20 09:01:42 America] START s9_select_ns_s0
[2026-11-20 09:03:07 America] DONE s9_select_ns_s0
[2026-11-20 09:03:07 America] START s9_select_nf_s1
[2026-11-20 09:04:23 America] DONE s9_select_nf_s1
[2026-11-20 09:04:23 America] START s9_select_ne_s1
[2026-11-20 09:05:45 America] DONE s9_select_ne_s1
[2026-11-20 09:05:45 America] START s9_select_uc_s1
[2026-11-20 09:07:06 America] DONE s9_select_uc_s1
[2026-11-20 09:07:06 America] START s9_select_ns_s1
[2026-11-20 09:08:35 America] DONE s9_select_ns_s1
[2026-11-20 09:08:35 America] START s9_select_nf_s2
[2026-11-20 09:09:39 America] DONE s9_select_nf_s2
[2026-11-20 09:09:39 America] START s9_select_ne_s2
[2026-11-20 09:11:01 America] DONE s9_select_ne_s2
[2026-11-20 09:11:01 America] START s9_select_uc_s2
[2026-11-20 09:12:20 America] DONE s9_select_uc_s2
[2026-11-20 09:12:20 America] START s9_select_ns_s2
[2026-11-20 09:13:49 America] DONE s9_select_ns_s2
[2026-11-20 09:13:49 America] test arms: A1=A1,A2=A2,N1_240=N1_240,N6_best=N6_60_0.1,S:N6_best=S:N6_60_0.1,R_N6best=R_N6_60_0.1,Rfc_N6best=Rfc_N6_60_0.1,RfcP_N6best=Rfc600e15_N6_60_0.1,S:RfcP_N6best=S:Rfc600e15_N6_60_0.1,SB=R_N6_60_0.1,RL5=RL5,RL6_s0=RL6,RL6_s1=RL6,RL6_s2=RL6,RL6_s3=RL6,RL6_s4=RL6,RL6noES_s0=RL6,RL6noES_s1=RL6,RL6noES_s2=RL6,RL6noES_s3=RL6,RL6noES_s4=RL6,RL6nf_s0=RL6,RL6nf_s1=RL6,RL6nf_s2=RL6,RL6ne_s0=RL6,RL6ne_s1=RL6,RL6ne_s2=RL6,RL6uc_s0=RL6,RL6uc_s1=RL6,RL6uc_s2=RL6,RL6ns_s0=RL6,RL6ns_s1=RL6,RL6ns_s2=RL6
[2026-11-20 09:13:49 America] START s10_testM
[2026-11-20 11:09:40 America] FAIL s10_testM rc=143 (see logs/s10_testM.log)
[2026-11-20 11:09:40 America] STOP: required stage s10_testM failed
[2026-11-20 12:35:57 America] WX6 run_all start: ncpu=36 workers=34 smoke=0 seeds=[0 1 2 3 4]/[0 1 2] shield=1 es=250 x pop 20 x batch 16 teacher=RL5 M=8 p=0.5 budget=2.5h+2.5h python=Python 3.12.13
[2026-11-20 12:35:59 America] skip s1_tsc_train (done)
[2026-11-20 12:35:59 America] skip s1_tsc_dev (done)
[2026-11-20 12:35:59 America] skip s1_tsc_test (done)
[2026-11-20 12:35:59 America] skip s1_tsc_g (done)
[2026-11-20 12:35:59 America] skip s1_tsc_l (done)
[2026-11-20 12:35:59 America] skip s1_ts_test (done)
[2026-11-20 12:35:59 America] skip s1_tscr10_test (done)
[2026-11-20 12:35:59 America] skip s1_tsr_test (done)
[2026-11-20 12:35:59 America] skip s1_pad_test (done)
[2026-11-20 12:35:59 America] skip s2_cover_train_tsc (done)
[2026-11-20 12:35:59 America] skip s2_cover_dev_tsc (done)
[2026-11-20 12:35:59 America] skip s2_cover_test_tsc (done)
[2026-11-20 12:35:59 America] skip s2_cover_fresh6_tsc (done)
[2026-11-20 12:35:59 America] skip s2_cover_large6_tsc (done)
[2026-11-20 12:35:59 America] skip s2_cover_test_tscr10 (done)
[2026-11-20 12:35:59 America] skip s2_cover_test_tsr (done)
[2026-11-20 12:35:59 America] skip s2_cover_test_pad (done)
[2026-11-20 12:36:00 America] author's unmodified TSALNS plans leaving Omega uncovered: [cover] 47/50 plans leave Omega points uncovered
[2026-11-20 12:36:00 America] skip s3_dev_rules (done)
[2026-11-20 12:36:00 America] skip s3_author_gate (done)
[2026-11-20 12:36:00 America] skip s3_n6_freeze (done)
[2026-11-20 12:36:00 America] N6_best frozen: N6_60_0.1
[2026-11-20 12:36:00 America] skip s3_dev_reopt (done)
[2026-11-20 12:36:00 America] skip s3_sb_freeze (done)
[2026-11-20 12:36:01 America] SB (strongest fair non-RL baseline) frozen on dev: R_N6_60_0.1
[2026-11-20 12:36:01 America] skip s4_teacher_r0 (done)
[2026-11-20 12:36:01 America] skip s5_distill_r0 (done)
[2026-11-20 12:36:01 America] skip s6_teacher_r1 (done)
[2026-11-20 12:36:01 America] skip s7_distill_main_s0 (done)
[2026-11-20 12:36:01 America] skip s7_distill_main_s1 (done)
[2026-11-20 12:36:01 America] skip s7_distill_main_s2 (done)
[2026-11-20 12:36:01 America] skip s7_distill_main_s3 (done)
[2026-11-20 12:36:01 America] skip s7_distill_main_s4 (done)
[2026-11-20 12:36:01 America] skip s7_distill_nf_s0 (done)
[2026-11-20 12:36:01 America] skip s7_distill_ne_s0 (done)
[2026-11-20 12:36:01 America] skip s7_distill_nf_s1 (done)
[2026-11-20 12:36:01 America] skip s7_distill_ne_s1 (done)
[2026-11-20 12:36:01 America] skip s7_distill_nf_s2 (done)
[2026-11-20 12:36:01 America] skip s7_distill_ne_s2 (done)
[2026-11-20 12:36:01 America] ES: 17 runs x 2 workers; OT reference for training = S:N6_60_0.1 (selection uses SB=R_N6_60_0.1 on dev)
[2026-11-20 12:36:01 America] skip s9_select_main_s0 (done)
[2026-11-20 12:36:01 America] skip s9_select_main_s1 (done)
[2026-11-20 12:36:01 America] skip s9_select_main_s2 (done)
[2026-11-20 12:36:01 America] skip s9_select_main_s3 (done)
[2026-11-20 12:36:01 America] skip s9_select_main_s4 (done)
[2026-11-20 12:36:01 America] skip s9_select_nf_s0 (done)
[2026-11-20 12:36:01 America] skip s9_select_ne_s0 (done)
[2026-11-20 12:36:01 America] skip s9_select_uc_s0 (done)
[2026-11-20 12:36:01 America] skip s9_select_ns_s0 (done)
[2026-11-20 12:36:01 America] skip s9_select_nf_s1 (done)
[2026-11-20 12:36:01 America] skip s9_select_ne_s1 (done)
[2026-11-20 12:36:01 America] skip s9_select_uc_s1 (done)
[2026-11-20 12:36:01 America] skip s9_select_ns_s1 (done)
[2026-11-20 12:36:01 America] skip s9_select_nf_s2 (done)
[2026-11-20 12:36:01 America] skip s9_select_ne_s2 (done)
[2026-11-20 12:36:01 America] skip s9_select_uc_s2 (done)
[2026-11-20 12:36:01 America] skip s9_select_ns_s2 (done)
[2026-11-20 12:36:02 America] test arms: A1=A1,A2=A2,N1_240=N1_240,N6_best=N6_60_0.1,S:N6_best=S:N6_60_0.1,R_N6best=R_N6_60_0.1,Rfc_N6best=Rfc_N6_60_0.1,RfcP_N6best=Rfc600e15_N6_60_0.1,S:RfcP_N6best=S:Rfc600e15_N6_60_0.1,SB=R_N6_60_0.1,RL5=RL5,RL6_s0=RL6,RL6_s1=RL6,RL6_s2=RL6,RL6_s3=RL6,RL6_s4=RL6,RL6noES_s0=RL6,RL6noES_s1=RL6,RL6noES_s2=RL6,RL6noES_s3=RL6,RL6noES_s4=RL6,RL6nf_s0=RL6,RL6nf_s1=RL6,RL6nf_s2=RL6,RL6ne_s0=RL6,RL6ne_s1=RL6,RL6ne_s2=RL6,RL6uc_s0=RL6,RL6uc_s1=RL6,RL6uc_s2=RL6,RL6ns_s0=RL6,RL6ns_s1=RL6,RL6ns_s2=RL6
[2026-11-20 12:36:02 America] skip s10_testM (done)
[2026-11-20 12:36:02 America] START s10_testG
