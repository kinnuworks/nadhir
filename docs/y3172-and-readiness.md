# Mapping to ITU-T Y.3172 and the ITU AI Readiness Framework 2.0

Y.3172 (06/2019) describes a machine-learning pipeline in a network: source, collector, pre-processor, model, policy, distributor and sink, run by an ML function orchestrator (MLFO), with an ML sandbox kept apart from the live network (the underlay). Each row below names the file that does the job, so the table can be checked against the code.

| Node | In Nadhir | Code | Readiness 2.0 dimension | Documents (KB ids) |
|---|---|---|---|---|
| SRC | Hazard bulletins and event reports, each marked verified or unverified; past alerts for replays | `bench/incidents/`, `bench/scenarios/`, web inputs | D4 Contextualization (UAE meteorological bulletins in English and Arabic) | UAE-NAT-2026, WMO-CAP-GUIDE |
| C | Collects inputs per event, plus the operator's chosen target area, issuer register and prior alerts | `nadhir/pipeline.py` `envelope_for` | D7 Strategy alignment (who may warn for what, across agencies) | UAE-ISSUERS, SEOUL-2023 |
| PP | Turns drafts into CAP 1.2 XML, checks it against the official schema, counts cell broadcast pages (GSM-7 / UCS-2) | `nadhir/cap.py`, `gate.py` R0, R6 | D13 Digital infrastructure (cell broadcast bearer limits) | CAP12, CAPXSD, TS23041, TS23038 |
| M | Drafter and translator agents. They only propose text; they cannot send | `nadhir/agents.py`, `llm.py` | D8 Collaboration with AI (AI drafts, people decide) | ESTR-AICNHM, MHEWS-2026 |
| P | The gate: 12 deterministic rules, each citing its source. Blocks, or holds for people | `nadhir/gate.py` | D10 AI policy and policy for AI (each rule is a policy turned into a check) | FCC-HI-2018, FCC-DA-25-12, UAE-AI-CHARTER |
| D | Release step: approvers recorded in the alert, signed with the issuer's key, final check | `pipeline.py` `approve_and_release` | D8 Collaboration with AI (two people for high-impact alerts) | FCC-HI-2018, CAP12 §3.3.4.1 |
| SINK | The signed alert, handed to a cell broadcast centre (stub here), plus the hash-chained audit log | `nadhir/log.py`, `runs/bench/logs/` | D13 Digital infrastructure | TDRA-TS040, TDRA-2017-CB |
| MLFO | Orchestrator: runs the agents in order, feeds gate failures back to the drafter (up to 2 redrafts), picks the model and effort | `nadhir/pipeline.py` | D7 Strategy alignment | Y3172 |
| ML sandbox | The replay bench and the demo issuer, keys and zones. Nothing touches a real broadcast system | `nadhir/bench.py`, `nadhir/keys/demo/` | D10 AI policy (rules tried on real failures before any live use) | Y3172 |
| Underlay | A real cell broadcast centre and handsets. Not touched | n/a | n/a | TS23041 |

## What tests each node, and its limit

| Node | Checked by | Limit |
|---|---|---|
| SRC | R11 tests (invented number, place, hazard) | Inputs are typed or pasted; no live bulletin feed |
| C | R3 and R4 tests; Seoul and LA replays | Demo issuer register and zones |
| PP | R0 schema test; R6 tests, including UCS-2 pages for Arabic | Page budget is noted, not enforced: no UAE limit exists (G6) |
| M | Every model answer is recorded; CI replays all runs from the recordings and fails on any change | Recordings fix the outputs, not the model's behaviour |
| P | 36 rule tests, 6 agent tests (quote check, partial views, dropped objections), 54 injected faults, the replays | The agents stand in for roles, not the real bodies |
| D | R1, R5, R8 and R9 tests, including tampering after signing | Demo keys; approver names are not identity-checked |
| SINK | Log tests (edit and deletion detected); CI re-verifies every log's chain | No real cell broadcast centre |
| MLFO | Bench runs with and without the gate | Fixed order; no load or failover testing |
| ML sandbox | CI reruns the bench on every push | Replays are rebuilt from public reports, not the original systems |

## All 13 Readiness dimensions, with status

Dimension names follow the ITU AI Readiness Framework 2.0 as used in the organisers' own simulation code (ITUAIReadiness, `simulation/server/agents/`). Their Y.3172 node-to-dimension map (`usecase.py`) is in the second column, so the two tables line up. Status says how far this prototype goes, with the file or result that shows it.

| # | Dimension | Organisers' nodes | Status here | What shows it (or why not) |
|---|---|---|---|---|
| D1 | Data / model marketplace | SRC, C, PP | Partly | The knowledge base is open: clause index of our sources plus the organisers' own UAE policy dataset (`kb/index/`), and every real alert we read is kept as a snapshot (`audit/snapshot/`). No marketplace or exchange. |
| D2 | Generated content marketplace | PP, M | Not addressed | AI-generated alert text is the subject, but there is no exchange of generated content. The provenance profile (G1) would let such content be labelled. |
| D3 | Cross-domain correlation | C, PP, M | Not addressed | One domain (public warning over cell broadcast). |
| D4 | Contextualization and regional impact | SRC | Exercised | Arabic and English are both required (R7); Arabic needs a vetted template or a named Arabic reader (R9); an Arabic reviewer agent compares meaning; pages are counted per script, since Arabic fits 41 characters a page, not 93 (R6). |
| D5 | Level of integration of AI in workflows | M, D, SINK, MLFO | Partly | AI drafts and translates; four agents review; people approve. We did not measure time saved. |
| D6 | Human interface | D, SINK | Partly | The approver sees the draft, the rule table, each agent's quoted objections and the open items to read before release. Plain UI, not user-tested. |
| D7 | Strategy alignment | P, MLFO | Exercised | The issuer register and the issuing-authority agent check who may warn for what; overreach past a higher authority's alert is held for escalation (R4, Seoul 2023 replay). |
| D8 | Collaboration with AI | P, MLFO | Exercised | AI proposes; agents object with quotes; named people decide and can overrule an objection only on the record (audit log). Two people for a high-impact alert (R1). |
| D9 | Impacts of humans in AI integration | M | Not addressed | No study of skills or staffing. |
| D10 | AI policy and policy for AI | P, Sandbox | Exercised | Each rule turns a written policy or official finding into a check; agents must quote the clause they rely on; searches that find no clause become gap leads (`docs/gaps.md`). |
| D11 | AI for inclusion | Sandbox | Partly | Arabic on equal terms with English. No accessibility or other-language work (the UAE's large non-Arabic, non-English population is not covered). |
| D12 | Granular priorities | D, SINK | Not addressed | No regional prioritisation beyond the operator's chosen zone. |
| D13 | Digital infrastructure | SRC, C, SINK | Exercised | Cell broadcast page budgets per encoding (R6, 3GPP TS 23.038/23.041), CAP schema validation (R0) and XML signatures (R5). |

Five exercised, four partly, four not addressed. We claim only the five.
