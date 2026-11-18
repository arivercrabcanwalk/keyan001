# Dynamic results — scenario `base` (10 maps × 50 days = 500 paired runs of 500 expected; worker errors 0)

completion metric used for G3: `complete_strict`

| arm | J5 | cost | fails | overtime min | urgent late min | urgent on-time | CVaR90 late | completion | makespan (secondary) | decision p99 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| OURS_s0 | 11523.8 | 2492.9 | 13.2 | 593.6 | 167.8 | 0.804 | 33.2 | 1.000 | 583.8 | 2.0 |
| OURS_s1 | 11649.6 | 2479.1 | 13.0 | 562.9 | 173.7 | 0.799 | 35.2 | 0.998 | 582.0 | 2.0 |
| OURS_s2 | 12454.7 | 2468.3 | 12.4 | 638.8 | 196.1 | 0.789 | 38.0 | 1.000 | 579.8 | 2.0 |
| TS_A1 | 26688.1 | 2746.3 | 15.4 | 352.3 | 500.3 | 0.512 | 69.3 | 0.840 | 566.2 | 0.0 |
| TS_N6 | 23453.6 | 2933.3 | 12.3 | 695.5 | 416.7 | 0.659 | 60.8 | 0.842 | 613.0 | 1.9 |
| TS_Rfc | 23501.7 | 2845.8 | 13.9 | 652.4 | 419.5 | 0.651 | 61.9 | 0.842 | 612.3 | 116.1 |
| TS_RL5 | 19536.4 | 3001.3 | 10.0 | 673.1 | 330.2 | 0.690 | 57.2 | 0.842 | 606.3 | 1.8 |

## OURS_s0 vs baselines (J5; map-level Wilcoxon, Holm over 4 baselines)

| baseline | ΔJ5 % | 95% crossed-bootstrap CI | p | Holm p (family) | Δfails % | Δot min | Δon-time_h | median per-map Δ % |
|---|---|---|---|---|---|---|---|---|
| TS_A1 | -56.8% | [-65.0, -48.5] | 2.0e-03 | 5.9e-03 (non-RL) | -14.7% | +241.3 | +0.292 | -57.8% |
| TS_N6 | -50.9% | [-59.5, -41.9] | 2.0e-03 | 5.9e-03 (non-RL) | +7.3% | -102.0 | +0.145 | -50.9% |
| TS_Rfc | -51.0% | [-59.4, -42.4] | 2.0e-03 | 5.9e-03 (non-RL) | -5.3% | -58.9 | +0.153 | -50.2% |
| TS_RL5 | -41.0% | [-49.7, -33.0] | 2.0e-03 | 2.0e-03 (RL) | +31.8% | -79.5 | +0.114 | -39.3% |

Gates: G2_J5=PASS, G4_fails=FAIL, G2b_all_nonRL=PASS, G3_completion=PASS, G5_overtime=PASS, G6_latency=PASS

## OURS_s1 vs baselines (J5; map-level Wilcoxon, Holm over 4 baselines)

| baseline | ΔJ5 % | 95% crossed-bootstrap CI | p | Holm p (family) | Δfails % | Δot min | Δon-time_h | median per-map Δ % |
|---|---|---|---|---|---|---|---|---|
| TS_A1 | -56.3% | [-64.3, -48.6] | 2.0e-03 | 5.9e-03 (non-RL) | -15.6% | +210.6 | +0.287 | -56.0% |
| TS_N6 | -50.3% | [-58.9, -41.7] | 2.0e-03 | 5.9e-03 (non-RL) | +6.1% | -132.7 | +0.140 | -47.5% |
| TS_Rfc | -50.4% | [-58.7, -42.3] | 2.0e-03 | 5.9e-03 (non-RL) | -6.3% | -89.6 | +0.148 | -48.9% |
| TS_RL5 | -40.4% | [-48.9, -32.8] | 2.0e-03 | 2.0e-03 (RL) | +30.3% | -110.2 | +0.109 | -34.3% |

Gates: G2_J5=PASS, G4_fails=FAIL, G2b_all_nonRL=PASS, G3_completion=FAIL, G5_overtime=PASS, G6_latency=PASS

## OURS_s2 vs baselines (J5; map-level Wilcoxon, Holm over 4 baselines)

| baseline | ΔJ5 % | 95% crossed-bootstrap CI | p | Holm p (family) | Δfails % | Δot min | Δon-time_h | median per-map Δ % |
|---|---|---|---|---|---|---|---|---|
| TS_A1 | -53.3% | [-60.8, -46.4] | 2.0e-03 | 5.9e-03 (non-RL) | -19.7% | +286.5 | +0.277 | -52.6% |
| TS_N6 | -46.9% | [-54.8, -39.1] | 2.0e-03 | 5.9e-03 (non-RL) | +1.0% | -56.8 | +0.130 | -43.7% |
| TS_Rfc | -47.0% | [-54.9, -39.6] | 2.0e-03 | 5.9e-03 (non-RL) | -10.8% | -13.7 | +0.138 | -44.0% |
| TS_RL5 | -36.2% | [-44.4, -28.6] | 2.0e-03 | 2.0e-03 (RL) | +24.0% | -34.3 | +0.099 | -31.1% |

Gates: G2_J5=PASS, G4_fails=FAIL, G2b_all_nonRL=PASS, G3_completion=PASS, G5_overtime=PASS, G6_latency=PASS

**All pre-registered dynamic gates pass for all seeds: False**
