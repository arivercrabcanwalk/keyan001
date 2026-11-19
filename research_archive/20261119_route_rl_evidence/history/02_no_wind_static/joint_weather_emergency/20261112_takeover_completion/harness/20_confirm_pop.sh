#!/bin/bash
# 20_confirm_pop.sh - ordinals 2-4 (36 maps) as a confirmation set.
# Registered BEFORE any of these maps is generated: the 12 maps already analysed
# are (family, ordinal=1) only; ordinals 2-4 are unseen and are used exactly once.
set -euo pipefail
R=<EXECUTION_PATH>
GEN=$R/code/route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>
export PYTHONHASHSEED=0
POP=$R/g3_confirm
mkdir -p $POP
python3 - <<'PY'
import json, pathlib, time
p = pathlib.Path('<EXECUTION_PATH>')
p.write_text(json.dumps({
  "schema": "takeover_g3_confirmation_prereg_v1",
  "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "namespace": "takeover-20261112-g3-v1",
  "partition": "opportunity",
  "ordinals": [2, 3, 4],
  "families": 12,
  "expected_maps": 36,
  "already_seen": "ordinal 1 only (12 maps, analysed in G3_DEV_REPORT.md)",
  "primary_estimand": "mean paired change in M_return of exact cost-neutral reassignment vs author anchor, map-level bootstrap 95% CI",
  "secondary_estimand": "LPT 6s vs exact cost-neutral; joint_minmax 12s vs exact cost-neutral",
  "decision_rule": "replication counts only if the point estimate keeps the same sign and the 95% CI excludes zero; otherwise the dev effect is reported as not replicated",
  "no_selection": "all 36 maps enter; no ordinal, family, or map may be dropped after results are seen; anchor failures are retained and reported",
  "budget": {"author_wall_s_per_map_max": 1800, "route_budget_s": [6, 12], "output_bytes_cap": 2000000000}
}, indent=2, sort_keys=True) + "\n")
print("PREREG_CONFIRM_WRITTEN")
PY
python3 $R/harness/gen_maps.py --namespace takeover-20261112-g3-v1 \
  --partition opportunity --out $POP --ordinals 2,3,4 --generator-dir $GEN
echo "--- generated ---"
python3 $R/harness/02_run_author.py --out $POP --timeout 1800
echo "--- author done ---"
python3 $R/harness/03_run_nonrl.py --out $POP --budgets 6,12
echo "--- nonrl done ---"
python3 $R/harness/04_exact_reassign.py --out $POP
echo "--- exact done ---"
date -u +%FT%TZ
