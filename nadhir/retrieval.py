"""Clause-level search over the knowledge base (kb/index/clauses.jsonl).

Plain BM25, no model and no network: the same query always returns the same clauses, so every
agent's evidence can be replayed. Arabic is normalised (diacritics and letter variants) before
indexing so Arabic and English clauses are searched the same way.

`quote_in` is the check the orchestrator runs on every citation an agent makes: the quoted words
must appear, word for word, in the clause the agent says they come from.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "kb" / "index" / "clauses.jsonl"
DOCS = ROOT / "kb" / "index" / "documents.json"

K1, B = 1.4, 0.75
# A hit must match at least this many distinct query words and reach this score; below that it is
# noise and the agent is told nothing relevant was found (a "no basis" result).
MIN_SCORE = 8.0
MIN_TERMS = 2

STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were will with
which who whom what when where how not no all any can may must shall should would could than then there these
those their they them our we you your he she his her its into also such other more most only same so very""".split())
STOP |= {"في", "من", "على", "إلى", "الى", "عن", "أن", "ان", "التي", "الذي", "هذا", "هذه", "ذلك", "مع", "أو", "او", "و"}

_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_TOKEN = re.compile(r"[a-z0-9]+|[ء-ي]+")


def normalise(text: str) -> str:
    """Folding used for both searching and quote checks."""
    t = text.lower()
    t = _AR_DIACRITICS.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = (t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("–", "-").replace("—", "-").replace(" ", " "))
    return " ".join(t.split())


def _stem(w: str) -> str:
    if w.isascii():
        for suf in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf):
                return w[: -len(suf)]
        return w
    if w.startswith("ال") and len(w) > 4:
        w = w[2:]
    return w


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in _TOKEN.findall(normalise(text)) if w not in STOP and len(w) > 1]


class Index:
    def __init__(self, clauses: list[dict], documents: dict[str, dict]):
        self.clauses = clauses
        self.by_id = {c["id"]: c for c in clauses}
        self.docs = documents
        self.tf = []
        df = Counter()
        for c in clauses:
            tf = Counter(tokens(c["text"] + " " + (documents.get(c["doc"], {}).get("title") or "")))
            self.tf.append(tf)
            df.update(tf.keys())
        n = len(clauses) or 1
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.lens = [sum(tf.values()) for tf in self.tf]
        self.avg = (sum(self.lens) / n) if clauses else 1.0
        self.post = defaultdict(list)
        for k, tf in enumerate(self.tf):
            for t in tf:
                self.post[t].append(k)

    def search(self, query: str, k: int = 5, collections: set[str] | None = None,
               exclude_docs: set[str] | None = None, only_docs: set[str] | None = None) -> list[dict]:
        q = Counter(tokens(query))
        scores: dict[int, float] = defaultdict(float)
        matched: dict[int, int] = defaultdict(int)
        for t in q:
            idf = self.idf.get(t)
            if not idf:
                continue
            for d in self.post[t]:
                f = self.tf[d][t]
                scores[d] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.lens[d] / self.avg))
                matched[d] += 1
        hits = []
        for d, s in sorted(scores.items(), key=lambda x: (-x[1], x[0])):
            c = self.clauses[d]
            doc = self.docs.get(c["doc"], {})
            if collections and doc.get("collection") not in collections:
                continue
            if exclude_docs and c["doc"] in exclude_docs:
                continue
            if only_docs is not None and c["doc"] not in only_docs:
                continue
            if matched[d] < min(MIN_TERMS, len(q)) or s < MIN_SCORE:
                continue
            hits.append({"id": c["id"], "doc": c["doc"], "title": doc.get("title"), "publisher": doc.get("publisher"),
                         "url": doc.get("url"), "status": doc.get("status"), "collection": doc.get("collection"),
                         "locator": c.get("locator"), "lang": c.get("lang"), "text": c["text"],
                         "score": round(s, 2), "matched_terms": matched[d]})
            if len(hits) >= k:
                break
        return hits


@lru_cache(maxsize=1)
def index() -> Index:
    clauses = []
    if INDEX.exists():
        with INDEX.open(encoding="utf-8") as f:
            clauses = [json.loads(line) for line in f if line.strip()]
    docs = {}
    if DOCS.exists():
        docs = {d["id"]: d for d in json.loads(DOCS.read_text(encoding="utf-8"))}
    return Index(clauses, docs)


@lru_cache(maxsize=1)
def uae_docs() -> frozenset:
    """Documents that are UAE texts: the organisers' UAE dataset plus our sources with a UAE jurisdiction."""
    import yaml
    ids = {d for d, meta in index().docs.items() if meta.get("collection") == "itu-sandbox-uae"}
    src = ROOT / "kb" / "sources.yaml"
    if src.exists():
        for x in (yaml.safe_load(src.read_text(encoding="utf-8")) or {}).get("sources", []):
            if str(x.get("jurisdiction", "")).startswith("AE"):
                ids.add(x["id"])
    return frozenset(ids)


def search_local_first(query: str, k: int = 3, k_local: int = 2) -> list[dict]:
    """Top hits from UAE texts, then the top hits overall: a UAE reviewer reads UAE rules first."""
    local = index().search(query, k_local, only_docs=set(uae_docs()))
    seen = {h["id"] for h in local}
    return local + [h for h in index().search(query, k + k_local) if h["id"] not in seen][:k]


def search(query: str, k: int = 5, **kw) -> list[dict]:
    return index().search(query, k, **kw)


def clause(cid: str) -> dict | None:
    return index().by_id.get(cid)


def quote_in(quote: str, text: str, min_words: int = 5) -> bool:
    """True when `quote` (at least `min_words` words) appears word for word in `text`."""
    q = normalise(quote).strip(" .\"'")
    return len(q.split()) >= min_words and q in normalise(text)


def stats() -> dict:
    ix = index()
    by = Counter(ix.docs.get(c["doc"], {}).get("collection", "?") for c in ix.clauses)
    return {"clauses": len(ix.clauses), "documents": len(ix.docs), "by_collection": dict(by)}
