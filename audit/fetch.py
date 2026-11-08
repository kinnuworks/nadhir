#!/usr/bin/env python3
"""Download a snapshot of public CAP alert data for the provenance audit.

Fetches:
  (a) the most recent IPAWS alerts from OpenFEMA (raw CAP XML is in each record),
  (b) the WMO Register of Alerting Authorities feed list,
  (c) the current items of the CAP feeds the register lists for the GCC states
      (SAU, KWT, QAT, BHR, OMN, ARE) plus Canada and Australia.

Everything is saved as received under audit/snapshot/<UTC date>/ with a
manifest.json (url, fetched_at, sha256, bytes). Standard library only.

Usage:
  python3 -I audit/fetch.py [--out DIR] [--ipaws N] [--delay SECONDS]
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "cap-provenance-audit/0.1"
IPAWS_URL = "https://www.fema.gov/api/open/v1/IpawsArchivedAlerts"
REGISTER_URL = "https://alertingauthority.wmo.int/rss.xml"
GCC = ["SAU", "KWT", "QAT", "BHR", "OMN", "ARE"]
EXTRA = ["CAN", "AUS"]
GZIP_THRESHOLD = 60 * 1024 * 1024  # IPAWS pages are gzipped above this total

NS_ISO = "http://www.itu.int/tML/tML-ISO-3166"
NS_RAA = "http://www.oid-info.com/get/2.49.0"
NS_ATOM = "http://www.w3.org/2005/Atom"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Fetcher:
    def __init__(self, root, delay):
        self.root = root
        self.delay = delay
        self.files = []
        self.errors = []
        self._last = 0.0

    def get(self, url, retries=2, timeout=60):
        """Return (status, body, content_type, error). Never raises."""
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        err = None
        for attempt in range(retries + 1):
            self._last = time.monotonic()
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, resp.read(), resp.headers.get("Content-Type", ""), None
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code}"
                if e.code < 500:
                    return e.code, b"", "", err
            except Exception as e:  # network errors, timeouts
                err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))
        return None, b"", "", err

    def save(self, rel_path, url, status, body, ctype, error, meta, gzip_it=False):
        entry = {
            "url": url,
            "path": rel_path,
            "fetched_at": now_utc(),
            "http_status": status,
            "content_type": ctype,
        }
        entry.update(meta)
        if error or status != 200:
            entry["error"] = error or f"HTTP {status}"
            entry["path"] = None
            entry["bytes"] = 0
            entry["sha256"] = None
            self.errors.append({"url": url, "error": entry["error"], "kind": meta.get("kind")})
            self.files.append(entry)
            print(f"  FAIL {url}: {entry['error']}", file=sys.stderr)
            return entry
        stored = body
        if gzip_it:
            entry["raw_bytes"] = len(body)
            entry["raw_sha256"] = hashlib.sha256(body).hexdigest()
            stored = gzip.compress(body, mtime=0)
            entry["path"] = rel_path = rel_path + ".gz"
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(stored)
        entry["bytes"] = len(stored)
        entry["sha256"] = hashlib.sha256(stored).hexdigest()
        self.files.append(entry)
        return entry


def fetch_ipaws(fx, total, page_size):
    print(f"IPAWS: fetching {total} most recent alerts", file=sys.stderr)
    pages = []
    skip = 0
    n = 0
    while skip < total:
        top = min(page_size, total - skip)
        query = urllib.parse.urlencode(
            {"$top": top, "$skip": skip, "$orderby": "sent desc"},
            safe="$", quote_via=urllib.parse.quote,
        )
        url = f"{IPAWS_URL}?{query}"
        status, body, ctype, err = fx.get(url, timeout=120)
        got = 0
        if status == 200 and not err:
            try:
                got = len(json.loads(body).get("IpawsArchivedAlerts", []))
            except ValueError as e:
                err = f"bad JSON: {e}"
        pages.append((n, url, status, body, ctype, err, got))
        print(f"  page {n}: skip={skip} got={got} {err or ''}", file=sys.stderr)
        if err or status != 200 or got == 0:
            break
        skip += top
        n += 1
    total_bytes = sum(len(p[3]) for p in pages)
    gz = total_bytes > GZIP_THRESHOLD
    for n, url, status, body, ctype, err, got in pages:
        fx.save(f"ipaws/page-{n:03d}.json", url, status, body, ctype, err,
                {"kind": "ipaws_page", "records": got}, gzip_it=gz)
    return gz


def parse_register(body):
    root = ET.fromstring(body)
    out = []
    for item in root.iter("item"):
        feeds = [
            {"lang": f.get(XML_LANG), "url": (f.text or "").strip()}
            for f in item.findall(f"{{{NS_RAA}}}capAlertFeed")
        ]
        out.append({
            "country": (item.findtext(f"{{{NS_ISO}}}countrycode") or "").strip(),
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "pubDate": (item.findtext("pubDate") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
            "feeds": [f for f in feeds if f["url"]],
        })
    return out


def feed_item_links(body):
    """Links to CAP documents in an RSS 2.0 or Atom feed, in feed order."""
    root = ET.fromstring(body)
    links = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        if link:
            links.append(link)
    for entry in root.iter(f"{{{NS_ATOM}}}entry"):
        chosen = None
        for ln in entry.findall(f"{{{NS_ATOM}}}link"):
            href = ln.get("href", "").strip()
            if href and ln.get("rel", "alternate") == "alternate":
                chosen = href
                break
        if chosen:
            links.append(chosen)
    seen, uniq = set(), []
    for link in links:
        if link not in seen:
            seen.add(link)
            uniq.append(link)
    return uniq


def slug(url):
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:80]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="snapshot directory (default audit/snapshot/<UTC date>)")
    ap.add_argument("--ipaws", type=int, default=1000, help="number of IPAWS alerts")
    ap.add_argument("--page-size", type=int, default=250)
    ap.add_argument("--delay", type=float, default=0.3, help="seconds between requests")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    started = now_utc()
    out = args.out or os.path.join(here, "snapshot", started[:10])
    if os.path.exists(os.path.join(out, "manifest.json")):
        sys.exit(f"{out} already holds a snapshot; pass --out to write elsewhere")
    os.makedirs(out, exist_ok=True)
    fx = Fetcher(out, args.delay)

    gz = fetch_ipaws(fx, args.ipaws, args.page_size)

    print("WMO register", file=sys.stderr)
    status, body, ctype, err = fx.get(REGISTER_URL)
    fx.save("wmo/register-rss.xml", REGISTER_URL, status, body, ctype, err,
            {"kind": "wmo_register"})
    sources = []
    if status == 200 and not err:
        register = parse_register(body)
        wanted = [r for r in register if r["country"] in GCC + EXTRA]
        # The UAE record page itself, for a human to check against the RSS entry.
        for r in wanted:
            if r["country"] == "ARE" and r["link"]:
                s2, b2, c2, e2 = fx.get(r["link"])
                fx.save(f"wmo/record-{slug(r['link'])}.html", r["link"], s2, b2, c2, e2,
                        {"kind": "wmo_record", "country": "ARE"})
        # One source per distinct feed URL; several register entries can share one.
        by_url = {}
        for r in wanted:
            for f in r["feeds"]:
                src = by_url.setdefault(f["url"], {
                    "source_id": f"{r['country']}:{slug(f['url'])}",
                    "country": r["country"],
                    "feed_url": f["url"],
                    "authorities": [],
                    "langs": [],
                })
                if r["title"] not in src["authorities"]:
                    src["authorities"].append(r["title"])
                if f["lang"] and f["lang"] not in src["langs"]:
                    src["langs"].append(f["lang"])
        sources = list(by_url.values())

    for src in sources:
        print(f"Feed {src['source_id']}", file=sys.stderr)
        base = f"feeds/{src['source_id'].replace(':', '_')}"
        status, body, ctype, err = fx.get(src["feed_url"])
        entry = fx.save(f"{base}/feed.xml", src["feed_url"], status, body, ctype, err,
                        {"kind": "feed", "source_id": src["source_id"]})
        src["feed_ok"] = entry.get("error") is None
        links = []
        if src["feed_ok"]:
            try:
                links = feed_item_links(body)
            except ET.ParseError as e:
                src["feed_parse_error"] = str(e)
        src["items_listed"] = len(links)
        print(f"  {len(links)} items", file=sys.stderr)
        for i, link in enumerate(links):
            s2, b2, c2, e2 = fx.get(link)
            fx.save(f"{base}/items/{i:04d}.xml", link, s2, b2, c2, e2,
                    {"kind": "cap_item", "source_id": src["source_id"]})

    manifest = {
        "tool": "cap-provenance-audit fetch.py 0.1",
        "user_agent": USER_AGENT,
        "started_at": started,
        "finished_at": now_utc(),
        "ipaws_requested": args.ipaws,
        "ipaws_gzipped": gz,
        "sources": sources,
        "errors": fx.errors,
        "files": fx.files,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"Saved {len(fx.files)} files to {out}; {len(fx.errors)} failures", file=sys.stderr)


if __name__ == "__main__":
    main()
