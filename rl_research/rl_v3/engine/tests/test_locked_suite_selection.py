import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_bench import select_instances


def test_locked_suite_uses_manifest_and_verifies_hashes():
    manifest = json.loads((ROOT / "datasets" / "locked_v2" / "manifest.json").read_text())
    paths = select_instances("locked_v2")
    assert len(paths) == 60
    assert [Path(p).stem for p in paths] == [row["name"] for row in manifest["rows"]]
    for path, row in zip(paths, manifest["rows"]):
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == row["sha256"]
        assert not Path(path).name.startswith("._")


if __name__ == "__main__":
    test_locked_suite_uses_manifest_and_verifies_hashes()
    print("PASS locked_suite_selection")
