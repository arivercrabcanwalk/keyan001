#!/usr/bin/env bash
# No implicit training. All scientific starts require an admitted ticket.
set -euo pipefail
cd "$(dirname "$0")"
export RLV3_ROOT="$PWD" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY="${PY:-$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
mode="${MODE:-check}"
if [[ "${SMOKE:-0}" == 1 && "$mode" != check && "$mode" != smoke && "$mode" != joint-smoke ]]; then
  echo "SMOKE conflicts with the requested mode" >&2; exit 2
fi
case "$mode" in
  experiment)
    args=(--part A --profile "${PROFILE:-standard}" --device "${DEVICE:-auto}")
    if [[ -n "${OUT:-}" ]]; then args+=(--out "$OUT"); fi
    if [[ -n "${SEEDS:-}" ]]; then args+=(--seeds "$SEEDS"); fi
    PY="$(command -v "$PY")"; export PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"
    exec bash ../run_experiments.sh "${args[@]}"
    ;;
  check|smoke)
    "$PY" -B -m pytest -p no:cacheprovider -q tests
    exec "$PY" -B -m rlcore.engineering_smoke
    ;;
  joint-smoke)
    : "${OUT:?supply a new absolute engineering output directory}"
    exec "$PY" -B -m rlcore.joint_driver joint-smoke --out "$OUT"
    ;;
  joint-preflight|joint-train)
    : "${TICKET:?approved joint development ticket required}"
    : "${OUT:?supply a new absolute output directory}"
    args=("$mode" --ticket "$TICKET" --out "$OUT")
    if [[ "$mode" == joint-train ]]; then
      : "${PREFLIGHT:?supply successful joint-preflight output}"
      args+=(--preflight "$PREFLIGHT")
    fi
    exec "$PY" -B -m rlcore.joint_driver "${args[@]}"
    ;;
  legacy-preflight|legacy-pilot)
    : "${TICKET:?approved original campaign ticket required}"
    : "${OUT:?supply an output directory for the legacy campaign}"
    args=(--ticket "$TICKET" --out "$OUT" --workers "${W:-4}")
    if [[ "$mode" == legacy-preflight ]]; then args+=(--preflight-only); fi
    exec "$PY" -B -m rlcore.campaign "${args[@]}"
    ;;
  *) echo "Use joint-smoke, joint-preflight, joint-train or check; old sequential controls: legacy-preflight/legacy-pilot. No Formal entry." >&2; exit 2 ;;
esac
