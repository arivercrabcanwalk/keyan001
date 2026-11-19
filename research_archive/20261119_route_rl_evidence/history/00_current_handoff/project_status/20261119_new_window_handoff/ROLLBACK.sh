#!/bin/sh
# Restore the archived handoff ONLY in a separately marked disposable copy.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
old="$here/../20261112_new_window_handoff/NEW_WINDOW_TAKEOVER_PROMPT.md"
target=$(CDPATH= cd -- "${1:?supply a separate marked proof directory}" && pwd -P)
test "$target" != "$here"
test "$target" != "$(CDPATH= cd -- "$(dirname -- "$old")" && pwd -P)"
test -f "$target/.handoff-proof-copy"
test ! -L "$target/.handoff-proof-copy"
test -f "$target/NEW_WINDOW_TAKEOVER_PROMPT.md"
test ! -L "$target/NEW_WINDOW_TAKEOVER_PROMPT.md"
test "$(/usr/bin/shasum -a 256 "$old" | cut -d ' ' -f 1)" = "3c21ad6e8869b92f3ee441925651167e43d8daaac8f4c9e615044a6faeb6c19f"
tmp=$(mktemp "$target/.restored.XXXXXX")
trap 'rm -f "$tmp"' EXIT HUP INT TERM
cp "$old" "$tmp"
mv -f "$tmp" "$target/NEW_WINDOW_TAKEOVER_PROMPT.md"
cmp -s "$old" "$target/NEW_WINDOW_TAKEOVER_PROMPT.md"
printf '%s\n' 'ORIGINAL_20261112_HANDOFF_RESTORED_ON_PROOF_COPY'
