#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:?Supply independent copy directory}
test -d "$target"
cp "$base/ORIGINALS/air2_before.py" "$target/MODIFIED_FILE.py"
printf '%s\n' 'ROLLBACK_BYTES_RESTORED'
