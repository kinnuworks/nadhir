"""Load the knowledge base registry (kb/sources.yaml) and look up cited quotes."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "kb" / "sources.yaml"


@lru_cache(maxsize=1)
def sources() -> dict[str, dict]:
    if not KB_PATH.exists():
        return {}
    data = yaml.safe_load(KB_PATH.read_text(encoding="utf-8")) or []
    if isinstance(data, dict):
        data = data.get("sources", [])
    return {s["id"]: s for s in data if isinstance(s, dict) and "id" in s}


def cite(source_id: str) -> dict:
    """Short citation for the UI and logs: title, url, status and the first quote."""
    s = sources().get(source_id)
    if not s:
        return {"id": source_id, "title": None, "url": None, "status": "missing", "quote": None}
    quotes = s.get("quotes") or []
    q = quotes[0] if quotes else None
    return {
        "id": source_id,
        "title": s.get("title"),
        "publisher": s.get("publisher"),
        "url": s.get("url"),
        "status": s.get("status"),
        "quote": q.get("text") if isinstance(q, dict) else q,
        "locator": q.get("locator") if isinstance(q, dict) else None,
    }
