#!/usr/bin/env bash
# Run only handwritten engineering checks; no historical instances or training.
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
for pkg in rlv3_weather rlv3_emergency; do
  MODE=check bash "$pkg/run_all.sh"
done
py="${PY:-python3}"
if [[ -z "${PY:-}" && -x "$root/rlv3_weather/.venv/bin/python" ]]; then
  py="$root/rlv3_weather/.venv/bin/python"
fi
"$py" -B -m pytest -q -p no:cacheprovider tests
