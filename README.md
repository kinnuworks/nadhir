# Nadhir

**AI drafts the public warning. Cited rules and two people decide whether it goes out.**

Nadhir (نذير, "warner") is a pre-broadcast check for AI-drafted emergency alerts in CAP 1.2 (ITU-T X.1303bis), the format behind cell broadcast warnings such as UAE-Alert. Two AI agents draft and translate the alert. The model never decides. Twelve deterministic rules decide, each one quoting a public policy or an official investigation from a 43-source knowledge base. A person approves, the alert is signed, and every step goes into a hash-chained log.

**Live demo:** https://nadhir-gilt.vercel.app (no sign-up)

**Try it in 30 seconds**
1. Open the live demo. The inputs are already filled in: a real UAE National Center of Meteorology dust warning, plus an unverified rumour. Press **Draft alert**.
2. Look at what the gate did. The drafter left the rumour out. The Arabic version is machine translated, so the alert is held until someone who reads Arabic approves it (rule R9). A severe alert needs two different people (R1).
3. Type two names and an Arabic reviewer, then press **Approve**. You get the signed CAP XML, the final verdicts and the audit log with its hash chain.

## What it found

**Replays of real alert failures.** We rebuilt six real public alert failures from published reports and ran each message through the gate as it was actually sent. Our answer key is each investigator's or authority's own finding, not ours.

| Real failure | Answer key | Rules that fired on the real message | Rule the finding points to |
|---|---|---|---|
| Hawaii, Jan 2018: missile alert sent live during a drill; correction 38 min later | FCC (official report) | R1, R2, R10 (correction) | R2, R1, R10: caught |
| Japan, Oct 2022: J-Alert also sent to Tokyo's islands | Fire and Disaster Management Agency white paper (official) | R3 | R3: caught |
| Seoul, May 2023: city air-raid alert the ministry called erroneous | Interior Ministry statement (via press) | R3, R4 | R4: caught |
| Los Angeles, Jan 2025: evacuation warning sent county-wide, not to the fire area | US congressional report (official) | R3, R10 (correction) | R3: caught |
| Brazil, Jun 2026: "Extreme" alerts sent by an intruder | Ministry official note | R1, R4, R5 | R5: caught |
| India, 2023: test messages shown as Extreme alerts | Press only | R2 | R2: caught |

In every replay, the rule the official finding points to fired on the real message (6 of 6). Seoul's evidence is the ministry's own public correction, quoted in the press. India's is press reporting only.

The rules were written with these findings in hand, so this shows the rules encode the findings. It is not an independent test. For that, see the next result.

**The gate on 1,000 real routine alerts.** We ran the context-free rules (R0, R2, R6, R10) over the 1,000 most recent US IPAWS alerts. It would hold 5 of them: 3 cancellations sent as brand-new alerts with no `<references>` to the alert they cancel (R10, the same pattern as Hawaii's correction), and 2 test messages sent with status Actual (R2). Our first run also flagged 119 scheduled US EAS tests, which go out as "Actual" by US convention. We then added a narrow exemption for them and say so here.

**What real alerts record today.** We read 1,711 live alerts from 8 public feeds (US IPAWS, Canada, Australia, Saudi Arabia, Qatar, Kuwait) on 8 Nov 2026. None records that AI or machine translation was involved, and none records an approval. The only approver-like field is one US vendor's `UserName` login parameter, in 17 alerts. The UAE lists no public feed on the WMO Register of Alerting Authorities. Details: [`audit/`](audit/README.md).

**AI on the same inputs.** We gave the drafter the same inputs in 5 of the replays, plus 4 UAE scenarios built on real NCM warnings, run 3 times each.
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
7. **CAP status and US test practice conflict.** 246 of 1,000 US alerts marked "Actual" were scheduled tests.

## How it works

```
event inputs ─► Drafter (LLM) ─► Translator (LLM) ─► Gate: R0–R11 ─► people approve ─► sign ─► Gate again ─► broadcast
   (verified /     English CAP       Arabic: vetted       deterministic,     two names for      XML-DSig      release
    unverified)    fields            template or MT       cites sources      high impact                       check
                       ▲                                       │
                       └──────── failed text rules go back to the drafter (up to 2 redrafts) ────┘
```

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
.venv/bin/python -m nadhir.serve                            # local demo at http://localhost:8000 (needs ANTHROPIC_API_KEY in .env to draft new alerts)
```

CI runs all of this on every push.

## Limits

- Replays are rebuilt from public reports, not the original systems. Fields the reports don't give are marked as reconstructed in each incident file. Wherever the record is silent (signature, number of approvers), the replay assumes the alert was fine, so the gate gets no credit it hasn't earned.
- Three incidents (J-Alert, Seoul, India) rest on press reports of official statements. Brazil's official note is quoted, but no investigation report is public.
- The UAE handset rules (Arabic and English, one page) come from a compliance firm's summary of the TDRA spec, not the spec itself.
- The issuer, target zones and signing keys in the demo are stand-ins. Nothing here connects to a real broadcast system.
- In replays the approvals are scripted and labelled as such. In the live demo, a person clicks.
- R11 is a surface check. It catches invented numbers, hazard words and listed place names, not every wrong claim.
- One model (claude-opus-5-5) plays both agents. Recorded answers make every run replayable, but a fresh run can differ.
- If an intruder controls an issuer's own signing key, R5 cannot tell. The two-person rule is the backstop.

## Repository

`nadhir/` the gate, agents, orchestrator and server · `kb/` the knowledge base (metadata, hashes and short quotes only) · `bench/` real incidents, UAE scenarios and vetted templates · `audit/` real-feed audit and snapshot · `runs/` recorded model answers, results and logs · `docs/` gaps, CAP profile, mapping · `tests/`.

Open source under the MIT licence. Uses public documents only.
