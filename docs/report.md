# AI for Good Sandbox Hackathon – {{TEAM}} – Nadhir: AI-drafted public warnings, checked before broadcast

Team leader: {{LEADER}} · Team members: {{MEMBERS}} · Contact details: {{CONTACT}} · GitHub link: {{REPO}} · Live demo: {{LIVE_URL}}

## 1. Introduction

Nadhir shows AI agents drafting public warning alerts, while a gate of cited rules and named people decides whether each alert goes out. It is built for the UAE's cell broadcast warning system (UAE-Alert) and the alert format behind it, the Common Alerting Protocol (CAP 1.2, ITU-T X.1303bis).

AI is starting to write warning text. The US National Weather Service publishes AI-translated products. ITU's 2026 report *Leveraging AI to Enhance Multi-Hazard Early Warning Systems* calls for AI to "operate within human-in-the-loop governance frameworks". Nobody has built that frame for the alert itself. Nadhir is one: the model proposes, and deterministic rules and people decide. Each rule quotes its policy source, and the mapping exercise produced seven policy and standards gaps (section 6). That ties the prototype to the AI Readiness Framework's "policy for AI" dimension, not just to a product.

## 2. Description of the use case

**Problem.** A wrong public alert reaches millions of phones in seconds. The record of real failures shows what goes wrong: a drill sent live (Hawaii 2018), a target area loaded from old drill data (Japan 2022), a city overreaching a national alert (Seoul 2023), a polygon that was never saved so a whole county was warned (Los Angeles 2025), and an intruder sending "Extreme" alerts nationwide (Brazil 2026). AI drafting adds new ways to fail, such as invented detail and unchecked translation. It also needs new records: who approved, and whether AI wrote the text.

**Shortcomings of existing solutions.** Alerting software checks the CAP format but not policy. CAP itself has no field to record AI involvement or approvers. In our audit of 1,711 live alerts from 8 public feeds, none does.

**Our solution.** A Drafter agent turns verified event inputs into CAP fields and leaves unverified inputs out. A Translator agent produces Arabic, from a vetted template where one exists, otherwise by machine translation flagged for review. The gate then runs 12 rules (R0–R11). Text failures go back to the Drafter, up to twice. Process failures (area, issuer, approvals, signature) are held for people. After approval, the approver roles and the AI involvement are written into the alert and signed. The gate checks it once more, then releases it. Every step is logged in a hash chain.

## 3. Use case requirements per pipeline node

- **SRC:** event inputs must be marked verified or unverified. Only verified inputs may reach the alert text (R11 checks every number, hazard and listed place against them).
- **C:** the operator, not the AI, chooses the target area. The area must be drawn for this event (R3). The issuer register says who may warn for which hazard and area (R4).
- **PP:** the draft becomes CAP 1.2 XML that validates against the official schema (R0). Text is counted in cell broadcast pages per script: GSM-7 93 and UCS-2 41 characters a page (R6).
- **M:** the model only proposes text. It has no send function. Every model answer is recorded, so every run can be replayed without the model.
- **P:** 12 deterministic rules, each with a source and quote from the knowledge base. Any failed rule blocks; any missing approval holds.
- **D:** two different named people approve a severe or extreme live alert (R1). Machine-translated text needs a named reader of that language (R9). Approver roles and AI involvement are written into the alert before signing (R8), and the signature binds them (R5).
- **SINK:** a cell broadcast centre stub and a hash-chained audit log with a verify command.

## 4. Mapping with ITU-T Y.3172, the Readiness 2.0 report and domain policies

{{MAPPING_TABLE}}

## 5. Error scenarios

{{SCENARIOS}}

**Judges' own scenario.** On the live demo, a judge can type any event (verified or not), pick a zone, mark it as a drill, and watch the agents and gate respond. A judge can also paste any real CAP alert into the checker.

## 6. Policy gaps and standards gaps

{{GAPS}}

**Limits.** Replays are rebuilt from public reports. Where the record is silent, we assume the alert was fine. Three incidents rest on press reports of official statements. The UAE handset rules come from a compliance firm's summary. The demo issuer, zones and keys are stand-ins. One model plays both agents.
