#!/usr/bin/env bash
# Build the AUTHOR'S TSALNS (Liu et al., EJOR 2026) from the author's public code + our minimal patch tsalns_v6.patch:
#   -Dsecs (wall budget), -Diters, -Dreserve (battery reserve), -Dlam (makespan weight, 0 = author), TRIP output   [e2e_v2]
#   -Dcov=<file>  WX-E6: Omega points added to the author's own location-feasibility test + author-style greedy init
# Without -Dcov/-Dreserve/-Dlam the search is the author's algorithm unchanged.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LRPHSD_DIR="${LRPHSD_DIR:-}"
for c in "$LRPHSD_DIR" "$HERE/../../third_party/LRPHSD" "$HERE/../../../LRPHSD" "$HOME/LRPHSD" "/workspace/LRPHSD"; do
  if [ -n "$c" ] && [ -f "$c/code/TSALNS/Main.java" ]; then LRPHSD_DIR="$c"; break; fi
done
if [ -z "$LRPHSD_DIR" ] || [ ! -f "$LRPHSD_DIR/code/TSALNS/Main.java" ]; then
  echo "[tsalns] author code not found: set LRPHSD_DIR=/path/to/LRPHSD (repo with code/TSALNS)"; exit 3; fi
JAVAC="${JAVAC:-$(command -v javac || true)}"
[ -z "$JAVAC" ] && { echo "[tsalns] javac not found (sudo apt install -y openjdk-17-jdk-headless)"; exit 4; }
rm -rf "$HERE/build"; mkdir -p "$HERE/build/src" "$HERE/build/classes"
cp "$LRPHSD_DIR"/code/TSALNS/*.java "$HERE/build/src/"
( cd "$HERE/build/src" && patch -p1 < "$HERE/tsalns_v6.patch" )
"$JAVAC" -encoding UTF-8 -d "$HERE/build/classes" "$HERE"/build/src/*.java
echo "[tsalns] built OK from $LRPHSD_DIR"
