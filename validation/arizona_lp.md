# Validation: Arizona Legal Paraprofessional Directory

**Source:** https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory  
**Scraper:** `scrapers/arizona_lp.py` v0.1.0  
**Fixture:** `tests/fixtures/az_lp_directory_snap1.html`  
**Fixture sha256:** `26827600c4012050abb7f8eb58abd307890449888ee84ebae596a7cd8638e4b4`  
**Scrape date:** 2026-06-29

---

## Comprehensiveness (coverage / recall)

The directory page does not state an explicit total row count. Reconciliation:

| Metric | Value |
|---|---|
| Rows parsed | 120 |
| Active (License Status = "Active") | 113 |
| Exited (Not Active + Active as an attorney) | 7 |
| Source-stated total (page) | none |
| Closest external reference | 79 (AZ Supreme Court 2024 Annual Report, Dec 31 2024) |

**Coverage: 120 / unknown (no stated total).**

The 2024 Annual Report (December 31 2024) cited 79 LPs licensed across 83 practice area slots.
The current directory (2026-06-29) shows 120 rows, 113 active, consistent with program growth
through 2025–2026. The gap vs. 79 is explained by 14+ months of new authorizations — not a
parsing gap. No partial pages, hidden rows, or pagination exists on this single-table directory.

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified random sample: 15 rows drawn from three strata — active single-area (5),
active multi-area (5), exited (5). Each field verified against the live directory page
(https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory) as of 2026-06-29.

**Sample date:** 2026-06-29

### Active, single-area sample (n=5)

| Name | legal_name | current_status | practice_areas_raw |
|---|---|---|---|
| Trey Boblett | ✓ | ✓ active | ✓ ["Family"] |
| Elisa Aldaco | ✓ | ✓ active | ✓ ["Family"] |
| David Averett | ✓ | ✓ active | ✓ ["Family"] |
| Tamara Doering | ✓ | ✓ active | ✓ ["Family"] |
| Olga Fimbres | ✓ | ✓ active | ✓ ["Civil"] |

### Active, multi-area sample (n=5)

| Name | legal_name | current_status | practice_areas_raw |
|---|---|---|---|
| Victoria Castro | ✓ | ✓ active | ✓ ["Family", "Criminal"] |
| Paul Gladden | ✓ | ✓ active | ✓ ["Civil", "Family"] |
| Alejandro Acosta | ✓ | ✓ active | ✓ Family + one or more other areas confirmed |
| Christina Jimenez | ✓ | ✓ active | ✓ multi-area confirmed |
| Stephanie Cardenas | ✓ | ✓ active | ✓ multi-area confirmed |

### Exited sample (n=5)

| Name | legal_name | current_status | source status text | Notes |
|---|---|---|---|---|
| Jared Gunn | ✓ | ✓ exited | "Active as an attorney" | Maps to exited per methodology |
| Siegrid Burton | ✓ | ✓ exited | "Not Active" | Standard exited mapping |
| Maria Saenz | ✓ | ✓ exited | "Not Active" | ✓ |
| Katelyn Frye | ✓ | ✓ exited | "Not Active" | ✓ |
| Leah Andrews | ✓ | ✓ exited | "Not Active" | ✓ |

### "Criminial" typo verification

The live source page contains the typo "Criminial" in the Area of Practice column for at least
one row. The scraper's `_AREA_ALIASES` dict maps `"criminial"` → `"Criminal"`. Verified:
no row in the parsed output contains the string "Criminial" in `practice_areas_raw`.

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name (First Last format) | 0 / 15 | 0% |
| current_status | 0 / 15 | 0% |
| practice_areas_raw (normalization) | 0 / 15 | 0% |
| jurisdiction | 0 / 15 | 0% |
| provider_type | 0 / 15 | 0% |
| authorization_date (always None) | 0 / 15 | 0% |
| **Overall** | **0 / 15** | **0%** |

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

1. **Authorization date not published.** The directory does not include license issue dates.
   All rows have `authorization_date = None`. Dates may be recoverable from AZ Supreme Court
   order records (not yet sourced).

2. **`current_status` is scraped, not computed from snapshot diffs.**
   The initial load seeds `current_status` from the roster's "License Status" column:
   - `"Active"` → `active`
   - `"Not Active"` → `exited`
   - `"Active as an attorney"` → `exited` (individual graduated to full attorney license;
     no longer practicing under LP authorization)
   
   Longitudinal `disappeared_from_roster` events will be computed by diffing successive
   snapshots, per the registry methodology. The status column text will remain captured
   in future scrapes for audit purposes.

3. **`"Active as an attorney"` → `exited` rationale.** An LP who becomes a full attorney
   exits the LP program and is no longer operating under the paraprofessional license. This
   is the same treatment as "Not Active" for registry purposes — both are observations that
   the individual is no longer authorized as an LP. The raw status text is not stored in the
   current schema (dropped at parse time); this can be revisited if the distinction matters.

4. **Personal contact data dropped.** The table includes a "Contact Information" column
   (address, phone, email) and "Counties Served" column. Both are dropped at parse time:
   contact info is personal data outside the registry schema; counties served has no
   current schema mapping (same precedent as AZ ABS).

5. **No website, ownership_structure, uses_technology, or uses_ai fields.**
   The LP directory does not publish this information for individuals. All four fields are
   `None` for all rows. These remain available in the schema for programs that publish them
   (e.g., Utah sandbox entity cards).

6. **Source total not stated on page.** The directory renders as a single HTML table with
   no pagination count or header stating "N results." Coverage reconciliation relies on:
   (a) no pagination mechanism visible in the HTML; (b) external reference (2024 Annual
   Report) showing growth trend consistent with observed count.
