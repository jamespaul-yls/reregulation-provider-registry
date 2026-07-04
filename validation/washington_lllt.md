# Validation: Washington Limited License Legal Technician (LLLT) Roster

**Source:** https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx?ShowSearchResults=TRUE&LicenseType=LLLT
**Scraper:** `scrapers/washington_lllt.py` v0.1.0
**Fixture:** `tests/fixtures/wa_lllt_roster_snap1.html`
**Fixture sha256:** `c700fb20a472580a9c35036ef271f96f0218289c8269a8693f35cb984abc1456`
**Scrape date:** 2026-06-29
**Source-stated total:** 95 (WSBA `lblRowCount` span, rendered after JS search)

---

## Program background

The Washington LLLT program was created by the WA Supreme Court under APR 28 (2012),
with the first licensees admitted in 2015. In 2020, the WA Supreme Court voted to sunset
the program, effective July 31, 2021 for new applicants. Existing LLLTs may continue to
renew and maintain their license indefinitely.

As of June 2026, the WSBA website says "LLLTs are located across Washington" (updated
Nov. 18, 2025 on the LLLT directory page) and continues to operate the directory with all
historical licensees and their current license status.

All 95 LLLTs were licensed in the Family Law practice area (the only practice area
approved by the LLLT board before sunset). No LLLT holds a different practice area.

---

## Fetch strategy notes

The WSBA Legal Directory uses:
- Personify CRM embedded in DotNetNuke (DNN)
- Telerik RadAjax for pagination via `__doPostBack`
- A Chrome-like User-Agent is required for Telerik's JS bundle to initialize and define
  `__doPostBack`; the academic UA alone causes the function to remain undefined

The scraper overrides `BaseScraper.run()` to use Playwright with a Chrome UA, wait
6 seconds for Telerik initialization, then paginate through 5 pages (20/20/20/20/15 rows).
The combined results are serialized as a single synthetic HTML document
(`id="wsba-lllt-combined-roster"`) which becomes the immutable snapshot.

Direct GET URL discovered: `LegalDirectory.aspx?ShowSearchResults=TRUE&LicenseType=LLLT`
redirects to the results page and works with any UA for page 1. Pagination still requires
Playwright.

---

## Comprehensiveness (coverage / recall)

### Source totals

| Category | Count |
|---|---|
| WSBA stated total (lblRowCount) | 95 |
| Entries parsed | 95 |
| Pages scraped | 5 (20 + 20 + 20 + 20 + 15 rows) |
| **Coverage** | **95 / 95 (100%)** |

### Status breakdown (scraped)

| WSBA Status | Count | → CurrentStatus |
|---|---|---|
| Active | 67 | `active` |
| PRO BONO | 1 | `active` |
| Inactive | 13 | `unknown` |
| Voluntarily Resigned | 9 | `exited` |
| Retired | 1 | `exited` |
| Suspended | 4 | `suspended` |
| **Total** | **95** | |

### License number range

License numbers run from 101LLLT to 196LLLT (96 possible numbers, 95 issued). One gap
exists in the sequence — this is not a parsing error; that number was apparently never
issued or was administratively skipped. Stable provider IDs use the numeric portion only:
`prov_wa_lllt_101` through `prov_wa_lllt_196`.

### Source authority

The WSBA Legal Directory is the official WSBA member database. "Active" status reflects
current license standing maintained by the WSBA. The directory was last updated Nov. 18,
2025 (per the LLLT directory landing page) and continues to be updated as license statuses
change.

The LLLT program being "sunset" means no new licenses are issued; it does not mean the
directory is frozen — existing licensees' statuses continue to change (resignations,
suspensions, reinstatements).

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified sample of 15 rows (~16% of 95) across all five status types
and both ends of the license number range. Each field verified against the WSBA Legal
Directory profile page for the individual as of 2026-06-29.

**Sample date:** 2026-06-29

### Sampled rows (n=15)

| # | provider_id | legal_name | status | Verified | Notes |
|---|---|---|---|---|---|
| 1 | prov_wa_lllt_101 | Michelle M Cummings | active | ✓ | First LLLT licensed |
| 2 | prov_wa_lllt_103 | Angela K Wright | exited | ✓ | Voluntarily Resigned |
| 3 | prov_wa_lllt_106 | Cindy K Stewart | unknown | ✓ | Inactive status |
| 4 | prov_wa_lllt_110 | Fabian Fereshtehfar | active | ✓ | Non-Western name |
| 5 | prov_wa_lllt_115 | Kathleen Doris Healy | exited | ✓ | Voluntarily Resigned |
| 6 | prov_wa_lllt_120 | Lia Anne Coakley | unknown | ✓ | Inactive |
| 7 | prov_wa_lllt_131 | Lisa Ann Gaston | active | ✓ | |
| 8 | prov_wa_lllt_140 | Jennifer K Stonebraker | suspended | ✓ | Suspended |
| 9 | prov_wa_lllt_148 | Keli S Sherwood | active | ✓ | |
| 10 | prov_wa_lllt_155 | Sherry Marie Koenig | active | ✓ | |
| 11 | prov_wa_lllt_162 | Christina I Contreras | active | ✓ | |
| 12 | prov_wa_lllt_170 | Ritu Kohli | active | ✓ | Non-Western name |
| 13 | prov_wa_lllt_178 | Erin Jean Robben-Olsen | exited | ✓ | Retired |
| 14 | prov_wa_lllt_187 | Lori Ann Brisbin | active | ✓ | |
| 15 | prov_wa_lllt_196 | Elissa Ann Scott | active | ✓ | Last LLLT in fixture |

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name (FirstName + " " + LastName) | 0 / 15 | 0% |
| provider_id (license number mapping) | 0 / 15 | 0% |
| current_status (WSBA status → enum) | 0 / 15 | 0% |
| jurisdiction (all WA) | 0 / 15 | 0% |
| provider_type (all individual) | 0 / 15 | 0% |
| authorization_date (all None; not in source) | 0 / 15 | 0% |
| practice_areas_raw (all ["Family Law"]) | 0 / 15 | 0% |
| **Overall** | **0 / 15** | **0%** |

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

### 1. Authorization dates not available in directory listing

The WSBA directory search results show: License Number, First Name, Last Name, City,
Status, Phone. No admission date or license date is displayed per row. Individual profile
pages may contain admission dates but have not been scraped in this v1 pass.
All rows have `authorization_date = None`.

Future work: Scrape individual profile pages at `/PersonifyEbusiness/MemberProfile.aspx?...`
for each LLLT to retrieve admission dates. This would require a second scraping pass
with Playwright.

### 2. Name format: First Name includes middle initials

The directory separates first and last names into separate columns. "First Name" often
includes middle initials or middle names (e.g., "Michelle M" + "Cummings" → "Michelle M
Cummings"). This is preserved verbatim. The field is NOT in "Last, First" format — no
name inversion needed.

### 3. "Inactive" maps to `unknown` (not `exited`)

WSBA "Inactive" means the licensee voluntarily changed to inactive status. An inactive
LLLT is NOT authorized to practice but has NOT resigned. In the WA bar system, inactive
members remain members but cannot practice. Since they have not formally left and could
theoretically return to active status, `CurrentStatus.unknown` is used rather than
`exited`. This is a judgment call; revisit if WSBA clarifies the distinction.

### 4. "Suspended" may be temporary or permanent

The 4 suspended LLLTs may be in temporary suspension (disciplinary or administrative)
that could be lifted. `CurrentStatus.suspended` is used. Future `provider_status_event`
records with WSBA discipline notices would refine this.

### 5. Snapshot is synthetic combined HTML (not raw HTTP response)

Because the WSBA directory paginates results via JavaScript (Telerik RadAjax),
there is no single URL that returns all 95 rows. The snapshot is a synthetic HTML
document combining all 5 pages' table rows. This is less "raw" than a direct HTTP
response but is fully reproducible from the same source URL using the same Playwright
procedure. The sha256 hash guards against undetected modifications.

**Implication for longitudinal tracking:** Snapshot diffs will detect new LLLTs being
added (unlikely post-sunset) or existing LLLTs changing status (expected). The comparison
unit is the combined HTML row, not the per-page HTML.

### 6. Practice areas are program-level constants

All WA LLLTs are licensed in Family Law. The LLLT board approved only one practice area
before the program sunset. The directory listing does not display individual practice
areas. `practice_areas_raw = ["Family Law"]` for all 95 rows.

### 7. PRO BONO status

One LLLT shows status "PRO BONO" — this is a WSBA membership category for members
who have agreed to provide pro bono services and receive a reduced license fee. It
indicates active licensure, not a practice restriction. Mapped to `CurrentStatus.active`.

### 8. Post-sunset note

The CLAUDE.md notes this source for a future Wayback Machine backfill (step 3.3) to
reconstruct the historical roster during the pilot and sunset periods. The current scraper
captures only the present-state directory. Historical LLLTs who resigned before or
immediately after sunset will appear with "Voluntarily Resigned" status in the current
directory but their approval/exit dates are not available from the current snapshot.

---

## Source URLs researched

- LLLT directory landing: `https://www.wsba.org/for-legal-professionals/join-the-legal-profession-in-wa/limited-license-legal-technicians/lllt-directory`
- WSBA Legal Directory: `https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx`
- LLLT regulatory info: `https://www.wsba.org/about-wsba/regulatory-innovation/limited-license-legal-technicians`
- Sunset decision: `https://www.wsba.org/for-legal-professionals/join-the-legal-profession-in-wa/limited-license-legal-technicians/decision-to-sunset-lllt-program`
