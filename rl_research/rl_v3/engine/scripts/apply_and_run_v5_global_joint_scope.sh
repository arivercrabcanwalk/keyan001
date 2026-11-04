#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rivermind-data/ca_rl_completion_v5_staging/code
cd "$ROOT"
PY=/opt/conda/bin/python
[ -f results/V5_RL_GLOBAL_TRANSFER_COMPLETE ] || {
  echo "global Joint scope experiment is gated on completion of the RL transfer diagnostic" >&2
  exit 10
}
[ ! -e results/V5_GLOBAL_JOINT_SCOPE_COMPLETE ] || {
  echo "global Joint scope experiment already has a completion marker" >&2
  exit 11
}
BACKUP=results/v5_global_joint_scope_source_before
if [ -d "$BACKUP" ]; then
  # An earlier audit already preserved the pre-global-Joint source. Never overwrite it.
  for f in search.py neighborhood.py runner.py source.sha256; do
    [ -f "$BACKUP/$f" ] || { echo "incomplete preserved source backup: $BACKUP/$f" >&2; exit 12; }
  done
else
  mkdir -p "$BACKUP"
  cp carl/search.py "$BACKUP/search.py"
  cp carl/neighborhood.py "$BACKUP/neighborhood.py"
  cp carl/runner.py "$BACKUP/runner.py"
  sha256sum carl/search.py carl/neighborhood.py carl/runner.py > "$BACKUP/source.sha256"
fi
"$PY" - <<'PY'
from pathlib import Path
p = Path("carl/neighborhood.py")
s = p.read_text()
old = """                repair_mask = sum(
                    1 << si for si, kind in enumerate(current_types) if kind)
                repair_drone_mask = 0"""
new = """                # Joint receiver scope must use post-move station types:
                # newly opened stations may receive targets; stations scheduled
                # to close must not remain in the receiver mask.
                repair_types = list(current_types)
                for si, kind in move.kinds:
                    repair_types[si] = kind
                repair_mask = sum(
                    1 << si for si, kind in enumerate(repair_types) if kind)
                repair_drone_mask = 0"""
if new not in s:
    if s.count(old) != 1:
        raise SystemExit(f"expected one original or patched receiver-mask block; found original={s.count(old)}, patched={s.count(new)}")
    p.write_text(s.replace(old, new))
else:
    print("post-move Joint receiver-mask patch already applied; preserving idempotently")
PY
diff -u "$BACKUP/neighborhood.py" carl/neighborhood.py > "$BACKUP/neighborhood_global_joint.patch.diff" || true
"$PY" -m py_compile carl/neighborhood.py carl/search.py carl/runner.py
echo "[JOINT_SCOPE] post-move receiver-mask patch applied; source backup preserved"

SMOKE=results/v5_global_joint_scope_smoke_postpatch_20261101
[ ! -e "$SMOKE" ] || { echo "smoke output already exists: $SMOKE" >&2; exit 13; }
METHODS=m1d,m1d_global_asg,m1d_global_joint,m1d_global_all,m2,m2_global_asg,m2_global_joint,m2_global_all
"$PY" -B scripts/run_bench.py --instances "$ROOT/external/LRPHSD/data/Instances_Alg/3_10_7.txt" --methods "$METHODS" \
  --seeds 101 --seconds 1 --workers 1 --out "$SMOKE"
"$PY" - "$SMOKE" <<'PY'
import glob,json,sys
from pathlib import Path
d=Path(sys.argv[1])
m=json.loads((d/"manifest.json").read_text())
rows=[json.load(open(p)) for p in glob.glob(str(d/"*__s*.json"))]
if m.get("finished") is None or m.get("errors") != 0 or m.get("tasks") != 8:
    raise SystemExit("Joint-scope smoke manifest failed")
if len(rows)!=8 or any(r.get("status")!="ok" or r.get("feasible") is not True for r in rows):
    raise SystemExit("Joint-scope smoke has invalid or infeasible outputs")
expected={
 "m1d":"local","m1d_global_asg":"global_assignment",
 "m1d_global_joint":"global_joint","m1d_global_all":"global_assignment_joint",
 "m2":"local","m2_global_asg":"global_assignment",
 "m2_global_joint":"global_joint","m2_global_all":"global_assignment_joint"}
for r in rows:
    if r.get("repair_scope_mode") != expected[r["method"]]:
        raise SystemExit("wrong repair scope metadata: "+r["method"])
hashes={(r.get("provenance") or {}).get("code_sha256") for r in rows}
if len(hashes)!=1 or None in hashes:
    raise SystemExit("smoke source hash mismatch")
print("JOINT_SCOPE_SMOKE_OK",len(rows),"all feasible","code_hash",next(iter(hashes)))
PY

bash scripts/run_v5_global_joint_scope.sh
