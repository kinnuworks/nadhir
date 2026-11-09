"""The pre-broadcast gate. Deterministic: no model call happens in here.

Every rule returns a verdict with the sources it rests on. An alert is released only when
no rule fails and nothing is pending (for example a missing human approval).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from . import cap, kb

PASS, FAIL, PENDING, WARN, NA = "pass", "fail", "pending", "warn", "n/a"

P = "AIPROV:0.1:"  # proposed parameter prefix (our draft profile, see docs/cap-ai-provenance-profile.md)
P_AI, P_MODEL, P_MT = P + "AIInvolvement", P + "AIModel", P + "MachineTranslated"
P_APPROVED_BY, P_APPROVAL_COUNT = P + "ApprovedBy", P + "ApprovalCount"
AI_VALUES = {"none", "assisted", "translated", "generated"}

PROFILES = {
    # max_pages: 3GPP TS 23.041 allows up to 15 pages. advised_pages: a 2015 summary of the TDRA handset spec
    # (TDRA-TS040, secondary) says 1 page; the current primary spec (TDRA-TSFS001, 2019) sets no page limit.
    "UAE": {"languages": ["ar", "en"], "max_pages": 15, "advised_pages": 1, "max_chars": None,
            "gazetteer": ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Umm Al Quwain", "Ras Al Khaimah",
                          "Fujairah", "Al Ain", "Khor Fakkan", "Kalba", "Liwa", "Ruwais", "Hatta",
                          "Al Dhafra", "Dibba", "Madinat Zayed", "Mussafah", "Jebel Ali"]},
    "US": {"languages": ["en"], "max_pages": None, "advised_pages": None, "max_chars": 360, "gazetteer": []},
    "GENERIC": {"languages": [], "max_pages": 15, "advised_pages": None, "max_chars": None, "gazetteer": []},
}

RULES = {
    "R0": ("Valid CAP 1.2 (ITU-T X.1303bis) message", ["CAP12", "X1303BIS", "CAPXSD"]),
    "R1": ("Two named people approve a high-impact live alert", ["FCC-HI-2018", "UAE-AI-CHARTER"]),
    "R2": ("Status matches reality: no drill sent live, no 'not a drill' in a drill", ["FCC-HI-2018", "INDIA-2023", "CAP12", "TDRA-TSFS001"]),
    "R3": ("Area sent is the area requested, for this event", ["LA-2025", "JALERT-2022", "CAP12"]),
    "R4": ("Sender may warn for this hazard and area", ["UAE-PORTAL-EWS", "UAE-ISSUERS", "SEOUL-2023"]),
    "R5": ("Signed by a registered originator key", ["CAP12", "IPAWS-OPEN", "BRAZIL-2026"]),
    "R6": ("Fits the cell broadcast page budget", ["TS23041", "TS23038", "TDRA-TS040", "FCC-16-127"]),
    "R7": ("Required languages present", ["TDRA-TSFS001", "TDRA-TS040", "TDRA-2017-CB"]),
    "R8": ("AI involvement and approvers recorded in the alert", ["CAPCP", "ESTR-AICNHM", "MHEWS-2026", "UAE-AI-CHARTER"]),
    "R9": ("Machine translation: vetted template or named language approver", ["FCC-DA-25-12", "FCC-23-88"]),
    "R10": ("Corrections reference the alert they correct", ["CAP12", "FCC-HI-2018"]),
    "R11": ("No detail the inputs don't contain", ["ESTR-AICNHM", "UAE-AI-CHARTER"]),
}

DRILL_IN_LIVE = re.compile(r"exercise[, ]+exercise|this is a drill|this is an exercise|test message|"
                           r"this is a test", re.I)
# US EAS scheduled tests (RWT/RMT, practice/demo) go out as status Actual by convention so stations relay them.
EAS_TEST = re.compile(r"(required|routine) (weekly|monthly) test|^\s*R[WM]T\s*$|practice/demo|demonstration message", re.I)
NOT_A_DRILL = re.compile(r"not a drill|not an exercise|this is not a test|this is real", re.I)
TEST_MARKERS = re.compile(r"\btest\b|\bexercise\b|\bdrill\b|تجريبي|تجربة|اختبار|تمرين|परीक्षण", re.I)
CORRECTION_WORDS = re.compile(r"false alarm|disregard|cancel(l?ed)?\b|no (missile )?threat|sent in error|"
                              r"erroneous|تجاهل|إنذار كاذب|إلغاء", re.I)
HAZARD_TERMS = ["dam", "missile", "tsunami", "chemical", "explosion", "nuclear", "radiation", "earthquake",
                "fire", "wildfire", "flood", "landslide", "shooting", "terror", "gas leak", "evacuat",
                "storm", "dust", "fog", "hail", "cyclone", "hurricane", "heat"]
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUM_RE = re.compile(r"\d+(?:[:.]\d+)?")
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ"
           "ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM7_EXT = set("^{}\\[~]|€\f")


@dataclass
class Envelope:
    """Everything the gate needs besides the CAP XML itself."""
    cap_xml: str
    profile: str = "UAE"
    event_id: str | None = None
    environment: str = "live"            # live | test (where the console is pointed)
    exercise: bool = False                # the triggering context is a drill or exercise
    requested_area: dict | None = None    # {areaDesc, geocodes: [[name, value]], polygons: [], event_id, origin}
    approvals: list = field(default_factory=list)       # [{name, role, kind: human, scope: release|language:xx, at}]
    event_inputs: list = field(default_factory=list)    # source texts the draft must stay inside
    issuers: dict = field(default_factory=dict)         # sender -> {name, level, areas: [...] or ["*"], categories}
    active_alerts: list = field(default_factory=list)   # [{sender, event, geocodes, level}]
    prior_alerts: list = field(default_factory=list)    # [{identifier, sender, sent}]
    vetted_templates: list = field(default_factory=list)  # [{id, language, text}]
    registered_certs: dict = field(default_factory=dict)  # sender -> [cert pem bytes]
    ai: dict = field(default_factory=lambda: {"involvement": "none", "machine_translated": [], "model": None})
    historic: bool = False                # a replay of a real past alert (proposed profile not in force)


@dataclass
class Verdict:
    rule: str
    status: str
    detail: str
    title: str = ""
    sources: list = field(default_factory=list)

    def as_dict(self):
        return {"rule": self.rule, "title": self.title, "status": self.status, "detail": self.detail,
                "sources": [kb.cite(s) for s in self.sources]}


def _v(rule, status, detail):
    title, sources = RULES[rule]
    return Verdict(rule, status, detail, title, sources)


def _texts(info):
    return " ".join(x for x in (info.get("headline"), info.get("description"), info.get("instruction")) if x)


def _lang(info):
    return (info.get("language") or "en-US").split("-")[0].lower()


def _area_keys(areas):
    keys = set()
    for a in areas:
        for name, value in a.get("geocodes", []):
            keys.add(f"{name}={value}")
        for poly in a.get("polygons", []):
            keys.add("polygon:" + " ".join(poly.split()))
    return keys


def _humans(approvals, scope="release"):
    return sorted({a["name"] for a in approvals
                   if a.get("kind", "human") == "human" and a.get("scope", "release") == scope and a.get("name")})


def check(env: Envelope, stage: str = "release") -> list[Verdict]:
    """stage='review': before people approve (missing approvals/signature are pending).
    stage='release': the final check right before broadcast (missing means fail)."""
    missing = PENDING if stage == "review" else FAIL
    prof = PROFILES.get(env.profile, PROFILES["GENERIC"])
    out: list[Verdict] = []

    errors = cap.validate(env.cap_xml)
    out.append(_v("R0", FAIL if errors else PASS, "; ".join(errors[:3]) if errors else "valid against the official CAP 1.2 schema"))
    try:
        alert = cap.parse(env.cap_xml)
    except Exception as e:  # not parseable at all: nothing else can run
        out.append(_v("R0", FAIL, f"could not parse: {e}"))
        return out
    infos = alert.get("info", [])
    status = alert.get("status", "")
    severities = {i.get("severity") for i in infos}
    all_text = " ".join(_texts(i) for i in infos)

    # R1: approvals
    high_impact = status == "Actual" and bool(severities & {"Extreme", "Severe"})
    need = 2 if high_impact else 1
    names = _humans(env.approvals)
    if len(names) >= need:
        out.append(_v("R1", PASS, f"{len(names)} named approver(s): {', '.join(names)} (needed {need})"))
    else:
        why = "a high-impact live alert" if high_impact else "any alert"
        out.append(_v("R1", missing, f"{len(names)} of {need} human approvals for {why}"))

    # R2: status consistency
    problems = []
    if status == "Actual" and env.environment == "test":
        problems.append("status Actual sent from a test environment")
    if status == "Actual" and env.exercise:
        problems.append("the triggering event is an exercise, but the alert is marked Actual")
    if status in ("Exercise", "Test") and NOT_A_DRILL.search(all_text):
        problems.append(f"status {status} but the text says it is not a drill")
    us_scheduled_test = env.profile == "US" and any(EAS_TEST.search(i.get("event") or "") for i in infos)
    if status == "Actual" and DRILL_IN_LIVE.search(all_text) and not us_scheduled_test:
        problems.append("status Actual but the text reads like a drill or test")
    if status in ("Exercise", "Test") and alert.get("scope") == "Public":
        unmarked = [_lang(i) for i in infos if not TEST_MARKERS.search(_texts(i))]
        if unmarked:
            problems.append(f"public {status} message does not say so in: {', '.join(unmarked)}")
        if "Extreme" in severities:
            problems.append(f"{status} message carries severity Extreme")
    out.append(_v("R2", FAIL if problems else PASS, "; ".join(problems) or f"status {status} is consistent with the context"))

    # R3: area
    sent = set()
    no_area = [_lang(i) for i in infos if not _area_keys(i.get("areas", []))]
    for i in infos:
        sent |= _area_keys(i.get("areas", []))
    problems = []
    if no_area:
        problems.append(f"no polygon or geocode in: {', '.join(no_area)}")
    req = env.requested_area
    if req:
        want = _area_keys([req])
        if want and sent != want:
            extra, lost = sorted(sent - want), sorted(want - sent)
            if extra:
                problems.append(f"sent to areas not requested: {', '.join(extra[:6])}")
            if lost:
                problems.append(f"requested areas missing from the alert: {', '.join(lost[:6])}")
        if req.get("origin") in ("drill", "template", "previous"):
            problems.append(f"target area was loaded from a {req['origin']}, not drawn for this event")
        if req.get("event_id") and env.event_id and req["event_id"] != env.event_id:
            problems.append(f"target area belongs to event {req['event_id']}, not {env.event_id}")
    out.append(_v("R3", FAIL if problems else PASS, "; ".join(problems) or f"area matches the request ({len(sent)} area keys)"))

    # R4: issuer authority
    sender = alert.get("sender", "")
    who = env.issuers.get(sender)
    problems = []
    if not env.issuers:
        out.append(_v("R4", NA, "no issuer register supplied"))
    else:
        if not who:
            problems.append(f"sender {sender!r} is not in the issuer register")
        else:
            areas = who.get("areas", ["*"])
            if "*" not in areas:
                outside = sorted(k for k in sent if k not in areas)
                if outside:
                    problems.append(f"{who.get('name', sender)} may not warn for: {', '.join(outside[:5])}")
            cats = who.get("categories", ["*"])
            got = {c for i in infos for c in (i.get("category") or [])}
            if "*" not in cats and got - set(cats):
                problems.append(f"category {', '.join(sorted(got - set(cats)))} is outside this sender's remit")
            for act in env.active_alerts:
                if act.get("level", 9) < who.get("level", 9) and act.get("sender") != sender:
                    theirs = set(f"{n}={v}" for n, v in act.get("geocodes", []))
                    beyond = sorted(sent - theirs)
                    if beyond:
                        problems.append(f"a higher authority ({act.get('name', act.get('sender'))}) has an active "
                                        f"alert for this event; this one goes beyond its area ({', '.join(beyond[:4])}); "
                                        "escalate before sending")
        out.append(_v("R4", FAIL if problems else PASS, "; ".join(problems) or f"{who.get('name', sender)} is registered for this hazard and area"))

    # R5: signature
    if not alert.get("signed"):
        out.append(_v("R5", missing, "not signed (signing happens after approval)" if stage == "review" else "no XML signature"))
    else:
        certs = env.registered_certs.get(sender, [])
        ok, why = cap.verify(env.cap_xml, certs) if certs else (False, f"no registered key for sender {sender!r}")
        out.append(_v("R5", PASS if ok else FAIL, why))

    # R6: bearer length
    problems, notes, pages_seen = [], [], []
    for i in infos:
        # US alerts carry the phone text in the IPAWS profile's CMAMlongtext / CMAMtext parameters
        wea = dict(i.get("parameters", []))
        lang = _lang(i)
        if env.profile == "US":
            text = wea.get("CMAMlongtext") or wea.get("CMAMtext")
            if not text:
                notes.append(f"{lang}: no WEA phone text (CMAMtext); not a phone broadcast")
                continue
        else:
            text = i.get("description") or ""
        if prof["max_chars"] and len(text) > prof["max_chars"]:
            problems.append(f"{lang}: {len(text)} characters, limit {prof['max_chars']}")
        gsm = all(c in GSM7 or c in GSM7_EXT for c in text)
        units = sum(2 if c in GSM7_EXT else 1 for c in text) if gsm else len(text)
        pages = max(1, math.ceil(units / (93 if gsm else 41)))
        pages_seen.append(pages)
        notes.append(f"{lang}: {len(text)} chars, {'GSM-7' if gsm else 'UCS-2'}, {pages} page(s)")
        if prof["max_pages"] and pages > prof["max_pages"]:
            problems.append(f"{lang}: {pages} pages, limit {prof['max_pages']}")
    status6 = FAIL if problems else PASS
    if not problems and prof["advised_pages"] and any(n > prof["advised_pages"] for n in pages_seen):
        status6 = WARN
        notes.append(f"longer than the {prof['advised_pages']}-page advice in the handset spec summary")
    out.append(_v("R6", status6, "; ".join(problems or notes)))

    # R7: languages
    need_langs = prof["languages"]
    have = {_lang(i) for i in infos}
    lacking = [x for x in need_langs if x not in have]
    out.append(_v("R7", FAIL if lacking else (PASS if need_langs else NA),
                  f"missing: {', '.join(lacking)}" if lacking else f"languages present: {', '.join(sorted(have))}"))

    # R8: provenance (proposed profile)
    involvement = (env.ai or {}).get("involvement", "none")
    if env.historic:
        out.append(_v("R8", NA, "historic alert: the proposed provenance profile was not in force"))
    else:
        params = {}
        for i in infos:
            for n, v in i.get("parameters", []):
                params.setdefault(n, v)
        problems = []
        declared = params.get(P_AI)
        if declared is None:
            problems.append(f"no {P_AI} parameter")
        elif declared not in AI_VALUES:
            problems.append(f"{P_AI}={declared!r} is not one of {sorted(AI_VALUES)}")
        elif declared != involvement:
            problems.append(f"alert says {P_AI}={declared} but the pipeline recorded {involvement}")
        mt = (env.ai or {}).get("machine_translated") or []
        if mt and set((params.get(P_MT) or "").split(",")) != set(mt):
            problems.append(f"{P_MT} should list {','.join(mt)}")
        stat = FAIL if problems else PASS
        if not problems:
            appr = params.get(P_APPROVED_BY)
            if not appr:
                stat = missing
                problems.append("approvers not yet recorded (added at approval, then signed)")
            elif params.get(P_APPROVAL_COUNT) != str(len(names)):
                stat = FAIL
                problems.append(f"{P_APPROVAL_COUNT}={params.get(P_APPROVAL_COUNT)} but {len(names)} people approved")
        out.append(_v("R8", stat, "; ".join(problems) or f"{P_AI}={declared}; approvers recorded and bound by the signature"))

    # R9: machine translation
    mt = (env.ai or {}).get("machine_translated") or []
    if not mt:
        out.append(_v("R9", NA, "no machine-translated language"))
    else:
        source = next((i for i in infos if _lang(i) not in mt), None)
        src_nums = set(NUM_RE.findall((_texts(source) if source else "").translate(AR_DIGITS)))
        problems, pend, ok = [], [], []
        for i in infos:
            lang = _lang(i)
            if lang not in mt:
                continue
            nums = set(NUM_RE.findall(_texts(i).translate(AR_DIGITS)))
            if nums != src_nums:
                problems.append(f"{lang}: numbers differ from the source ({sorted(nums)} vs {sorted(src_nums)})")
                continue
            tmpl = next((t for t in env.vetted_templates if t["language"] == lang
                         and _template_match(t["text"], i.get("description") or "")), None)
            if tmpl:
                ok.append(f"{lang}: matches vetted template {tmpl['id']}")
            elif _humans(env.approvals, f"language:{lang}"):
                ok.append(f"{lang}: approved by {', '.join(_humans(env.approvals, f'language:{lang}'))}")
            else:
                pend.append(f"{lang}: machine translated, no vetted template match and no language approver")
        stat = FAIL if problems else (missing if pend else PASS)
        out.append(_v("R9", stat, "; ".join(problems + pend + ok)))

    # R10: corrections
    refs = (alert.get("references") or "").split()
    mtype = alert.get("msgType")
    if mtype in ("Update", "Cancel"):
        known = {f"{p['sender']},{p['identifier']},{p['sent']}" for p in env.prior_alerts}
        bad = [r for r in refs if r not in known] if known else []
        if not refs:
            out.append(_v("R10", FAIL, f"{mtype} without <references> to the original alert"))
        elif bad:
            out.append(_v("R10", FAIL, f"references an alert this system did not send: {bad[0]}"))
        else:
            out.append(_v("R10", PASS, f"{mtype} references {len(refs)} earlier alert(s)"))
    elif CORRECTION_WORDS.search(all_text):
        out.append(_v("R10", FAIL, "text corrects an earlier alert, but msgType is Alert with no <references>; "
                                    "phones cannot link it to the alert it corrects"))
    else:
        out.append(_v("R10", NA, "not a correction"))

    # R11: grounding (only for AI-written text)
    if involvement in ("none",) or not env.event_inputs:
        out.append(_v("R11", NA, "no AI-written text" if involvement == "none" else "no event inputs supplied"))
    else:
        inputs = " ".join(env.event_inputs).translate(AR_DIGITS).lower()
        problems = []
        source_infos = [i for i in infos if _lang(i) not in mt] or infos
        draft = " ".join(_texts(i) for i in source_infos).translate(AR_DIGITS)
        for n in sorted(set(NUM_RE.findall(draft))):
            if n not in inputs and n.replace(".", ":") not in inputs:
                problems.append(f"number {n} is not in the inputs")
        low = draft.lower()
        for term in HAZARD_TERMS:
            if re.search(r"\b" + term, low) and not re.search(r"\b" + term, inputs):
                problems.append(f"hazard '{term}' is not in the inputs")
        for place in prof["gazetteer"]:
            if place.lower() in low and place.lower() not in inputs:
                problems.append(f"place '{place}' is not in the inputs")
        out.append(_v("R11", FAIL if problems else PASS, "; ".join(problems) or "every number, hazard and listed place is in the inputs"))

    return out


def _template_match(template: str, text: str) -> bool:
    norm = lambda s: " ".join(s.split())
    parts = re.split(r"\[[^\]]+\]", norm(template))
    # a slot holds a short value, never a new sentence: this stops extra text riding inside a slot
    slot = r"((?:(?!\. )[^!?؟\n]){1,80}?)"
    pattern = slot.join(re.escape(p) for p in parts)
    return re.fullmatch(pattern, norm(text)) is not None


def decision(verdicts: list[Verdict]) -> str:
    if any(v.status == FAIL for v in verdicts):
        return "blocked"
    if any(v.status == PENDING for v in verdicts):
        return "waiting"
    return "release"
