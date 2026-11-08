# Policy and standards gaps

Each gap lists what is missing, where we looked, what evidence the prototype produced, a global example, and who could act. KB ids refer to `kb/sources.yaml`. "Not found" means we searched the public texts listed and did not find it. It is not proof that nothing exists internally.

## G1. CAP has no defined field for AI involvement or a named approver (standards, ITU-T SG17)

- **Missing.** CAP 1.2 / ITU-T X.1303bis defines no element for "AI drafted or translated this" or "these roles approved it". `<sender>` names the organisation, `<source>` is free text, and the signature proves which key signed, not who reviewed the text.
- **Searched.** CAP 1.2 (CAP12), X.1303bis (X1303BIS), the schema (CAPXSD), the US IPAWS profile (IPAWS-PROFILE), Canada's CAP-CP (CAPCP) and Australia's CAP-AU (CAPAU).
- **Evidence.** Our audit counted 1,711 live alerts from 8 public feeds (US IPAWS, Canada, Australia, Saudi Arabia, Qatar, Kuwait) on 8 Nov 2026. None records AI or machine involvement. None records an approval. The only approver-like fields are one US vendor's `UserName` login parameter, in 17 alerts. All 100 Canadian alerts declare the CAP-CP profile, which has an optional `AutoTranslated` flag, and none uses it.
- **Why now.** ITU's own reports ask for this oversight. ESTR.AICNHM (ITU-T, 2025): "Establish warning systems, oversights and failsafes." *Leveraging AI to Enhance MHEWS* (ITU, UNDRR, WMO, IFRC, 2026): "Define how AI informs warning decisions; ensure human oversight and documentation of use." Neither defines where that documentation goes in the alert.
- **Global example.** Canada's CAP-CP `AutoTranslated` (machine translation only, optional, no approver).
- **Proposal.** Five registered `<parameter>` names, signed with the alert: `docs/cap-ai-provenance-profile.md`. Implemented and tested as gate rule R8.

## G2. No public UAE rule on who approves an AI-drafted public alert (policy, NCEMA / TDRA)

- **Missing.** The UAE AI Charter says human oversight is irreplaceable (UAE-AI-CHARTER, principle 6) and asks for governance and accountability (principle 7). No public operational rule says how many people approve an alert before broadcast, in which roles, or what changes when AI drafts the text.
- **Searched.** UAE AI Charter, Dubai AI ethics guidance (DUBAI-AI-ETHICS), press explainers of the UAE early warning system (UAE-ISSUERS, UAE-KT-2026, UAE-NAT-2026), the TDRA handset specs (TDRA-TS040, TDRA-2017-CB). Khaleej Times notes the decision chain "has, however, not been revealed to the public" (UAE-KT-2026).
- **Evidence.** In the Hawaii 2018 replay, the alert went out with one operator. The gate's R1 (two named people for a high-impact live alert) is the rule the FCC recommended afterwards: "Require more than one credentialed person to validate the message content prior to transmission" (FCC-HI-2018).
- **Global example.** The FCC Hawaii recommendations (2018). The MHEWS report's call for "human-in-the-loop governance frameworks" (MHEWS-2026).
- **Proposal.** A published two-person rule for high-impact alerts, with a named reviewer for any AI-drafted or machine-translated text, written so a gate like R1 and R9 can check it.

## G3. Machine translation of alerts: no UAE rule, and the US is split (policy)

- **Missing.** UAE handsets must show Arabic and English (TDRA-TS040, secondary). Nothing public says whether either language, or any third language, may be machine translated, or who must check it.
- **Searched.** TDRA-TS040, TDRA-2017-CB, UAE AI Charter, ETSI EU-Alert (ETSI-EUALERT).
- **Global example.** The US is split. The FCC declined machine translation for Wireless Emergency Alerts (FCC-23-88) and then said "We do not—and cannot—revisit the viability of machine translation" (FCC-DA-25-12). Instead it published human-vetted templates in 13 languages, Arabic included. Meanwhile the National Weather Service uses AI translation for its products (NWS-AI-TRANSLATION).
- **Evidence.** In our UAE scenarios the translator agent chose machine translation for Arabic over the US vetted template. The gate held every such alert until a named Arabic reader approved the wording (R9). It also checks that every number and time in the translation matches the source.
- **Proposal.** A UAE rule: alert text in any language comes from a vetted template, or a named person who reads that language approves it. Record which, in the alert (G1).

## G4. The UAE lists no public CAP feed on the WMO Register of Alerting Authorities (policy, low cost)

- **Missing.** The UAE register entry ("United Arab Emirates: Meteorological Department") is dated 11 Sep 2013 and shows "CAP Feed URL(s): [ blank ]" (WMO-REGISTER).
- **Evidence.** Saudi Arabia, Qatar and Kuwait list feeds that are live, and our audit read 54, 5 and 1 current alerts from them. Bahrain and Oman list feeds that were empty on 8 Nov 2026.
- **Global example.** WMO's CAP guidance and the Early Warnings for All dissemination pillar, which ITU leads (WMO-CAP-GUIDE, EW4ALL-P3).
- **Proposal.** Publish UAE warnings as a public CAP feed and update the register entry. A feed published from the start with G1's parameters would be the first national feed to record AI involvement and approval.

## G5. No international norm for correcting a false alert, or reporting on it afterwards (standards and policy)

- **Missing.** CAP lets a correction point to the alert it fixes (`msgType` Update or Cancel with `<references>`). The IPAWS profile requires it for related messages (IPAWS-PROFILE). Nothing we found sets an international norm for how fast a false public alert must be corrected, over which channels, or what is published afterwards.
- **Evidence.** In the Hawaii replay, the 38-minute correction was a new alert with no link to the false one, and the gate's R10 holds it. The FCC report asked that "corrections to false alerts must be issued over the same systems used to issue the false alert" (FCC-HI-2018). LA County's 2025 correction was also sent as a new alert. In 1,000 recent real US alerts, the gate found 3 more cancellations sent as new alerts with no `<references>`.
- **Global example.** The FCC Hawaii report and the US congressional report on LA County (LA-2025) are public after-action reviews. EU-Alert law sets duties to deliver warnings (EU-ALERT) but not after-action reporting.
- **Proposal.** An ITU-T or ITU-D good-practice text: corrections must reference the original, go out on the same channels and reach the same area, and a short after-action note is published.

## G6. Vetted multilingual templates don't fit cell broadcast page limits (standards, found by the prototype)

- **Missing.** No rule ties alert templates to the bearer they travel on.
- **Evidence.** Filled in, the FCC's vetted Arabic dust storm template is 384 characters. Arabic needs UCS-2 encoding on cell broadcast, at 41 characters a page (TS23038), so this is 10 pages. The English version is 4 pages in GSM-7. The UAE handset spec summary says "Message should be limited to 1 page maximum" (TDRA-TS040, secondary). The templates were written for the US WEA limit of 360 characters (FCC-16-127), not for cell broadcast pages.
- **Proposal.** Template sets that state their bearer and length per script, so a country adopting them for cell broadcast knows the cost in pages. Gate rule R6 counts pages per language.

## G7. CAP status and US test practice conflict (standards, found by the prototype)

- **Missing.** CAP 1.2 has a `Test` status. In US practice, scheduled EAS tests go out with status `Actual` so that broadcast stations relay them.
- **Evidence.** 246 of the 1,000 IPAWS alerts in our snapshot carry a test event code but status `Actual`. Our first gate run flagged 119 of them under R2 before we added a narrow US exemption. A receiver that relies on `status` alone cannot tell a scheduled test from a live alert.
- **Proposal.** SG17 could note the convention in X.1303bis guidance, or profiles could add a parameter that marks scheduled tests explicitly.

## How the gaps map to the AI Readiness Framework

G1, G5, G6 and G7 are standards gaps (ITU-T SG17 for CAP / X.1303bis). G2 and G3 sit under D10 "AI policy and policy for AI": domain rules that don't yet say anything about AI. G4 sits under D13 digital infrastructure. G2 also touches D7 strategy alignment, since several UAE bodies may issue alerts (UAE-ISSUERS) and no public text says how they coordinate.
