"""Search the organisers' UAE policy dataset for each gap. python -m kb.gap_search

For every gap in docs/gaps.md we run fixed queries over the UAE documents in the index
(ITU Sandbox_Training, Dataset/UAE) and keep the best hits with their scores. A gap claim says
"not found"; this file shows what the closest text actually says, so a reader can judge.
Writes kb/index/gap-search.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nadhir import retrieval  # noqa: E402

GAPS = {
    "G1": ["record AI involvement in public alert message", "approver name recorded in emergency alert",
           "common alerting protocol AI generated content label"],
    "G2": ["approval of AI generated public warning before broadcast", "human review before emergency alert sent",
           "two person approval emergency notification"],
    "G3": ["machine translation of emergency alerts", "automatic translation government messages Arabic English",
           "translated public warning accuracy review"],
    "G4": ["common alerting protocol feed publish warnings", "WMO register of alerting authorities",
           "early warning alerts open data feed"],
    "G5": ["correct false emergency alert", "erroneous public alert correction procedure",
           "after action report false alarm"],
    "G6": ["cell broadcast message length pages", "alert template character limit Arabic",
           "emergency message one page handset"],
    "G7": ["test alert status actual exercise", "public alert test message marking",
           "emergency alert drill test procedure"],
}


def main() -> int:
    out = {"collection": "itu-sandbox-uae", "documents": sum(1 for d in retrieval.index().docs.values()
                                                             if d.get("collection") == "itu-sandbox-uae"),
           "min_score": retrieval.MIN_SCORE, "gaps": {}}
    for gap, queries in GAPS.items():
        rows = []
        for q in queries:
            hits = retrieval.search(q, k=3, collections={"itu-sandbox-uae"})
            rows.append({"query": q, "hits": [{"id": h["id"], "title": h["title"], "locator": h["locator"],
                                               "score": h["score"], "text": h["text"][:300]} for h in hits]})
        out["gaps"][gap] = rows
        best = max((h["score"] for r in rows for h in r["hits"]), default=0)
        print(f"{gap}: best score {best}; " + "; ".join(f"{r['query']!r} -> {len(r['hits'])} hit(s)" for r in rows))
    p = Path(__file__).resolve().parent / "index" / "gap-search.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
