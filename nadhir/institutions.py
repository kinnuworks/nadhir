"""Institution agents: four reviewers, each standing in for a body with its own mandate and its own
partial view of the alert. None of them can approve or send. Each one:

1. writes its own search queries for the knowledge base (one model call),
2. reads the clauses the search returns (code, deterministic),
3. agrees, objects or escalates (second model call), quoting its evidence.

The orchestrator keeps an objection only if at least one quote is found word for word in the clause or
the text it names. Everything else is dropped and logged as dropped. Concerns the agent could not back
with any clause are kept apart as "no basis found": they are leads for policy gaps, not objections.

The agents stand in for roles. They are not the real UAE bodies and do not speak for them.
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor

from . import cap, retrieval
from .llm import call_json

GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ"
           "ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà^{}\\[~]|€")

AGENTS = {
    "met": {
        "name": "Met office reviewer",
        "stands_for": "the national meteorological centre (hazard facts)",
        "mandate": ("You check that the alert says what the hazard bulletin says: the same hazard, the same times, "
                    "the same places, severity and certainty no higher or lower than the bulletin supports, and no "
                    "unverified report in the alert."),
        "sees": "the event inputs (marked verified or unverified) and the English alert fields",
    },
    "issuer": {
        "name": "Issuing authority reviewer",
        "stands_for": "the national emergency authority that issues alerts (who, where, when)",
        "mandate": ("You check that this sender may issue this alert, for this area, now: the sender is in the "
                    "issuer register, the target area is the one requested for this event, the status fits the "
                    "context (a drill stays a drill), it does not overreach an active alert from a higher "
                    "authority, and a correction points to the alert it corrects."),
        "sees": "the issuer register, active and earlier alerts, the requested area and the alert's status, type, sender and area",
    },
    "operator": {
        "name": "Network operator and regulator reviewer",
        "stands_for": "the telecom regulator and mobile operators (cell broadcast delivery)",
        "mandate": ("You check that the message can be delivered and read on a handset: required languages present, "
                    "the length per language in cell broadcast pages, encoding, and that the first page carries the "
                    "hazard and the action."),
        "sees": "each language's phone text with its character count, encoding and page count, and the profile's required languages",
    },
    "arabic": {
        "name": "Arabic language reviewer",
        "stands_for": "an Arabic reviewer at the issuing authority",
        "mandate": ("You compare the Arabic text with the English text and report any difference in meaning: "
                    "numbers, times, places, the hazard, and above all the protective action. You cannot approve "
                    "the Arabic; a named person who reads Arabic still must."),
        "sees": "the English and Arabic headline, description and instruction, and how the Arabic was produced",
    },
}

PLAN_SYSTEM = """You are the {name}, standing in for {stands_for}. {mandate}
You see only {sees}. You do not see anything else about this alert.
Before you review, search the knowledge base for the rules and guidance you need. It holds standards
(CAP 1.2 / ITU-T X.1303bis, 3GPP cell broadcast specs, WMO and ITU guidance), regulator reports on past
alert failures (FCC), and UAE policy texts. Write up to 3 short keyword queries (3 to 8 words each)."""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"], "additionalProperties": False,
}

REVIEW_SYSTEM = """You are the {name}, standing in for {stands_for}. {mandate}
You see only {sees}. You cannot approve or send the alert; people decide.

Review the alert within your mandate only. Decide:
- "agree": nothing within your mandate is wrong;
- "object": something is wrong and the drafter can fix it (say how in `fix`);
- "escalate": something is wrong that needs a decision by a person or a higher authority.

Every objection needs evidence. Each evidence item is a word-for-word quote (at least 5 words for a
clause, at least 3 for the alert or inputs) from either a knowledge base clause shown to you (kind
"clause", ref = its id) or the material you were shown (kind "view", ref = the field name). Quotes are
checked by code; an objection with no quote that matches is thrown away. Do not object to things
outside your mandate. Do not repeat the same issue twice.
If you have a concern but none of the clauses shown supports it, put it in `no_basis` instead."""

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "position": {"type": "string", "enum": ["agree", "object", "escalate"]},
        "summary": {"type": "string"},
        "objections": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "issue": {"type": "string"},
                "field": {"type": "string"},
                "blocking": {"type": "boolean"},
                "fix": {"type": "string"},
                "evidence": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"kind": {"type": "string", "enum": ["clause", "view"]},
                                   "ref": {"type": "string"}, "quote": {"type": "string"}},
                    "required": ["kind", "ref", "quote"], "additionalProperties": False}},
            },
            "required": ["issue", "field", "blocking", "fix", "evidence"], "additionalProperties": False}},
        "no_basis": {"type": "array", "items": {
            "type": "object",
            "properties": {"concern": {"type": "string"}, "searched_for": {"type": "string"}},
            "required": ["concern", "searched_for"], "additionalProperties": False}},
    },
    "required": ["position", "summary", "objections", "no_basis"], "additionalProperties": False,
}


def _pages(text: str) -> dict:
    gsm = all(c in GSM7 for c in text)
    units = sum(2 if c in "^{}\\[~]|€" else 1 for c in text) if gsm else len(text)
    return {"characters": len(text), "encoding": "GSM-7" if gsm else "UCS-2",
            "pages": max(1, math.ceil(units / (93 if gsm else 41)))}


def views(scn: dict, xml: str, fields: dict | None = None, versions: list | None = None) -> dict:
    """What each agent is allowed to see. Built from the CAP XML, so faults injected into the XML are visible."""
    alert = cap.parse(xml)
    infos = alert.get("info", [])
    by_lang = {(i.get("language") or "en").split("-")[0].lower(): i for i in infos}
    en = by_lang.get("en") or (infos[0] if infos else {})
    ar = by_lang.get("ar")
    area0 = (en.get("areas") or [{}])[0]
    machine = {(v.get("language") or "").split("-")[0] for v in (versions or []) if v.get("method") == "machine"}
    text = lambda i: {k: i.get(k) or "" for k in ("headline", "description", "instruction")}
    req = scn.get("requested_area") or {}
    return {
        "met": {
            "event_inputs": [{"n": n, "verified": i.get("verified", True), "source": i.get("source", ""),
                              "text": i["text"]} for n, i in enumerate(scn.get("inputs", []), 1)],
            "context": "EXERCISE / DRILL" if scn.get("exercise") else "real event",
            "alert_english": {"status": alert.get("status"), "event": en.get("event"), "severity": en.get("severity"),
                              "urgency": en.get("urgency"), "certainty": en.get("certainty"), **text(en)},
        },
        "issuer": {
            "issuer_register": scn.get("issuers", {}),
            "active_alerts_from_other_authorities": scn.get("active_alerts", []),
            "earlier_alerts_from_this_system": scn.get("prior_alerts", []),
            "context": "EXERCISE / DRILL" if scn.get("exercise") else "real event",
            "console_environment": scn.get("environment", "live"),
            "requested_area": {"areaDesc": req.get("areaDesc"), "codes": req.get("geocodes", []),
                               "drawn_for_event": req.get("event_id"), "origin": req.get("origin")},
            "alert": {"sender": alert.get("sender"), "status": alert.get("status"), "msgType": alert.get("msgType"),
                      "scope": alert.get("scope"), "references": alert.get("references"),
                      "category": en.get("category"), "event": en.get("event"), "severity": en.get("severity"),
                      "areaDesc": area0.get("areaDesc"), "codes": [list(g) for g in area0.get("geocodes", [])],
                      "polygons": area0.get("polygons", []), "headline": en.get("headline")},
        },
        "operator": {
            "profile": scn.get("profile", "UAE"),
            "required_languages": {"UAE": ["ar", "en"]}.get(scn.get("profile", "UAE"), []),
            "handset_advice": "UAE handset spec summary: message should be limited to 1 page" if scn.get("profile", "UAE") == "UAE" else None,
            "phone_text": [{"language": lang, "text": i.get("description") or "", **_pages(i.get("description") or "")}
                           for lang, i in by_lang.items()],
        },
        "arabic": None if not ar else {
            "english": text(en), "arabic": text(ar),
            "arabic_produced_by": "machine translation" if "ar" in machine else ("vetted template" if versions else "unknown"),
        },
    }


def _flat(view) -> str:
    return json.dumps(view, ensure_ascii=False)


def review_one(role: str, view: dict, salt: str) -> dict:
    a = AGENTS[role]
    shown = json.dumps(view, ensure_ascii=False, indent=1)
    plan, pmeta = call_json(PLAN_SYSTEM.format(**a), "What you can see:\n" + shown, PLAN_SCHEMA,
                            salt=f"{salt}:plan", effort="low")
    queries = [q for q in plan.get("queries", []) if q.strip()][:3]
    clauses, seen = [], set()
    for q in queries:
        for h in retrieval.search(q, k=4):
            if h["id"] not in seen:
                seen.add(h["id"])
                clauses.append({**h, "query": q})
    empty = [q for q in queries if not any(c["query"] == q for c in clauses)]
    kb_text = "\n\n".join(f"[{c['id']}] {c['title']} ({c['locator']}):\n{c['text']}" for c in clauses) or "(no clause scored high enough)"
    user = ("What you can see:\n" + shown + "\n\nKnowledge base clauses returned by your searches "
            f"({', '.join(repr(q) for q in queries)}):\n\n" + kb_text)
    data, rmeta = call_json(REVIEW_SYSTEM.format(**a), user, REVIEW_SCHEMA, salt=f"{salt}:review")
    kept, dropped = [], []
    by_id = {c["id"]: c for c in clauses}
    flat = _flat(view)
    for o in data.get("objections", []):
        ok_ev = []
        for e in o.get("evidence", []):
            if e["kind"] == "clause" and e["ref"] in by_id and retrieval.quote_in(e["quote"], by_id[e["ref"]]["text"]):
                c = by_id[e["ref"]]
                ok_ev.append({**e, "title": c["title"], "locator": c["locator"], "url": c["url"], "status": c["status"],
                              "collection": c["collection"]})
            elif e["kind"] == "view" and retrieval.quote_in(e["quote"], flat, min_words=3):
                ok_ev.append(e)
        if ok_ev:
            kept.append({**o, "evidence": ok_ev, "policy_cited": any(e["kind"] == "clause" for e in ok_ev),
                         "unchecked_evidence": len(o.get("evidence", [])) - len(ok_ev)})
        else:
            dropped.append({**o, "why": "no quote matched its clause or the alert word for word"})
    position = data.get("position", "agree")
    if position != "agree" and not kept:
        position = "agree"  # every objection fell at the quote check
    return {"role": role, "name": a["name"], "stands_for": a["stands_for"], "position": position,
            "summary": data.get("summary", ""), "objections": kept, "dropped": dropped,
            "no_basis": data.get("no_basis", []), "queries": queries, "queries_without_hits": empty,
            "clauses": [{k: c[k] for k in ("id", "title", "locator", "score", "query", "url", "collection")} for c in clauses],
            "model": {"plan": pmeta, "review": rmeta}}


def review(scn: dict, xml: str, fields: dict | None, versions: list | None, salt: str,
           roles: list[str] | None = None) -> list[dict]:
    v = views(scn, xml, fields, versions)
    roles = [r for r in (roles or list(AGENTS)) if v.get(r) is not None]
    with ThreadPoolExecutor(max_workers=len(roles) or 1) as pool:
        futs = {r: pool.submit(review_one, r, v[r], f"{salt}:{r}") for r in roles}
        return [futs[r].result() for r in roles]


def open_objections(reviews: list[dict]) -> list[dict]:
    return [{"by": r["name"], "role": r["role"], **o} for r in reviews for o in r["objections"]]


def feedback(reviews: list[dict]) -> list[str]:
    """Objections the drafter can act on, as plain feedback lines."""
    out = []
    for r in reviews:
        for o in r["objections"]:
            cite = next((f"{e['title']}, {e['locator']}" for e in o["evidence"] if e["kind"] == "clause"), None)
            out.append(f"{r['name']} objects ({o['field']}): {o['issue']} Fix: {o['fix']}"
                       + (f" [cites {cite}]" if cite else ""))
    return out
