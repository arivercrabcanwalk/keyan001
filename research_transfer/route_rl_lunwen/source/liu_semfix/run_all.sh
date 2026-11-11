#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"
: "${JAVA_HOME:?Set JAVA_HOME to JDK 17 before running}"

PY=${PYTHON:-/opt/conda/bin/python}
"$PY" -B scripts/build_official_java_reference.py
"$PY" -B scripts/build_guarded_java_reference.py
"$PY" -B build_paper_java.py
"$PY" -B build_postguard_java.py
"$PY" -B scripts/reference_greedy_differential_v3.py
"$PY" -B scripts/verify_official_greedy.py
"$PY" -B exact_certificates.py

for profile in J0 J1 J2 P1 P2; do
  "$PY" -B run_matrix.py --profile "$profile" --out "results/full_$profile" \
    --seeds 0,1,2,3,4 --outer 500 --timeout 600
done
for profile in J1b J2b; do
  "$PY" -B run_postguard_matrix.py --profile "$profile" --out "results/full_$profile" \
    --maps-per-group 10 --seeds 0,1,2,3,4 --timeout 600
done

"$PY" -B analyze_matrix.py --output results/full_matrix_audit.json
"$PY" -B analyze_postguard.py --maps-per-group 10 --output results/postguard_full_audit.json
"$PY" -B analyze_paper_table.py
printf 'REPRODUCTION_COMPLETE source profiles and 4200 full-run tasks audited\n'
