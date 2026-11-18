# Static plan cost vs TSALNS (fresh_ts3.jsonl)

| arm | n | mean gap | median | max | wins | Wilcoxon p | mean wall s |
|---|---|---|---|---|---|---|---|
| OURS_full_3s | 50/50 (fail 0) | -3.50% | -3.37% | +0.18% | 48/50 | 1.24e-14 | 3.78 (max 4.9) |
| OURS_pure | 50/50 (fail 0) | -2.06% | -2.13% | +3.01% | 37/50 | 2.37e-06 | 0.41 (max 1.2) |

**G1 static gate** (OURS_full_3s mean gap <= +1.0%): PASS (-3.50%)
