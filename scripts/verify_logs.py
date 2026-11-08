"""Verify the hash chain of every audit log in a folder. Exit 1 if any is broken."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nadhir.log import verify_file  # noqa: E402

bad = 0
files = sorted(Path(sys.argv[1]).glob("*.jsonl"))
for f in files:
    ok, why = verify_file(f)
    print(("ok   " if ok else "FAIL ") + f.name + ": " + why)
    bad += not ok
print(f"{len(files) - bad}/{len(files)} logs intact")
sys.exit(1 if bad or not files else 0)
