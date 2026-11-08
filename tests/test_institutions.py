"""Institution agents: the quote check, the partial views and the retrieval, without calling a model."""
import yaml

from nadhir import institutions, pipeline, retrieval
from nadhir.retrieval import Index

CLAUSES = [
    {"id": "FCC-HI-2018#0001", "doc": "FCC-HI-2018", "locator": "p.12", "lang": "en", "kind": "text",
     "text": "Require more than one credentialed person to validate the message content prior to transmission."},
    {"id": "CAP12#0001", "doc": "CAP12", "locator": "3.2.1", "lang": "en", "kind": "text",
     "text": "Cancel - Cancels the earlier message(s) identified in references."},
    {"id": "AR#0001", "doc": "AR", "locator": "p.1", "lang": "ar", "kind": "text",
     "text": "يجب أن تكون رسائل الإنذار المبكر باللغتين العربية والإنجليزية."},
]
DOCS = {"FCC-HI-2018": {"id": "FCC-HI-2018", "title": "FCC Hawaii report", "collection": "project", "status": "verified-primary"},
        "CAP12": {"id": "CAP12", "title": "CAP 1.2", "collection": "project", "status": "verified-primary"},
        "AR": {"id": "AR", "title": "Arabic test clause", "collection": "itu-sandbox-uae", "status": "verified-primary"}}


def _fake_index(monkeypatch):
    ix = Index(CLAUSES, DOCS)
    monkeypatch.setattr(retrieval, "index", lambda: ix)
    monkeypatch.setattr(retrieval, "MIN_SCORE", 0.0)
    monkeypatch.setattr(retrieval, "MIN_TERMS", 1)
    return ix


def test_search_finds_clause_and_arabic(monkeypatch):
    _fake_index(monkeypatch)
    assert retrieval.search("credentialed person validate message")[0]["id"] == "FCC-HI-2018#0001"
    # Arabic with and without the definite article and hamza variants
    assert retrieval.search("رسائل انذار العربيه")[0]["id"] == "AR#0001"


def test_quote_check_is_word_for_word():
    text = "Require more than one credentialed person to validate the message content."
    assert retrieval.quote_in("more than one credentialed person to validate", text)
    assert not retrieval.quote_in("more than two credentialed people to validate", text)
    assert not retrieval.quote_in("one credentialed", text)  # too short to count


def _scn():
    return yaml.safe_load(open("bench/scenarios/uae-dust-2026-03-04.yaml", encoding="utf-8"))


def _xml(scn):
    fields = {"status": "Actual", "msgType": "Alert", "category": "Met", "event": "Dust", "urgency": "Expected",
              "severity": "Moderate", "certainty": "Likely", "headline": "Dust until 19:00",
              "description": "Blowing dust until 19:00.", "instruction": "Drive with care."}
    versions = [{"language": "ar", "method": "machine", "template_id": "", "slots": [],
                 "headline": "غبار حتى الساعة 19:00", "description": "غبار متطاير حتى الساعة 19:00.",
                 "instruction": "قودوا بحذر."}]
    xml, _ = pipeline.compose(scn, fields, versions, "t")
    return xml, fields, versions


def test_views_are_partial():
    scn = _scn()
    xml, fields, versions = _xml(scn)
    v = institutions.views(scn, xml, fields, versions)
    assert "issuer_register" not in v["met"] and "event_inputs" not in v["issuer"]
    assert "event_inputs" not in v["arabic"] and "phone_text" in v["operator"]
    assert v["arabic"]["arabic_produced_by"] == "machine translation"


def test_uncited_objections_are_dropped(monkeypatch):
    _fake_index(monkeypatch)
    scn = _scn()
    xml, fields, versions = _xml(scn)

    def fake(system, user, schema, salt="", mode=None, effort=None):
        if "queries" in schema["properties"]:
            return {"queries": ["credentialed person validate"]}, {}
        return {"position": "object", "summary": "s", "no_basis": [], "objections": [
            {"issue": "good", "field": "description", "blocking": True, "fix": "f",
             "evidence": [{"kind": "clause", "ref": "FCC-HI-2018#0001", "quote": "more than one credentialed person to validate"}]},
            {"issue": "made-up quote", "field": "description", "blocking": True, "fix": "f",
             "evidence": [{"kind": "clause", "ref": "FCC-HI-2018#0001", "quote": "two supervisors must always sign every alert"}]},
            {"issue": "clause it never retrieved", "field": "description", "blocking": True, "fix": "f",
             "evidence": [{"kind": "clause", "ref": "CAP12#0001", "quote": "Cancels the earlier message(s) identified in references"}]},
            {"issue": "quotes the alert", "field": "language:ar", "blocking": True, "fix": "f",
             "evidence": [{"kind": "view", "ref": "arabic", "quote": "غبار متطاير حتى الساعة"}]},
        ]}, {}

    monkeypatch.setattr(institutions, "call_json", fake)
    r = institutions.review_one("arabic", institutions.views(scn, xml, fields, versions)["arabic"], "t")
    kept = [o["issue"] for o in r["objections"]]
    assert kept == ["good", "quotes the alert"]
    assert {d["issue"] for d in r["dropped"]} == {"made-up quote", "clause it never retrieved"}
    assert r["objections"][0]["policy_cited"] and not r["objections"][1]["policy_cited"]


def test_all_objections_dropped_means_agree(monkeypatch):
    _fake_index(monkeypatch)
    scn = _scn()
    xml, fields, versions = _xml(scn)

    def fake(system, user, schema, salt="", mode=None, effort=None):
        if "queries" in schema["properties"]:
            return {"queries": ["anything"]}, {}
        return {"position": "escalate", "summary": "s", "no_basis": [], "objections": [
            {"issue": "x", "field": "area", "blocking": True, "fix": "f",
             "evidence": [{"kind": "view", "ref": "alert", "quote": "words that are not in the alert at all"}]}]}, {}

    monkeypatch.setattr(institutions, "call_json", fake)
    r = institutions.review_one("issuer", institutions.views(scn, xml, fields, versions)["issuer"], "t")
    assert r["position"] == "agree" and not r["objections"] and len(r["dropped"]) == 1
