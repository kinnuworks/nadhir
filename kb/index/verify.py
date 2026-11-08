"""Check that each quote in kb/sources.yaml appears verbatim in its source's indexed text.

Only sources indexed with full text (clause kind "text") are checked. Sources indexed
from quotes only are listed under quote_only. Writes kb/index/verify-report.json.
"""

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "kb"
OUT = KB / "index"

sys.path.insert(0, str(OUT))
from build import clean  # noqa: E402  same normalisation as the index

FOLD = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x2032: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"', 0x2033: '"',
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-", 0x2212: "-",
    0x00A0: " ", 0x202F: " ", 0x2007: " ",
}


def norm(text):
    text = clean(unicodedata.normalize("NFKC", text).translate(FOLD))
    text = re.sub(r"\s+([,.;:)\]!?])", r"\1", text)  # space before punctuation from markup
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.lower()


def main():
    import sys
    check = "--check" in sys.argv
    before = json.loads((OUT / "verify-report.json").read_text()) if (OUT / "verify-report.json").exists() else None
    sources = yaml.safe_load((KB / "sources.yaml").read_text())["sources"]
    by_doc = defaultdict(list)
    with open(OUT / "clauses.jsonl", encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            by_doc[c["doc"]].append(c)

    checked, found, not_found, quote_only = 0, 0, [], []
    for src in sources:
        clauses = by_doc.get(src["id"], [])
        if not any(c["kind"] == "text" for c in clauses):
            quote_only.append(src["id"])
            continue
        # consecutive clauses joined, so a quote spanning a clause break still matches
        texts = [norm(c["text"]) for c in clauses]
        windows = [texts[i] + " " + texts[i + 1] if i + 1 < len(texts) else texts[i]
                   for i in range(len(texts))]
        for q in src.get("quotes") or []:
            checked += 1
            nq = norm(q["text"])
            if any(nq in w for w in windows):
                found += 1
            else:
                not_found.append({"id": src["id"], "quote": q["text"], "locator": q.get("locator", "")})

    report = {"checked": checked, "found": found, "not_found": not_found, "quote_only": quote_only}
    (OUT / "verify-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(f"checked {checked}, found {found}, not found {len(not_found)}, quote-only sources {len(quote_only)}")
    for nf in not_found:
        print(f"  not found: {nf['id']}: {nf['quote'][:80]}")
    if check and before and {(x["id"], x["quote"]) for x in not_found} - {(x["id"], x["quote"]) for x in before["not_found"]}:
        print("new quotes failed the check")
        sys.exit(1)


if __name__ == "__main__":
    main()
