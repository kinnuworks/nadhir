"""Feed checker: only allowlisted feeds and hosts, and R6 is a note, not a hold."""
import pytest

from nadhir import cap, feeds


def _alert(desc, status="Actual", msg="Alert"):
    return cap.build({"identifier": "t-1", "sender": "x@example.org", "sent": "2026-11-09T10:00:00+04:00",
                      "status": status, "msgType": msg, "scope": "Public",
                      "info": [{"language": "en-US", "category": ["Met"], "event": "Fog", "urgency": "Expected",
                                "severity": "Moderate", "certainty": "Likely", "headline": "Fog",
                                "description": desc, "instruction": "", "parameters": [],
                                "areas": [{"areaDesc": "Coast", "polygons": [], "geocodes": [("X", "1")]}]}]})


def test_unknown_feed_rejected():
    with pytest.raises(ValueError):
        feeds.check_feed("http://169.254.169.254/")


def test_long_text_is_a_note_not_a_hold():
    r = feeds._check_one(_alert("Fog. " * 400))
    assert r["failed"] == [] and r["too_long_for_cell_broadcast"]


def test_test_text_sent_as_actual_is_held():
    r = feeds._check_one(_alert("This is a test message. Fog on the coast."))
    assert r["failed"] == ["R2"]


def test_item_links_off_the_allowed_hosts_are_ignored(monkeypatch):
    rss = b"""<rss><channel><item><link>http://internal.example/secret</link></item>
              <item><link>https://www.met.gov.kw/a.xml</link></item></channel></rss>"""
    got = []
    monkeypatch.setattr(feeds, "_get", lambda url, timeout=8: (got.append(url), rss if url.endswith("kuwait_cap.xml") else _alert("Fog").encode())[1])
    r = feeds.check_feed("kwt-en")
    assert "http://internal.example/secret" not in got and r["checked"] == 1
