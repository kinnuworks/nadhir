# Draft: recording AI involvement and human approval in CAP alerts

Status: draft written as a possible input to ITU-T Study Group 17 (the group that maintains X.1303bis). Version 0.1. Not adopted by anyone.

## The problem

CAP 1.2 (OASIS, 2010; ITU-T X.1303bis, 2014) gives an alert no defined place to say:

- whether software or an AI model drafted it, or translated part of it;
- who approved it, and how many people did.

The fields that come closest are free text. `<sender>` names the organisation, not a person. `<source>` is free text with no format. `<note>` is meant for exercises and errors. The XML signature proves which key signed the message, not who looked at it or how it was written.

National profiles we checked (US IPAWS, Canada CAP-CP, Australia CAP-AU) do not fill the gap. The one precedent is the Canadian CAP-CP rule set's `AutoTranslated` yes/no parameter, which covers machine translation only and names no approver.

Meanwhile AI is already writing warning text. The US National Weather Service publishes AI-translated products. The FCC, on the other hand, has twice declined machine translation for Wireless Emergency Alerts. An alert from either regime looks the same on the wire. ITU's own recent reports ask for human oversight of AI in early warning (ESTR.AICNHM, 2025; *Leveraging AI to Enhance Multi-Hazard Early Warning Systems*, 2026). There is no field in the alert where that oversight can be recorded.

Our audit of real feeds (see `audit/`) shows what this means in practice: in live alerts, AI involvement and approvers are not recorded in any standard way. Where software vendors want to record an operator, they invent their own parameter names.

## Proposal

Use the existing `<info><parameter>` extension point. No schema change is needed. The proposal is a small registered set of `valueName`s, so receivers can read them the same way everywhere:

| valueName | Value | Required |
|---|---|---|
| `AIPROV:0.1:AIInvolvement` | `none`, `assisted`, `translated`, or `generated` | Yes, in every `<info>` |
| `AIPROV:0.1:AIModel` | Free text naming the model or tool | When AIInvolvement is not `none` |
| `AIPROV:0.1:MachineTranslated` | Comma-separated language codes of machine-translated `<info>` blocks | When any block was machine translated |
| `AIPROV:0.1:ApprovedBy` | Comma-separated role identifiers (not personal names) | Yes |
| `AIPROV:0.1:ApprovalCount` | Number of distinct people who approved release | Yes |

Rules:

1. These parameters are added **before** signing, so the existing enveloped XML signature (CAP 1.2 §3.3.4.1) binds them. Changing them later breaks the signature.
2. Role identifiers, not names, go in the alert. Names stay in the issuer's own audit log. This keeps personal data off the broadcast.
3. A receiver that does not understand the parameters ignores them, as CAP already requires for unknown parameters. Nothing breaks.
4. `AIInvolvement` values:
   - `none`: people wrote every word.
   - `assisted`: people wrote it with AI suggestions.
   - `translated`: people wrote the source language and AI translated one or more languages.
   - `generated`: AI drafted the text and people approved it.

## What it is not

- It does not say whether AI should be used. It only makes the choice visible.
- It does not replace national approval rules. The UAE, the US and others decide who must approve. This only records that they did.
- It is not proof that the declaration is true. It is a signed statement by the issuer, the same trust model as the rest of the alert.

## Reference implementation

`nadhir/gate.py`, rule R8, checks these parameters. `nadhir/pipeline.py` writes them, and the approvers are added at approval time, before signing. The tests are in `tests/test_gate.py` (`test_r8_*`).
