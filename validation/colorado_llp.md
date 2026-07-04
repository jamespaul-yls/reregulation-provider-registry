# Validation: Colorado Limited License Professional (LLP) Roster

**Source:** https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf  
**Scraper:** `scrapers/colorado_llp.py` v0.1.0  
**Fixture:** `tests/fixtures/co_llp_roster_snap1.pdf`  
**Fixture sha256:** `49941ce75946f286e969d218ae59576187c563434113d9e00a2096b40a931bf0`  
**Scrape date:** 2026-06-29  
**PDF stated as-of date:** 2026-02-06

---

## Comprehensiveness (coverage / recall)

### Source totals

The PDF contains 3 pages with registration numbers 600000–600125 (consecutive, no gaps).

| Category | Count |
|---|---|
| Raw entries in PDF | 126 |
| Entries parsed | 126 |
| Active | 126 |
| Exited / suspended / unknown | 0 |
| **Coverage** | **126 / 126 (100%)** |

### Source authority

The PDF is titled "Admitted LLP Roster" and published directly by the Colorado Office of
Attorney Regulation Counsel (OARC) at `coloradolegalregulation.com`. The OARC is the official
regulator for the Colorado LLP program; this is the **authoritative mandatory roster**, not
an opt-in directory. Compare: Utah LPP (licensedlawyer.org — opt-in referral directory).

**Implication:** `disappeared_from_roster` events computed from this source will be strong
inferential signals (exiting the official OARC roster implies loss of active status).

### Note on PDF vs. JS search widget

The OARC attorney-search page (`/attorney-search/`) also has a JS-driven search widget.
The PDF roster was chosen because:
1. It is a direct, authoritative download from the regulator's own domain.
2. It contains all admitted LLPs in a single file (no pagination or JS interaction).
3. It is simpler and more reproducible than scraping a JS-rendered search form.

The PDF is re-published periodically (footer says "As of February 6, 2026"); the scraper
will detect stale data via content SHA-256 diffing on future scrapes.

### Source totals reconciliation

The PDF footer states "As of February 6, 2026." There is no separately stated total count
on the source page. Parsed row count (126) is confirmed by consecutive registration numbers
600000–600125 with no gaps.

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified sample of 15 rows (10% of 126 ≈ 13; rounded up to 15).
Sampled by registration number decile (one from each ~12-number block) plus 2 names
with non-standard features (suffix, compound name). Each field verified against the
fixture PDF (frozen at sha256 above) and cross-checked against the live OARC PDF
as of 2026-06-29.

**Sample date:** 2026-06-29

### Sampled rows (n=15)

| # | provider_id | legal_name | Verified | Notes |
|---|---|---|---|---|
| 1 | prov_co_llp_600000 | Catherine Joy McClaugherty | ✓ | First admitted LLP |
| 2 | prov_co_llp_600012 | Susan Rae Harris | ✓ | |
| 3 | prov_co_llp_600022 | Kyle Alan Melchior | ✓ | One of few male names |
| 4 | prov_co_llp_600033 | Kris Marrie Freeman | ✓ | |
| 5 | prov_co_llp_600043 | Sarah Lynn Del Rio-Garcia | ✓ | Hyphenated compound last name |
| 6 | prov_co_llp_600055 | Deborah E. Brown Frederick | ✓ | Middle initial + compound last |
| 7 | prov_co_llp_600061 | Mark David Smith | ✓ | |
| 8 | prov_co_llp_600072 | Aracely Noemy Gutierrez | ✓ | |
| 9 | prov_co_llp_600083 | Kelly Furca Thompson | ✓ | |
| 10 | prov_co_llp_600091 | Fernanda Victoria Soto Gonzalez | ✓ | Four-part name |
| 11 | prov_co_llp_600100 | Bobby Coe Jones, Jr. | ✓ | Comma from suffix, not Last-First inversion |
| 12 | prov_co_llp_600104 | Harry C. Green, IV | ✓ | Roman numeral suffix |
| 13 | prov_co_llp_600110 | Chloe Elizabeth Crandall | ✓ | |
| 14 | prov_co_llp_600118 | Jamie Ann Romero | ✓ | |
| 15 | prov_co_llp_600125 | Teresa Detton | ✓ | Last entry in PDF |

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name (as printed in PDF) | 0 / 15 | 0% |
| provider_id (reg number mapping) | 0 / 15 | 0% |
| current_status (all active per admitted roster) | 0 / 15 | 0% |
| jurisdiction (all CO) | 0 / 15 | 0% |
| provider_type (all individual) | 0 / 15 | 0% |
| authorization_date (all None, not in source) | 0 / 15 | 0% |
| practice_areas_raw (all ["Domestic Relations"]) | 0 / 15 | 0% |
| **Overall** | **0 / 15** | **0%** |

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

1. **PDF as-of date lags scrape date.** The PDF footer says "As of February 6, 2026" but was
   fetched on 2026-06-29. The OARC updates the PDF periodically; changes between the stated
   date and the fetch date are not captured. The snapshot sha256 will detect future PDF updates.

2. **Authorization date not available.** The PDF publishes only registration number and name.
   No admission date, license issue date, or year is included. All rows have
   `authorization_date = None`. Future work: contact OARC or check individual profile pages
   for admission dates.

3. **Practice areas are program-level, not individual.** The Colorado LLP program authorizes
   domestic relations practice only (C.R.C.P. Chapter 20 Rule 220). The PDF does not indicate
   individual practice area subsets (if any exist). All rows have
   `practice_areas_raw = ["Domestic Relations"]`.

4. **Name suffixes contain commas.** Two entries — "Bobby Coe Jones, Jr." (600100) and
   "Harry C. Green, IV" (600104) — have commas from name suffixes. These are correct and are
   preserved verbatim. The test suite allows commas only in suffix position (Jr./Sr./II/III/IV/V).

5. **Registration numbers as provider IDs.** `prov_co_llp_<reg_num>` is used as the stable
   provider ID. Registration numbers are assigned sequentially by OARC and are permanent;
   they are the most stable identifier available and do not depend on name spelling.

6. **No status distinctions in PDF.** The PDF is titled "Admitted LLP Roster" with no inactive
   or suspended sub-lists. All 126 entries are treated as active. If OARC publishes a
   separate suspended or revoked list, those entries are not captured in this scrape.
   Monitor OARC website for additional roster files.
