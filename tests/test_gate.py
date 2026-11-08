"""One or more tests per gate rule. No model calls."""
import copy

import pytest

from nadhir import cap, gate, keys

SENDER = "test.issuer"
AREA = {"areaDesc": "Al Ain", "geocodes": [["UAE-AREA", "AA-01"]], "event_id": "e1", "origin": "drawn"}


def alert(**over):
    a = {
        "identifier": "t1", "sender": SENDER, "sent": "2026-11-09T10:00:00+04:00", "status": "Actual",
        "msgType": "Alert", "scope": "Public",
        "info": [
            {"language": "en-US", "category": ["Met"], "event": "Dust storm", "urgency": "Immediate",
             "severity": "Severe", "certainty": "Observed", "headline": "Dust storm warning",
             "description": "Dust storm in Al Ain until 18:00. Visibility under 500 m.",
             "instruction": "Avoid driving.", "parameters": [(gate.P_AI, "generated")],
             "areas": [{"areaDesc": "Al Ain", "geocodes": [("UAE-AREA", "AA-01")]}]},
            {"language": "ar-AE", "category": ["Met"], "event": "Dust storm", "urgency": "Immediate",
             "severity": "Severe", "certainty": "Observed", "headline": "تحذير من عاصفة ترابية",
             "description": "عاصفة ترابية في العين حتى 18:00. الرؤية أقل من 500 متر.",
             "instruction": "تجنب القيادة.", "parameters": [(gate.P_AI, "generated")],
             "areas": [{"areaDesc": "Al Ain", "geocodes": [("UAE-AREA", "AA-01")]}]},
        ],
    }
    for k, v in over.items():
        if k.startswith("info_"):
            for i in a["info"]:
                i[k[5:]] = v
        else:
            a[k] = v
    return a


def env(a=None, **over):
    _, cert = keys.ensure(SENDER)
    e = gate.Envelope(
        cap_xml=cap.build(a or alert()), event_id="e1", requested_area=copy.deepcopy(AREA),
        issuers={SENDER: {"name": "Test issuer", "level": 2, "areas": ["UAE-AREA=AA-01"], "categories": ["Met"]}},
        event_inputs=["NCM: dust storm over Al Ain, visibility below 500 m until 18:00"],
        ai={"involvement": "generated", "machine_translated": []}, registered_certs={SENDER: [cert]},
    )
    for k, v in over.items():
        setattr(e, k, v)
    return e


def released(e, approvers=("Amal", "Omar")):
    """Approve, record approvers, sign, as the pipeline does."""
    key, cert = keys.ensure(SENDER)
    e.approvals = [{"name": n, "role": f"role-{n}"} for n in approvers]
    xml = cap.with_parameters(e.cap_xml, [(gate.P_APPROVED_BY, "duty,supervisor"),
                                          (gate.P_APPROVAL_COUNT, str(len(set(approvers))))])
    e.cap_xml = cap.sign(xml, key, cert)
    return e


def verdict(e, rule, stage="release"):
    return next(v for v in gate.check(e, stage) if v.rule == rule)


def test_clean_alert_releases():
    vs = gate.check(released(env()), "release")
    assert gate.decision(vs) == "release", [(v.rule, v.status, v.detail) for v in vs if v.status != "pass"]


def test_review_stage_waits_for_people():
    vs = gate.check(env(), "review")
    assert gate.decision(vs) == "waiting"
    assert verdict(env(), "R1", "review").status == gate.PENDING


def test_r0_schema_rejects_bad_status():
    e = env(alert(status="Real"))
    assert verdict(e, "R0").status == gate.FAIL


def test_r1_one_approver_is_not_enough_for_severe():
    e = released(env(), approvers=("Amal",))
    assert verdict(e, "R1").status == gate.FAIL


def test_r1_same_person_twice_counts_once():
    e = released(env(), approvers=("Amal", "Amal"))
    assert verdict(e, "R1").status == gate.FAIL


def test_r1_minor_alert_needs_one():
    e = released(env(alert(info_severity="Minor")), approvers=("Amal",))
    assert verdict(e, "R1").status == gate.PASS


def test_r2_drill_sent_live():
    assert verdict(env(exercise=True), "R2").status == gate.FAIL


def test_r2_not_a_drill_inside_exercise():
    a = alert(status="Exercise", info_description="EXERCISE. Missile threat. THIS IS NOT A DRILL.")
    assert verdict(env(a), "R2").status == gate.FAIL


def test_r2_test_without_test_marker():
    a = alert(status="Test", info_description="Severe alert. Stay indoors.")
    assert verdict(env(a), "R2").status == gate.FAIL


def test_r2_live_console_in_test_environment():
    assert verdict(env(environment="test"), "R2").status == gate.FAIL


def test_r3_area_sent_differs_from_request():
    e = env()
    e.requested_area = {"areaDesc": "Zone 4", "geocodes": [["UAE-AREA", "AA-04"]], "event_id": "e1"}
    assert verdict(e, "R3").status == gate.FAIL


def test_r3_area_from_old_drill():
    e = env()
    e.requested_area["origin"] = "drill"
    assert verdict(e, "R3").status == gate.FAIL


def test_r3_area_from_other_event():
    e = env()
    e.requested_area["event_id"] = "drill-2025-03"
    assert verdict(e, "R3").status == gate.FAIL


def test_r4_unknown_sender():
    e = env()
    e.issuers = {"someone.else": {"level": 1, "areas": ["*"]}}
    assert verdict(e, "R4").status == gate.FAIL


def test_r4_outside_own_area():
    e = env()
    e.issuers[SENDER]["areas"] = ["UAE-AREA=DXB-01"]
    assert verdict(e, "R4").status == gate.FAIL


def test_r4_goes_beyond_higher_authority_alert():
    e = env()
    e.active_alerts = [{"sender": "national", "name": "National authority", "level": 1,
                        "geocodes": [["UAE-AREA", "AA-09"]]}]
    assert verdict(e, "R4").status == gate.FAIL


def test_r5_unsigned_fails_at_release():
    e = env()
    e.approvals = [{"name": "Amal"}, {"name": "Omar"}]
    assert verdict(e, "R5").status == gate.FAIL


def test_r5_signed_with_unregistered_key():
    e = released(env())
    other_key, other_cert = keys.ensure("not.registered")
    e.registered_certs = {SENDER: [other_cert]}
    assert verdict(e, "R5").status == gate.FAIL


def test_r5_tampered_after_signing():
    e = released(env())
    e.cap_xml = e.cap_xml.replace("Avoid driving.", "Drive normally.")
    assert verdict(e, "R5").status == gate.FAIL


def test_r6_too_long_for_wea_profile():
    a = alert(info_parameters=[(gate.P_AI, "generated"), ("CMAMlongtext", "x" * 400)])
    assert verdict(env(a, profile="US"), "R6").status == gate.FAIL


def test_r6_us_alert_without_phone_text_is_not_a_phone_broadcast():
    a = alert(info_description="x" * 900)
    assert verdict(env(a, profile="US"), "R6").status == gate.PASS


def test_r2_us_scheduled_test_sent_as_actual_is_allowed():
    a = alert(info_event="Required Weekly Test", info_description="This is a test of the Emergency Alert System.")
    assert verdict(env(a, profile="US"), "R2").status == gate.PASS
    assert verdict(env(a, profile="UAE"), "R2").status == gate.FAIL


def test_r6_arabic_counts_ucs2_pages():
    long_ar = "عاصفة ترابية " * 10
    a = alert()
    a["info"][1]["description"] = long_ar
    v = verdict(env(a), "R6")
    assert v.status == gate.WARN and "UCS-2" in v.detail


def test_r7_arabic_missing():
    a = alert()
    a["info"] = a["info"][:1]
    assert verdict(env(a), "R7").status == gate.FAIL


def test_r8_ai_involvement_hidden():
    a = alert(info_parameters=[(gate.P_AI, "none")])
    assert verdict(env(a), "R8").status == gate.FAIL


def test_r8_no_provenance_parameter():
    a = alert(info_parameters=[])
    assert verdict(env(a), "R8").status == gate.FAIL


def test_r8_not_applied_to_historic_replays():
    a = alert(info_parameters=[])
    assert verdict(env(a, historic=True), "R8").status == gate.NA


def test_r9_machine_arabic_needs_language_approver():
    e = released(env(ai={"involvement": "generated", "machine_translated": ["ar"]}))
    e.cap_xml = e.cap_xml  # params lack MachineTranslated: R8 will flag it, R9 is what we test here
    assert verdict(e, "R9").status == gate.FAIL
    e.approvals.append({"name": "Huda", "scope": "language:ar"})
    assert verdict(e, "R9").status == gate.PASS


def test_r9_numbers_changed_in_translation():
    a = alert()
    a["info"][1]["description"] = "عاصفة ترابية في العين حتى 20:00. الرؤية أقل من 500 متر."
    e = env(a, ai={"involvement": "generated", "machine_translated": ["ar"]})
    assert verdict(e, "R9").status == gate.FAIL


def test_r9_vetted_template_match():
    a = alert()
    a["info"][1]["description"] = "تحذير من عاصفة ترابية حتى 18:00 الرؤية 500 متر"
    e = env(a, ai={"involvement": "generated", "machine_translated": ["ar"]},
            vetted_templates=[{"id": "T1", "language": "ar", "text": "تحذير من عاصفة ترابية حتى [time] الرؤية [distance]"}])
    assert verdict(e, "R9").status == gate.PASS


def test_r10_correction_without_references():
    a = alert(info_description="FALSE ALARM. There is no missile threat.")
    assert verdict(env(a), "R10").status == gate.FAIL


def test_r10_cancel_with_reference():
    prior = {"sender": SENDER, "identifier": "t0", "sent": "2026-11-09T09:00:00+04:00"}
    a = alert(msgType="Cancel", references=f"{SENDER},t0,2026-11-09T09:00:00+04:00")
    assert verdict(env(a, prior_alerts=[prior]), "R10").status == gate.PASS


def test_r11_invented_dam_failure():
    a = alert(info_description="Dam failure near Al Ain. Flooding expected by 18:00.")
    assert verdict(env(a), "R11").status == gate.FAIL


def test_r11_invented_number():
    a = alert(info_description="Dust storm in Al Ain until 21:00.")
    assert verdict(env(a), "R11").status == gate.FAIL


def test_r11_invented_place():
    a = alert(info_description="Dust storm in Al Ain and Dubai until 18:00.")
    assert verdict(env(a), "R11").status == gate.FAIL


def test_template_matcher():
    assert gate._template_match("Warning until [time]. Avoid [place].", "Warning until 18:00. Avoid the E11.")
    assert not gate._template_match("Warning until [time].", "Warning until 18:00. Extra words.")
