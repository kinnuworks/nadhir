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

## Readiness dimensions claimed (5 of 13)

We claim only the dimensions the prototype exercises:

- **D4 Contextualization and regional impact.** Every UAE alert needs Arabic and English (R7). Arabic must come from a vetted template, or a named person who reads Arabic must approve it (R9). Cell broadcast page counts are done per script, since Arabic needs UCS-2 and fits 41 characters a page, not 93 (R6).
- **D7 Strategy alignment.** The issuer register (R4) encodes who may warn for which hazard and area. When a higher authority already has an alert out, a lower one must not reach beyond its area without escalating.
- **D8 Collaboration with AI.** The model drafts and translates. People approve. Two different people approve a high-impact live alert (R1). The alert records which roles approved (R8).
- **D10 AI policy and policy for AI.** Each rule turns a written policy or an official finding into a check, with the source quoted next to the verdict. The gaps in `docs/gaps.md` come from the places where no policy text could be found to back a rule.
- **D13 Digital infrastructure.** Cell broadcast limits (R6) and the CAP signature (R5) are infrastructure facts the gate enforces.

Dimensions we do not claim: data and model marketplace, generated content marketplace, cross-domain analysis, level of integration (no time-saving measured), human interface (the UI is plain), impact of humans in AI integration, inclusion beyond language, priorities.
