# Draft contribution to ITU-T Study Group 17

**Status: draft, not submitted.** ITU-T contributions come from members. This text is laid out so that a Member State or Sector Member can file it with little editing. The fields marked "to be filled in" are theirs.

| | |
|---|---|
| Study Group | 17 (Security), which maintains Recommendation ITU-T X.1303bis |
| Question | To be assigned |
| Source | To be filled in by the submitting member |
| Title | Recording AI involvement and human approval in Common Alerting Protocol alerts |
| Purpose | Proposal |

**Abstract.** This contribution proposes five registered `<parameter>` names for X.1303bis (CAP 1.2) alerts. They record whether an AI system drafted or translated the alert, and how many people, in which roles, approved it. The proposal needs no schema change. An audit of 1,711 live alerts from 8 public feeds found none that records either fact. A reference implementation with tests is public.

## 1. Background

X.1303bis defines `<sender>`, `<source>`, `<note>`, `<code>` and `<parameter>`. None of them is defined as the place to say that software wrote or translated the text, or that a person approved it. `<sender>` names an organisation. `<source>` and `<note>` are free text. The XML signature shows which key signed the message.

AI is already writing warning text. The US National Weather Service is building AI translation for its products. ITU's own reports ask for a record of that use:

- ESTR.AICNHM (ITU-T, 2025): "Establish warning systems, oversights and failsafes."
- *Leveraging AI to Enhance Multi-Hazard Early Warning Systems* (ITU, UNDRR, WMO, IFRC, 2026): "Define how AI informs warning decisions; ensure human oversight and documentation of use."

Neither report says where in the alert that documentation goes. The one national precedent we found is Canada's CAP-CP 1.0 (Draft 2, 2016), which recommends an optional `AutoTranslated` yes/no parameter. It covers machine translation only and names no approver.

## 2. Evidence from live feeds

We read 8 public CAP feeds between 18:50 and 19:02 UTC on 8 November 2026 and counted every alert with status other than Test or Exercise. The script and the snapshot are in `audit/`.

| Feed | Alerts | Record AI or machine involvement | Record an approver | Signed |
|---|---|---|---|---|
| United States, IPAWS (OpenFEMA) | 1,000 | 0 | 0 | 1,000 |
| Canada, NAAD (ECCC, Quebec) | 93 | 0 | 0 | 93 |
| Saudi Arabia NCM, Arabic | 54 | 0 | 0 | 54 |
| Saudi Arabia NCM, English | 54 | 0 | 0 | 54 |
| Qatar CAA, Arabic | 5 | 0 | 0 | 5 |
| Qatar CAA, English | 5 | 0 | 0 | 5 |
| Kuwait Met Department | 1 | 0 | 0 | 0 |
| Australia BoM (WMO mirror) | 499 | 0 | 0 | 0 |
| **Total** | **1,711** | **0** | **0** | **1,211** |

Two details from the same snapshot:

- 17 US alerts carry one vendor's `UserName` parameter. It holds the login or shift name of whoever was signed in to the sending software, in a format no other sender uses.
- All 100 Canadian alerts fetched (93 counted, 7 Test or Exercise) declare the CAP-CP profile. None uses `AutoTranslated`.

## 3. Proposal

Register five `valueName`s for use in `<info><parameter>`:

| valueName | Value | Presence |
|---|---|---|
| `AIPROV:0.1:AIInvolvement` | `none`, `assisted`, `translated` or `generated` | SHALL be present in every `<info>` |
| `AIPROV:0.1:AIModel` | Free text naming the model or tool | SHALL be present when AIInvolvement is not `none` |
| `AIPROV:0.1:MachineTranslated` | Comma-separated language codes of the machine-translated `<info>` blocks | SHALL be present when any block was machine translated |
| `AIPROV:0.1:ApprovedBy` | Comma-separated role identifiers | SHALL be present |
| `AIPROV:0.1:ApprovalCount` | Number of distinct people who approved release | SHALL be present |

Rules:

1. The five parameters SHALL be added before the alert is signed, so that the enveloped signature of CAP 1.2 §3.3.4.1 covers them.
2. `ApprovedBy` SHALL carry role identifiers. Personal names stay in the issuer's own records, which keeps personal data off the broadcast.
3. `AIInvolvement` means: `none`, people wrote every word; `assisted`, people wrote it with AI suggestions; `translated`, people wrote the source language and AI translated one or more others; `generated`, AI drafted the text and people approved it.

## 4. Example

The `<info>` block below was built by the reference implementation (`cap.build` and `cap.with_parameters`) and validates against the CAP 1.2 schema. The values are samples. Line breaks were added between parameters for reading.

```xml
<info>
  <language>en-US</language>
  <category>Met</category>
  <event>Flash flood</event>
  <urgency>Immediate</urgency>
  <severity>Severe</severity>
  <certainty>Likely</certainty>
  <headline>EXERCISE. Flash flood warning for Al Ain</headline>
  <instruction>Stay away from wadis and flooded roads.</instruction>
  <parameter><valueName>AIPROV:0.1:AIInvolvement</valueName><value>generated</value></parameter>
  <parameter><valueName>AIPROV:0.1:AIModel</valueName><value>example-model-1</value></parameter>
  <parameter><valueName>AIPROV:0.1:MachineTranslated</valueName><value>ar</value></parameter>
  <parameter><valueName>AIPROV:0.1:ApprovedBy</valueName><value>duty-forecaster,duty-officer</value></parameter>
  <parameter><valueName>AIPROV:0.1:ApprovalCount</valueName><value>2</value></parameter>
  <area><areaDesc>Al Ain</areaDesc><polygon>24.10,55.60 24.10,55.90 24.35,55.90 24.35,55.60 24.10,55.60</polygon></area>
</info>
```

(`<senderName>` and `<description>` are left out here for length.)

## 5. Backward compatibility

`<parameter>` is CAP's own extension point, so the XML schema does not change. A receiver that does not know these names ignores them, as it does any unknown parameter today. An alert without them stays a valid CAP 1.2 message. A national profile can make them mandatory when its authority is ready.

## 6. What the parameters do and do not show

They are a signed statement by the issuer, with the same trust as the rest of the alert. They show what the issuer declared and bind it to the signature. They do not prove the declaration is true, and they do not decide whether AI may be used or who must approve. Those choices stay with each country.

## 7. Reference implementation

An open prototype writes and checks the parameters:

- `nadhir/pipeline.py` writes `AIInvolvement`, `AIModel` and `MachineTranslated` when the draft is composed, and `ApprovedBy` and `ApprovalCount` at approval, before signing.
- `nadhir/gate.py`, rule R8, blocks release when `AIInvolvement` is missing, invalid or different from what the pipeline recorded, when `MachineTranslated` does not list the machine-translated languages, when `ApprovedBy` is missing, or when `ApprovalCount` differs from the number of approvers. R8 does not check `AIModel`.
- The tests are `test_r8_*` in `tests/test_gate.py`. In the same file, `test_r5_tampered_after_signing` edits a signed alert and checks that the signature rule (R5) fails it.

## 8. Proposal to the Study Group

SG17 is invited to:

1. consider adding the five names, with the rules in section 3, to X.1303bis as an informative appendix, or as a registered parameter set that national profiles can cite;
2. consider a liaison statement to OASIS (Emergency Management Technical Committee) and WMO, since both maintain CAP guidance that alerting authorities follow.
