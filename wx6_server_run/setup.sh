#!/usr/bin/env bash
# WX6 setup (idempotent): python venv with numpy/scipy (no torch / GPU needed: the RL6 policy is a numpy network,
# training is CPU-parallel ES + rollout-teacher distillation), Java 17 + the author's TSALNS (mandatory baselines).
set -euo pipefail
cd "$(dirname "$0")"
PYBIN="${PYBIN:-python3}"
[ -x .venv/bin/python ] || "$PYBIN" -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python -c "import numpy, scipy; print('[setup] numpy', numpy.__version__, 'scipy', scipy.__version__)"
if ! command -v javac >/dev/null 2>&1; then
  echo "[setup] javac not found -> trying: sudo apt-get install -y openjdk-17-jdk-headless"
  (sudo -n apt-get update -qq && sudo -n apt-get install -y -qq openjdk-17-jdk-headless) || \
    echo "[setup] could not install Java automatically. Run:  sudo apt install -y openjdk-17-jdk-headless   then re-run setup.sh"
fi
if [ -z "${LRPHSD_DIR:-}" ] && [ ! -f third_party/LRPHSD/code/TSALNS/Main.java ]; then
  git clone -q --depth 1 https://github.com/lps11735/LRPHSD third_party/LRPHSD || echo "[setup] could not clone the author's repo (set LRPHSD_DIR)"
fi
if command -v javac >/dev/null 2>&1; then
  bash baselines/tsalns_java/build.sh
else
  echo "[setup] WARNING: no Java -> the official run cannot start (author baselines are mandatory)"; exit 4
fi
echo "[setup] done"
