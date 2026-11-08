"""The two model-backed agents. Neither can send anything: they only propose text.

Drafter: event inputs -> English alert fields.
Translator: English alert -> other languages, using a vetted template when one fits.
"""
from __future__ import annotations

import json
import re

from .llm import call_json

DRAFTER_SYSTEM = """You draft public warning messages for a national alerting authority.
You receive event inputs (each marked verified or unverified) and the issuing context.
Write one alert in English as CAP 1.2 fields.

- Use only facts present in the verified inputs. Do not add places, numbers, times or hazards that are not there.
- Leave unverified inputs out of the alert, and say why in `left_out`.
- `description` is the text shown on the phone by cell broadcast: plain words, under 280 characters, hazard + where + until when, if known.
- `instruction` is the protective action in one or two short sentences.
- Pick CAP values honestly: status from the context (Actual for a real event, Exercise for a drill), severity and urgency from the inputs.
- `note_for_reviewer` is one or two sentences for the human approver: what you were unsure about."""

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["Actual", "Exercise", "System", "Test", "Draft"]},
        "msgType": {"type": "string", "enum": ["Alert", "Update", "Cancel"]},
        "category": {"type": "string", "enum": ["Geo", "Met", "Safety", "Security", "Rescue", "Fire", "Health",
                                                  "Env", "Transport", "Infra", "CBRNE", "Other"]},
        "event": {"type": "string"},
        "urgency": {"type": "string", "enum": ["Immediate", "Expected", "Future", "Past", "Unknown"]},
        "severity": {"type": "string", "enum": ["Extreme", "Severe", "Moderate", "Minor", "Unknown"]},
        "certainty": {"type": "string", "enum": ["Observed", "Likely", "Possible", "Unlikely", "Unknown"]},
        "headline": {"type": "string"},
        "description": {"type": "string"},
        "instruction": {"type": "string"},
        "left_out": {"type": "array", "items": {"type": "string"}},
        "note_for_reviewer": {"type": "string"},
    },
    "required": ["status", "msgType", "category", "event", "urgency", "severity", "certainty", "headline",
                 "description", "instruction", "left_out", "note_for_reviewer"],
    "additionalProperties": False,
}

TRANSLATOR_SYSTEM = """You translate public warning messages.
For each target language, first look at the vetted templates provided. When a template's hazard is the same
hazard as the alert's event, you must use it, even if its wording is longer or more general than the English: return method "template", its id, and the slot values. Slot values stay as in the English
alert (agency name, place, time, URL), because the vetted templates keep their fill-in elements untranslated.
If the English gives no URL, use the issuer's public site given in the input. Only if no template fits, translate the
English text yourself (method "machine"). Keep every number and time exactly as in the English.
Never add information that is not in the English text."""

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "versions": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "method": {"type": "string", "enum": ["template", "machine"]},
                "template_id": {"type": "string"},
                "slots": {"type": "array", "items": {"type": "object", "properties": {
                    "slot": {"type": "string"}, "value": {"type": "string"}},
                    "required": ["slot", "value"], "additionalProperties": False}},
                "headline": {"type": "string"},
                "description": {"type": "string"},
                "instruction": {"type": "string"},
            },
            "required": ["language", "method", "template_id", "slots", "headline", "description", "instruction"],
            "additionalProperties": False,
        }},
    },
    "required": ["versions"],
    "additionalProperties": False,
}


def draft(inputs: list[dict], context: dict, salt: str = "") -> tuple[dict, dict]:
    lines = [f"Issuer: {context.get('issuer_name') or context.get('issuer')}",
             f"Context: {'EXERCISE / DRILL' if context.get('exercise') else 'real event'}",
             f"Target area (chosen by the operator): {context.get('areaDesc', 'not given')}",
             "", "Event inputs:"]
    for n, item in enumerate(inputs, 1):
        tag = "verified" if item.get("verified", True) else "UNVERIFIED"
        lines.append(f"{n}. [{tag}; {item.get('source', 'source not given')}] {item['text']}")
    return call_json(DRAFTER_SYSTEM, "\n".join(lines), DRAFT_SCHEMA, salt=salt)


def fill_template(text: str, slots: dict) -> str:
    def sub(m):
        return slots.get(m.group(0)) or slots.get(m.group(0).strip("[]")) or m.group(0)
    return re.sub(r"\[[^\]]+\]", sub, text)


def translate(english: dict, languages: list[str], templates: list[dict], salt: str = "") -> tuple[list[dict], dict]:
    usable = [t for t in templates if t["language"] in languages]
    user = json.dumps({"english": {k: english[k] for k in ("event", "headline", "description", "instruction")},
                       "target_languages": languages,
                       "vetted_templates": [{"id": t["id"], "language": t["language"], "hazard": t.get("hazard"),
                                             "text": t["text"]} for t in usable]},
                      ensure_ascii=False, indent=1)
    data, meta = call_json(TRANSLATOR_SYSTEM, user, TRANSLATE_SCHEMA, salt=salt)
    out = []
    by_id = {t["id"]: t for t in usable}
    for v in data["versions"]:
        if v["method"] == "template" and v["template_id"] in by_id:
            # the template text is filled by code, word for word; the model only picks it and its slot values
            t = by_id[v["template_id"]]
            v = {**v, "description": fill_template(t["text"], {s["slot"]: s["value"] for s in v["slots"]})}
        else:
            v = {**v, "method": "machine"}
        out.append(v)
    return out, meta
