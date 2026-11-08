# Nadhir

**For alerting authorities: AI drafts the public warning, and cited rules, institution reviewers and two people decide whether it goes out.**

Nadhir writes and checks emergency phone alerts. One AI agent drafts the alert and a second translates it into Arabic. Neither can send anything. Twelve fixed rules then check it, each quoting a public policy or an official investigation. Four more agents review it next, each standing in for an institution with its own partial view: the met office, the issuing authority, the network operator and regulator, and an Arabic reviewer. They search an 11,188-clause knowledge base themselves and must quote what they rely on; code drops any objection whose quote isn't word for word in its source. People approve last, and the alert is signed.

Run on the real 2018 Hawaii missile alert, the rules block it for the two reasons the US regulator later named: a drill was sent live, and one person could send it alone. Run on three real failures added after the rules were frozen, they catch two; the agents catch the third.

It works on CAP 1.2 (ITU-T X.1303bis), the alert format behind cell broadcast systems such as UAE-Alert, and keeps every step in a tamper-evident (hash-chained) log.

**Live demo:** https://nadhir-gilt.vercel.app (no sign-up)

**Try it in 30 seconds**
1. Open the live demo. The inputs are already filled in: a real UAE National Center of Meteorology dust warning, plus an unverified rumour. Press **Draft alert**.
2. Look at what happened. The drafter left the rumour out. The rule table shows the Arabic is machine translated, so it waits for someone who reads Arabic (R9). Below it, the four institution reviewers each give a position, with the clauses they searched and the quotes they rely on. Their objections went back to the drafter once; the ones still open are listed for the approvers.
3. Type two names and an Arabic reviewer, tick that you read the open objections, then press **Approve**. You get the signed CAP XML, the final verdicts and the audit log with its hash chain.

## What it found

### Replays of real alert failures

We rebuilt nine real public alert failures from published reports and ran each message through the gate as it was actually sent. The answer key for each replay is the investigator's or authority's own published finding. Three of them (marked held out) were added after the rules were frozen at commit `beb8f54`; `nadhir/gate.py` has not changed since, and nobody who wrote the rules picked or mapped those three.

| Real failure | Answer key | Rules that fired on the real message | Finding's rule caught by the rules? | By the agents alone? |
|---|---|---|---|---|
| Hawaii, Jan 2018: missile alert sent live during a drill; correction 38 min later | FCC (official report) | R1, R2, R10 (correction) | yes | yes (R2) |
| Japan, Oct 2022: J-Alert also sent to Tokyo's islands | Fire and Disaster Management Agency white paper (official) | R3 | yes | yes |
| Seoul, May 2023: city air-raid alert the ministry called erroneous | Interior Ministry statement (via press) | R3, R4 | yes | yes |
| Los Angeles, Jan 2025: evacuation warning sent county-wide, not to the fire area | US congressional report (official) | R3, R10 (correction) | yes | yes |
| Brazil, Jun 2026: "Extreme" alerts sent by an intruder | Ministry official note | R1, R4, R5 | yes | no: agents don't see signatures |
| India, 2023: test messages shown as Extreme alerts | Press only | R2 | yes | yes |
| **Held out.** Ontario, Jan 2020: Pickering nuclear alert sent from the live system during training | Ontario Solicitor General investigation (official) | R1, R2 | yes | yes (R2, R10) |
| **Held out.** Florida, Apr 2023: broadcasters' monthly test reached phones at 4:45 a.m. | Florida Division of Emergency Management statement | R2 | yes | yes |
| **Held out.** Taiwan, Jan 2024: satellite launch alert whose English said "missile" and "air raid" | Ministry of National Defense statement | none | **no** | yes (met office reviewer: "the alert names the wrong hazard") |

The rules catch the finding in 8 of 9, and in 2 of the 3 held-out cases. Taiwan is a real miss: R11 (no detail the inputs don't contain) only runs on AI-written text, and Taiwan's wrong English came from an old human template. The agents, reading the same inputs, caught it. Seoul and Florida rest on official statements as quoted or published, not investigation reports; India is press only.

### Which layer catches what (ablation)

We injected 16 kinds of fault into real AI drafts, one at a time, 30 cases in all. Each copies a failure type from the record (a drill sent live, a widened area, a wrong time in the Arabic, a reversed protective action, a rumour, an unregistered sender, and so on). The same faulty alert then went through each setup:

| Setup | Faults named before broadcast (of 30) |
|---|---|
| No checks (the AI pipeline alone) | 0 |
| 12 rules only | 20 |
| 4 institution agents only | 30 |
| Rules and agents | 30 |

The agents named 10 cases the rules missed: the Arabic protective action reversed ("no precautions needed, drive normally"), severity inflated to Extreme, an area description saying "All emirates" while the codes were unchanged, an English action made unsafe, and Arabic text stretched to 20 pages. The rules are still needed: they are deterministic, and they see what the agents never see (signatures, approver counts, the signing key). "Named" for an agent means a kept objection whose text points at that fault. The matching terms are fixed in `nadhir/ablation.py`. We narrowed them after the first run because broad words such as "time" and "page" also matched objections on clean drafts; none of the narrowed terms matches any clean-draft objection.

The cost of the agents is noise. On the 12 clean drafts they raised 35 objections, 27 of them from the network operator reviewer, almost all saying the text runs past the one-page handset advice (which is gap 6, below). After one redraft, 22 were still open and went to the approvers. 103 of the 121 objections in the fault runs cite a knowledge-base clause; the rest quote the alert or the inputs. 2 were dropped because their quote didn't match. The agents also logged 52 concerns they could not back with any clause; we read those as leads for policy gaps.

### The knowledge base

`kb/index/` holds 11,188 clauses from 105 documents: 43 of our sources (29 with full text, from CAP and X.1303bis to the FCC reports and 3GPP specs) and 62 documents from the organisers' own UAE policy dataset (ITU Sandbox_Training, `Dataset/UAE`, folders 01 to 06). Search is plain BM25, no model and no network, so every agent's evidence replays exactly. 54 of the 55 quotes in `kb/sources.yaml` are found word for word in the indexed text (the miss is quoted from a secondary summary, as its locator says). Only 1 of the agents' 135 clause citations came from the UAE dataset, and our gap search over it (`python -m kb.gap_search`) finds nothing on AI-drafted alerts, alert approval or alert translation. That absence is the evidence behind gaps 2 and 3.

### The gate on 1,000 real routine alerts

We ran the context-free rules (R0, R2, R6, R10) over the 1,000 most recent US IPAWS alerts. It would hold 5 of them: 3 cancellations sent as brand-new alerts with no `<references>` to the alert they cancel (R10, the same pattern as Hawaii's correction), and 2 test messages sent with status Actual (R2). Our first run also flagged 119 scheduled US EAS tests, which go out as "Actual" by US convention, so we added a narrow exemption for them after that run.

### What real alerts record today

We read 1,711 live alerts from 8 public feeds (US IPAWS, Canada, Australia, Saudi Arabia, Qatar, Kuwait) on 8 Nov 2026. None records that AI or machine translation was involved, and none records an approval. The only approver-like field is one US vendor's `UserName` login parameter, in 17 alerts. The UAE lists no public feed on the WMO Register of Alerting Authorities. Details: [`audit/`](audit/README.md).

### AI on the same inputs

We gave the drafter the same inputs in 5 of the original replays, plus 4 UAE scenarios built on real NCM warnings, run 3 times each.
- Its first drafts broke no content rule in any of the 12 UAE runs. It left the unverified dam rumour out in 3 of 3, and it kept the drill marked as an exercise in 3 of 3.
- In all 12 runs it machine-translated the Arabic instead of using the FCC's vetted template. Without the gate, unreviewed machine Arabic would have gone to phones 12 times. With it, every one waited for a named Arabic reader (R9).
- Every draft was longer than the one-page advice in the UAE handset spec summary: 2 to 3 pages in English and 5 to 6 in Arabic (R6, warning only).
- In the Seoul replay, the drafter read the ministry's ambiguous instruction and drafted an alert for the islands, which the city may not issue. The gate held it for escalation (R4).

So the gate's work on AI-written alerts here is mostly holding them for people: reviewers, two approvers, escalation. Invented content was not the main risk in these runs.

## The gaps

The full list, with sources and global examples, is in [docs/gaps.md](docs/gaps.md). In short:

1. **CAP has no field for AI involvement or a named approver.** We propose five registered parameters, signed with the alert, as an input to ITU-T SG17: [docs/cap-ai-provenance-profile.md](docs/cap-ai-provenance-profile.md).
2. **No public UAE rule on who approves an AI-drafted alert.** The UAE AI Charter asks for human oversight but sets no operational rule for it.
3. **Machine translation of alerts.** The UAE has no rule. In the US, the FCC refuses it for phone alerts while the National Weather Service uses it.
4. **The UAE lists no public CAP feed** on the WMO Register of Alerting Authorities. Saudi Arabia, Qatar and Kuwait do.
5. **No international norm for correcting false alerts.** Hawaii's correction took 38 minutes and was not linked to the false alert.
6. **Vetted templates don't fit cell broadcast.** The FCC's Arabic dust storm template is 10 cell broadcast pages long. The UAE handset spec summary says 1 page.
7. **CAP status and US test practice conflict.** 246 of 1,000 US alerts marked "Actual" carried a test event code.

## How it works

```
event inputs ─► Drafter ─► Translator ─► Gate: R0–R11 ─► 4 institution agents ─► people approve ─► sign ─► Gate again ─► broadcast
 (verified /    English     Arabic:       deterministic,    met office, issuer,     two names, read      XML-DSig    release
  unverified)   CAP fields  template/MT   cites sources     operator, Arabic:       open objections                  check
                    ▲                          │            search KB, quote it
                    ├── failed text rules ─────┘ (up to 2 redrafts)    │
                    └── cited objections ──────────────────────────────┘ (1 redraft, then reviewed again)
```

Each institution agent sees only part of the alert:

| Agent | Stands in for | Sees | Does not see |
|---|---|---|---|
| Met office reviewer | the national meteorological centre | event inputs (verified or not), English text, severity and certainty | register, area codes, Arabic |
| Issuing authority reviewer | the national emergency authority | issuer register, active and earlier alerts, requested area, alert status, sender and area | the hazard bulletin, Arabic |
| Network operator and regulator reviewer | the telecom regulator and operators | each language's phone text with characters, encoding and pages | inputs, register |
| Arabic language reviewer | an Arabic reviewer at the issuer | English and Arabic text, and how the Arabic was made | inputs, register, area |

None of them can approve. A person can release an alert with an objection still open only after ticking that they read it, and the log records who did.

| Rule | Checks | Main source |
|---|---|---|
| R0 | Valid CAP 1.2 against the official schema | OASIS CAP 1.2 / ITU-T X.1303bis |
| R1 | Two different named people approve a severe or extreme live alert | FCC Hawaii report (2018) |
| R2 | Status matches reality: no drill sent live, no "not a drill" in a drill, tests labelled | FCC Hawaii report |
| R3 | The area sent is the area requested, drawn for this event | US congressional report on LA County (2025) |
| R4 | The sender may warn for this hazard and area; no overreach past a higher authority's alert | UAE issuer list (press), Seoul 2023 |
| R5 | Signed with a registered originator key | CAP 1.2 §3.3.4.1 |
| R6 | Fits the cell broadcast page budget (GSM-7 93 / UCS-2 41 characters a page) | 3GPP TS 23.038, TDRA handset spec summary |
| R7 | Arabic and English both present | TDRA handset spec summary |
| R8 | The alert records AI involvement and who approved it | Proposed profile (gap 1) |
| R9 | Machine translation: vetted template or a named reader approves | FCC DA 25-12 |
| R10 | Corrections reference the alert they correct | CAP 1.2, IPAWS profile, FCC Hawaii report |
| R11 | No number, hazard or place that the inputs don't contain | ITU ESTR.AICNHM, MHEWS report (2026) |

Mapping to ITU-T Y.3172 and the AI Readiness Framework: [docs/y3172-and-readiness.md](docs/y3172-and-readiness.md).

## Check it yourself

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -q                               # one or more tests per rule
NADHIR_LLM=replay .venv/bin/python -m nadhir.bench          # rerun every replay from recorded model answers, no API key
.venv/bin/python scripts/verify_logs.py runs/bench/logs     # check every audit log's hash chain
python3 -I audit/count.py audit/snapshot/2026-11-08         # recount the real-feed audit offline
NADHIR_LLM=replay .venv/bin/python -m nadhir.ablation       # rerun the fault ablation from recorded answers
.venv/bin/python kb/index/verify.py                         # check every KB quote against the indexed text
.venv/bin/python -m kb.gap_search                           # search the UAE dataset for each gap
.venv/bin/python -m nadhir.serve                            # local demo at http://localhost:8000 (needs ANTHROPIC_API_KEY in .env to draft new alerts)
```

CI runs all of this on every push.

## Limits

- Replays are rebuilt from public reports, not the original systems. Fields the reports don't give are marked as reconstructed in each incident file. Wherever the record is silent (signature, number of approvers), the replay assumes the alert was fine, so the gate gets no credit it hasn't earned.
- Seoul rests on the ministry's statement as quoted in the press, and India on press reports only. J-Alert's official finding is a government white paper, but the detail that the area came from old drill data is press only. Brazil's official note is quoted, but no investigation report is public.
- The UAE handset rules (Arabic and English, one page) come from a compliance firm's summary of the TDRA spec, not the spec itself.
- The issuer, target zones and signing keys in the demo are stand-ins. Nothing here connects to a real broadcast system.
- In replays the approvals are scripted and labelled as such. In the live demo, a person clicks.
- R11 is a surface check. It catches invented numbers, hazard words and listed place names, not every wrong claim.
- One hosted language model plays all six agents (set with `NADHIR_MODEL`). The institution agents stand in for roles; they are not the real UAE bodies and don't speak for them. Recorded answers make every run replayable, but a fresh run can differ.
- The fault ablation uses faults we injected, copying real failure types; the answer key there is ours. The held-out replays are the independent test, and there are only three of them.
- Pickering, Florida and Taiwan were reconstructed by a separate research pass from public reports; several CAP fields are inferred and marked so in each file. Where the area encoding isn't public, the replay assumes it matched the request.
- If an intruder controls an issuer's own signing key, R5 cannot tell. The two-person rule is the backstop.

## Repository

`nadhir/` the gate, agents, institution reviewers, retrieval, orchestrator and server · `kb/` the knowledge base (registry with hashes and quotes; `kb/index/` the clause index and its build and verify scripts) · `bench/` real incidents, UAE scenarios and vetted templates · `audit/` real-feed audit and snapshot · `runs/` recorded model answers, results and logs · `docs/` gaps, CAP profile, mapping · `tests/`.

Open source under the MIT licence. Uses public documents only.
