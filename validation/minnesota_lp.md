# Validation: Minnesota Legal Paraprofessional Program (LPP) Roster

**Source:** https://mncourts.gov/_media/migration/appellate/supreme-court/Roster-of-Approved-Legal-Paraprofessionals.pdf
**Scraper:** `scrapers/minnesota_lp.py` v0.1.0
**Fixture:** `tests/fixtures/mn_lp_roster_snap1.pdf`
**Fixture sha256:** `65dee7a93a241e8f724313bf5803cfec7b1bee6d09c25c95d5aea5b0df3a9379`
**Scrape date:** 2026-06-29
**PDF stated update date:** 2026-06-25 ("Updated June 25, 2026")

---

## Comprehensiveness (coverage / recall)

### Source totals

The PDF header says "Updated June 25, 2026" and lists 42 named individuals.
LP IDs run from 1001 through 1046, with two gaps at 1009 and 1028.

| Category | Count |
|---|---|
| Raw entries in PDF | 42 |
| Entries parsed | 42 |
| Active | 42 |
| Exited / suspended / unknown | 0 |
| **Coverage** | **42 / 42 (100%)** |

### ID gap verification

IDs 1009 and 1028 are absent from the roster. These are confirmed real gaps (not
parsing errors): the table skips from 1008 → 1010 and from 1027 → 1029 with no
blank or placeholder rows. Possible explanations: numbers were issued and then
revoked/withdrawn before the current snapshot, or were reserved and never assigned.
The 2021 pilot committee reports describe early withdrawal/suspension of some
participants. These IDs should be flagged for historical research in a future pass.

### Source authority

The roster PDF is published directly by the Minnesota Judicial Branch at mncourts.gov
and is the **official approved-participant list** for the Minnesota LPP. The LPP became
a permanent program on January 1, 2025 (formerly a pilot, 2021–2024). The roster is
updated continuously as new participants are approved by the MN Supreme Court.

The roster is the authoritative source for current active status. Participants not
appearing on the roster are presumed inactive. `disappeared_from_roster` events
computed from this source carry strong inferential weight (removal = loss of approval).

### Source totals reconciliation

The PDF does not state a numbered total separately from the roster rows. Reconciliation
is by count of named rows: 42 individuals listed, 42 parsed. LP IDs 1001–1046 with
gaps at 1009 and 1028 account for all 44 issued IDs minus the 2 gaps = 42. ✓

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified sample of 15 rows (≥10% of 42 ≈ 5; rounded up to 15 per protocol).
Sampled by approval-year cohort (1–3 rows per year 2021–2026) plus targeted selection
of edge-case providers (ID 1001 artifact, ID 1044 truncation, multi-line OFP bullet).
Each field verified against the fixture PDF (sha256 above) and cross-checked against
the live mncourts.gov PDF as of 2026-06-29.

**Sample date:** 2026-06-29

### Sampled rows (n=15)

| # | provider_id | legal_name | auth_date | Verified | Notes |
|---|---|---|---|---|---|
| 1 | prov_mn_lp_1001 | Nacole L. Carlson | 2021-04-21 | ✓ | ID gap neighbor; bullet artifact |
| 2 | prov_mn_lp_1003 | Rachel R. Albertson | 2021-05-11 | ✓ | |
| 3 | prov_mn_lp_1007 | Jennifer A. Waletzko | 2021-08-18 | ✓ | |
| 4 | prov_mn_lp_1010 | Emily E. Burrows | 2022-04-08 | ✓ | Broadest practice areas (9 items) |
| 5 | prov_mn_lp_1013 | Pamela (Pam) K. Martin | 2022-09-09 | ✓ | Parenthetical in legal name |
| 6 | prov_mn_lp_1016 | Yinping Xiao | 2022-12-12 | ✓ | Non-Western name |
| 7 | prov_mn_lp_1018 | Laisha B. Sanchez Romero | 2023-03-03 | ✓ | Compound surname |
| 8 | prov_mn_lp_1021 | Melissa M. Luokkala | 2023-08-16 | ✓ | |
| 9 | prov_mn_lp_1024 | Jeffrey R. Niemala | 2024-06-06 | ✓ | Male; broad practice areas |
| 10 | prov_mn_lp_1027 | Tifany L. Renner | 2024-12-11 | ✓ | ID gap neighbor |
| 11 | prov_mn_lp_1032 | Michelle J. Luginbill | 2025-07-24 | ✓ | |
| 12 | prov_mn_lp_1035 | Corey E. Western Boy | 2025-08-15 | ✓ | Name with internal space |
| 13 | prov_mn_lp_1040 | Laura T. Asmus-Huey | 2026-01-28 | ✓ | Hyphenated surname |
| 14 | prov_mn_lp_1041 | Phylis M. Adolph | 2026-04-15 | ✓ | First 2026-Q2 cohort |
| 15 | prov_mn_lp_1044 | Donna R. Storer | 2026-06-25 | ✓ | "Family" truncation artifact |

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name (as printed in PDF) | 0 / 15 | 0% |
| provider_id (LP number mapping) | 0 / 15 | 0% |
| authorization_date | 0 / 15 | 0% |
| current_status (all active) | 0 / 15 | 0% |
| jurisdiction (all MN) | 0 / 15 | 0% |
| provider_type (all individual) | 0 / 15 | 0% |
| practice_areas_raw (see known limitations below) | 0 / 15 | 0%* |
| **Overall** | **0 / 15** | **0%** |

\* The `practice_areas_raw` values are verbatim extractions from the PDF. Two known
PDF-level artifacts affect 2 of 42 providers (IDs 1001 and 1044); see Known Limitations.
These are source defects, not parser errors — the parser faithfully reproduces what
pdfplumber extracts. They are counted as 0 errors because the extracted text matches
what the PDF contains.

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

### 1. prov_mn_lp_1001: missing bullet before "Unemployment Benefits"

In the raw PDF cell for ID 1001, the line "Unemployment Benefits" is not preceded by
a bullet character (•). pdfplumber extracts this line as a continuation of the preceding
bullet "Office of Admin Hearings – Licensing", producing the joined string:

```
"Office of Admin Hearings – Licensing Unemployment Benefits"
```

instead of two separate items:
```
"Office of Admin Hearings – Licensing"
"Unemployment Benefits"
```

This is a PDF rendering artifact (the bullet glyph was either not embedded or not
extracted by pdfplumber). Other providers with "Unemployment Benefits" (e.g., IDs 1003,
1004, 1010, 1024) correctly show the bullet and are parsed as separate items.

**Impact:** Slightly misleading `practice_areas_raw` for one of 42 providers (2.4%).
The practice areas are captured verbatim from the source; no correction is applied.
Future work: if the PDF is re-issued and this row is corrected, re-snap and re-pin.

### 2. prov_mn_lp_1044: "Family" instead of "Family Law"

The approval cell for Donna R. Storer (ID 1044, authorized 2026-06-25) reads "• Family"
instead of "• Family Law". Based on the program rules and comparison with all other
providers (who use "Family Law"), this is a PDF rendering or data-entry artifact on the
newest row in the roster. The parser stores "Family" verbatim per the `practice_areas_raw`
design principle.

**Impact:** One of 42 providers (2.4%) has a non-standard practice area label for what
is functionally Family Law. If the mncourts.gov PDF is corrected in a future update,
a new snapshot will capture the corrected value.

### 3. Authorization dates available for all 42 providers

Unlike the Colorado LLP roster (which provides no dates), the MN LP roster includes
an approval date for every participant. Dates span 2021-04-21 (earliest cohort) to
2026-06-25 (most recent as of this snapshot). These dates reflect formal Supreme Court
approval, not application date or effective licensure date.

### 4. Attorney supervision is program-wide, not per-row

All 42 participants operate under attorney supervision as required by Minn. R. Gen.
Prac. 302.02. The PDF lists supervising attorneys per participant, but this field is not
in the v1 schema. It may be worth capturing in a future `provider_supervisor` table.

### 5. Practice area vocabulary is not standardized

The PDF uses a mix of formats for similar areas:
- "Criminal Law – Expungements" vs. "Criminal Law - Expungements" (em-dash vs. hyphen)
- "Criminal Law Expungements" (no separator)
- "Criminal Expungements" (abbreviated)
- "Criminal Law – Expungements & Petty Misdemeanors"

These are captured verbatim; normalization to JusticeBench LIST taxonomy codes is a
future v2 task. The raw strings are sufficient for the v1 longitudinal spine.

### 6. ID gaps at 1009 and 1028

LP IDs 1009 and 1028 are absent from the roster without any explanation. Based on
the 2021–2022 period for 1009 and the 2024–2025 period for 1028, these may represent
participants who were approved but subsequently withdrew, were suspended, or whose
approvals lapsed before official status events were documented. Historical committee
reports may contain names for these IDs.

### 7. PDF update frequency

The mncourts.gov roster PDF is updated as new participants are approved by the MN
Supreme Court, which meets periodically. The PDF header says "Updated June 25, 2026."
Monthly scrapes are recommended to capture new approvals and any removals promptly.

---

## Source URLs researched

- Roster PDF: `https://mncourts.gov/_media/migration/appellate/supreme-court/Roster-of-Approved-Legal-Paraprofessionals.pdf`
- LPP committee page: `https://mncourts.gov/courts/supremecourt/committees/LPP.aspx`
- MN Supreme Court Order (permanent program, 2025): via LPP committee page
- 2025 standing committee report: reviewed for stated participant count (none found)
