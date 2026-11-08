#!/usr/bin/env python3
"""Count provenance-related fields in a CAP snapshot made by fetch.py.

Reads a snapshot directory (no network) and writes results.json and
results.md. Standard library only.

Usage:
  python3 -I audit/count.py audit/snapshot/<date> [--out DIR]
"""

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
NS_ISO = "http://www.itu.int/tML/tML-ISO-3166"
NS_RAA = "http://www.oid-info.com/get/2.49.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
GCC = ["SAU", "KWT", "QAT", "BHR", "OMN", "ARE"]
EXTRA = ["CAN", "AUS"]
TEST_STATUSES = {"Test", "Exercise"}
# SAME event codes for scheduled tests and demos; IPAWS sends them with status Actual.
SAME_TEST_EVENTS = {"RMT", "RWT", "NPT", "DMO"}

# Short tokens are matched as whole tokens so "ai" does not hit "rain" or "Maine".
AI_PATTERNS = [
    ("ai", re.compile(r"(?<![a-z0-9])ai(?![a-z])", re.I)),
    ("artificial", re.compile(r"artificial", re.I)),
    ("machine", re.compile(r"machine", re.I)),
    ("auto-translat", re.compile(r"auto[-_ ]?translat", re.I)),
    ("generated", re.compile(r"generated", re.I)),
    ("llm", re.compile(r"(?<![a-z0-9])llm(?![a-z])", re.I)),
    ("gpt", re.compile(r"(?<![a-z0-9])gpt(?![a-z])", re.I)),
]
APPROVER_PATTERNS = [
    ("approv", re.compile(r"approv", re.I)),
    ("authoriz/authoris", re.compile(r"authori[sz]", re.I)),
    ("username", re.compile(r"user[-_ ]?name", re.I)),
    ("operator", re.compile(r"operator", re.I)),
]

METRICS = [
    ("with_source", "has <source>"),
    ("with_note", "non-empty <note>"),
    ("with_signature", "XML Signature"),
    ("multi_language", ">1 <info> language"),
    ("with_instruction", "<instruction>"),
    ("with_parameter", "any <parameter>"),
    ("ai_marker", "AI/machine marker"),
    ("approver_marker", "approver marker"),
]


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def ns(tag):
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def text(el):
    return (el.text or "").strip() if el is not None else ""


def child(el, name):
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def children(el, name):
    return [c for c in el if local(c.tag) == name]


def pairs(el, name):
    out = []
    for p in children(el, name):
        out.append((text(child(p, "valueName")), text(child(p, "value"))))
    return out


def find_alert(root):
    if local(root.tag) == "alert":
        return root
    for el in root.iter():
        if local(el.tag) == "alert":
            return el
    return None


def parse_cap(data):
    """Return a dict of the fields we count, or None if not a CAP alert."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    alert = find_alert(root)
    if alert is None:
        return None
    infos = children(alert, "info")
    langs = set()
    params, other_pairs = [], []
    has_instruction = False
    same_events = set()
    for info in infos:
        langs.add(text(child(info, "language")) or "en-US")  # CAP default
        if text(child(info, "instruction")):
            has_instruction = True
        params += pairs(info, "parameter")
        ev = pairs(info, "eventCode")
        other_pairs += [("eventCode", n, v) for n, v in ev]
        same_events |= {v for n, v in ev if n == "SAME"}
        for area in children(info, "area"):
            other_pairs += [("geocode", n, v) for n, v in pairs(area, "geocode")]
    signed = any(local(el.tag) == "Signature" and ns(el.tag) == NS_DSIG for el in root.iter())
    source_el = child(alert, "source")
    return {
        "identifier": text(child(alert, "identifier")),
        "sender": text(child(alert, "sender")),
        "sent": text(child(alert, "sent")),
        "status": text(child(alert, "status")),
        "msgType": text(child(alert, "msgType")),
        "source": text(source_el),
        "has_source": source_el is not None and bool(text(source_el)),
        "note": text(child(alert, "note")),
        "codes": [text(c) for c in children(alert, "code")],
        "signed": signed,
        "languages": sorted(langs),
        "has_instruction": has_instruction,
        "parameters": params,
        "other_pairs": other_pairs,
        "same_events": sorted(same_events),
    }


def search(alert):
    """Return (ai_hits, approver_hits): lists of (field, raw text, pattern)."""
    ai_fields = [("source", alert["source"]), ("note", alert["note"])]
    ai_fields += [("code", c) for c in alert["codes"]]
    # For a pair, the reported text is "valueName = value" so a reviewer sees both halves.
    pair_fields = []
    all_pairs = [("parameter", n, v) for n, v in alert["parameters"]] + alert["other_pairs"]
    for kind, n, v in all_pairs:
        shown = f"{n} = {v}"
        pair_fields += [(f"{kind}.valueName", n, shown), (f"{kind}.value", v, shown)]
    ai_fields = [(f, v, v) for f, v in ai_fields] + pair_fields

    def hits(fields, patterns):
        out = []
        for field, value, shown in fields:
            if not value:
                continue
            for label, rx in patterns:
                if rx.search(value):
                    out.append((field, shown, label))
        return out

    return hits(ai_fields, AI_PATTERNS), hits(pair_fields, APPROVER_PATTERNS)


def new_group():
    g = {"alerts": 0}
    for key, _ in METRICS:
        g[key] = 0
    return g


def summarise(alerts):
    """Counters for one source; test/exercise messages kept in their own group."""
    groups = {"live": new_group(), "test_exercise": new_group()}
    status_counts = collections.Counter()
    param_names = collections.Counter()
    source_values = collections.Counter()
    ai_raw, appr_raw = collections.Counter(), collections.Counter()
    live_same_test = 0
    seen = set()
    duplicates = 0
    for a in alerts:
        key = (a["sender"], a["identifier"], a["sent"])
        if a["identifier"] and key in seen:
            duplicates += 1
            continue
        seen.add(key)
        status_counts[a["status"] or "(none)"] += 1
        is_test = a["status"] in TEST_STATUSES
        g = groups["test_exercise" if is_test else "live"]
        ai_hits, appr_hits = search(a)
        g["alerts"] += 1
        g["with_source"] += a["has_source"]
        g["with_note"] += bool(a["note"])
        g["with_signature"] += a["signed"]
        g["multi_language"] += len(a["languages"]) > 1
        g["with_instruction"] += a["has_instruction"]
        g["with_parameter"] += bool(a["parameters"])
        g["ai_marker"] += bool(ai_hits)
        g["approver_marker"] += bool(appr_hits)
        if not is_test and SAME_TEST_EVENTS & set(a["same_events"]):
            live_same_test += 1
        for name in {n for n, _ in a["parameters"]}:
            param_names[name] += 1
        if a["source"]:
            source_values[a["source"]] += 1
        grp = "test_exercise" if is_test else "live"
        for field, value, label in set(ai_hits):
            ai_raw[(grp, field, value, label)] += 1
        for field, value, label in set(appr_hits):
            appr_raw[(grp, field, value, label)] += 1

    def raw_list(counter):
        return [
            {"group": g, "field": f, "value": v, "pattern": p, "alerts": n}
            for (g, f, v, p), n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    return {
        "groups": groups,
        "status_counts": dict(status_counts),
        "duplicates_skipped": duplicates,
        "live_with_same_test_event": live_same_test,
        "parameter_valueNames": dict(param_names.most_common()),
        "distinct_source_values": len(source_values),
        "top_source_values": dict(source_values.most_common(10)),
        "ai_marker_values": raw_list(ai_raw),
        "approver_marker_values": raw_list(appr_raw),
    }


def read_file(snap, entry):
    with open(os.path.join(snap, entry["path"]), "rb") as f:
        data = f.read()
    ok = hashlib.sha256(data).hexdigest() == entry.get("sha256")
    if entry["path"].endswith(".gz"):
        data = gzip.decompress(data)
    return data, ok


def parse_register(data):
    root = ET.fromstring(data)
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
            "feeds": [f for f in feeds if f["url"]],
        })
    return out


def feed_dates(data):
    """lastBuildDate / pubDate / updated of an RSS or Atom feed, if present."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return {}
    out = {}
    for el in root.iter():
        name = local(el.tag)
        if name in ("lastBuildDate", "pubDate", "updated") and name not in out:
            out[name] = text(el)
        if name in ("item", "entry"):
            break
    return out


def analyse(snap):
    with open(os.path.join(snap, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    files = manifest["files"]
    hash_mismatch = []
    results = {
        "snapshot": os.path.basename(os.path.normpath(snap)),
        "fetched": {"started_at": manifest.get("started_at"),
                    "finished_at": manifest.get("finished_at")},
        "fetch_failures": manifest.get("errors", []),
        "method": {
            "test_statuses_separated": sorted(TEST_STATUSES),
            "ai_patterns": [p for p, _ in AI_PATTERNS],
            "ai_fields": "source, note, code, and every valueName/value pair "
                         "(parameter, eventCode, geocode)",
            "approver_patterns": [p for p, _ in APPROVER_PATTERNS],
            "approver_fields": "every valueName/value pair (parameter, eventCode, geocode)",
            "token_match": "ai, llm and gpt match as whole tokens; the rest as substrings",
        },
        "sources": [],
    }

    # IPAWS
    ipaws_alerts, unparsed, records = [], 0, 0
    for e in files:
        if e.get("kind") != "ipaws_page" or not e.get("path"):
            continue
        data, ok = read_file(snap, e)
        if not ok:
            hash_mismatch.append(e["path"])
        for rec in json.loads(data).get("IpawsArchivedAlerts", []):
            records += 1
            parsed = parse_cap((rec.get("originalMessage") or "").encode("utf-8"))
            if parsed is None:
                unparsed += 1
            else:
                ipaws_alerts.append(parsed)
    if records:
        s = summarise(ipaws_alerts)
        s.update({"source_id": "IPAWS", "label": "US IPAWS (OpenFEMA archive)",
                  "country": "USA", "records": records, "unparsed": unparsed})
        if ipaws_alerts:
            sent = sorted(t for t in (utc(a["sent"]) for a in ipaws_alerts) if t)
            s["sent_range_utc"] = [sent[0], sent[-1]] if sent else None
        results["sources"].append(s)

    # Register
    register = None
    for e in files:
        if e.get("kind") == "wmo_register" and e.get("path"):
            data, ok = read_file(snap, e)
            if not ok:
                hash_mismatch.append(e["path"])
            register = parse_register(data)
    if register is not None:
        reg = {"entries_total": len(register), "states": {}}
        for cc in GCC + EXTRA:
            ents = [r for r in register if r["country"] == cc]
            reg["states"][cc] = {
                "gcc": cc in GCC,
                "lists_cap_feed": any(r["feeds"] for r in ents),
                "entries": ents,
            }
        results["wmo_register"] = reg

    # Feeds
    feed_files = {e["source_id"]: e for e in files if e.get("kind") == "feed"}
    items = collections.defaultdict(list)
    for e in files:
        if e.get("kind") == "cap_item":
            items[e["source_id"]].append(e)
    for src in manifest.get("sources", []):
        sid = src["source_id"]
        fe = feed_files.get(sid, {})
        alerts, unparsed, failed = [], 0, 0
        for e in items.get(sid, []):
            if not e.get("path"):
                failed += 1
                continue
            data, ok = read_file(snap, e)
            if not ok:
                hash_mismatch.append(e["path"])
            parsed = parse_cap(data)
            if parsed is None:
                unparsed += 1
            else:
                alerts.append(parsed)
        s = summarise(alerts)
        dates = {}
        if fe.get("path"):
            data, ok = read_file(snap, fe)
            if not ok:
                hash_mismatch.append(fe["path"])
            dates = feed_dates(data)
        s.update({
            "source_id": sid,
            "label": f"{'; '.join(src['authorities'])} [{', '.join(src['langs'])}]",
            "country": src["country"],
            "feed_url": src["feed_url"],
            "feed_http_status": fe.get("http_status"),
            "feed_error": fe.get("error"),
            "feed_dates": dates,
            "items_listed": src.get("items_listed", 0),
            "item_fetch_failures": failed,
            "unparsed": unparsed,
        })
        results["sources"].append(s)

    results["hash_mismatches"] = hash_mismatch
    return results


def utc(stamp):
    try:
        t = dt.datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        return None
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pct(n, d):
    return f"{n} ({100 * n / d:.1f}%)" if d else "0"


def render_md(r):
    out = [f"# CAP provenance audit: snapshot {r['snapshot']}", ""]
    out.append(f"Fetched {r['fetched']['started_at']} to {r['fetched']['finished_at']} (UTC). "
               "Generated by count.py; do not edit by hand.")
    out.append("")
    out.append("## Live alerts (status not Test/Exercise)")
    out.append("")
    head = ["Source", "Alerts", "Test/Exercise"] + [label for _, label in METRICS]
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))
    for s in r["sources"]:
        g = s["groups"]["live"]
        row = [f"{s['country']}: {s['label']}", str(g["alerts"]),
               str(s["groups"]["test_exercise"]["alerts"])]
        row += [pct(g[k], g["alerts"]) for k, _ in METRICS]
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append("## Test/Exercise alerts (counted apart)")
    out.append("")
    out.append("| " + " | ".join(["Source", "Alerts"] + [l for _, l in METRICS]) + " |")
    out.append("|" + "---|" * (2 + len(METRICS)))
    for s in r["sources"]:
        g = s["groups"]["test_exercise"]
        if g["alerts"]:
            row = [f"{s['country']}: {s['label']}", str(g["alerts"])]
            row += [pct(g[k], g["alerts"]) for k, _ in METRICS]
            out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append("## Raw values behind the AI/machine and approver counts")
    out.append("")
    out.append(f"AI patterns: {', '.join(r['method']['ai_patterns'])} "
               f"(searched in {r['method']['ai_fields']}). "
               f"Approver patterns: {', '.join(r['method']['approver_patterns'])} "
               f"(searched in {r['method']['approver_fields']}). "
               f"{r['method']['token_match']}.")
    out.append("")
    for key, title in (("ai_marker_values", "AI/machine"), ("approver_marker_values", "Approver")):
        any_hits = False
        for s in r["sources"]:
            vals = s[key]
            if not vals:
                continue
            any_hits = True
            out.append(f"**{title}, {s['country']}: {s['label']}**")
            out.append("")
            out.append("| Group | Field | Raw value | Pattern | Alerts |")
            out.append("|---|---|---|---|---|")
            for v in vals:
                val = v["value"].replace("|", "\\|").replace("\n", " ")
                out.append(f"| {v['group']} | {v['field']} | `{val}` | {v['pattern']} | {v['alerts']} |")
            out.append("")
        if not any_hits:
            out.append(f"{title}: no matches in any source.")
            out.append("")
    out.append("## Feed status")
    out.append("")
    out.append("| Source | Feed URL | HTTP | Feed dates | Items listed | Parsed alerts | Fetch failures | Not CAP |")
    out.append("|---|---|---|---|---|---|---|---|")
    for s in r["sources"]:
        if s["source_id"] == "IPAWS":
            continue
        n = s["groups"]["live"]["alerts"] + s["groups"]["test_exercise"]["alerts"]
        dates = "; ".join(f"{k} {v}" for k, v in s["feed_dates"].items())
        out.append(f"| {s['country']}: {s['label']} | {s['feed_url']} | "
                   f"{s['feed_http_status'] or s['feed_error']} | {dates} | {s['items_listed']} | "
                   f"{n} | {s['item_fetch_failures']} | {s['unparsed']} |")
    out.append("")
    reg = r.get("wmo_register")
    if reg:
        out.append(f"## WMO Register of Alerting Authorities ({reg['entries_total']} entries)")
        out.append("")
        out.append("| State | GCC | State lists any CAP feed | Entry | Record date | Feeds in this entry |")
        out.append("|---|---|---|---|---|---|")
        for cc, st in reg["states"].items():
            gcc = "yes" if st["gcc"] else "no"
            any_feed = "yes" if st["lists_cap_feed"] else "no"
            if not st["entries"]:
                out.append(f"| {cc} | {gcc} | no | (no entry) | | |")
            for e in st["entries"]:
                feeds = ", ".join(f"{f['lang']}: {f['url']}" for f in e["feeds"]) or "none listed"
                out.append(f"| {cc} | {gcc} | {any_feed} | "
                           f"[{e['title']}]({e['link']}) | {e['pubDate']} | {feeds} |")
        out.append("")
    out.append("## Other details")
    out.append("")
    for s in r["sources"]:
        out.append(f"**{s['country']}: {s['label']}**")
        out.append("")
        out.append(f"- Status counts: {json.dumps(s['status_counts'])}; duplicates skipped: "
                   f"{s['duplicates_skipped']}; unparsed: {s['unparsed']}")
        if s.get("sent_range_utc"):
            out.append(f"- Sent range (UTC): {s['sent_range_utc'][0]} to {s['sent_range_utc'][1]}")
        if s["live_with_same_test_event"]:
            out.append(f"- Live alerts that carry a SAME test/demo event code "
                       f"({', '.join(sorted(SAME_TEST_EVENTS))}): {s['live_with_same_test_event']}")
        out.append(f"- Distinct <source> values: {s['distinct_source_values']}; most common: "
                   + (", ".join(f"`{k}` ({v})" for k, v in list(s["top_source_values"].items())[:5]) or "none"))
        names = ", ".join(f"`{k}` ({v})" for k, v in s["parameter_valueNames"].items())
        out.append(f"- Parameter valueNames (alerts carrying each): {names or 'none'}")
        out.append("")
    if r["fetch_failures"]:
        out.append("## Fetch failures")
        out.append("")
        for e in r["fetch_failures"]:
            out.append(f"- {e['kind']}: {e['url']}: {e['error']}")
        out.append("")
    if r["hash_mismatches"]:
        out.append("## Files that no longer match the manifest hash")
        out.append("")
        out += [f"- {p}" for p in r["hash_mismatches"]]
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("snapshot", help="snapshot directory written by fetch.py")
    ap.add_argument("--out", help="where to write results.json/.md (default: audit/)")
    args = ap.parse_args()
    out = args.out or os.path.dirname(os.path.abspath(__file__))
    results = analyse(args.snapshot)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out, "results.md"), "w", encoding="utf-8") as f:
        f.write(render_md(results))
    for s in results["sources"]:
        g = s["groups"]["live"]
        print(f"{s['source_id']}: live={g['alerts']} test/exercise="
              f"{s['groups']['test_exercise']['alerts']} ai_marker={g['ai_marker']} "
              f"approver_marker={g['approver_marker']}")
    print(f"Wrote {out}/results.json and results.md")


if __name__ == "__main__":
    main()
