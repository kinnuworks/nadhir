# AI for Good Sandbox Hackathon – {{TEAM}} – Nadhir: AI-drafted public warnings, checked before broadcast

Team leader: {{LEADER}} · Team members: {{MEMBERS}} · Contact details: {{CONTACT}} · GitHub link: {{REPO}} · Live demo: {{LIVE_URL}}

## 1. Introduction

We read 1,711 live alerts from 8 public feeds in 6 countries. None records whether AI drafted it or who approved it, and the Common Alerting Protocol (CAP 1.2, ITU-T X.1303bis) defines no field for either. Nadhir is a working prototype of the missing checks: AI agents draft the alert, and a gate of cited rules, four institution agents that must quote their sources, and named people decide whether it goes out. It is built for the UAE's cell broadcast warning system (UAE-Alert).

AI is starting to write warning text. The US National Weather Service publishes AI-translated products. ITU leads Pillar 3 of the Early Warnings for All initiative, on warning dissemination and communication, which is the step Nadhir works on. ITU's 2026 report *Leveraging AI to Enhance Multi-Hazard Early Warning Systems* calls for AI to "operate within human-in-the-loop governance frameworks". Nobody has built that frame for the alert itself. Nadhir is one: the model proposes, and deterministic rules and people decide. Each rule quotes its policy source, and the mapping exercise and the agents' own runs produced twelve policy and standards gaps, each with draft wording a named body could adopt (section 6). That links the prototype to the AI Readiness Framework's "policy for AI" dimension.

## 2. Description of the use case

**Problem.** A wrong public alert reaches millions of phones in seconds. The record of real failures shows what goes wrong: a drill sent live (Hawaii 2018), a target area loaded from old drill data (Japan 2022), a city overreaching a national alert (Seoul 2023), a polygon that was never saved so a whole county was warned (Los Angeles 2025), and an intruder sending "Extreme" alerts nationwide (Brazil 2026). AI drafting adds new ways to fail, such as invented detail and unchecked translation. It also needs new records: who approved, and whether AI wrote the text.

**Shortcomings of existing solutions.** Alerting software checks the CAP format but not policy, and CAP cannot record AI involvement or approvers (section 1, gap G1).

**Our solution.** A Drafter agent turns verified event inputs into CAP fields and leaves unverified inputs out. A Translator agent produces Arabic, from a vetted template where one exists, otherwise by machine translation flagged for review. The gate then runs 12 rules (R0–R11). Text failures go back to the Drafter, up to twice. Four institution agents then review the draft, each standing in for a body with its own partial view: a met office reviewer (sees the bulletin and the English text), an issuing-authority reviewer (sees the issuer register, active alerts and the area), a network operator and regulator reviewer (sees each language's text with its cell broadcast page count) and an Arabic reviewer (sees English and Arabic only). Each writes its own searches over a clause-level knowledge base and must quote what it relies on; code drops any objection whose quote is not word for word in the clause or the alert. Cited objections go back to the Drafter once; any still open go to the people, who must read them before release. Process failures (area, issuer, approvals, signature) are held for people. After approval, the approver roles and the AI involvement are written into the alert and signed. The gate checks it once more, then releases it. Every step is logged in a hash chain.

![Figure 1. (a) The pipeline, labelled with ITU-T Y.3172 nodes. (b) Which layer names each injected fault. A fault counts as named only if the rule or agent output contains the terms committed for it in advance.](docs/media/fig-pipeline-layers.png)

## 3. Use case requirements per pipeline node

- **SRC:** event inputs must be marked verified or unverified. Only verified inputs may reach the alert text (R11 checks every number, hazard and listed place against them).
- **C:** the operator, not the AI, chooses the target area. The area must be drawn for this event (R3). The issuer register says who may warn for which hazard and area (R4).
- **PP:** the draft becomes CAP 1.2 XML that validates against the official schema (R0). Text is counted in cell broadcast pages per script: GSM-7 93 and UCS-2 41 characters a page (R6).
- **M:** the model only proposes text. It has no send function. Every model answer is recorded, so every run can be replayed without the model.
- **P:** 12 deterministic rules, each with a source and quote from the knowledge base. Any failed rule blocks; any missing approval holds. The four institution agents search an 11,572-clause knowledge base, UAE texts first (our 53 sources, including TDRA's cell broadcast spec, plus the organisers' UAE policy dataset), and must quote it word for word.
- **D:** two different named people approve a severe or extreme live alert (R1). Machine-translated text needs a named reader of that language (R9). Approver roles and AI involvement are written into the alert before signing (R8), and the signature binds them (R5).
- **SINK:** a cell broadcast centre stub and a hash-chained audit log with a verify command. On every push, CI reruns the tests, replays the bench and both fault sets from the recorded model answers, rechecks every knowledge-base quote and re-verifies every log's hash chain.

## 4. Mapping with ITU-T Y.3172, the Readiness 2.0 report and domain policies

| Node | Use case (Nadhir) | Readiness 2.0 dimension | Documents (KB) |
|---|---|---|---|
| SRC | NCM hazard warnings and event reports, marked verified or unverified | D4 Contextualization (UAE bulletins in Arabic and English) | NCM warnings via WAM; WMO CAP guidance |
| C | Inputs per event, operator-drawn target area, issuer register, prior alerts | D7 Strategy alignment (who may warn for what) | UAE issuer list (press); Seoul 2023 ministry statement |
| PP | Draft to CAP 1.2 XML, schema check, cell broadcast page count per script | D13 Digital infrastructure | CAP 1.2 / X.1303bis and XSD; 3GPP TS 23.041, 23.038; TDRA TS FS 001 v2.0 (UAE-Alert) |
| M | Drafter and Translator agents (hosted LLM); propose only, every answer recorded | D8 Collaboration with AI | ITU ESTR.AICNHM; MHEWS report 2026 |
| P | 12 deterministic rules, each citing a source; block or hold. Four institution agents with partial views object with verified quotes | D7, D8, D10 (organisers' own map for P) | FCC Hawaii report; FCC DA 25-12; UAE AI Charter; 3GPP TS 23.041 |
| D | Two named approvers, approver roles and AI involvement written in, XML signature, final check | D8 Collaboration with AI | FCC Hawaii report; CAP 1.2 §3.3.4.1; proposed profile |
| SINK | Signed alert to a cell broadcast centre stub; hash-chained audit log | D13 Digital infrastructure | TDRA cell broadcast specs (2017; TS FS 001 v2.0, 2019) |
| MLFO / sandbox | Orchestrator with gate-feedback redrafts; replay bench of real failures, demo keys and zones | D7, D10 | ITU-T Y.3172 |

All 13 Readiness dimensions are rated in `docs/y3172-and-readiness.md`, each with its evidence or the reason it is missing: five are exercised by running code (D4, D7, D8, D10, D13), four partly (D1, D5, D6, D11), and four are not addressed (D2, D3, D9, D12).

| Node | Code | Checked by | Limit |
|---|---|---|---|
| SRC / C | `pipeline.py` | R3, R4, R11 tests; Seoul and LA replays | Demo issuer register and zones; inputs typed, not fed live |
| PP | `cap.py`, `gate.py` R0, R6 | Schema and UCS-2 page tests | Page budget noted, not enforced (no UAE limit, G6) |
| M | `agents.py` | Every answer recorded; CI replays all runs from recordings | Recordings fix outputs, not model behaviour |
| P | `gate.py`, `institutions.py` | 36 rule tests, 6 agent tests, 54 injected faults, replays | Agents stand in for roles, not the real bodies |
| D | `pipeline.py` | R1, R5, R8, R9 tests, incl. tampering after signing | Demo keys; approver names not identity-checked |
| SINK / MLFO | `log.py`, `pipeline.py` | Log tests; CI re-verifies every chain | Broadcast centre is a stub; no load testing |

## 5. Error scenarios

Each scenario follows the template's steps: deployed, problem noticed, handled under rules in the KB. The first four replay real failures; the answer key is the official finding. Across thirteen real failures the rules catch the official finding in 8. Seven were held out: added after the rules were frozen, and picked and mapped by someone who did not write the rules. The frozen rules catch 2 of those 7 and the agents one more; the misses are in scenario 6.

1. **A drill goes out live (Hawaii, 2018).** Step 1: an internal drill message says "EXERCISE" and "this is not a drill". Step 2: one officer sends it as a live statewide missile alert. Step 3: the gate blocks it on R2 (the event is an exercise, the alert says Actual) and R1 (one approver for an extreme alert). The 38-minute correction was a new alert with no link to the false one; R10 holds it. All three match the FCC's recommendations. Given the same drill input, the AI drafter kept it marked as an exercise.
2. **The wrong area (Los Angeles, 2025; Japan, 2022).** The fire polygon was never saved, so the alert held only the county code and went to the whole county. In Japan, the alert also went to Tokyo's islands. R3 (area sent = area requested, drawn for this event) blocks both.
3. **Controversy: who may warn (Seoul, 2023).** The ministry alerted two islands and told "areas that did not receive the alert" to issue their own. Seoul read that as itself and alerted the whole city. The ministry called it an error; the mayor called it an over-reaction, not an error. The gate does not settle the dispute. It holds the city's alert under R4 because a higher authority's active alert covers a different area, and escalates to that authority. Given the same ambiguous instruction, the AI drafter also produced an alert the city may not send, and the gate held it the same way.
4. **An intruder (Brazil, 2026).** "Extreme" alerts were sent by someone outside the national civil defence system. R5 (registered signing key) and R4 (registered sender) block it. If the intruder held the platform's own key, R5 would not catch it; R1 (two named approvers) would.
5. **AI translation in the UAE (our scenarios, real NCM warnings).** In all 12 runs the translator machine-translated the Arabic. Without the gate it would have gone to phones unreviewed. With the gate each alert waited for a named Arabic reader (R9). Every draft ran 5 to 6 Arabic cell broadcast pages, which the gate notes (R6); no UAE text sets a page budget (gap G6).

6. **Held out: what twelve rules miss, and the rule each miss calls for.** Taiwan 2024: a satellite-launch alert went out with English from an old missile template ("Missile flyover Taiwan airspace"). The rules miss it because R11 only checks AI-written text; the met office agent objects that "the alert names the wrong hazard". Four more held-out failures, added on the last day, are missed by rules and agents alike. Each of the five points to a rule we propose and have not built. R12: run the grounding check on all text, templates included (Taiwan). R13: every phone number and link must be on the issuer's verified contact list (Netherlands 2019, a wrong WhatsApp number). R14: hash the approved text in each language and require re-approval if it changes before release (UK 2023, an autocorrect broke a Welsh word). R15: status Test may go only to a registered test group (New Zealand 2017, tests left the closed group). R16: the channel must fit the size of the target area (Minnesota 2024, a one-block shelter order aired over broadcast). The rules stayed frozen, and the counts above record all five as misses for the rules. (For New Zealand, R2 fired only because the message text is not public; we do not count it.)
7. **Which layer catches what.** A separate agent that saw only the drafts wrote 24 faults and the words that count as naming each, committed before the run. The rules alone named 14, the four institution agents alone 23, both together all 24. Only the agents caught meaning changes in the Arabic (eastern for western, "go into standing water", a drill's "exercise" label dropped). On our own 30-fault set: rules 20, agents 28, both 30. On 12 clean drafts the agents raised 10 objections; 6 stayed open after one redraft and went to the approvers. Of 117 objections, 99 record that no UAE text applies: evidence for gaps G2, G3 and G5. The reviewers also logged concerns no clause backed: in 37 of the 54 fault cases the operator reviewer recorded that no clause requires an action on the first page, and in 30 the met office reviewer recorded that none sets the severity. We searched for that text and wrote up G8 and G9.

**Judges' own scenario.** The live demo takes any typed event or any pasted CAP alert.

## 6. Policy gaps and standards gaps

Twelve gaps (S standards, P UAE policy, N international norm); G8 to G12 came from running the agents. docs/gaps.md gives the evidence and full draft wording (ours, no legal review). G1 is also laid out as a draft contribution to ITU-T SG17 (docs/sg17-draft-contribution.md, not submitted). In the organisers' 62-document UAE dataset the closest clauses are about other things, and 6 of 36 queries returned nothing.

<!-- widths: 6 41 33 20 -->
| Gap | Missing today, with evidence | Draft wording a body could adopt | Who files · rule |
|---|---|---|---|
| G1 S | CAP (X.1303bis) has no field for AI involvement or a named approver. Of 1,711 live alerts from 8 feeds, none records either. | Five registered parameters SHALL be in every `<info>`, added before signing so the signature covers them. | A Member State or Sector Member, to SG17 · R8 |
| G2 P | No public rule on who approves an AI-drafted alert; the UAE AI Charter states principles only. FCC after Hawaii: two-person sign-off. | Two named approvers for a live severe or extreme alert; one reads the AI text in each language. | NCEMA with TDRA · R1, R9 |
| G3 P | No rule on machine-translated alerts. The FCC refuses it for phone alerts (vetted templates in 13 languages); the US weather service uses it. | Other-language text is an approved template or is approved by a named reader; the alert records which. | NCEMA with TDRA · R9, R7 |
| G4 P | No public CAP feed on the WMO Register of Alerting Authorities (record dated 2013). Saudi Arabia, Qatar and Kuwait publish live feeds. | NCM publishes UAE warnings as a CAP 1.2 feed and keeps the register entry current. | NCM · no rule; the feed audit would read it |
| G5 N | No norm on correcting a false alert or publishing an after-action note. 3 of 1,000 recent US alerts cancelled earlier alerts without a link. | A correction uses Update or Cancel, references the original and goes to the same channels and area. | SG17 for CAP, ITU-D for practice · R10 |
| G6 S | US templates assume 360 characters. The FCC Arabic dust storm text runs 10 UCS-2 pages; TDRA TS FS 001 sets no page budget. | Templates state bearer, encoding, length and pages per language; TDRA sets a UAE page budget. | Template publishers or SG17; TDRA · R6 |
| G7 S | CAP status and US test practice disagree: 246 of 1,000 US alerts marked "Actual" carry a test event code. | A scheduled test SHOULD use status Test; a profile that sends tests as Actual SHALL define a marking parameter. | SG17 and national profile owners · R2 |
| G8 S, P | CAP marks `<instruction>` optional, so an alert need not say what to do. 658 of the 1,711 carry one; neither Saudi feed does. | The hazard and one protective action within the first page, in each required language. | SG17; NCEMA with TDRA · no rule yet; operator reviewer |
| G9 P | No public table maps bulletin levels to CAP urgency, severity and certainty. Australia has one ("Emergency Warning = Extreme"). | A published table from warning levels to the three CAP values. | NCM with NCEMA · no rule yet; met office reviewer |
| G10 P | No rule that the area sent must match the area requested (Los Angeles 2025, Japan 2022). The FCC sets it as an objective. | The originator compares the two areas before release; operators deliver within a stated tolerance and report to TDRA. | TDRA with operators · R3 |
| G11 S, P | Signing is optional in CAP and no UAE text requires it. 1,211 of the 1,711 live alerts are signed; none of Australia's 499 is. | Every alert carries a registered originator's electronic seal (UAE 2021 law); gateways reject the rest. | SG17; TDRA with NCEMA · R5, R4 |
| G12 P | No retention rule for origination or AI drafting records. UAE text covers consumer records only; the FCC requires gateway logs. | Keep the origination record (inputs, AI drafts, objections, approver roles, message) for a stated period. | TDRA with NCEMA · no rule; the hash-chained log |

**Limits.** Replays are rebuilt from public reports; where the record is silent, we assume the alert was fine. Five incidents rest on investigation reports or official reviews, the others on official statements, and India on press only. The injected faults and their matching terms are ours. The demo issuer, zones and keys are stand-ins. Two models play the six agents; the institution agents stand in for roles, not the real bodies.
