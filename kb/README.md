# Knowledge base

`sources.yaml` lists the public documents that the gate rules (R0 to R11) and the gap list (G1 to G7) rely on. Each entry has the document's title, publisher, date, URL, kind, jurisdiction, a check status, the date we fetched it, the SHA-256 of the bytes we fetched, the rules and gaps it supports, and one to three short verbatim quotes with a locator.

The repo holds metadata, hashes and short quotes only. Full documents are not stored here. Every source is public and free to read. Nothing is paywalled or confidential.

## Status values

- `verified-primary`: we fetched the issuing body's own text and found each quote in it.
- `verified-secondary`: the primary text was not reachable, so a press report or other summary was used. The quotes come from that summary, and the `notes` field names it. Every press article in the KB has this status, because a news report of an official finding is not the finding.
- `not-fetched`: we could not fetch the source. It has no quotes and no hash. No entry currently has this status.

The KB has 53 entries: 40 verified-primary and 13 verified-secondary. The clause index in `index/` splits these sources, plus the organisers' public UAE policy dataset, into 11,572 searchable clauses from 115 documents. Two entries were removed after the first pass: a u.ae page that returned HTTP 404, and press reports of a 2026 UAE alert whose cause is not public.

## How quotes were checked

1. Each URL was downloaded with curl into a scratch folder outside the repo.
2. The SHA-256 in `sources.yaml` is the hash of those raw bytes. Web pages and feeds change, so a later fetch of an HTML page, the OpenFEMA metadata or the WMO RSS will usually give a different hash. PDFs should match unless the publisher replaces the file.
3. PDFs were converted to text with `pdftotext`, in both layout and plain mode. HTML had scripts, styles and tags stripped. XML and JSON were also searched as raw text.
4. A script searched for each quote in the extracted text after normalising whitespace, Unicode compatibility forms (for example the "fi" ligature), curly versus straight quotes, dashes, zero-width characters and a space before punctuation left by HTML markup. The quote is otherwise character for character. All quotes in the file passed this check on 8 Nov 2026.
5. Locators give the section, paragraph or PDF page where the quote sits. "PDF p." is the page index in the file, which can differ from the printed page number.

## Points to know before citing

- UAE handset rules. The 2015 TS040 requirements (Arabic and English, one page) are known only from a compliance firm's summary, so `TDRA-TS040` is verified-secondary. TDRA's 2019 UAE-Alert specification (`TDRA-TSFS001`, TS FS 001 v2.0) is verified-primary: handsets must show alerts in Arabic and English, and it sets no page limit. For the 2017 cell broadcast behaviour spec we did fetch the TRA-hosted file (`TDRA-2017-CB`), but it is a one-page table with no title or date. The title and the 21 Sep 2017 effective date come from the Kiwa summary that links to it. The table gives channel IDs for a primary and a secondary language. It does not name the languages.
- UAE issuers. The list of bodies allowed to send alerts comes from Gulf News (`UAE-ISSUERS`). No NCEMA document with the list was found.
- Rules whose incident evidence is press only: R2 (India test alerts), R3 (J-Alert 2022), R4 (Seoul 2023) and R5 (Brazil 2026). Each of these rules also has at least one primary standard or regulator source.
- Three US failures have primary findings: Hawaii 2018 (FCC report), Los Angeles 2025 (Rep. Garcia's report) and the FCC orders on machine translation.

## Checks

Question: is the Canadian CAP-CP `AutoTranslated` parameter still in the current CAP-CP 1.0 rules?

Answer: yes, but it is now a recommendation, not a rule. The CAP-CP hub page at publicsafety.gc.ca lists "1.0 Draft 2" (August 2016) as the latest Introduction and Rule Set, after 1.0 Draft 1 (January 2016) and Beta 0.4A (July 2012). In 1.0 Draft 2 the item is "Recommendation #6. Indicate automated translation of free form text". It is marked Use: Optional, with valueName `profile:CAP-CP:1.0:AutoTranslated` and value yes or no. In 1.0 Draft 1 it is Recommendation #5. In Beta 0.3 it was item 17 of the rule set (`profile:CAP-CP:0.3:AutoTranslated`), also marked Optional. Version 1.0 moved it into a separate list of recommendations. The 1.0 document's version block still reads Date "<ADD FINAL DATE>" and Approval Date "TBD", and the hub calls it "Version 1.0 (draft)". So no approved, final 1.0 text was found.

Sources:
- 1.0 Draft 2: https://www.publicsafety.gc.ca/cnt/rsrcs/pblctns/capcp-ntro-rl-st/index5-eng.aspx
- 1.0 Draft 1: https://www.publicsafety.gc.ca/cnt/rsrcs/pblctns/capcp-ntro-rl-st/index4-eng.aspx
- Hub and version table: https://www.publicsafety.gc.ca/cnt/mrgnc-mngmnt/mrgnc-prprdnss/capcp/index-en.aspx
- Beta 0.3: https://www.publicsafety.gc.ca/cnt/rsrcs/pblctns/capcp-ntro-rl-st/index-eng.aspx

The 1.0 document names www.CAP-CP.ca as the official site. We could not read it: its HTTPS certificate does not match the host name, so the fetch failed. Treat the publicsafety.gc.ca copy as the best public text.

How to word it: "Canada's CAP-CP 1.0 (Draft 2, 2016) recommends an optional `AutoTranslated` yes/no parameter for machine-translated text. It records no approver and no AI drafting."
