#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
target=${1:?Supply an independent source-proof copy}
test "$target" != "$base"
test -f "$target/.ROLLBACK_PROOF_ONLY"
test -d "$target/MODIFIED_FILE"
rm -rf "$target/MODIFIED_FILE"
cp -R "$base/ORIGINALS/production" "$target/MODIFIED_FILE"
printf '%s\n' 'ORIGINAL_PRODUCTION_SOURCE_RESTORED; SCIENTIFIC_DRIVER_ABSENT'
