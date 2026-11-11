#!/usr/bin/env bash
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python3 - "$ROOT/source" <<'PY2'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for path in sorted(root.rglob('*.py')):
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
print('Python syntax check passed for exported source tree.')
PY2
