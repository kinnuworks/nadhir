# AI for Good Sandbox Hackathon – {{TEAM}} – Nadhir: AI-drafted public warnings, checked before broadcast

Team leader: {{LEADER}} · Team members: {{MEMBERS}} · Contact details: {{CONTACT}} · GitHub link: {{REPO}} · Live demo: {{LIVE_URL}}

## 1. Introduction

Nadhir shows AI agents drafting public warning alerts, while a gate of cited rules, four institution agents that must quote their sources, and named people decide whether each alert goes out. It is built for the UAE's cell broadcast warning system (UAE-Alert) and the alert format behind it, the Common Alerting Protocol (CAP 1.2, ITU-T X.1303bis).

AI is starting to write warning text. The US National Weather Service publishes AI-translated products. ITU's 2026 report *Leveraging AI to Enhance Multi-Hazard Early Warning Systems* calls for AI to "operate within human-in-the-loop governance frameworks". Nobody has built that frame for the alert itself. Nadhir is one: the model proposes, and deterministic rules and people decide. Each rule quotes its policy source, and the mapping exercise produced seven policy and standards gaps (section 6). That links the prototype to the AI Readiness Framework's "policy for AI" dimension.

## 2. Description of the use case

**Problem.** A wrong public alert reaches millions of phones in seconds. The record of real failures shows what goes wrong: a drill sent live (Hawaii 2018), a target area loaded from old drill data (Japan 2022), a city overreaching a national alert (Seoul 2023), a polygon that was never saved so a whole county was warned (Los Angeles 2025), and an intruder sending "Extreme" alerts nationwide (Brazil 2026). AI drafting adds new ways to fail, such as invented detail and unchecked translation. It also needs new records: who approved, and whether AI wrote the text.

**Shortcomings of existing solutions.** Alerting software checks the CAP format but not policy. CAP itself has no field to record AI involvement or approvers. In our audit of 1,711 live alerts from 8 public feeds, none does.

**Our solution.** A Drafter agent turns verified event inputs into CAP fields and leaves unverified inputs out. A Translator agent produces Arabic, from a vetted template where one exists, otherwise by machine translation flagged for review. The gate then runs 12 rules (R0–R11). Text failures go back to the Drafter, up to twice. Four institution agents then review the draft, each standing in for a body with its own partial view: a met office reviewer (sees the bulletin and the English text), an issuing-authority reviewer (sees the issuer register, active alerts and the area), a network operator and regulator reviewer (sees each language's text with its cell broadcast page count) and an Arabic reviewer (sees English and Arabic only). Each writes its own searches over a clause-level knowledge base and must quote what it relies on; code drops any objection whose quote is not word for word in the clause or the alert. Cited objections go back to the Drafter once; any still open go to the people, who must read them before release. Process failures (area, issuer, approvals, signature) are held for people. After approval, the approver roles and the AI involvement are written into the alert and signed. The gate checks it once more, then releases it. Every step is logged in a hash chain.

## 3. Use case requirements per pipeline node

- **SRC:** event inputs must be marked verified or unverified. Only verified inputs may reach the alert text (R11 checks every number, hazard and listed place against them).
- **C:** the operator, not the AI, chooses the target area. The area must be drawn for this event (R3). The issuer register says who may warn for which hazard and area (R4).
- **PP:** the draft becomes CAP 1.2 XML that validates against the official schema (R0). Text is counted in cell broadcast pages per script: GSM-7 93 and UCS-2 41 characters a page (R6).
- **M:** the model only proposes text. It has no send function. Every model answer is recorded, so every run can be replayed without the model.
- **P:** 12 deterministic rules, each with a source and quote from the knowledge base. Any failed rule blocks; any missing approval holds. Four institution agents (met office, issuing authority, network operator and regulator, Arabic reviewer) each see only their part of the alert, search an 11,572-clause knowledge base, UAE texts first (our 53 sources, including TDRA's cell broadcast spec, plus the organisers' UAE policy dataset) and must quote it word for word; code drops any objection that fails the quote check.
- **D:** two different named people approve a severe or extreme live alert (R1). Machine-translated text needs a named reader of that language (R9). Approver roles and AI involvement are written into the alert before signing (R8), and the signature binds them (R5).
- **SINK:** a cell broadcast centre stub and a hash-chained audit log with a verify command.

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

## 5. Error scenarios

Each scenario follows the template's steps: deployed, problem noticed, handled under rules in the KB. The first four replay real failures; the answer key is the official finding. Across nine real failures the rules catch the official finding in 8; three of the nine were added after the rules were frozen, and the rules catch 2 of those 3 (the miss is in scenario 6).

1. **A drill goes out live (Hawaii, 2018).** Step 1: an internal drill message says "EXERCISE" and "this is not a drill". Step 2: one officer sends it as a live statewide missile alert. Step 3: the gate blocks it on R2 (the event is an exercise, the alert says Actual) and R1 (one approver for an extreme alert). The 38-minute correction was a new alert with no link to the false one; R10 holds it. All three match the FCC's recommendations. Given the same drill input, the AI drafter kept it marked as an exercise.
2. **The wrong area (Los Angeles, 2025; Japan, 2022).** The fire polygon was never saved, so the alert held only the county code and went to the whole county. In Japan, the alert also went to Tokyo's islands. R3 (area sent = area requested, drawn for this event) blocks both.
3. **Controversy: who may warn (Seoul, 2023).** The ministry alerted two islands and told "areas that did not receive the alert" to issue their own. Seoul read that as itself and alerted the whole city. The ministry called it an error; the mayor called it an over-reaction, not an error. The gate does not settle the dispute. It holds the city's alert under R4 because a higher authority's active alert covers a different area, and escalates to that authority. Given the same ambiguous instruction, the AI drafter also produced an alert the city may not send, and the gate held it the same way.
4. **An intruder (Brazil, 2026).** "Extreme" alerts were sent by someone outside the national civil defence system. R5 (registered signing key) and R4 (registered sender) block it. If the intruder held the platform's own key, R5 would not catch it; R1 (two named approvers) would.
5. **AI translation in the UAE (our scenarios, real NCM warnings).** In all 12 runs the translator machine-translated the Arabic. Without the gate it would have gone to phones unreviewed. With the gate each alert waited for a named Arabic reader (R9). Every draft ran 5 to 6 Arabic cell broadcast pages, which the gate notes (R6); no UAE text sets a page budget (gap G6).

6. **Held out: the wrong hazard in a human template (Taiwan, 2024).** A satellite-launch alert went out with English text from an old missile template ("Missile flyover Taiwan airspace"). The frozen rules miss it, because R11 only checks AI-written text. The met office agent, comparing the alert with the inputs, objects that "the alert names the wrong hazard". Lesson: a grounding check should run on every alert, not only AI-written ones.
7. **Which layer catches what.** A separate agent that saw only the drafts wrote 24 faults and the words that count as naming each, committed before the run. The rules alone named 14, the four institution agents alone 23, both together all 24. Only the agents caught meaning changes in the Arabic (eastern for western, "go into standing water", a drill's "exercise" label dropped). On our own 30-fault set: rules 20, agents 28, both 30. On 12 clean drafts the agents raised 10 objections; 6 stayed open after one redraft and went to the approvers. Of 117 objections, 99 record that no UAE text applies: evidence for gaps G2, G3 and G5.

**Judges' own scenario.** On the live demo, a judge can type any event (verified or not), pick a zone, mark it as a drill, and watch the agents and gate respond. A judge can also paste any real CAP alert into the checker.

## 6. Policy gaps and standards gaps

Seven gaps, each with sources and a global example in docs/gaps.md. For each, we also searched the organisers' UAE policy dataset (62 documents, clause by clause); the closest clauses are about other things (for G3, sign-language translation in the accessibility policy):

1. **G1, standards (SG17):** CAP / X.1303bis has no field for AI involvement or a named approver. In 1,711 live alerts from 8 feeds, none records either. We propose five registered parameters, signed with the alert (draft profile in the repo).
2. **G2, UAE policy:** no public rule on who approves an AI-drafted public alert; the UAE AI Charter states principles only. Global example: the FCC's two-person recommendation after Hawaii.
3. **G3, UAE policy:** no rule on machine translation of alerts. The US is split: the FCC refuses it for phone alerts and publishes vetted templates in 13 languages, while the National Weather Service uses AI translation.
4. **G4, UAE policy:** no public CAP feed on the WMO Register of Alerting Authorities (record dated 2013). Saudi Arabia, Qatar and Kuwait publish live feeds.
5. **G5, international norm:** no norm on correcting false alerts (link to the original, same channels, same area) or publishing an after-action note. 3 of 1,000 recent US alerts cancelled earlier alerts without a link.
6. **G6, standards:** vetted multilingual templates are written for a 360-character US limit, not cell broadcast pages. The FCC Arabic dust storm template is 10 pages in UCS-2; no UAE text sets a page budget (TDRA TS FS 001 v2.0 sets none).
7. **G7, standards:** CAP status vs US test practice. 246 of 1,000 US alerts marked "Actual" carry a test event code.

**Limits.** Replays are rebuilt from public reports. Where the record is silent, we assume the alert was fine. Four incidents rest on official statements rather than investigation reports, and India on press only. The injected faults and their matching terms are ours. The 2015 handset rules (TS040) come from a compliance firm's summary; TDRA's 2019 UAE-Alert specification is the primary text. The demo issuer, zones and keys are stand-ins. Two models play the six agents (one drafts and translates, another reviews); the institution agents stand in for roles, not the real bodies.
