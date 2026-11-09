"""Check a public CAP feed now: fetch its latest alerts and run the rules that need no issuer context.

Only the feeds below can be fetched (WMO-registered national feeds that were live on 8 Nov 2026), and
only from the hosts listed for each, so the server never fetches an address a visitor types.
No model is called: this is the deterministic gate only, and it answers in seconds.
"""
from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import cap, gate

FEEDS = {
    "sau-en": ("Saudi Arabia, National Center for Meteorology (English)", "https://ncm.gov.sa/en/cap-alerts", {"www.ncm.gov.sa", "ncm.gov.sa"}),
    "sau-ar": ("Saudi Arabia, National Center for Meteorology (Arabic)", "https://ncm.gov.sa/ar/cap-alerts", {"www.ncm.gov.sa", "ncm.gov.sa"}),
    "qat-en": ("Qatar, Civil Aviation Authority met service (English)", "https://cap-sources.s3.amazonaws.com/qa-caa-en/rss.xml", {"cap-sources.s3.amazonaws.com"}),
    "qat-ar": ("Qatar, Civil Aviation Authority met service (Arabic)", "https://cap-sources.s3.amazonaws.com/qa-caa-ar/rss.xml", {"cap-sources.s3.amazonaws.com"}),
    "kwt-en": ("Kuwait, Meteorological Department", "https://www.met.gov.kw/rss_eng/kuwait_cap.xml", {"www.met.gov.kw"}),
    "can": ("Canada, NAAD public alerts", "http://rss.naad-adna.pelmorex.com/", {"capcp2.naad-adna.pelmorex.com"}),
    "aus": ("Australia, Bureau of Meteorology (via WMO)", "https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/rss.xml", {"severeweather.wmo.int"}),
}
NS_ATOM = "{http://www.w3.org/2005/Atom}"
UA = "Mozilla/5.0 (public CAP feed check)"
MAX_ITEMS = 12
CONTEXT_FREE = ["R0", "R2", "R6", "R10"]  # rules that need nothing from the issuer's console


def _get(url: str, timeout: float = 8) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_000)


def _links(body: bytes) -> list[str]:
    root = ET.fromstring(body)
    out = [(i.findtext("link") or "").strip() for i in root.iter("item")]
    for e in root.iter(NS_ATOM + "entry"):
        for ln in e.findall(NS_ATOM + "link"):
            if ln.get("href") and ln.get("rel", "alternate") == "alternate":
                out.append(ln.get("href").strip())
                break
    seen, uniq = set(), []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _check_one(xml: str) -> dict:
    env = gate.Envelope(cap_xml=xml, profile="GENERIC", ai={"involvement": "none", "machine_translated": []})
    vs = {v.rule: v for v in gate.check(env, "release")}
    try:
        a = cap.parse(xml)
    except Exception:
        a = {}
    info = (a.get("info") or [{}])[0]
    params = {n for i in a.get("info", []) for n, _ in i.get("parameters", [])}
    # R6 is a note here, not a hold: many feed alerts are not meant to go to phones as written
    failed = [r for r in CONTEXT_FREE if r != "R6" and r in vs and vs[r].status == gate.FAIL]
    return {"identifier": a.get("identifier"), "sender": a.get("sender"), "sent": a.get("sent"),
            "status": a.get("status"), "msgType": a.get("msgType"), "event": info.get("event"),
            "severity": info.get("severity"), "headline": info.get("headline"),
            "languages": sorted({(i.get("language") or "en").split("-")[0] for i in a.get("info", [])}),
            "signed": bool(a.get("signed")),
            "records_ai_or_approver": any(p.startswith(gate.P) for p in params),
            "failed": failed,
            "too_long_for_cell_broadcast": bool(vs.get("R6") and vs["R6"].status == gate.FAIL),
            "verdicts": [{"rule": r, "status": vs[r].status, "detail": vs[r].detail, "title": vs[r].title}
                         for r in CONTEXT_FREE if r in vs]}


def check_feed(feed_id: str) -> dict:
    if feed_id not in FEEDS:
        raise ValueError("unknown feed")
    name, url, hosts = FEEDS[feed_id]
    try:
        links = _links(_get(url))
    except Exception as e:  # network or parse error: report it, don't crash
        return {"feed": name, "url": url, "error": f"could not read the feed ({type(e).__name__})"}
    links = [x for x in links if urlparse(x).netloc in hosts][:MAX_ITEMS]

    def one(link):
        try:
            return {"link": link, **_check_one(_get(link).decode("utf-8", "replace"))}
        except Exception as e:
            return {"link": link, "error": type(e).__name__}

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(one, links))
    ok = [r for r in rows if "error" not in r]
    return {"feed": name, "url": url, "checked": len(ok), "unreadable": len(rows) - len(ok),
            "held": sum(1 for r in ok if r["failed"]),
            "with_ai_or_approver_record": sum(1 for r in ok if r["records_ai_or_approver"]),
            "signed": sum(1 for r in ok if r["signed"]), "alerts": rows,
            "too_long_for_cell_broadcast": sum(1 for r in ok if r["too_long_for_cell_broadcast"]),
            "rules": CONTEXT_FREE,
            "note": "Only the rules that need no issuer context run here: schema (R0), status (R2) and corrections "
                    "(R10) can hold an alert; phone-text length (R6) is a note, since many feed alerts are not sent "
                    "to phones as written. Area, sender authority, approvals and keys need the issuer's own console."}
