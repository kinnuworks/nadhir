import json

from nadhir.log import AuditLog, verify, verify_file


def test_chain_verifies_and_detects_edits(tmp_path):
    p = tmp_path / "run.jsonl"
    log = AuditLog(p)
    for n in range(4):
        log.append("gate", "review", {"n": n}, "2026-11-09T10:00:00+04:00")
    assert verify_file(p)[0]
    recs = [json.loads(x) for x in p.read_text().splitlines()]
    recs[2]["payload"]["n"] = 99
    ok, why = verify(recs)
    assert not ok and "record 2" in why


def test_deleted_record_breaks_chain():
    log = AuditLog()
    for n in range(3):
        log.append("a", "b", {"n": n}, "t")
    recs = log.records[:1] + log.records[2:]
    assert not verify(recs)[0]
