# Static plan cost vs TSALNS (fresh_ts30.jsonl)

| arm | n | mean gap | median | max | wins | Wilcoxon p | mean wall s |
|---|---|---|---|---|---|---|---|
| OURS_full_30s | 50/50 (fail 0) | -0.55% | -0.50% | +0.34% | 43/50 | 6.34e-11 | 30.95 (max 32.3) |
| OURS_pure | 50/50 (fail 0) | +1.21% | +1.05% | +4.64% | 4/50 | 1.44e-10 | 0.41 (max 1.2) |

**G1 static gate** (OURS_full_30s mean gap <= +1.0%): PASS (-0.55%)
