#!/usr/bin/env bash
set -eu
TARGET="${1:-MODIFIED_FILE}"
BASELINE="${2:-ORIGINAL_COPY}"
if [ ! -f "$BASELINE" ]; then
  printf 'baseline_missing=%s\n' "$BASELINE" >&2
  exit 2
fi
cp "$BASELINE" "$TARGET"
printf 'restored=%s\n' "$TARGET"
