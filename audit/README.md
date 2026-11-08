# CAP provenance audit

This audit counts what real public CAP alerts record today about who or what made them. CAP 1.2 (ITU-T X.1303bis) has no defined field for saying that AI drafted or translated an alert, or which named person or role approved it. The scripts download real alerts and count the fields that come closest.

## What it measures

Sources:

- US IPAWS: the 1,000 most recent alerts in the OpenFEMA archive (`IpawsArchivedAlerts`, ordered by `sent` descending). Each record holds the raw CAP XML, and the audit reads that XML rather than FEMA's parsed fields.
- The WMO Register of Alerting Authorities (`rss.xml`): which GCC states (Saudi Arabia, Kuwait, Qatar, Bahrain, Oman, UAE) list a CAP feed, plus Canada and Australia.
- The current items of every CAP feed the register lists for those eight states.

For each source, `count.py` reports:

- the number of alerts;
- how many carry a non-empty `<source>`, a non-empty `<note>`, an XML Signature (`ds:Signature`), more than one `<info>` language, an `<instruction>`, or any `<parameter>`;
- every distinct parameter `valueName`, with the number of alerts that carry it;
- how many alerts carry any marker of AI or machine involvement. It searches `source`, `note`, `code` and every `valueName`/`value` pair, case-insensitively, for `ai`, `artificial`, `machine`, `auto-translat`/`autotranslat`, `generated`, `llm` and `gpt`. `ai`, `llm` and `gpt` must stand as whole tokens, otherwise `ai` would match "rain" and "Maine";
- how many alerts name an approver: a `valueName` or `value` containing `approv`, `authoriz`/`authoris`, `username` or `operator`;
- the raw text behind every marker match, so a person can rule out false positives.

Messages with status `Test` or `Exercise` are counted in their own column. Nothing is dropped.

## How to rerun

```
python3 -I audit/fetch.py
python3 -I audit/count.py audit/snapshot/<date>
```

`fetch.py` writes `audit/snapshot/<UTC date>/`: the IPAWS pages as returned, the register RSS, the UAE register record page, and each feed with its items. `manifest.json` lists every request with its URL, fetch time, SHA-256, size and any error. The script waits 0.3 s between requests and identifies itself as `cap-provenance-audit/0.1`. If the IPAWS pages together exceed 60 MB they are stored gzip-compressed.

`count.py` uses no network. It checks each file against the manifest hash, then writes `audit/results.json` and `audit/results.md`.

Both scripts use only the Python standard library. Tests (pytest, three fixture alerts):

```
python3 -I -m pytest tests/test_audit.py
```

## Results (snapshot 2026-11-08)

Fetched 8 Nov 2026, 18:50 to 19:02 UTC. Full tables, every parameter name and every matched raw value are in `results.md` and `results.json`. Counts are for alerts whose status is not Test or Exercise; the Test/Exercise column is counted apart.

| Source | Alerts | Test/Exercise | `<source>` | non-empty `<note>` | XML Signature | >1 language | `<instruction>` | any `<parameter>` | AI/machine marker | Approver marker |
|---|---|---|---|---|---|---|---|---|---|---|
| US IPAWS (OpenFEMA) | 1000 | 0 | 997 | 4 | 1000 | 324 | 405 | 874 | 0 | 17 |
| Canada, NAAD feed (ECCC, Quebec) | 93 | 7 | 93 | 93 | 93 | 93 | 32 | 93 | 0 | 0 |
| Saudi Arabia NCM, ar feed | 54 | 0 | 0 | 0 | 54 | 0 | 0 | 0 | 0 | 0 |
| Saudi Arabia NCM, en feed | 54 | 0 | 0 | 0 | 54 | 0 | 0 | 0 | 0 | 0 |
| Kuwait Met Dept | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| Qatar CAA, ar feed | 5 | 0 | 0 | 0 | 5 | 0 | 5 | 0 | 0 | 0 |
| Qatar CAA, en feed | 5 | 0 | 0 | 0 | 5 | 0 | 5 | 0 | 0 | 0 |
| Australia BoM (WMO mirror) | 499 | 0 | 0 | 0 | 0 | 0 | 210 | 0 | 0 | 0 |
| Bahrain (ar, en), Oman (ar, en), Alberta | 0 | 0 | | | | | | | | |

What the numbers say:

- No alert in any source carries a marker of AI or machine involvement. That includes all 100 Canadian alerts, which declare `profile:CAP-CP:0.4` but never use the profile's `AutoTranslated` parameter.
- No alert names an approver. The 17 IPAWS "approver" matches are all a vendor-specific `UserName` parameter, sent alongside `OriginatingSystem = EMnet`. The values are logins or shift names (`EMnet`, `Administrator`, `seoc`, `SHIFT D SOD`, `Operator 145` and a few others). They say who was logged in to the sending software, not who approved the message.
- IPAWS `<source>` holds a code and a software version (`050302 v1.1` in 214 alerts, `211803 v2.3.0` in 201, `091903v6.0` in 182; 35 distinct values). The four non-empty notes are `EAS-150` (2), `WEA-150` and `TEST-1`.
- The 93 Canadian notes are all an ECCC service notice about the CAP feed itself.
- Every IPAWS alert has status Actual, but 246 of them carry a SAME test or demo event code (RMT, RWT, NPT or DMO). They are counted as live because their CAP status says so.
- Signatures: IPAWS, Canada, Saudi Arabia and Qatar sign every alert. Kuwait and the Australian mirror copies are unsigned.

WMO register (303 entries). Saudi Arabia, Kuwait, Qatar, Bahrain and Oman list CAP feeds. The UAE has one entry, "United Arab Emirates: Meteorological Department" (record dated 11 Sep 2013, `recId=173`), and it lists no `capAlertFeed`. The record page, saved in the snapshot, shows "CAP Feed URL(s)" and "Authorization Basis" both blank. Of the GCC feeds, Saudi Arabia (54 items per language, updated the day of the snapshot), Kuwait (1 item, 8 Nov 2026) and Qatar (5 items, latest 27 Oct 2026) had current alerts. Bahrain's feeds were empty (last built 30 Sep 2026). Oman's were empty and last built in 2023 and 2024.

Fetch failures: 1 of 737 requests. One Australian item listed in the feed returned HTTP 404.

## Limits

- IPAWS dominates. It supplies 1,000 of the 1,718 alerts counted (1,711 live), and one country's practice shapes the pooled picture. Read each source on its own row.
- This is one snapshot. Feeds list only what is current, so the GCC rows cover days or weeks, not a year. The IPAWS sample covers 17 Oct to 7 Nov 2026.
- The keyword search finds the listed words and nothing else. An improvised marker in other words (for example a vendor code that means "drafted by assistant") would be missed. Free-text fields (`headline`, `description`, `instruction`) are not searched. The raw-value lists exist so a person can check what was and was not caught.
- `ai`, `llm` and `gpt` match only as whole tokens. Without that rule `ai` matches "rain", "Maine" and "Bahrain".
- The Australian feed on the register is a WMO mirror (`severeweather.wmo.int`), and signatures or other fields may differ from what the Bureau publishes directly.
- Saudi Arabia, Qatar, Bahrain and Oman publish each language as a separate feed, so their alerts show one language each. ">1 language" counts languages inside one alert only.
- A signature is counted when a `ds:Signature` element is present. The audit does not verify signatures.
- The register shows what each country has registered with WMO, not every public alert channel it runs. The UAE's cell-broadcast alerts come from other authorities, and this audit says nothing about them.
