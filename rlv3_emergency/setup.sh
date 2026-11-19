#!/usr/bin/env bash
# One-time environment setup (Ubuntu + NVIDIA driver; RTX 3090 / 5090).  Creates ./.venv
#   bash setup.sh                 # auto: CUDA 12.8 wheels (needed for RTX 50xx / Blackwell; also fine for 3090 with driver >= 570)
#   TORCH_INDEX=https://download.pytorch.org/whl/cu121 bash setup.sh   # older driver (3090, driver < 570)
#   PY=/path/to/python bash run_all.sh  # alternatively reuse an existing env that already has torch>=2.1, numpy, scipy, pytest
set -euo pipefail
cd "$(dirname "$0")"
PYBIN="${PYBIN:-python3}"
"$PYBIN" -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
if command -v nvidia-smi >/dev/null 2>&1; then
  IDX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"
else
  IDX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"
fi
pip install -q torch --index-url "$IDX"
pip install -q -r requirements.txt
python - <<'P'
import torch, numpy, scipy
print("torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
P
if ! command -v javac >/dev/null 2>&1; then
  echo "[setup] javac not found. The author's TSALNS (Java) is needed for the training-map plans:"
  echo "        sudo apt-get install -y openjdk-17-jdk-headless   (or set PATH to a JDK >= 11)"
fi
python -m pip freeze --all > .venv/rlv3-environment.txt
echo "[setup] environment captured. MODE=check bash run_all.sh runs synthetic engineering checks only."
