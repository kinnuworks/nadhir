"""Append-only, hash-chained audit log (JSON Lines). Any edit breaks the chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _digest(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.records: list[dict] = []
        if self.path and self.path.exists():
            self.records = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]

    @property
    def head(self) -> str:
        return self.records[-1]["hash"] if self.records else GENESIS

    def append(self, actor: str, action: str, payload: dict, at: str) -> dict:
        rec = {"seq": len(self.records), "at": at, "actor": actor, "action": action,
               "payload": payload, "prev": self.head}
        rec["hash"] = _digest(rec)
        self.records.append(rec)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return rec


def verify(records: list[dict]) -> tuple[bool, str]:
    prev = GENESIS
    for i, rec in enumerate(records):
        if rec.get("seq") != i:
            return False, f"record {i}: sequence number is {rec.get('seq')}"
        if rec.get("prev") != prev:
            return False, f"record {i}: previous-hash link broken"
        if _digest(rec) != rec.get("hash"):
            return False, f"record {i}: content does not match its hash"
        prev = rec["hash"]
    return True, f"{len(records)} records, chain intact, head {prev[:12]}"


def verify_file(path: Path) -> tuple[bool, str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return verify([json.loads(x) for x in lines if x.strip()])
