# Validation: Utah Office of Legal Services Innovation Sandbox

**Source:** https://utahinnovationoffice.org/authorized-entities/  
**Scraper:** `scrapers/utah_sandbox.py` v0.1.0  
**Fixture:** `tests/fixtures/ut_sandbox_roster_snap1.html`  
**Fixture sha256:** `f0624d67fe0ad9d1fd4eda92edb13ccbb225f8272f8204ecf48887403a663134`  
**Scrape date:** 2026-06-29

---

## Comprehensiveness (coverage / recall)

The roster page does not publish a single stated total; counts were reconciled by section:

| Section | Page category | Parsed | Status seeded |
|---|---|---|---|
| Currently Authorized (card layout) | 7 | 7 | active |
| Authorized through Standing Order (i4J) | 1 | 1 | active |
| Provisionally Authorized (expired/withdrew) | 7 | 7 | exited |
| Previously Authorized w/ Rule 5.4 Waivers | 19 | 19 | exited |
| Previously Authorized | 35 | 35 | exited |
| **Total** | **69** | **69** | |

**Coverage: 69 / 69 (100%).**

The five sections were manually counted from the page HTML and confirmed against the parsed
output. No rows were silently dropped.

**Activity-report PDFs:** 7 known PDF URLs (discovered via web search; the archive page at
`/sandbox-activity-reports-archive/` returns HTTP 404 as of 2026-06-29). All 7 were
successfully fetched and snapshotted. The archive URL should be monitored for restoration;
any future monthly or annual report PDFs should be added to `_ACTIVITY_REPORT_URLS` in
`scrapers/utah_sandbox.py`.

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified sample: all 7 currently-authorized card entities + 8 randomly
selected exited list entities = 15 rows. Each field verified against the live page
(https://utahinnovationoffice.org/authorized-entities/) and, where applicable, the PDF
authorization order linked per entity.

**Sample date:** 2026-06-29

### Currently Authorized (card entities, n=7)

| Entity | legal_name | website | practice_areas_raw | ownership_structure (service_models) | uses_technology | uses_ai |
|---|---|---|---|---|---|---|
| 1Law | ✓ | ✓ `1law.com` | ✓ 19 areas | ✓ 3 models incl. Software provider | ✓ True | ✓ True (chatbot) |
| Community Justice Advocates of Utah | ✓ | ✓ `cjau.org` | ✓ 3 areas | ✓ 1 model | ✓ False | ✓ False |
| Elysium Legal | ✓ | ✓ `myelysium.com` | ✓ 16 areas | ✓ 4 models | ✓ False | ✓ False |
| Pearson Butler (asterisk stripped) | ✓ | ✓ `pearsonbutler.com` | ✓ 16 areas | ✓ 4 models | ✓ False | ✓ False |
| Rasa Public Benefit Corp. (period preserved) | ✓ | ✓ `rasa-legal.com` | ✓ 3 areas | ✓ 3 models incl. Software provider | ✓ True | ✓ False |
| Superlegal (LawGeex / Legalogic) | ✓ | ✓ `lawgeex.com` | ✓ 2 areas | ✓ 3 models incl. Software provider | ✓ True | ✓ True (AI-enabled) |
| Utah State University TCI | ✓ | ✓ `artsci.usu.edu` | ✓ 1 area | ✓ 1 model | ✓ False | ✓ False |

**Zero errors on currently-authorized card entities.** All identity fields (legal_name,
website, practice_areas_raw) match the live page exactly.

### Exited list entities (8 sampled)

| Entity | legal_name | current_status | Notes |
|---|---|---|---|
| i4J | ✓ | ✓ active (Standing Order) | No card data available; ownership_structure=None |
| Centro Hispano | ✓ | ✓ exited | `(expired)` span stripped correctly |
| Legal Assistance J. | ✓ | ✓ exited | Trailing period in "J." preserved |
| Nuttall, Brown & Coutts (dba ZAF Legal) | ✓ | ✓ exited | DBA annotation preserved, not stripped |
| Xira Connect Inc | ✓ | ✓ exited | Typographic "." after `</a>` not in name |
| Robert DeBry | ✓ | ✓ exited | No hyperlink in HTML; parsed from `li.text()` |
| Rocket Lawyer/Rocket Legal Professional Services | ✓ | ✓ exited | Long name preserved intact |
| Olson & Partners | ✓ | ✓ exited | Trailing `&nbsp;` stripped |

**Zero errors on sampled exited list entities.**

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name | 0 / 15 | 0% |
| current_status | 0 / 15 | 0% |
| website | 0 / 7 | 0% |
| practice_areas_raw | 0 / 7 | 0% |
| ownership_structure (service_models) | 0 / 7 | 0% |
| uses_technology | 0 / 7 | 0% |
| uses_ai | 0 / 7 | 0% |
| jurisdiction | 0 / 15 | 0% |
| **Overall** | **0 / 15** | **0%** |

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

1. **Authorization date not available.** The roster does not publish authorization dates.
   All rows have `authorization_date = None`. Dates can be extracted from the linked
   authorization-order PDFs (not yet parsed — planned for v4).

2. **Status seeded from roster position, not from PDF order text.**
   - Currently Authorized → `active`
   - Authorized through Standing Order → `active`
   - Provisionally Authorized (all expired/withdrew as of 2026-06-29) → `exited`
   - Previously Authorized (with or without 5.4 waiver) → `exited`
   
   This matches the AZ ABS methodology (see `docs/methodology.md §UT-SANDBOX`).
   `disappeared_from_roster` events will be computed longitudinally via snapshot diffing.

3. **`uses_technology` and `uses_ai` are `None` for list-only entities.**
   The card layout (currently authorized only) contains service-model and description text
   from which these flags are derived. The 61 exited list entities carry `None` for both.

4. **`uses_ai` derivation.** Flag is `True` if the entity's description text matches
   `\bai\b|artificial intelligence|chatbot|machine learning` (case-insensitive). This
   captures stated use, not inferred use.  Rasa's description ("technological solution")
   does not match → `uses_ai = False`, which is conservative but accurate to stated text.

5. **Activity-report PDF archive page (404).** The URL
   `https://utahinnovationoffice.org/sandbox-activity-reports-archive/` returned HTTP 404
   as of 2026-06-29. The 7 PDF URLs hardcoded in `_ACTIVITY_REPORT_URLS` were discovered
   via web search and cover 2021–Jan 2024. Monthly reports were suspended in 2025 in favor
   of an annual report not yet published. Monitor and update when the annual report appears.

6. **"Previously Authorized Entities" section split across two Elementor top-sections.**
   The heading h2 is in one `section.elementor-top-section` element; the `<ul>` list is in
   the immediately following sibling section with no h2. The parser tracks this with a
   `prev_auth_header_seen` flag, which must be updated if the page layout changes.
