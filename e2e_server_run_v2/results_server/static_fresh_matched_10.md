# Static plan cost vs TSALNS (fresh_ts10.jsonl)

| arm | n | mean gap | median | max | wins | Wilcoxon p | mean wall s |
|---|---|---|---|---|---|---|---|
| OURS_full_10s | 50/50 (fail 0) | -1.06% | -0.72% | +0.19% | 46/50 | 1.95e-13 | 11.31 (max 13.0) |
| OURS_pure | 50/50 (fail 0) | +0.59% | +0.44% | +5.69% | 17/50 | 1.66e-02 | 0.41 (max 1.2) |

**G1 static gate** (OURS_full_10s mean gap <= +1.0%): PASS (-1.06%)
