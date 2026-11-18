#!/usr/bin/env bash
# Commit the packed results back to the repository (uses the git credentials already configured on this machine;
# never writes tokens anywhere). Target: <repo>/wx6_server_run/results_server/
set -euo pipefail
cd "$(dirname "$0")/.."
DST=results_server; mkdir -p $DST
cp -f results_out.tar.gz results_out.sha256 $DST/
cp -rf results_final/SUMMARY_ZH.md results_final/ANALYSIS_V6.json results_final/raw_compact.csv.gz results_final/*.json PROGRESS_SERVER.md $DST/ 2>/dev/null || true
cp -rf results_final/models $DST/ 2>/dev/null || true
git add $DST
git commit -m "wx6_server_run: official results ($(date -u +%Y-%m-%dT%H:%MZ))" >> logs/push.log 2>&1 || true
for i in 1 2 3; do git pull --rebase >> logs/push.log 2>&1 && git push >> logs/push.log 2>&1 && exit 0; sleep 5; done
exit 1
