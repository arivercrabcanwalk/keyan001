# Static plan cost vs TSALNS (fresh_ts1.jsonl)

| arm | n | mean gap | median | max | wins | Wilcoxon p | mean wall s |
|---|---|---|---|---|---|---|---|
| OURS_full_1s | 49/50 (fail 0) | -4.56% | -4.37% | +0.32% | 47/49 | 1.78e-14 | 1.41 (max 2.7) |
| OURS_pure | 49/50 (fail 0) | -3.25% | -3.40% | +2.24% | 43/49 | 2.29e-10 | 0.41 (max 1.2) |

WARNING: reference missing/infeasible on 1 instances: ['f6_50_2']

**G1 static gate** (OURS_full_1s mean gap <= +1.0%): PASS (-4.56%)
