#!/usr/bin/env bash
# Creates .venv with PyTorch (CUDA build if an NVIDIA GPU is present, else CPU) + numpy/scipy; checks Java for the
# TSALNS baseline. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
PYBIN="${PYBIN:-python3}"
[ -x .venv/bin/python ] || "$PYBIN" -m venv .venv
PY=.venv/bin/python
$PY -m pip install -q --upgrade pip
if $PY -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() or not __import__('shutil').which('nvidia-smi') else 1)" 2>/dev/null; then
  echo "[setup] torch already OK: $($PY -c 'import torch;print(torch.__version__, torch.cuda.is_available())')"
else
  if command -v nvidia-smi >/dev/null 2>&1; then
    CV=$(nvidia-smi | sed -n 's/.*CUDA Version: \([0-9]*\)\.\([0-9]*\).*/\1\2/p' | head -1); CV=${CV:-121}
    if   [ "$CV" -ge 128 ]; then IDX=cu128
    elif [ "$CV" -ge 126 ]; then IDX=cu126
    elif [ "$CV" -ge 124 ]; then IDX=cu124
    elif [ "$CV" -ge 121 ]; then IDX=cu121
    else IDX=cu118; fi
    echo "[setup] NVIDIA driver supports CUDA ${CV}; installing torch from $IDX"
    $PY -m pip install -q torch --index-url "https://download.pytorch.org/whl/$IDX" || $PY -m pip install -q torch
  else
    echo "[setup] no nvidia-smi: installing CPU torch"
    $PY -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu
  fi
fi
$PY -m pip install -q -r requirements.txt
$PY -c "import torch,numpy,scipy;print('[setup] torch',torch.__version__,'cuda',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
if [ -z "${LRPHSD_DIR:-}" ] && [ ! -f third_party/LRPHSD/code/TSALNS/Main.java ] && command -v git >/dev/null 2>&1; then
  git clone -q --depth 1 https://github.com/lps11735/LRPHSD third_party/LRPHSD || echo "[setup] could not clone the author's repo"
fi
[ -z "${LRPHSD_DIR:-}" ] && [ -f third_party/LRPHSD/code/TSALNS/Main.java ] && export LRPHSD_DIR="$PWD/third_party/LRPHSD"
if command -v javac >/dev/null 2>&1 || [ -n "${JAVAC:-}" ]; then
  bash baselines/tsalns_java/build.sh || echo "[setup] TSALNS Java build skipped (set LRPHSD_DIR); compute-matched TSALNS stage will be skipped"
else
  echo "[setup] javac not found: install openjdk-17-jdk-headless and set LRPHSD_DIR for the compute-matched TSALNS baselines"
fi
echo "[setup] done"
