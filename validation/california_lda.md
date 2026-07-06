# Validation: California Legal Document Assistant (LDA) Program

**Source:** https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=6400.&lawCode=BPC
**Scraper:** `scrapers/california_lda.py` v0.1.0
**Fixture:** `tests/fixtures/ca_lda_program_snap1.html`
**Fixture sha256:** `ff8e81c925f3fbfe23c66546a04f557005ac554e8f8703dd7b8162d1cd2651ef`
**Scrape date:** 2026-06-29

---

## Program background

California Business & Professions Code § 6400 et seq. (enacted 1999) creates the
**Legal Document Assistant (LDA)** category. An LDA may help self-represented litigants
prepare and complete legal documents but may not give legal advice.

Key statutory requirements:
- Register with the county clerk in each county where services are provided (§ 6400.5)
- Post a $25,000 surety bond per county (§ 6400.5)
- Use a written contract with each client (§ 6410)
- Include "I am not an attorney" disclosure on all materials (§ 6409)

This is a **county-level registration** scheme — there is no statewide LDA database,
no state licensing board, and no centralized roster. Each of California's 58 county
clerks independently maintains a list of registered LDAs in that county. Registration
formats, fees, and public availability vary by county.

---

## Why provider count is zero in v1

| Reason | Detail |
|---|---|
| No statewide registry | 58 county clerks each maintain independent lists |
| Highly fragmented | Some counties post PDF lists; others require in-person lookup; most have no web-accessible roster |
| v1 scope decision | 58 separate county scrapers (each with distinct HTML/PDF formats) is out of scope for v1; deferred to v2 |

**Coverage: 0/unknown (N/A for v1)**

The statute page is snapshotted to document the program's legal basis and to detect
any future move toward a statewide registry.

---

## Comprehensiveness (coverage / recall)

| Category | Count |
|---|---|
| Source-stated statewide total | Unknown (no official aggregate published) |
| Entries parsed (v1) | 0 |
| Counties with registries | 58 (all independent) |
| **Coverage** | **0/unknown — county-level scraping deferred to v2** |

### Estimated LDA population

No official count exists. Industry estimates from CALDA (California Legal Document
Assistants association) suggest several thousand registered LDAs statewide, with
concentration in LA, SF Bay Area, San Diego, and Central Valley counties. This is
unverified; treat as a rough lower bound for planning county-scraping prioritization.

---

## Accuracy (precision)

Not applicable — zero provider rows produced.

The program row was verified against the statute:

| Field | Value | Source verified? |
|---|---|---|
| `program_name` | California Legal Document Assistant Program | ✓ B&P Code § 6400 heading |
| `program_status` | `active` | ✓ Statute in force; registrations ongoing |
| `launch_date` | `1999-01-01` | ✓ B&P Code § 6400 enacted Stats. 1999, c. 711 |
| `regulator` | California County Clerks | ✓ § 6400.5 assigns registration to county clerks |
| `authorizing_rule` | B&P Code § 6400 et seq. | ✓ |
| `program_type` | `document_preparer` | ✓ Document preparation only; no legal advice |
| `allows_upl_waiver` | `False` | ✓ LDAs may NOT give legal advice (§ 6400) |
| `allows_nonlawyer_ownership` | `False` | ✓ No ownership structure; individual registration |

---

## Known limitations and methodological notes

### 1. No statewide roster — fundamental data gap

The LDA registration system is intentionally decentralized. Unlike Utah's Innovation
Office or Arizona's ABS program, California has no state agency that aggregates
registrations. This is not a scraping limitation; it is a structural feature of
the statute. Future work requires 58 independent scraping efforts.

### 2. Paralegal title rules (B&P Code § 6450) — out of scope for this scraper

B&P Code § 6450 (enacted 1999) restricts use of the title "paralegal" to individuals
who meet experience and education requirements. This is a **title-protection rule**,
not a licensing or registration program — no roster of California paralegals exists,
and no registry is required. Not scraped; documented here for completeness.

### 3. California ABS / sandbox — no program exists as of June 2026

The State Bar's Board of Trustees considered but **rejected** a proposed ABS framework
in 2022. As of June 2026, no California ABS or regulatory sandbox has been approved.
Monitor State Bar of California Board of Trustees agendas for future action.

### 4. County prioritization for v2

If county-level scraping is undertaken in v2, prioritize by LDA density:
1. Los Angeles County Clerk: `https://lavote.gov/`
2. San Francisco County Clerk: `https://sfgov.org/countyclerk/`
3. San Diego County Clerk: `https://www.sdcounty.ca.gov/`
4. Sacramento County Clerk: `https://www.saccounty.gov/`
5. Orange County Clerk-Recorder: `https://www.ocrecorder.com/`

Format and URL structure will require individual investigation per county.

### 5. Snapshot source choice

The B&P Code § 6400 statute page on leginfo.legislature.ca.gov is the most authoritative
single source for the program's legal definition and requirements. Snapshotting it
provides a longitudinal record of any statutory changes (amendments, repeals).
