"""Run the gate over real IPAWS alerts from the audit snapshot (no network, no model).

Question: how often would the gate block a routine real alert? Only rules that need no issuer
context are counted: R0 schema, R2 status/text, R6 phone-text length (IPAWS CMAM parameters),
R10 corrections. R8 (provenance) is reported separately: it is the gap, not an error by the sender.

Usage: python -m audit.gate_on_real audit/snapshot/<date>
"""
import json
import sys
from collections import Counter
from pathlib import Path

from nadhir import gate

CONTENT = ["R0", "R2", "R6", "R10"]


def main(snap: str) -> None:
    root = Path(snap)
    alerts = []
    for page in sorted((root / "ipaws").glob("page-*.json*")):
        if page.suffix == ".gz":
            import gzip
            data = json.loads(gzip.decompress(page.read_bytes()))
        else:
            data = json.loads(page.read_text(encoding="utf-8"))
        alerts += [r["originalMessage"] for r in data["IpawsArchivedAlerts"] if r.get("originalMessage")]
    fails, examples, blocked, r8 = Counter(), {}, 0, Counter()
    for xml in alerts:
        env = gate.Envelope(cap_xml=xml, profile="US", ai={"involvement": "none", "machine_translated": []})
        verdicts = {v.rule: v for v in gate.check(env, "release")}
        hit = [r for r in CONTENT if verdicts[r].status == gate.FAIL]
        for r in hit:
            fails[r] += 1
            examples.setdefault(r, []).append(verdicts[r].detail[:200]) if len(examples.get(r, [])) < 5 else None
        blocked += bool(hit)
        r8[verdicts["R8"].status] += 1
    out = {"alerts": len(alerts), "blocked_on_content_rules": blocked, "by_rule": dict(fails),
           "examples": examples, "r8_status": dict(r8),
           "note": "R0/R2/R6/R10 only. R1, R3, R4, R5 need the issuer's console and are not run here."}
    Path("audit/gate-on-real.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "examples"}, indent=1))
    for r, ex in examples.items():
        print(r, ex[:3])


if __name__ == "__main__":
    main(sys.argv[1])
