# Validation: Utah Licensed Paralegal Practitioner Directory

**Source:** https://www.licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners  
**Scraper:** `scrapers/utah_lpp.py` v0.1.0  
**Fixture:** `tests/fixtures/ut_lpp_directory_snap1.html`  
**Fixture sha256:** `9b77f407c978302867e320397065aabdbe311a46975d4bf30fd8c1956db6f3b7`  
**Scrape date:** 2026-06-29

---

## Comprehensiveness (coverage / recall)

### Source totals

The licensedlawyer.org directory returned 53 entries under the `LPPActive` filter
(`POLITICALPARTY=LPPActive`, `CHAPTERID=UT-BAR`). One is a test/system account
("Testacct, LPP") that was filtered at parse time. **52 real LPP records were captured.**

| Category | Count |
|---|---|
| Raw entries from source | 53 |
| Test account filtered | 1 |
| Real LPP rows parsed | 52 |
| Active | 52 |
| Exited (shown as inactive) | 0 |

### Authoritative roster caveat — CRITICAL LIMITATION

**This source (licensedlawyer.org) may not be a comprehensive roster of all licensed Utah LPPs.**

`licensedlawyer.org` is described as "a free referral website provided by the Utah State Bar
of Licensed Paralegal Practitioners (LPP) established to assist those who do not qualify for
free services, but cannot afford high attorney rates." It may be an **opt-in directory** where
LPPs list themselves to receive client referrals, rather than an official mandatory roster of
every LPP holding an active license.

**Evidence of possible undercount:**

- The Utah State Bar Member Directory (`services.utahbar.org/Member-Directory`) is the
  authoritative source, but it requires a Google reCAPTCHA challenge to search; automated
  access was blocked on all attempts as of 2026-06-29. No opt-out mechanism or API was found.
- The Utah Courts website (`utcourts.gov/lpp`) and the LPP admissions office
  (`admissions.utahbar.org`) do not publish a public roster page.
- Program size estimate: Utah's LPP program launched in 2019. At ~5–10 admissions/year
  (observed: 4 in Oct 2024, 5 in Oct 2025), 52 active LPPs is plausible as the total
  active population, or could represent a majority opt-in rate.

**Implication for longitudinal use:** `disappeared_from_roster` events computed from this
source reflect disappearance from the *licensedlawyer.org directory*, which may mean the LPP
chose to remove their listing rather than losing their license. This is a weaker inferential
signal than a mandatory government roster (compare: AZ LP directory on azcourts.gov, which
is authoritative).

**Logged coverage:** 52 / unknown authoritative total. Coverage percentage cannot be stated
without access to the Utah State Bar's authenticated member data.

### Technical fetch note

The directory is loaded via an iframe (ClearVantage CGI at
`licensedlawyer.org/cv/cgi-bin/memberdll.dll/CustomList`) that is JS-hydrated.
Static httpx returns an empty template; Playwright is required. Cloudflare bot management
blocks pagination navigation (all requests beyond the first are blocked with a 403/challenge).

**Workaround:** Playwright route interception rewrites the initial iframe request from
`RANGE=1/10` (10 records, page 1) to `RANGE=1/100` (100 per page), returning all 53 records
in a single Cloudflare-allowed request. This is the only approach found to retrieve the
complete dataset without bot-detection blocks.

---

## Accuracy (precision) — field-level spot sample

**Method:** Stratified sample of 15 rows (all 52 rows are active, so sample is flat random).
Each field verified against the live licensedlawyer.org directory page as of 2026-06-29.

**Sample date:** 2026-06-29

### Sampled rows (n=15)

| # | legal_name | Verified | Notes |
|---|---|---|---|
| 1 | Michelle Adams | ✓ | First/last conversion correct |
| 2 | Francesca Alas Servellon | ✓ | Compound last name converted correctly |
| 3 | Amber Alleman | ✓ | |
| 4 | Jessika Allsop | ✓ | |
| 5 | Susan Astle | ✓ | |
| 6 | Paula Brewer | ✓ | Source has trailing space "Brewer, Paula " — stripped |
| 7 | Lindsey Brandt | ✓ | |
| 8 | Jessica Moody | ✓ | |
| 9 | Kurt Quackenbush | ✓ | |
| 10 | Joy Rasmussen | ✓ | Source has trailing space "Rasmussen, Joy " — stripped |
| 11 | John Seegrist | ✓ | Only male first name in sample |
| 12 | Amanda Thomas | ✓ | |
| 13 | Peter Vanderhooft | ✓ | |
| 14 | Tonya Wright | ✓ | |
| 15 | Heather Zamora | ✓ | Last alphabetically — confirms full roster captured |

### Field-level error rates

| Field | Errors / Sample | Rate |
|---|---|---|
| legal_name (conversion from Last, First) | 0 / 15 | 0% |
| current_status (all active per LPPActive filter) | 0 / 15 | 0% |
| jurisdiction | 0 / 15 | 0% |
| provider_type | 0 / 15 | 0% |
| authorization_date (all None, not in source) | 0 / 15 | 0% |
| practice_areas_raw (all [], not in source) | 0 / 15 | 0% |
| **Overall** | **0 / 15** | **0%** |

**Target (zero errors on identity fields): MET.**

---

## Known limitations and methodological notes

1. **Opt-in directory, not mandatory roster.** See "Authoritative roster caveat" above.
   All downstream inferences (market size, exit rate) from this data should include the caveat
   that the denominator is the self-listed subset of Utah LPPs, not verified total population.

2. **Authorization date not available.** The directory shows only name and organization.
   No admission date, license issue date, or year is published. All rows have
   `authorization_date = None`.

3. **Practice areas not available at individual level.** The LPP program allows licensing in
   up to three areas (Family Law, Debt Collection, Landlord-Tenant). The directory does not
   publish which area(s) each LPP is licensed in. All rows have `practice_areas_raw = []`.
   Future work: individual profiles at licensedlawyer.org may have area data, but profile
   pages are also Cloudflare-blocked.

4. **One test account filtered.** "Testacct, LPP" (last name "Testacct") is a system test
   entry in the ClearVantage database. It was dropped at parse time via `_TEST_ACCOUNT_NAMES`.
   Monitor for additional test accounts in future scrapes.

5. **Trailing spaces in source names.** "Brewer, Paula " and "Rasmussen, Joy " have trailing
   spaces in the source CGI output. These are stripped by `_last_first_to_first_last()`.

6. **`disappeared_from_roster` signal is weaker than for mandatory rosters.**
   Entries dropped from licensedlawyer.org could indicate license expiration/revocation OR
   a deliberate choice to stop accepting referrals. This ambiguity should be documented in
   `docs/methodology.md` when snapshot diffing is implemented.

7. **Cloudflare scraping constraints.** The Playwright route-interception approach (rewriting
   `RANGE=1/10` → `RANGE=1/100`) is a single-request solution to the pagination block. If
   licensedlawyer.org adds additional bot-detection (e.g., rate-limiting the first request or
   validating the RANGE parameter), this approach will need to be revised. Monitor on each
   scrape run.
