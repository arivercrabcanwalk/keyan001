#!/usr/bin/env bash
# Never silently launch a costly or previously exposed study.
set -euo pipefail
cd "$(dirname "$0")"
export RLV3_ROOT="$PWD" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY="${PY:-$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)}"
mode="${MODE:-check}"
if [[ "${SMOKE:-0}" == 1 && "$mode" != check && "$mode" != smoke ]]; then
  echo "SMOKE conflicts with the explicit MODE" >&2; exit 2
fi
case "$mode" in
  check|smoke)
    "$PY" -B -m pytest -p no:cacheprovider -q tests
    "$PY" -B -m rlcore.engineering_smoke
    echo "ENGINEERING CHECK PASS; no training, no author solve, no scientific claim."
    ;;
  preflight|pilot)
    : "${TICKET:?supply the frozen development ticket with fresh inputs and G0/G3 evidence}"
    : "${OUT:?supply a new or matching pilot output directory}"
    args=(--ticket "$TICKET" --out "$OUT" --workers "${W:-4}")
    if [[ "$mode" == preflight ]]; then args+=(--preflight-only); fi
    exec "$PY" -B -m rlcore.campaign "${args[@]}"
    ;;
  formal|full)
    echo "FORMAL BLOCKED: exposed data, new strong comparators and independent qualification are not supplied by this release." >&2
    exit 2
    ;;
  *) echo "unknown MODE: $mode (use check, preflight or pilot)" >&2; exit 2 ;;
esac
