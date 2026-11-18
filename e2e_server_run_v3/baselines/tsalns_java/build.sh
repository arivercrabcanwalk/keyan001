#!/usr/bin/env bash
# Build the AUTHOR'S TSALNS (Liu et al., EJOR 2026) from the author's public code with our minimal patch
# (time budget -Dsecs, -Diters, battery reserve -Dreserve, makespan weight -Dlam, TRIP output; algorithm unchanged).
# v3: + tsalns_cov_v3.patch (CovExt: -Dcovfile hard emergency-coverage constraint, -Dfixtypes fixed siting).
# Needs: LRPHSD_DIR pointing at the author's repository (containing code/TSALNS/*.java) and a JDK (javac >= 11).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LRPHSD_DIR="${LRPHSD_DIR:-}"
for c in "$LRPHSD_DIR" "$HERE/../../../LRPHSD" "$HOME/LRPHSD" "/workspace/LRPHSD"; do
  if [ -n "$c" ] && [ -f "$c/code/TSALNS/Main.java" ]; then LRPHSD_DIR="$c"; break; fi
done
if [ -z "$LRPHSD_DIR" ] || [ ! -f "$LRPHSD_DIR/code/TSALNS/Main.java" ]; then
  echo "[tsalns] author code not found: set LRPHSD_DIR=/path/to/LRPHSD (repo with code/TSALNS)"; exit 3; fi
JAVAC="${JAVAC:-$(command -v javac || true)}"
[ -z "$JAVAC" ] && { echo "[tsalns] javac not found (apt install openjdk-17-jdk-headless)"; exit 4; }
rm -rf "$HERE/build"; mkdir -p "$HERE/build/src" "$HERE/build/classes"
cp "$LRPHSD_DIR"/code/TSALNS/*.java "$HERE/build/src/"
( cd "$HERE/build/src" && patch -p3 < "$HERE/tsalns_secs_reserve.patch" && patch -p1 < "$HERE/tsalns_cov_v3.patch" )
"$JAVAC" -encoding UTF-8 -d "$HERE/build/classes" "$HERE"/build/src/*.java
echo "[tsalns] built OK from $LRPHSD_DIR"
