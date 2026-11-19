#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:?Supply copy directory}
test -d "$target"
cp "$base/ORIGINALS/compiler.py" "$target/MODIFIED_FILE.py"
printf '%s\n' 'ROLLBACK_BYTES_RESTORED'
