"""Tests for audit/count.py on three small CAP fixtures (no network)."""

import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "audit"

_spec = importlib.util.spec_from_file_location("audit_count", ROOT / "audit" / "count.py")
count = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(count)


def load(name):
    return (FIX / name).read_bytes()


def test_parse_signed_bilingual():
    a = count.parse_cap(load("signed_bilingual.xml"))
    assert a["signed"] is True
    assert a["languages"] == ["en-CA", "fr-CA"]
    assert a["has_instruction"] is True
    assert a["has_source"] is False
    assert a["note"] == "Second issue of this warning"
    ai, appr = count.search(a)
    assert {label for _, _, label in ai} == {"auto-translat"}
    assert appr == []


def test_parse_ipaws_like_has_approver_but_no_ai_false_positive():
    a = count.parse_cap(load("ipaws_like.xml"))
    assert a["signed"] is False
    assert a["source"] == "182001 10.0.100474"
    assert a["note"] == ""  # empty <note/> does not count
    ai, appr = count.search(a)
    assert ai == []  # "rain", "Maine", "Bahrain" must not match "ai"
    assert appr == [("parameter.valueName", "UserName = Shift C", "username")]


def test_parse_exercise_cap11():
    a = count.parse_cap(load("exercise.xml"))
    assert a["status"] == "Exercise"
    assert a["languages"] == ["en-US"]  # CAP default when <language> is absent
    ai, appr = count.search(a)
    assert ("source", "AI-assisted draft tool 0.1", "ai") in ai
    assert ("parameter.valueName", "ApprovedBy = Duty officer", "approv") in appr


def test_parse_rejects_non_cap():
    assert count.parse_cap(b"<rss><channel/></rss>") is None
    assert count.parse_cap(b"not xml") is None


def test_summarise_counts_and_separates_exercises():
    alerts = [count.parse_cap(load(n)) for n in
              ("signed_bilingual.xml", "ipaws_like.xml", "exercise.xml", "ipaws_like.xml")]
    s = count.summarise(alerts)
    live, test = s["groups"]["live"], s["groups"]["test_exercise"]
    assert s["duplicates_skipped"] == 1
    assert live["alerts"] == 2 and test["alerts"] == 1
    assert live["with_signature"] == 1
    assert live["multi_language"] == 1
    assert live["with_instruction"] == 1
    assert live["with_source"] == 1
    assert live["with_note"] == 1
    assert live["with_parameter"] == 2
    assert live["ai_marker"] == 1 and live["approver_marker"] == 1
    assert test["ai_marker"] == 1 and test["approver_marker"] == 1
    assert test["with_note"] == 1 and test["with_source"] == 1
    assert s["parameter_valueNames"]["profile:CAP-CP:0.4:AutoTranslated"] == 1
    assert s["parameter_valueNames"]["EAS-ORG"] == 1
    assert s["status_counts"] == {"Actual": 2, "Exercise": 1}


REGISTER = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:iso="http://www.itu.int/tML/tML-ISO-3166"
     xmlns:raa="http://www.oid-info.com/get/2.49.0"><channel>
<item><title>United Arab Emirates: Met</title><iso:countrycode>ARE</iso:countrycode>
<link>https://example.org/rec/1</link><pubDate>Wed, 11 Sep 2013 00:38:42 +0000</pubDate></item>
<item><title>Saudi Arabia: Met</title><iso:countrycode>SAU</iso:countrycode>
<link>https://example.org/rec/2</link><pubDate>Sun, 21 Jun 2026 22:38:39 +0000</pubDate>
<raa:capAlertFeed xml:lang="en">https://example.org/sa/rss.xml</raa:capAlertFeed></item>
</channel></rss>"""


def _write(snap, rel, data, files, **meta):
    p = snap / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    files.append({"path": rel, "url": "https://example.org/" + rel, "fetched_at": "x",
                  "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), **meta})


def test_analyse_snapshot_end_to_end(tmp_path):
    snap = tmp_path / "snap"
    files = []
    page = {"IpawsArchivedAlerts": [
        {"originalMessage": load("ipaws_like.xml").decode()},
        {"originalMessage": load("exercise.xml").decode()},
        {"originalMessage": "<broken"},
    ]}
    _write(snap, "ipaws/page-000.json", json.dumps(page).encode(), files, kind="ipaws_page")
    _write(snap, "wmo/register-rss.xml", REGISTER, files, kind="wmo_register")
    _write(snap, "feeds/SAU/feed.xml", b"<rss><channel><lastBuildDate>d</lastBuildDate></channel></rss>",
           files, kind="feed", source_id="SAU:x", http_status=200)
    _write(snap, "feeds/SAU/items/0000.xml", load("signed_bilingual.xml"), files,
           kind="cap_item", source_id="SAU:x")
    files.append({"kind": "cap_item", "source_id": "SAU:x", "path": None,
                  "url": "https://example.org/gone.xml", "error": "HTTP 404"})
    manifest = {"started_at": "s", "finished_at": "f",
                "errors": [{"kind": "cap_item", "url": "https://example.org/gone.xml",
                            "error": "HTTP 404"}],
                "sources": [{"source_id": "SAU:x", "country": "SAU",
                             "feed_url": "https://example.org/sa/rss.xml",
                             "authorities": ["Saudi Arabia: Met"], "langs": ["en"],
                             "items_listed": 2}],
                "files": files}
    (snap / "manifest.json").write_text(json.dumps(manifest))

    r = count.analyse(str(snap))
    ipaws, sau = r["sources"]
    assert ipaws["records"] == 3 and ipaws["unparsed"] == 1
    assert ipaws["groups"]["live"]["approver_marker"] == 1
    assert ipaws["groups"]["test_exercise"]["ai_marker"] == 1
    assert sau["groups"]["live"]["alerts"] == 1
    assert sau["groups"]["live"]["with_signature"] == 1
    assert sau["item_fetch_failures"] == 1
    assert sau["feed_dates"] == {"lastBuildDate": "d"}
    reg = r["wmo_register"]["states"]
    assert reg["ARE"]["lists_cap_feed"] is False
    assert reg["ARE"]["entries"][0]["pubDate"].startswith("Wed, 11 Sep 2013")
    assert reg["SAU"]["lists_cap_feed"] is True
    assert reg["KWT"]["entries"] == []
    assert r["hash_mismatches"] == []

    md = count.render_md(r)
    assert "UserName = Shift C" in md and "AI-assisted draft tool 0.1" in md
    assert "https://example.org/gone.xml" in md
