#!/bin/bash
# Install Python deps. Tolerates an image that already has numpy (PyTorch CUDA image).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="${PY:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi
echo "Python: $($PY -V) at $(command -v $PY)"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Creating .venv (system-site-packages, so the image's numpy/scipy can be reused)"
  "$PY" -m venv --system-site-packages "$ROOT/.venv" || "$PY" -m venv "$ROOT/.venv"
fi
VPY="$ROOT/.venv/bin/python"
VPIP="$ROOT/.venv/bin/pip"
# pip may be missing in some venvs
if [ ! -x "$VPIP" ]; then
  "$VPY" -m ensurepip --upgrade || true
  VPIP="$VPY -m pip"
else
  VPIP="$VPIP"
fi
# If numpy+scipy already import, skip install. Otherwise pip-install loose pins.
if "$VPY" -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)" 2>/dev/null; then
  echo "numpy and scipy already available — skip pip install"
else
  echo "Installing requirements (this is tolerant of already-satisfied packages)"
  "$VPY" -m pip install --upgrade pip setuptools wheel || true
  "$VPY" -m pip install -r "$ROOT/requirements.txt" || \
    "$VPY" -m pip install 'numpy>=1.24' 'scipy>=1.10'
  "$VPY" -c "import numpy, scipy; print('numpy', numpy.__version__, 'scipy', scipy.__version__)"
fi
mkdir -p "$ROOT/data/days" "$ROOT/models" "$ROOT/wx_e/results" "$ROOT/wx_h/results" "$ROOT/logs" "$ROOT/results_final"
echo "setup OK. Next:  nohup bash run_all.sh > run_all.log 2>&1 &"
