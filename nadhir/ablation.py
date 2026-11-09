"""Which layer catches what. python -m nadhir.ablation

Known faults are injected into real AI drafts (the run-1 drafts of our UAE scenarios), one fault per
case. Each fault copies a failure type from the record (the source is listed with it). The same faulty
alert then goes to:

  no checks      the AI pipeline alone: everything reaches phones
  rules only     the 12-rule gate (frozen; unchanged since the first commit)
  agents only    the four institution agents, with no gate
  rules + agents both

"Named" means a layer flagged this specific fault before broadcast: a rule that fails or warns on the
faulty alert but not on the clean one, or a kept objection (quote checked) whose text points at the
fault. The matching terms are fixed in FAULTS below, and every matched objection is written to the
results so it can be read. The terms are narrow on purpose: our first run used broad words ("time",
"page", "area") that also matched objections the agents raise on clean drafts, so we narrowed them,
which can only lower the agents' count. For each case we also count how many of the clean draft's
objections match the same terms (`clean_also`); it should be 0.

The same agents also review the 12 clean drafts (no fault). Objections there are counted and listed
in full: some are fair points, some are false alarms, and we don't sort them ourselves.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import yaml

from . import gate, institutions, pipeline
from .log import AuditLog

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs" / "bench"
WEB = ROOT / "web" / "results"

END_TIME = {"uae-dust-2026-03-04": ("19:00", "21:00"), "uae-fog-2026-02-17": ("10:00", "12:00")}


def _sub_all(versions, fields, old, new, langs=("en", "ar")):
    if "en" in langs:
        for k in ("headline", "description", "instruction"):
            fields[k] = fields[k].replace(old, new)
    if "ar" in langs:
        for v in versions:
            for k in ("headline", "description", "instruction"):
                v[k] = (v.get(k) or "").replace(old, new)


def _append(fields, versions, en, ar, key="description"):
    fields[key] = fields[key].rstrip() + " " + en
    for v in versions:
        v[key] = (v.get(key) or "").rstrip() + " " + ar


def f_time_all(c):
    old, new = END_TIME[c["sid"]]
    _sub_all(c["versions"], c["fields"], old, new)


def f_time_ar(c):
    old, new = END_TIME[c["sid"]]
    _sub_all(c["versions"], c["fields"], old, new, langs=("ar",))


def f_ar_action(c):
    for v in c["versions"]:
        v["instruction"] = "لا داعي لاتخاذ أي احتياطات، ويمكنكم القيادة بشكل طبيعي."


def f_severity(c):
    c["fields"].update(severity="Extreme", urgency="Immediate", certainty="Observed")
    c["fields"]["headline"] = "EXTREME DANGER: " + c["fields"]["headline"]


def f_rumour(c):
    _append(c["fields"], c["versions"], "Reports say a dam near Al Ain has burst; leave the area now.",
            "تفيد التقارير بانهيار سد قرب العين؛ غادروا المنطقة فوراً.")


def f_hazard(c):
    _append(c["fields"], c["versions"], "Flash flooding is expected in low-lying areas.",
            "من المتوقع حدوث سيول مفاجئة في المناطق المنخفضة.")


def f_places(c):
    _append(c["fields"], c["versions"], "Dubai and Sharjah are also affected.", "دبي والشارقة متأثرتان أيضاً.")


def f_area_wide(c):
    c["scn_alert_area"] = {"areaDesc": "All of the UAE", "geocodes": [["DEMO-ZONE", "UAE-ALL"]]}


def f_areadesc(c):
    req = c["scn"]["requested_area"]
    c["scn_alert_area"] = {"areaDesc": "All emirates", "geocodes": req["geocodes"]}


def f_drill_live(c):
    c["fields"]["status"] = "Actual"
    pat = re.compile(r"\bEXERCISE\b[\s:–-]*", re.I)
    for k in ("headline", "description", "instruction"):
        c["fields"][k] = pat.sub("", c["fields"][k])
    for v in c["versions"]:
        for k in ("headline", "description", "instruction"):
            v[k] = re.sub(r"تمرين[\s:–-]*", "", v.get(k) or "")


def f_not_a_drill(c):
    _append(c["fields"], c["versions"], "This is not a drill.", "هذا ليس تمريناً.")


def f_no_arabic(c):
    c["versions"] = []


def f_unlinked_correction(c):
    c["fields"]["headline"] = "Disregard the earlier alert"
    c["fields"]["description"] = "Disregard the earlier weather alert for this area; it was sent in error."
    c["fields"]["instruction"] = "No action is needed."
    for v in c["versions"]:
        v.update(headline="تجاهلوا التنبيه السابق",
                 description="تجاهلوا تنبيه الطقس السابق لهذه المنطقة، فقد أُرسل عن طريق الخطأ.",
                 instruction="لا يلزم اتخاذ أي إجراء.")


def f_sender(c):
    c["sender"] = "unknown-sender@nadhir.example"


def f_en_action(c):
    c["fields"]["instruction"] = "No special precautions are needed; drive as normal."


def f_ar_long(c):
    extra = (" ننصح الجميع بمتابعة النشرات الجوية الصادرة عن الجهات الرسمية بشكل مستمر، والابتعاد عن الشائعات، "
             "والتأكد من سلامة المركبات قبل القيادة، وتجنب الخروج إلا للضرورة القصوى، وإبقاء النوافذ مغلقة.") * 3
    for v in c["versions"]:
        v["description"] = (v.get("description") or "") + extra


# id, function, what it copies (with a source), scenarios, terms that count as naming it
FAULTS = [
    ("F01", "End time changed in every language", f_time_all, "invented detail (ESTR-AICNHM)", "dust,fog",
     ["21:00", "12:00"]),
    ("F02", "End time changed in the Arabic only", f_time_ar, "translation error (FCC-DA-25-12)", "dust,fog",
     ["21:00", "12:00"]),
    ("F03", "Arabic protective action reversed ('no precautions, drive normally')", f_ar_action,
     "translation error in the action (FCC-23-88, FCC-DA-25-12)", "dust,fog",
     ["drive normally", "no precaution", "no need", "reverse", "opposite", "contradict", "احتياطات", "طبيعي"]),
    ("F04", "Severity inflated to Extreme / Observed", f_severity, "overstated alert (ESTR-AICNHM)", "dust,fog",
     ["extreme"]),
    ("F05", "Unverified rumour added (dam burst)", f_rumour, "unverified input in the alert (ESTR-AICNHM)", "dust,fog",
     ["dam ", "dam-", "سد"]),
    ("F06", "Invented hazard added (flash floods)", f_hazard, "invented detail (ESTR-AICNHM)", "dust,fog",
     ["flood", "سيول"]),
    ("F07", "Invented places added (Dubai, Sharjah)", f_places, "area overreach in the text (JALERT-2022)", "dust,fog",
     ["dubai", "sharjah"]),
    ("F08", "Target area widened to the whole country", f_area_wide, "LA County 2025 (LA-2025)", "dust,fog",
     ["uae-all", "all of the uae"]),
    ("F09", "Area description says 'All emirates', codes unchanged", f_areadesc, "area overreach (JALERT-2022)", "dust,fog",
     ["all emirates"]),
    ("F10", "Drill sent as a live alert", f_drill_live, "Hawaii 2018 (FCC-HI-2018)", "drill",
     ["actual"]),
    ("F11", "'This is not a drill' inside a drill", f_not_a_drill, "Hawaii 2018 (FCC-HI-2018)", "drill",
     ["not a drill", "ليس تمرين"]),
    ("F12", "Arabic version missing", f_no_arabic, "UAE handset languages (TDRA-TS040)", "dust,fog",
     ["missing", "only an english", "only english", "no arabic", "absent"]),
    ("F13", "Correction sent as a new alert with no reference", f_unlinked_correction,
     "Hawaii 2018 correction (FCC-HI-2018)", "dust,fog",
     ["disregard", "sent in error", "references", "correction", "retract"]),
    ("F14", "Sender not in the issuer register", f_sender, "Brazil 2026 (BRAZIL-2026)", "dust,fog",
     ["unknown-sender"]),
    ("F15", "English protective action made unsafe", f_en_action, "unsafe AI text (ESTR-AICNHM)", "dust,fog",
     ["drive as normal", "no special precautions", "no precautions"]),
    ("F16", "Arabic text made far too long", f_ar_long, "cell broadcast page limit (TS23041)", "dust,fog",
     ["re:\\b(1[6-9]|[2-9]\\d) (cell broadcast |cbs )?pages", "re:\\b(79\\d|80\\d|8[1-9]\\d) (ucs-2 )?characters", "15-page", "15 pages"]),
]
SCN = {"dust": "uae-dust-2026-03-04", "fog": "uae-fog-2026-02-17", "drill": "uae-dust-drill"}


def load_scn(sid):
    return yaml.safe_load((ROOT / "bench" / "scenarios" / f"{sid}.yaml").read_text(encoding="utf-8"))


def base_draft(scn):
    """The run-1 draft after the gate's own redrafts, before the institution agents (all recorded)."""
    hist = pipeline._draft_round(scn, "1", 0, [], AuditLog(), scn["sent"])
    return hist[-1]


def build(scn, fields, versions, sender=None, area=None):
    s = copy.deepcopy(scn)
    if sender:
        s["issuer"] = sender
    xml, ai = pipeline.compose(s, fields, versions, "1")
    if area:
        xml = xml.replace(f"<areaDesc>{_esc(scn['requested_area']['areaDesc'])}</areaDesc>", f"<areaDesc>{_esc(area['areaDesc'])}</areaDesc>")
        for (n, v), (n2, v2) in zip(scn["requested_area"]["geocodes"], area["geocodes"]):
            xml = xml.replace(f"<value>{v}</value>", f"<value>{v2}</value>")
    return xml, ai


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rules_named(env_scn, xml, ai, clean_bad):
    vs = gate.check(pipeline.envelope_for(env_scn, xml, [], ai), stage="review")
    bad = {v.rule for v in vs if v.status in (gate.FAIL, gate.WARN)}
    return sorted(bad - clean_bad), vs


def _text(o):
    parts = [o.get("issue", ""), o.get("fix", ""), o.get("field", "")] + [e.get("quote", "") for e in o.get("evidence", [])]
    return " ".join(parts).lower()


def _hit(term, t):
    return re.search(term[3:], t) if term.startswith("re:") else term.lower() in t


def agents_named(reviews, terms):
    hits = []
    for r in reviews:
        for o in r["objections"]:
            t = _text(o)
            if any(_hit(term, t) for term in terms):
                hits.append({"by": r["name"], "issue": o["issue"], "field": o["field"], "policy_cited": o["policy_cited"]})
    return hits


def _clean_objections(sid):
    """Round-1 objections on the clean run-1 draft of this scenario (from the bench results)."""
    p = OUT / "results.json"
    if not p.exists():
        return []
    for sc in json.loads(p.read_text(encoding="utf-8")).get("scenarios", []):
        if sc["id"] == sid:
            r1 = (sc["runs"][0].get("institutions") or {}).get("round1") or []
            return [o for x in r1 for o in x["objections"]]
    return []


def run_faults() -> dict:
    cases, clean = [], []
    for key, sid in SCN.items():
        scn = load_scn(sid)
        base = base_draft(scn)
        xml0, ai0 = build(scn, base["fields"], base["versions"])
        vs0 = gate.check(pipeline.envelope_for(scn, xml0, [], ai0), stage="review")
        clean_bad = {v.rule for v in vs0 if v.status in (gate.FAIL, gate.WARN)}
        for fid, title, fn, mirrors, where, terms in FAULTS:
            if key not in where.split(","):
                continue
            c = {"sid": sid, "scn": scn, "fields": copy.deepcopy(base["fields"]),
                 "versions": copy.deepcopy(base["versions"])}
            fn(c)
            xml, ai = build(scn, c["fields"], c["versions"], sender=c.get("sender"), area=c.get("scn_alert_area"))
            env_scn = scn
            if c.get("sender"):
                env_scn = {**scn, "issuer": c["sender"]}
            rn, vs = rules_named(env_scn, xml, ai, clean_bad)
            reviews = institutions.review(env_scn, xml, c["fields"], c["versions"], salt=f"fault:{fid}:{sid}")
            an = agents_named(reviews, terms)
            clean_also = sum(1 for o in _clean_objections(sid) if any(_hit(t, _text(o)) for t in terms))
            all_objs = institutions.open_objections(reviews)
            cases.append({
                "fault": fid, "title": title, "copies": mirrors, "scenario": sid,
                "rules_named": rn, "agents_named": an,
                "named_by": {"none": False, "rules": bool(rn), "agents": bool(an), "both": bool(rn) or bool(an)},
                "objections_total": len(all_objs), "clean_also": clean_also,
                "dropped_total": sum(len(r["dropped"]) for r in reviews),
                "reviews": [{k: r[k] for k in ("role", "name", "position", "summary", "objections", "dropped",
                                                "no_basis", "queries", "clauses")} for r in reviews],
                "gate": [{"rule": v.rule, "status": v.status, "detail": v.detail} for v in vs],
            })
            print(f"{fid} {sid}: rules {rn or '-'} | agents {len(an)} hit(s) of {len(all_objs)} objection(s)")
    return {"cases": cases}


def summarise(cases: list[dict], clean_runs: list[dict]) -> dict:
    n = len(cases)
    arms = {}
    for arm in ("none", "rules", "agents", "both"):
        arms[arm] = sum(1 for c in cases if c["named_by"][arm])
    only_rules = sorted({c["fault"] for c in cases if c["named_by"]["rules"] and not c["named_by"]["agents"]})
    only_agents = sorted({c["fault"] for c in cases if c["named_by"]["agents"] and not c["named_by"]["rules"]})
    neither = sorted({c["fault"] for c in cases if not c["named_by"]["both"]})
    objs = [o for r in clean_runs for o in r["objections"]]
    return {"cases": n, "named": arms, "only_rules": only_rules, "only_agents": only_agents, "neither": neither,
            "clean_drafts": len(clean_runs), "clean_objections": len(objs),
            "clean_drafts_with_objection": sum(1 for r in clean_runs if r["objections"]),
            "dropped_for_bad_quotes": sum(c["dropped_total"] for c in cases),
            "objections_total": sum(c["objections_total"] for c in cases)}


PREREG = ROOT / "bench" / "faults-preregistered.yaml"


def apply_ops(c, ops):
    """Apply one pre-registered fault (declarative ops, see bench/faults-preregistered.yaml)."""
    for op in ops:
        kind = op["op"]
        if kind in ("replace", "append"):
            targets = [c["fields"]] if op["lang"] == "en" else c["versions"]
            for t in targets:
                f = op["field"]
                if kind == "replace":
                    if op["find"] not in (t.get(f) or ""):
                        raise ValueError(f"find text not in {op['lang']} {f}: {op['find']!r}")
                    t[f] = t[f].replace(op["find"], op["with"])
                else:
                    t[f] = (t.get(f) or "").rstrip() + " " + op["text"]
        elif kind == "set":
            c["fields"][op["field"]] = op["value"]
        elif kind == "set_area":
            c["scn_alert_area"] = {"areaDesc": op["areaDesc"], "geocodes": [[c["scn"]["requested_area"]["geocodes"][0][0], op["code"]]]}
        elif kind == "set_areadesc":
            c["scn_alert_area"] = {"areaDesc": op["value"], "geocodes": c["scn"]["requested_area"]["geocodes"]}
        elif kind == "drop_language":
            c["versions"] = [v for v in c["versions"] if not v["language"].startswith(op["lang"])]
        elif kind == "set_sender":
            c["sender"] = op["value"]
        else:
            raise ValueError(f"unknown op {kind}")


def run_prereg() -> dict:
    """The fault set written by someone outside the build, committed before this ran, terms unchanged."""
    faults = yaml.safe_load(PREREG.read_text(encoding="utf-8"))
    cases = []
    bases = {}
    for f in faults:
        sid = f["scenario"]
        if sid not in bases:
            scn = load_scn(sid)
            base = base_draft(scn)
            xml0, ai0 = build(scn, base["fields"], base["versions"])
            vs0 = gate.check(pipeline.envelope_for(scn, xml0, [], ai0), stage="review")
            bases[sid] = (scn, base, {v.rule for v in vs0 if v.status in (gate.FAIL, gate.WARN)})
        scn, base, clean_bad = bases[sid]
        c = {"sid": sid, "scn": scn, "fields": copy.deepcopy(base["fields"]), "versions": copy.deepcopy(base["versions"])}
        apply_ops(c, f["ops"])
        xml, ai = build(scn, c["fields"], c["versions"], sender=c.get("sender"), area=c.get("scn_alert_area"))
        env_scn = {**scn, "issuer": c["sender"]} if c.get("sender") else scn
        rn, vs = rules_named(env_scn, xml, ai, clean_bad)
        reviews = institutions.review(env_scn, xml, c["fields"], c["versions"], salt=f"prereg:{f['id']}:{sid}")
        terms = [t.lower() for t in f["named_terms"]]
        an = agents_named(reviews, terms)
        clean_also = sum(1 for o in _clean_objections(sid) if any(_hit(t, _text(o)) for t in terms))
        cases.append({"fault": f["id"], "title": f["title"], "copies": f.get("copies"), "scenario": sid,
                      "rules_named": rn, "agents_named": an, "clean_also": clean_also,
                      "named_by": {"none": False, "rules": bool(rn), "agents": bool(an), "both": bool(rn) or bool(an)},
                      "objections_total": sum(len(r["objections"]) for r in reviews),
                      "dropped_total": sum(len(r["dropped"]) for r in reviews),
                      "reviews": [{k: r[k] for k in ("role", "name", "position", "summary", "objections", "dropped",
                                                      "no_basis", "queries", "clauses")} for r in reviews],
                      "gate": [{"rule": v.rule, "status": v.status, "detail": v.detail} for v in vs]})
        print(f"{f['id']} {sid}: rules {rn or '-'} | agents {len(an)} hit(s)")
    n = len(cases)
    summary = {"cases": n, "named": {a: sum(1 for c in cases if c["named_by"][a]) for a in ("none", "rules", "agents", "both")},
               "only_rules": sorted(c["fault"] for c in cases if c["named_by"]["rules"] and not c["named_by"]["agents"]),
               "only_agents": sorted(c["fault"] for c in cases if c["named_by"]["agents"] and not c["named_by"]["rules"]),
               "neither": sorted(c["fault"] for c in cases if not c["named_by"]["both"]),
               "terms_matching_clean_drafts": sum(1 for c in cases if c["clean_also"])}
    return {"cases": cases, "summary": summary}


def main(argv: list[str]) -> int:
    if "--prereg" in argv:
        res = run_prereg()
        res["note"] = ("Faults and matching terms written outside the build and committed before the run "
                       "(bench/faults-preregistered.yaml); reported as they came out.")
        (OUT / "ablation-prereg.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        slim = {"summary": res["summary"], "note": res["note"],
                "cases": [{k: c[k] for k in ("fault", "title", "copies", "scenario", "rules_named", "agents_named", "named_by", "clean_also")}
                          for c in res["cases"]]}
        (WEB / "ablation-prereg.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res["summary"], indent=1))
        return 0
    res = run_faults()
    clean_path = OUT / "results.json"
    clean_runs = []
    if clean_path.exists():
        bench = json.loads(clean_path.read_text(encoding="utf-8"))
        for s in bench.get("scenarios", []):
            for r in s["runs"]:
                rd = (r.get("institutions") or {}).get("round1") or []
                clean_runs.append({"scenario": s["id"], "run": r["run"],
                                   "objections": [{"by": x["name"], **o} for x in rd for o in x["objections"]]})
    res["clean"] = clean_runs
    res["summary"] = summarise(res["cases"], clean_runs)
    res["faults"] = [{"id": f[0], "title": f[1], "copies": f[3], "scenarios": f[4], "terms": f[5]} for f in FAULTS]
    res["note"] = ("Faults are injected by code into real AI drafts; each copies a failure type from the record. "
                   "The rules are unchanged since the first commit. Agent answers are recorded and replayable.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ablation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    slim = {"summary": res["summary"], "faults": res["faults"], "note": res["note"],
            "cases": [{k: c[k] for k in ("fault", "title", "copies", "scenario", "rules_named", "agents_named", "named_by")}
                      for c in res["cases"]],
            "clean": res["clean"]}
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "ablation.json").write_text(json.dumps(slim, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["summary"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
