#!/usr/bin/env bash
# Both independent simulated inspection experiments. No package installation or paid provision.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
if [[ -z "${PY:-}" ]]; then
  if [[ -x "$ROOT/rlv3_weather/.venv/bin/python" ]]; then PY="$ROOT/rlv3_weather/.venv/bin/python"; else PY=python3; fi
fi
exec "$PY" -Bu "$ROOT/rlv3_review/run_experiments.py" "$@"
