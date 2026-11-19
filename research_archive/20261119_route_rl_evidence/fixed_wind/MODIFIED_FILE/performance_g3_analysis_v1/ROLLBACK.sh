#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:?Supply independent source-and-state proof copy}
test "$target" != "$base"
test -f "$target/.ROLLBACK_PROOF_ONLY"
test -d "$target/MODIFIED_FILE"
rm -rf "$target/MODIFIED_FILE"
mkdir "$target/MODIFIED_FILE"
cp "$base/ORIGINALS/STATE.json" "$target/STATE.json"
printf '%s\n' 'PRE_ANALYSIS_PENDING_STATE_AND_ABSENT_AGGREGATOR_RESTORED'
