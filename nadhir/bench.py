"""Replay bench. python -m nadhir.bench  [--live]

1. Real failures (bench/incidents/*.yaml, facts only, each with a source) are rebuilt as CAP and run
   through the gate as sent. The rules that fire are compared with the official finding's rule(s).
2. The AI drafter gets the same inputs; we record what an ungoverned pipeline would have sent and
   what the governed one does (gate feedback, scripted approvals labelled as scripted).
3. UAE scenarios (bench/scenarios/*.yaml, ours, labelled) run 3 times each, gate off vs on.

Replay configuration that is ours, not a fact (issuer registers, keys, approver counts when unknown)
lives in bench/contexts.yaml so it never mixes with the sourced facts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from . import cap, gate, keys, pipeline
from .log import AuditLog, verify

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs" / "bench"
WEB = ROOT / "web" / "results"
CONTENT_RULES = {"R0", "R2", "R3", "R4", "R6", "R7", "R9", "R10", "R11"}  # what the public would actually receive
RUNS = 3


def load_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def contexts() -> dict:
    p = ROOT / "bench" / "contexts.yaml"
    return load_yaml(p) or {} if p.exists() else {}


def _area(a: dict | None) -> dict:
    a = a or {}
    geos = a.get("geocodes") or []
    norm = []
    for g in geos:
        if isinstance(g, dict):
            norm.append([g.get("valueName") or g.get("name"), str(g.get("value"))])
        elif isinstance(g, (list, tuple)):
            norm.append([g[0], str(g[1])])
        else:
            norm.append(["CODE", str(g)])
    polys = a.get("polygon") or a.get("polygons") or []
    if isinstance(polys, str):
        polys = [polys]
    return {"areaDesc": a.get("areaDesc") or a.get("description") or "", "geocodes": norm, "polygons": polys}


def defaults(inc: dict, ctx: dict) -> dict:
    """Replay settings. Anything the public record leaves unknown is set in the alert's favour,
    so the gate never gets credit for catching something nobody knows happened."""
    m, i = inc["real_message"], inc["inputs"]
    sender = m.get("sender") or i.get("issuer") or "unknown"
    signed = m.get("signed")
    d = {
        "sender": sender,
        "issuers": {sender: {"name": sender, "level": 1, "areas": ["*"], "categories": ["*"]}},
        "registered": [sender],
        # unknown or true: signed with the sender's registered key (R5 passes); false: unsigned
        "signed_by": sender if signed in (True, None, "unknown") else None,
        "exercise": i.get("intended_status") in ("Exercise", "Test"),
        "requested_area": i.get("requested_area"),
        "approvals_count": m.get("approvals_count") if isinstance(m.get("approvals_count"), int) else None,
    }
    d.update(ctx)
    return d


def _check_message(inc, d, m, ident, msg_type="Alert", status=None):
    sender = d["sender"]
    area = _area(m.get("area") or inc["real_message"].get("area") or {"areaDesc": m.get("areaDesc")})
    rm = inc["real_message"]
    info = {"language": m.get("language") or rm.get("language") or "en-US",
            "category": [m.get("category") or rm.get("category") or "Other"],
            "event": m.get("event") or rm.get("event") or "Alert",
            "urgency": m.get("urgency") or rm.get("urgency") or "Unknown",
            "severity": m.get("severity") or rm.get("severity") or "Unknown",
            "certainty": m.get("certainty") or rm.get("certainty") or "Unknown",
            "headline": m.get("headline") or "", "description": m.get("text_verbatim") or m.get("description") or "",
            "instruction": m.get("instruction") or "", "parameters": [],
            "areas": [{"areaDesc": area["areaDesc"] or "not recorded", "polygons": area["polygons"],
                       "geocodes": [tuple(g) for g in area["geocodes"]]}]}
    alert = {"identifier": ident, "sender": sender, "sent": d.get("sent", "2020-01-01T00:00:00+00:00"),
             "status": status or m.get("status") or "Actual", "msgType": m.get("msgType") or msg_type,
             "scope": m.get("scope") or "Public", "info": [info]}
    if m.get("references"):
        alert["references"] = m["references"]
    xml = cap.build(alert)
    if d.get("signed_by"):
        key_pem, cert_pem = keys.ensure(d["signed_by"])
        xml = cap.sign(xml, key_pem, cert_pem)
    n = d.get("approvals_count")
    approvals = [{"name": f"operator {k + 1}", "role": "operator"} for k in range(n)] if isinstance(n, int) else []
    req = d.get("requested_area")
    env = gate.Envelope(
        cap_xml=xml, profile=d.get("profile", "GENERIC"), event_id=inc["id"],
        environment=inc["inputs"].get("environment", "live"), exercise=bool(d.get("exercise")),
        requested_area=({**_area(req), **{k: req[k] for k in ("event_id", "origin") if k in req}} if req else None),
        approvals=approvals, issuers=d["issuers"], active_alerts=d.get("active_alerts", []),
        prior_alerts=d.get("prior_alerts", []),
        registered_certs={s: [keys.ensure(s)[1]] for s in d.get("registered", [])}, historic=True,
    )
    verdicts = gate.check(env, "release")
    if n is None:  # approver count not public: don't let R1 count against the alert
        verdicts = [v if v.rule != "R1" else gate._v("R1", gate.NA, "number of approvers not public") for v in verdicts]
    return xml, verdicts


def as_sent(inc: dict, ctx: dict) -> dict:
    """Rebuild the real message (and any public correction) as CAP and run the release check."""
    d = defaults(inc, ctx)
    xml, verdicts = _check_message(inc, d, inc["real_message"], f"{inc['id']}-as-sent")
    failed = [v.rule for v in verdicts if v.status == gate.FAIL]
    corrections = []
    for k, c in enumerate(inc.get("corrections") or []):
        if not c.get("text_verbatim"):
            continue
        cm = {"text_verbatim": c["text_verbatim"], "msgType": c.get("msgType", "Alert"),
              "severity": c.get("severity", "Minor"), "urgency": "Immediate", "certainty": "Observed"}
        # a correction should reach the same people as the alert it corrects, from whoever sent it
        rm = inc["real_message"]
        csender = c.get("sender") or d["sender"]
        cd = {**d, "exercise": False, "approvals_count": None, "sender": csender,
              "requested_area": rm.get("area"), "signed_by": csender,
              "registered": list(set(d.get("registered", [])) | {csender}),
              "issuers": {**d["issuers"], csender: d["issuers"].get(csender) or
                          {"name": csender, "level": 1, "areas": ["*"], "categories": ["*"]}}}
        _, cv = _check_message(inc, cd, cm, f"{inc['id']}-correction-{k + 1}")
        cf = [v.rule for v in cv if v.status == gate.FAIL]
        corrections.append({"at": c.get("t"), "text": c["text_verbatim"], "failed": cf,
                            "verdicts": [v.as_dict() for v in cv]})
        failed += [f"{r} (correction)" for r in cf]
    return {"decision": gate.decision(verdicts), "failed": failed, "xml": xml,
            "verdicts": [v.as_dict() for v in verdicts], "corrections": corrections}


def ai_arm(scn: dict, runs: int) -> dict:
    """Same inputs through the AI drafter, gate off vs gate on."""
    out = []
    for r in range(1, runs + 1):
        log = AuditLog()
        st = pipeline.draft_and_review(scn, run=str(r), log=log)
        first = st["first_draft"]["verdicts"]
        ungoverned = sorted({v["rule"] for v in first if v["status"] == gate.FAIL and v["rule"] in CONTENT_RULES})
        approvals = scn.get("approvals_script") or [
            {"name": "scripted approver A", "role": "duty-officer", "scripted": True},
            {"name": "scripted approver B", "role": "supervisor", "scripted": True}]
        if any(v["language"].startswith("ar") and v["method"] == "machine" for v in st["versions"]):
            approvals = approvals + [{"name": "scripted Arabic reviewer", "role": "arabic-reviewer",
                                      "scope": "language:ar", "scripted": True}]
        final = pipeline.approve_and_release(scn, st, approvals, log)
        ok, why = verify(log.records)
        path = OUT / "logs" / f"{scn['event_id']}-run{r}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in log.records), encoding="utf-8")
        out.append({"run": r, "ungoverned_violations": ungoverned, "attempts": st["attempts"],
                    "review_decision": st["decision"], "final_decision": final["decision"],
                    "final_failed": [v["rule"] for v in final["verdicts"] if v["status"] == gate.FAIL],
                    "status": st["fields"]["status"], "left_out": st["fields"]["left_out"],
                    "translation": [{"language": v["language"], "method": v["method"], "template": v.get("template_id")}
                                    for v in st["versions"]],
                    "log": str(path.relative_to(ROOT)), "log_check": why if ok else "BROKEN " + why,
                    "english": {k: st["fields"][k] for k in ("headline", "description", "instruction")}})
    released = sum(1 for x in out if x["final_decision"] == "release")
    with_viol = sum(1 for x in out if x["ungoverned_violations"])
    rules = sorted({r for x in out for r in x["ungoverned_violations"]})
    summary = (f"{with_viol}/{len(out)} first drafts broke a rule ({', '.join(rules) or 'none'}); "
               f"with the gate: {released}/{len(out)} released after redraft and approval, "
               f"{len(out) - released} held")
    return {"runs": out, "summary": summary}


def incident_scenario(inc: dict, ctx: dict) -> dict:
    i = inc["inputs"]
    d = defaults(inc, ctx)
    req = d.get("requested_area") or {}
    sender = d["sender"]
    return {
        "event_id": inc["id"], "profile": ctx.get("profile", "GENERIC"), "issuer": sender,
        "issuer_name": ctx.get("issuer_name", sender), "issuers": d["issuers"],
        "exercise": bool(d.get("exercise")), "environment": i.get("environment", "live"),
        "requested_area": {**_area(req), "event_id": inc["id"], "origin": "drawn"},
        "inputs": ctx.get("ai_inputs") or [{"text": i["event_text"], "verified": True, "source": "incident timeline"}],
        "languages": ctx.get("languages", []), "templates": [], "active_alerts": ctx.get("active_alerts", []),
        "prior_alerts": ctx.get("prior_alerts", []), "sent": ctx.get("sent", "2020-01-01T00:00:00+00:00"),
    }


def main(argv: list[str]) -> int:
    run_ai = "--no-ai" not in argv
    ctxs = contexts()
    rows = []
    for p in sorted((ROOT / "bench" / "incidents").glob("*.yaml")):
        inc = load_yaml(p)
        ctx = ctxs.get(inc["id"], {})
        sent = as_sent(inc, ctx)
        expected = inc.get("expected_rules", [])
        fired = {r.split(" ")[0] for r in sent["failed"]}
        caught = sorted(set(expected) & fired)
        match = bool(caught)
        f = inc.get("official_finding") or {}
        row = {"id": inc["id"], "title": inc["title"], "date": str(inc.get("date")),
               "outcome": (inc.get("real_outcome") or {}).get("text", ""),
               "finding": {"body": f.get("body"), "quote": f.get("quote"), "source": f.get("source")},
               "expected": expected, "as_sent": {k: sent[k] for k in ("decision", "failed", "verdicts", "corrections")},
               "match": match, "caught": caught, "missed": sorted(set(expected) - fired), "ai": None}
        if run_ai and not ctx.get("skip_ai"):
            row["ai"] = ai_arm(incident_scenario(inc, ctx), ctx.get("runs", 1))
        rows.append(row)
        print(f"{inc['id']}: as sent {sent['decision']} {sent['failed']} expected {expected} match={match}")
    scen = []
    if run_ai:
        for p in sorted((ROOT / "bench" / "scenarios").glob("*.yaml")):
            scn = load_yaml(p)
            res = ai_arm(scn, scn.get("runs", RUNS))
            scen.append({"id": scn["event_id"], "title": scn.get("title"), "label": scn.get("label"), **res})
            print(f"{scn['event_id']}: {res['summary']}")
    result = {"incidents": rows, "scenarios": scen,
              "matched": sum(r["match"] for r in rows), "total": len(rows),
              "note": "Replays are rebuilt from public reports, not the original systems. Approvals in AI runs are "
                      "scripted and labelled as such; in the live demo a person clicks."}
    OUT.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    slim = {**result, "incidents": [{**r, "as_sent": {k: r["as_sent"][k] for k in ("decision", "failed")}} for r in rows]}
    (WEB / "bench.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"official finding matched: {result['matched']}/{result['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
