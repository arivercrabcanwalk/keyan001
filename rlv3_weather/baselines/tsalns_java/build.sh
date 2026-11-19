#!/usr/bin/env bash
# Build the AUTHOR'S TSALNS (Liu et al., EJOR 2026; public code) - sources in author_src_patched/ are the author's
# code/TSALNS/*.java with the minimal I/O patch (tsalns_secs_reserve.patch: -Dsecs time budget, -Diters, TRIP output;
# search algorithm unchanged).  Optional: LRPHSD_DIR=/path/to/LRPHSD rebuilds from the author's repository + patch.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
JAVAC="${JAVAC:-$(command -v javac || true)}"
[ -z "$JAVAC" ] && { echo "[tsalns] javac not found (apt install openjdk-17-jdk-headless)"; exit 4; }
SRC="$HERE/author_src_patched"
if [ -n "${LRPHSD_DIR:-}" ] && [ -f "$LRPHSD_DIR/code/TSALNS/Main.java" ]; then
  rm -rf "$HERE/build/src"; mkdir -p "$HERE/build/src"; cp "$LRPHSD_DIR"/code/TSALNS/*.java "$HERE/build/src/"
  ( cd "$HERE/build/src" && patch -p3 < "$HERE/tsalns_secs_reserve.patch" ); SRC="$HERE/build/src"
fi
rm -rf "$HERE/build/classes"; mkdir -p "$HERE/build/classes"
"$JAVAC" -encoding UTF-8 -nowarn -d "$HERE/build/classes" "$SRC"/*.java
echo "[tsalns] built OK from $SRC"
