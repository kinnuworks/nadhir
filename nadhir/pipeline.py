"""Orchestrator (the Y.3172 MLFO role): runs drafter -> translator -> gate -> people -> signature -> gate.

The same function serves the replay bench (approvals scripted and labelled as such) and the
web demo (approvals come from a person clicking).
"""
from __future__ import annotations

from . import agents, cap, gate, keys
from .log import AuditLog

DRAFTER_FIXABLE = {"R0", "R2", "R6", "R11"}   # text problems the drafter can repair itself
MAX_REVISIONS = 2


def _info(fields: dict, lang: str, area: dict, sender_name: str) -> dict:
    return {
        "language": lang, "category": [fields["category"]], "event": fields["event"],
        "urgency": fields["urgency"], "severity": fields["severity"], "certainty": fields["certainty"],
        "senderName": sender_name, "headline": fields["headline"], "description": fields["description"],
        "instruction": fields["instruction"], "parameters": [],
        "areas": [{"areaDesc": area.get("areaDesc", ""), "polygons": area.get("polygons", []),
                   "geocodes": [tuple(g) for g in area.get("geocodes", [])]}],
    }


def envelope_for(scn: dict, xml: str, approvals: list, ai: dict) -> gate.Envelope:
    certs = {}
    for sender in scn.get("issuers", {}):
        c = keys.cert(sender)
        if c:
            certs[sender] = [c]
    return gate.Envelope(
        cap_xml=xml, profile=scn.get("profile", "UAE"), event_id=scn.get("event_id"),
        environment=scn.get("environment", "live"), exercise=bool(scn.get("exercise")),
        requested_area=scn.get("requested_area"), approvals=approvals,
        event_inputs=[i["text"] for i in scn["inputs"] if i.get("verified", True)],
        issuers=scn.get("issuers", {}), active_alerts=scn.get("active_alerts", []),
        prior_alerts=scn.get("prior_alerts", []), vetted_templates=scn.get("templates", []),
        registered_certs=certs, ai=ai,
    )


def compose(scn: dict, fields: dict, versions: list[dict], run: str) -> tuple[str, dict]:
    area = scn.get("requested_area") or {}
    name = scn.get("issuer_name", scn["issuer"])
    english = dict(fields)
    # Template first: if the Arabic (or other) text comes from a vetted template, the English broadcast
    # text comes from the English version of the same template, filled with the same slot values.
    for v in versions:
        if v["method"] == "template":
            base = v["template_id"].rsplit(":", 1)[0]
            en = next((t for t in scn.get("templates", []) if t["id"] == f"{base}:en"), None)
            if en:
                english["description"] = agents.fill_template(en["text"], {s["slot"]: s["value"] for s in v["slots"]})
                english["instruction"] = ""
            break
    infos = [_info(english, "en-US", area, name)]
    machine = []
    for v in versions:
        if v["method"] == "template":
            v = {**v, "instruction": ""}  # the vetted template already carries the protective actions
        infos.append(_info({**fields, **{k: v[k] for k in ("headline", "description", "instruction")}},
                           v["language"], area, name))
        if v["method"] == "machine":
            machine.append(v["language"].split("-")[0])
    ai = {"involvement": "generated", "machine_translated": machine, "model": agents_model()}
    params = [(gate.P_AI, "generated"), (gate.P_MODEL, ai["model"])]
    if machine:
        params.append((gate.P_MT, ",".join(machine)))
    alert = {
        "identifier": f"{scn['event_id']}-{run}", "sender": scn["issuer"], "sent": scn["sent"],
        "status": fields["status"], "msgType": fields["msgType"], "scope": "Public",
        "code": ["AIPROV-0.1"], "info": infos,
    }
    if fields["msgType"] in ("Update", "Cancel") and scn.get("prior_alerts"):
        p = scn["prior_alerts"][-1]
        alert["references"] = f"{p['sender']},{p['identifier']},{p['sent']}"
    return cap.with_parameters(cap.build(alert), params), ai


def agents_model() -> str:
    from .llm import MODEL
    return MODEL


def draft_and_review(scn: dict, run: str = "1", log: AuditLog | None = None) -> dict:
    """Steps up to human review. Returns the state a person (or the replay script) approves."""
    log = log or AuditLog()
    at = scn["sent"]
    log.append("orchestrator", "inputs", {"event_id": scn["event_id"], "inputs": scn["inputs"],
                                          "requested_area": scn.get("requested_area")}, at)
    feedback: list[str] = []
    history = []
    for attempt in range(MAX_REVISIONS + 1):
        inputs = scn["inputs"] + ([{"text": "Gate feedback on your previous draft, fix these: " + " | ".join(feedback),
                                    "verified": True, "source": "policy gate"}] if feedback else [])
        fields, meta = agents.draft(inputs, {**scn, "areaDesc": (scn.get("requested_area") or {}).get("areaDesc")},
                                    salt=f"{scn['event_id']}:{run}:{attempt}")
        log.append("drafter", "draft", {"attempt": attempt, "fields": fields, "model": meta}, at)
        versions, tmeta = [], None
        if scn.get("languages"):
            versions, tmeta = agents.translate(fields, scn["languages"], scn.get("templates", []),
                                               salt=f"{scn['event_id']}:{run}:{attempt}")
            log.append("translator", "translate", {"versions": versions, "model": tmeta}, at)
        xml, ai = compose(scn, fields, versions, run)
        verdicts = gate.check(envelope_for(scn, xml, [], ai), stage="review")
        log.append("gate", "review", {"decision": gate.decision(verdicts),
                                      "verdicts": [v.as_dict() | {"sources": [s["id"] for s in v.as_dict()["sources"]]} for v in verdicts]}, at)
        history.append({"attempt": attempt, "fields": fields, "versions": versions, "xml": xml,
                        "verdicts": [v.as_dict() for v in verdicts]})
        fixable = [v for v in verdicts if v.status == gate.FAIL and v.rule in DRAFTER_FIXABLE]
        if not fixable or attempt == MAX_REVISIONS:
            break
        feedback = [f"{v.rule} {v.title}: {v.detail}" for v in fixable]
    first = history[0]
    return {"scenario": scn["event_id"], "run": run, "xml": xml, "ai": ai, "fields": fields,
            "versions": versions, "verdicts": [v.as_dict() for v in verdicts],
            "decision": gate.decision(verdicts), "attempts": len(history),
            "first_draft": {"xml": first["xml"], "verdicts": first["verdicts"]}, "log": log}


def approve_and_release(scn: dict, state: dict, approvals: list[dict], log: AuditLog | None = None) -> dict:
    """People approve; approvers are written into the alert; the issuer signs; the gate checks again."""
    log = log or state.get("log") or AuditLog()
    at = scn["sent"]
    for a in approvals:
        log.append(a.get("name", "approver"), "approve", {"role": a.get("role"), "scope": a.get("scope", "release"),
                                                         "kind": a.get("kind", "human"),
                                                         "scripted": a.get("scripted", False)}, at)
    names = sorted({a["name"] for a in approvals if a.get("scope", "release") == "release"})
    roles = sorted({a.get("role", "approver") for a in approvals if a.get("scope", "release") == "release"})
    xml = cap.with_parameters(state["xml"], [(gate.P_APPROVED_BY, ",".join(roles)),
                                             (gate.P_APPROVAL_COUNT, str(len(names)))])
    if keys.cert(scn["issuer"]) or scn["issuer"] in scn.get("issuers", {}):
        key_pem, cert_pem = keys.ensure(scn["issuer"])
        xml = cap.sign(xml, key_pem, cert_pem)
    verdicts = gate.check(envelope_for(scn, xml, approvals, state["ai"]), stage="release")
    decision = gate.decision(verdicts)
    log.append("gate", "release-check", {"decision": decision,
                                         "verdicts": [{"rule": v.rule, "status": v.status, "detail": v.detail} for v in verdicts]}, at)
    log.append("orchestrator", "broadcast" if decision == "release" else "held", {"identifier": cap.parse(xml).get("identifier")}, at)
    return {"xml": xml, "verdicts": [v.as_dict() for v in verdicts], "decision": decision, "log": log}


def check_pasted(xml: str, profile: str = "UAE", inputs: list[str] | None = None) -> dict:
    """The paste box: check any CAP alert against the rules that need no outside context."""
    env = gate.Envelope(cap_xml=xml, profile=profile, event_inputs=inputs or [],
                        ai=_declared_ai(xml))
    verdicts = gate.check(env, stage="release")
    # Without the operator's console we can't know the requested area, issuer register or keys:
    keep = []
    for v in verdicts:
        if v.rule in ("R1", "R5") and v.status == gate.FAIL:
            v.status, v.detail = gate.PENDING, v.detail + " (needs the issuer's console to confirm)"
        if v.rule == "R8" and v.status == gate.FAIL:
            # today's alerts can't carry the proposed profile; show the gap without blocking on it
            v.status, v.detail = gate.WARN, ("this alert does not say whether AI was involved or who approved it. "
                                             "No standard field exists yet (proposed profile, gap G1): " + v.detail)
        keep.append(v)
    return {"verdicts": [v.as_dict() for v in keep], "decision": gate.decision(keep)}


def _declared_ai(xml: str) -> dict:
    try:
        alert = cap.parse(xml)
    except Exception:
        return {"involvement": "none", "machine_translated": []}
    params = {n: v for i in alert.get("info", []) for n, v in i.get("parameters", [])}
    inv = params.get(gate.P_AI, "none")
    mt = [x for x in (params.get(gate.P_MT) or "").split(",") if x]
    return {"involvement": inv if inv in gate.AI_VALUES else "none", "machine_translated": mt}
