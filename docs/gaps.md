# Policy and standards gaps

Each gap lists what is missing, where we looked, what evidence the prototype produced, a global example, and who could act. KB ids refer to `kb/sources.yaml`. "Not found" means we searched the public texts listed and did not find it. It is not proof that nothing exists internally.

We also searched the organisers' own UAE policy dataset (ITU Sandbox_Training, `Dataset/UAE`, 62 documents in folders 01 to 06, indexed clause by clause in `kb/index/`) with three fixed queries per gap. `python -m kb.gap_search` reruns it and writes every hit, with its score and text, to `kb/index/gap-search.json`. For every gap the closest UAE clauses are about something else, and six of the 36 queries returned nothing above the relevance floor. Examples: for G3 (machine translation of alerts) the best hit is the accessibility policy's sign-language translation; for G1 (who approved an alert) it is a blank business-continuity plan form in NCEMA 7000:2012; for G5 (correcting a false alert) it is the cybercrime law's notices to remove false content online; for G12 (keeping alert logs) it is the retention table for telecom consumer records; for G11 (signing alerts) it is the general law on electronic signatures and seals.

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
- **Found since.** The official portal (UAE-PORTAL-EWS) says sending warnings "is limited to entities responsible for the safety of individuals in the UAE" and names NCEMA, the Ministry of Interior, the emirates' police forces and the Ministry of Health and Prevention, but not who approves a message. Dubai Decree No. 48 of 2024 (DXB-DECREE-48-2024) tasks the Dubai Resilience Centre to "establish a unified early warning regulation for the Emirate"; we found no published regulation.
- **Proposal.** A published two-person rule for high-impact alerts, with a named reviewer for any AI-drafted or machine-translated text, written so a gate like R1 and R9 can check it.

## G3. Machine translation of alerts: no UAE rule, and the US is split (policy)

- **Missing.** UAE handsets must show Arabic and English (TDRA-TSFS001, TDRA's TS FS 001 v2.0). Nothing public says whether either language, or any third language, may be machine translated, or who must check it.
- **Searched.** TDRA-TSFS001, TDRA-TS040, TDRA-2017-CB, UAE-PORTAL-EWS, UAE AI Charter, ETSI EU-Alert (ETSI-EUALERT).
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
- **Evidence.** Filled in, the FCC's vetted Arabic dust storm template is 384 characters. Arabic needs UCS-2 encoding on cell broadcast, at 41 characters a page (TS23038), so this is 10 pages. The English version is 4 pages in GSM-7. The templates were written for the US WEA limit of 360 characters (FCC-16-127), not for cell broadcast pages. No UAE text sets a page budget either: TDRA's current handset spec (TDRA-TSFS001, TS FS 001 v2.0, 2019) requires Arabic and English but sets no page limit, while a 2015 summary of an earlier version says "Message should be limited to 1 page maximum" (TDRA-TS040, secondary).
- **Proposal.** Template sets that state their bearer and length per script, so a country adopting them for cell broadcast knows the cost in pages. Gate rule R6 counts pages per language.

## G7. CAP status and US test practice conflict (standards, found by the prototype)

- **Missing.** CAP 1.2 has a `Test` status. In US practice, scheduled EAS tests go out with status `Actual` so that broadcast stations relay them.
- **Evidence.** 246 of the 1,000 IPAWS alerts in our snapshot carry a test event code but status `Actual`. Our first gate run flagged 119 of them under R2 before we added a narrow US exemption. A receiver that relies on `status` alone cannot tell a scheduled test from a live alert.
- **Proposal.** SG17 could note the convention in X.1303bis guidance, or profiles could add a parameter that marks scheduled tests explicitly.

## G8. Nothing requires a phone alert to say what to do (standards and policy, SG17 / NCEMA with TDRA)

- **Missing.** CAP makes the protective action optional: `<instruction>` is "The text describing the recommended action to be taken by recipients of the alert message (OPTIONAL)" (CAP12 §3.2.2). No UAE text we found says a public alert must carry an action, or that the action must be on the first cell broadcast page, which is the only page many people read.
- **Searched.** CAP12, X1303BIS, CAPAU, TDRA-TSFS001, TDRA-TS040, ETSI-EUALERT. In the UAE dataset the closest clauses are service-level terms in the API First Guideline (p.37) and the definition of the "Blocking Message" shown for blocked internet content (Internet Access Management policy, p.2).
- **Evidence.** 658 of the 1,711 live alerts in our audit carry an `<instruction>`. Neither Saudi feed does in any of its 54 alerts. In the prototype, the network operator reviewer is asked to check that the first page carries the hazard and the action. In 37 of the 54 injected-fault cases it recorded that it found no clause requiring an action there (F01: "no clause shown requires an action on page one"). The gate has no rule for this today, because we found no text to cite for one.
- **Global example.** Australia's CAP profile: "It is RECOMMENDED that alert message producers include response types when applicable, along with a corresponding <instruction> value" (CAPAU, p.21). The FCC's vetted templates pair "a description of the threat and the protective action the public should take" (FCC-DA-25-12, p.21).
- **Proposal.** A UAE template rule: every public alert names the hazard and one action within the first page, in each required language. In X.1303bis guidance, make `<instruction>` expected for alerts with status `Actual`. Either text would let a gate rule check it.

## G9. No published mapping from UAE weather bulletins to CAP urgency, severity and certainty (policy, NCM with NCEMA)

- **Missing.** CAP needs three coded values per alert. No public UAE text says which bulletin wording or measured threshold (visibility in a dust storm, rainfall, wind) maps to Moderate, Severe or Extreme. An AI drafter has to choose, and a reviewer has nothing to check the choice against.
- **Searched.** UAE-PORTAL-EWS, TDRA-TSFS001, UAE-ISSUERS, CAP12, CAPAU, FCC-16-127. In the UAE dataset the query "urgency severity certainty of alert" returned nothing above the relevance floor. The closest clauses for the other two queries are about colour listings in phone directories (TDRA Consumer Protection Regulations, p.63) and ground-level ozone readings (National Air Quality Agenda 2031, p.9).
- **Evidence.** The met office reviewer recorded in 30 of the 54 fault cases that no clause sets the severity (F12: "The bulletin gives no severity grade, so "Moderate" is the drafter's choice"; F11: "No clause sets a severity level for dust events in the UAE"). When we inflated severity to Extreme (faults F04 and P24), no rule could object. Only the reviewers named it, by comparing the alert with the bulletin.
- **Global example.** Australia publishes the mapping for bushfire levels: "Advice = Moderate Watch and Act = Severe Emergency Warning = Extreme" (CAPAU, p.22). The US defines the values in regulation: "Severity - The CAP Severity element must be either Extreme (i.e., an extraordinary threat to life or property) or Severe (i.e., a significant threat to life or property)" (47 CFR 10.400(b), quoted in FCC-16-127, p.18).
- **Proposal.** NCM and NCEMA publish a table from warning level and hazard thresholds to the three CAP values. A deterministic rule can then replace the reviewer's judgement.

## G10. No UAE rule that the area sent must match the area requested (policy, TDRA with operators)

- **Missing.** No public UAE text sets a targeting-accuracy requirement for cell broadcast, or a check before sending that the polygon or zone codes are the ones the requester asked for.
- **Searched.** TDRA-TSFS001, TDRA-TS040, TDRA-2017-CB, UAE-PORTAL-EWS. In the UAE dataset "geographical area of emergency notification" returned nothing above the floor. The closest clause for the other queries is "Section 2: The Target Group" of the Guide to Access Government Information (p.2).
- **Evidence.** Two real incidents in our replays are area errors. In Los Angeles, "the message was sent county-wide in error" (LA-2025, p.8). In Japan, the J-Alert "mistakenly included Tokyo because data on where to send warnings was not erased after it was used in a previous drill" (JALERT-2022). Gate rule R3 holds both. In the fault tests R3 named a widened area (F08) and a swapped one (P10). When only the area description said "All emirates" and the codes stayed the same (F09), no rule fired and only the issuing authority reviewer named it.
- **Global example.** The FCC: "Our ultimate objective is for all Participating CMS Providers to match the target area provided by an alert originator" (FCC-16-127, p.37), later set as "Hit 100% target area within 0.1 mile overshoot by Nov 2019" (IPAWS-OPEN, p.23). EU-Alert: "EU-Alert shall support DBGF", device-based geo-fencing (ETSI-EUALERT, p.11).
- **Proposal.** A TDRA requirement on targeting accuracy for operators, and an origination rule that the area is drawn for this event and compared with the request before release, as R3 does.

## G11. Signing an alert is optional in CAP, and no UAE text requires it (standards and policy, SG17 / TDRA with NCEMA)

- **Missing.** CAP says the alert "MAY have an Enveloped Signature" (CAP12 §3.3.4.1) and adds that security mechanisms "should not be used indiscriminately" (§3.3.4). The UAE has a general law on electronic signatures and seals, which defines an electronic seal as "Data in electronic form that is attached to or logically associated with an Electronic Document" (Federal Decree-Law No. 46 of 2021, p.7, in the UAE dataset). Nothing we found applies it to public alerts or says a receiver must reject an unsigned one.
- **Searched.** CAP12, X1303BIS, IPAWS-PROFILE, TDRA-TSFS001, UAE-PORTAL-EWS. In the UAE dataset every close hit is the electronic transactions law or a digital-service target ("100% Services that require a manual signature offer a digital option", Digital Government Strategy 2025).
- **Evidence.** 1,211 of the 1,711 live alerts in our audit are signed. All 499 Australian alerts and the one from Kuwait are not. In our replay of Brazil 2026, where "at least 10 unauthorized alerts were sent to phones" (BRAZIL-2026), gate rules R1, R4 and R5 (signed by a registered originator key) hold the message.
- **Global example.** In the US, origination tools send digitally signed CAP messages to IPAWS-OPEN, and the aggregator authenticates the sender before anything is relayed (IPAWS-OPEN, pp.8-9).
- **Proposal.** A UAE rule that every alert is sealed by a registered originator under the 2021 law's trust services, and that gateways reject unsigned or unregistered messages. SG17 could make the signature expected in X.1303bis profiles for public alerting.

## G12. No retention rule for alert origination logs or AI drafting records (policy, TDRA with NCEMA)

- **Missing.** No public UAE text says how long the record of a public alert must be kept: who drafted it, what the AI produced, who approved it, what was sent. The UAE AI Charter asks for accountability (UAE-AI-CHARTER, principle 7), which needs the record to still exist when someone asks.
- **Searched.** UAE-AI-CHARTER, TDRA-TSFS001, UAE-PORTAL-EWS, CAP12. In the UAE dataset "retention of emergency alert logs" returned nothing above the floor. The closest retention rules are for telecom consumer records: "Hard copies shall be retained for at least three (3) years" and speed-test records "for at least 2 years" (TDRA Consumer Protection Regulations, clause 3.9, pp.11-12). The data protection and business-continuity texts cover records of processing and internal audits, not alerts.
- **Evidence.** The prototype writes a hash-chained log for every alert, and CI re-verifies every chain on each push. No text told us how long to keep those logs or who may read them, so the prototype sets no retention period.
- **Global example.** The FCC: "We require Participating CMS Providers to log their receipt of Alert Messages at their Alert Gateway and to appropriately maintain those records for review" (47 CFR 10.320(g), FCC-16-127, p.32).
- **Proposal.** A TDRA and NCEMA rule that origination logs, including AI drafts and reviewer objections, are kept for a stated period in a tamper-evident form and are available to the regulator on request.

## How the gaps map to the AI Readiness Framework

G1, G5, G6 and G7 are standards gaps (ITU-T SG17 for CAP / X.1303bis). G8 and G11 are standards gaps with a UAE policy side. G2, G3, G9 and G12 sit under D10 "AI policy and policy for AI": domain rules that don't yet say anything about AI, or that leave an AI drafter without a reference. G4 and G10 sit under D13 digital infrastructure. G2 also touches D7 strategy alignment, since several UAE bodies may issue alerts (UAE-ISSUERS) and no public text says how they coordinate.

Seven gaps (G1 to G7) came from the mapping exercise and the incident replays. Five (G8 to G12) came from running the agents: the reviewers kept recording concerns they could not back with a clause, and we searched for the missing text.
