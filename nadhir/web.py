"""Request handlers shared by the local server and the hosted functions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import pipeline
from .llm import ModelError
from .log import AuditLog, verify

ROOT = Path(__file__).resolve().parent.parent
SECRET = os.environ.get("NADHIR_STATE_SECRET", "local-dev-only").encode()
MAX_INPUT = 1500
GST = timezone(timedelta(hours=4))

# Illustrative target zones for the demo (not official UAE geocodes).
ZONES = {
    "al-ain": {"areaDesc": "Al Ain (demo zone)", "geocodes": [["DEMO-ZONE", "AUH-ALAIN"]]},
    "abu-dhabi-city": {"areaDesc": "Abu Dhabi city (demo zone)", "geocodes": [["DEMO-ZONE", "AUH-CITY"]]},
    "dubai": {"areaDesc": "Dubai (demo zone)", "geocodes": [["DEMO-ZONE", "DXB-ALL"]]},
    "sharjah": {"areaDesc": "Sharjah (demo zone)", "geocodes": [["DEMO-ZONE", "SHJ-ALL"]]},
    "fujairah": {"areaDesc": "Fujairah (demo zone)", "geocodes": [["DEMO-ZONE", "FUJ-ALL"]]},
}
ISSUER = "demo-national-authority@nadhir.example"
ISSUERS = {ISSUER: {"name": "Demo national authority (stands in for the real issuer)", "level": 1,
                    "areas": ["*"], "categories": ["*"]}}


def templates() -> list[dict]:
    """Vetted alert templates (FCC DA 25-12 Appendix C/D), one entry per language."""
    out = []
    for p in sorted((ROOT / "bench" / "templates").glob("fcc-*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for t in data.get("templates", []):
            if t.get("text"):
                lang = t["language"].split("-")[0]
                out.append({"id": f"{data.get('id', p.stem)}:{lang}", "language": lang,
                            "hazard": t.get("template"), "text": t["text"], "source": data.get("source_id")})
    return out


def _sign_state(state: dict) -> str:
    raw = json.dumps(state, sort_keys=True, ensure_ascii=False).encode()
    mac = hmac.new(SECRET, raw, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(raw).decode() + "." + mac


def _open_state(token: str) -> dict:
    raw_b64, mac = token.rsplit(".", 1)
    raw = base64.urlsafe_b64decode(raw_b64.encode())
    if not hmac.compare_digest(mac, hmac.new(SECRET, raw, hashlib.sha256).hexdigest()):
        raise ValueError("state was changed in the browser")
    return json.loads(raw)


def scenario(body: dict) -> dict:
    inputs = []
    for item in body.get("inputs", [])[:6]:
        text = str(item.get("text", "")).strip()[:MAX_INPUT]
        if text:
            inputs.append({"text": text, "verified": bool(item.get("verified", True)),
                           "source": str(item.get("source", "typed in the demo"))[:120]})
    if not inputs:
        raise ValueError("add at least one event input")
    zone = ZONES.get(body.get("zone"), ZONES["al-ain"])
    now = datetime.now(GST).replace(microsecond=0)
    event_id = "demo-" + hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:10]
    return {
        "event_id": event_id, "profile": "UAE", "issuer": ISSUER, "issuer_name": ISSUERS[ISSUER]["name"],
        "issuers": ISSUERS, "exercise": bool(body.get("exercise")), "environment": "live",
        "requested_area": {**zone, "event_id": event_id, "origin": "drawn"},
        "inputs": inputs + [{"text": "Issuer public site (demo): https://alerts.example.ae", "verified": True,
                             "source": "issuer profile"}],
        "languages": ["ar"], "templates": templates(),
        "sent": now.isoformat() if body.get("live_time") else "2026-11-09T14:00:00+04:00",
    }


def handle_draft(body: dict) -> dict:
    scn = scenario(body)
    try:
        st = pipeline.draft_and_review(scn, run=body.get("run", "web"), budget_s=95)
    except ModelError as e:
        return {"error": str(e)}
    log = st.pop("log")
    state = {"scn": scn, "xml": st["xml"], "ai": st["ai"], "log": log.records,
             "institutions": {"open_objections": [{"by": o["by"], "issue": o["issue"]}
                                                  for o in st["institutions"]["open_objections"]]}}
    return {**st, "state": _sign_state(state), "log": log.records}


def handle_approve(body: dict) -> dict:
    state = _open_state(body["state"])
    approvals = []
    for a in body.get("approvals", [])[:4]:
        name = str(a.get("name", "")).strip()[:60]
        if name:
            approvals.append({"name": name, "role": str(a.get("role", "approver"))[:40],
                              "scope": a.get("scope", "release") if a.get("scope") in ("release", "language:ar") else "release",
                              "kind": "human", "ack_objections": bool(body.get("ack_objections"))})
    log = AuditLog()
    log.records = state["log"]
    res = pipeline.approve_and_release(state["scn"], state, approvals, log)
    log = res.pop("log")
    ok, why = verify(log.records)
    return {**res, "log": log.records, "log_check": why if ok else "BROKEN: " + why}


def handle_check(body: dict) -> dict:
    xml = str(body.get("xml", ""))[:60000]
    if not xml.strip():
        return {"error": "paste a CAP XML alert"}
    profile = body.get("profile") if body.get("profile") in ("UAE", "US", "GENERIC") else "GENERIC"
    out = pipeline.check_pasted(xml, profile)
    if body.get("review"):
        try:
            out["reviews"] = pipeline.review_pasted(xml, profile if profile != "US" else "GENERIC")
        except ModelError as e:
            out["review_error"] = str(e)
        except Exception:
            out["review_error"] = "the reviewers could not read this alert"
    return out


def handle_feed(body: dict) -> dict:
    from . import feeds
    return feeds.check_feed(str(body.get("feed", "")))


ROUTES = {"/api/draft": handle_draft, "/api/approve": handle_approve, "/api/check": handle_check,
          "/api/feed": handle_feed}


def dispatch(path: str, raw: bytes) -> tuple[int, dict]:
    fn = ROUTES.get(path)
    if not fn:
        return 404, {"error": "not found"}
    try:
        body = json.loads(raw or b"{}")
        return 200, fn(body)
    except (ValueError, KeyError) as e:
        return 400, {"error": str(e)}
