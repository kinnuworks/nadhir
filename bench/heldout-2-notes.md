# Held-out set 2: notes

Fetched on 2026-11-10. Four new incident files in bench/incidents/:

- nl-alert-2019.yaml
- uk-welsh-test-2023.yaml
- nz-ema-test-2017.yaml
- hennepin-2024.yaml

I chose them on the strength of the official record first, then for spread across countries and failure types.
I mapped each one to rules using only the rule descriptions in the brief.

## Picked

| File | Country | Failure type | Official body quoted | expected_rules |
|---|---|---|---|---|
| nl-alert-2019 | Netherlands | Wrong facts: a national NL-Alert during the 112 outage gave a WhatsApp number that was a newspaper tip line. A correction alert followed an hour later. | Agentschap Telecom, Inspectie Justitie en Veiligheid and Inspectie Gezondheidszorg en Jeugd, joint report "Onbereikbaarheid van 112 op 24 juni 2019" (June 2020) | R11 |
| uk-welsh-test-2023 | United Kingdom | Language text altered by an automated step: an online autocorrect turned "ddiogel" (safe) into "Vogel" in the Welsh part of the bilingual national test. | Cabinet Office, written ministerial statement HCWS740, 25 April 2023 | R9 |
| nz-ema-test-2017 | New Zealand | Test reached the public: three Emergency Mobile Alert test messages meant for a restricted test environment went to Vodafone customers at about 1:30 am. | Ministry of Civil Defence & Emergency Management, statement on civildefence.govt.nz | R2 |
| hennepin-2024 | United States (Minnesota) | Wrong area through the wrong channel: a one-block shelter-in-place meant for WEA went out over EAS to the Twin Cities broadcast region. | Hennepin County Sheriff's Office media release, 23 April 2024 | R3 |

Rule mapping caveats, also written into each file:

- NL: R11 only catches the number if the inputs carry the verified numbers. The same report also finds that a control room sent its own national alert, which the ministry's guide reserved to the ministry (an R4 point). That alert is a different message, so I quoted it but did not count it.
- UK: the official cause is an autocorrect, not machine translation. R9 is the closest rule, not an exact one. R7 would pass because both languages were present.
- NZ: the messages were tests and were called tests. What went wrong was the audience, so R2 is the closest rule. R3 is not counted because no public area was requested. The message text is not public, so most CAP fields are unknown.
- Hennepin: R3 catches this only if the channel or the EAS geocodes are part of the area comparison. No correction alert was sent.

## Considered and rejected

- Alaska tsunami WEA, 15 July 2023 (alert reached Anchorage, outside the warned coast). Rejected. The only official words I found were a state official's remarks to the press and an NWS tweet saying it would look into it. I found no published finding.
- Germany Warntag, 10 September 2020 (national test reached phones late). Rejected. The BBK cause (many alerts triggered at once through MoWaS) reaches me only through a Land press release and a Bundestag question, not a BBK document I could fetch. The failure is also delivery delay, which none of the 12 rules covers.
- NWS tsunami test, 6 February 2018 (a test went out as a live warning through a private weather app). Rejected. NWS and AccuWeather blamed each other, I found no final root-cause document, and the channel was a private app, not a public alerting system.
- Warren County, Ohio, "secure doors" alert. Rejected. A county EMA said human error, but I had a stronger wrong-area case with a fuller official release (Hennepin).
- New Zealand tsunami alerts, July 2025 (duplicates and missed alerts). Rejected. NEMA's explanation is about delivery differences between handsets, not message content or area.
- NYC Spanish flood warning by drone, August 2024 (badly machine-voiced Spanish). Rejected. It was a drone loudspeaker, not a phone, cell broadcast or national alerting channel. The apology was a post on X, not a finding.
- Sonoma County fires 2017, Maui fires 2023, Valencia DANA 2024, Auckland floods 2023. Rejected. Their findings are about alerts sent late or not at all, which the 12 rules do not cover.
- Pickering 2020 French-language gap. Already covered by pickering-2020.yaml.
- Hawaii 2018, J-Alert 2022, Seoul 2023, India test 2023, LA County Kenneth fire 2025, Brazil 2026, Florida test 2023, Taiwan 2024. Already in the bench.

## Sources and hashes

I fetched every source cited in the four files with curl on 2026-11-10 and hashed the bytes with shasum -a 256.
Each file lists the hashes under source_hashes. Notes on fetching:

- civildefence.govt.nz returned 403, so I used the raw Wayback capture of 15 October 2017.
- The UK Parliament statement page refused automated fetches, so I used the Parliament written statements API record for HCWS740.
- News pages are dynamic, so their hashes may change on a refetch. The official PDFs, the API record and the Wayback capture should stay stable.

I quote official findings verbatim from those fetched bytes. Dutch quotes carry an unofficial translation.

## Independence

I did not open nadhir/gate.py, nadhir/bench.py, nadhir/institutions.py or anything under runs/, and I did not
run any code in nadhir/. The only repo files I read were bench/incidents/taiwan-2024.yaml and
bench/incidents/pickering-2020.yaml, plus the corrections blocks of hawaii-2018.yaml and la-county-2025.yaml
for their format, and grepped the finding_status values across bench/incidents.
