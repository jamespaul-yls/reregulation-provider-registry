# Coverage Report — Reregulation Provider Registry

**Generated:** 2026-06-29 · **Refreshed:** 2026-07-06
**Programs in scope:** 10 (`prog_dc_rule54` removed 2026-07-06 — see `docs/sampling_frame.md §4`)
**Total provider rows in DB:** 708
**DB path:** `data/db/registry.duckdb`

---

## Summary table

"Parsed" / "Source total" below reconcile the **latest roster snapshot** for each program
against what that source stated at the time of that snapshot — this is the coverage check.
For AZ ABS and UT Sandbox, the DB's cumulative provider count (see "Provider breakdown"
below) is higher than the latest-snapshot parse count because earlier snapshots (including
a Wayback capture) contributed providers that have since exited; both figures are correct,
they answer different questions. See `docs/methodology.md §10b` for the coverage method.

| program\_id | Source | Format | Parsed (latest snapshot) | Source total | Coverage | Last snapshot | Recon status |
|---|---|---|---|---|---|---|---|
| prog\_az\_abs | [AZ ABS Directory][az-abs] | HTML (static) | **167** | 167 | **100 %** | 2026-06-28 | ✅ full |
| prog\_az\_lp | [AZ LP Directory][az-lp] | HTML (headless) | **120** | not stated | — | 2026-06-29 | ⚠️ no\_source\_total |
| prog\_ca\_lda | [CA BPC § 6400][ca-lda] | HTML (statute) | 0 | N/A | N/A | 2026-06-29 | ✅ zero\_documented |
| prog\_co\_llp | [CO LLP Roster PDF][co-llp] | PDF | **126** | 126 ¹ | **100 %** | 2026-06-29 | ✅ full ¹ |
| prog\_mn\_lp | [MN LP Roster PDF][mn-lp] | PDF | **42** | 42 | **100 %** | 2026-06-29 | ✅ full |
| prog\_tx\_alp | [TX Bar Paraprofessionals][tx-alp] | HTML (status page) | 0 | 0 | N/A | 2026-07-04 | ✅ zero\_documented |
| prog\_ut\_lpp | [UT LPP Directory][ut-lpp] | HTML (static) | **52** | not stated ² | — | 2026-06-29 | ⚠️ opt\_in\_dir |
| prog\_ut\_sandbox | [UT Sandbox Roster][ut-sb] | HTML + PDF | **69** | 69 | **100 %** | 2026-06-29 | ✅ full |
| prog\_wa\_entity\_pilot | [WSBA Entity Pilot Applicants][wa-ep] | HTML (static) | 0 | 4 applicants (0 authorized) | **N/A (0/4 authorized)** | 2026-07-04 | ✅ zero\_documented |
| prog\_wa\_lllt | [WA LLLT Directory][wa-lllt] | HTML (headless, synthetic) | **95** | 95 | **100 %** | 2026-06-29 | ✅ full |

[az-abs]: https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory
[az-lp]: https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory
[ca-lda]: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=6400.&lawCode=BPC
[co-llp]: https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf
[mn-lp]: https://mncourts.gov/_media/migration/appellate/supreme-court/Roster-of-Approved-Legal-Paraprofessionals.pdf
[tx-alp]: https://www.texasbar.com/paraprofessionals/
[ut-lpp]: https://www.licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners
[ut-sb]: https://utahinnovationoffice.org/authorized-entities/
[wa-ep]: https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants
[wa-lllt]: https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx?ShowSearchResults=TRUE&LicenseType=LLLT

**¹** CO LLP PDF content dated 2026-02-06 (PDF's own "as-of" date), though fetched on 2026-06-29.
The PDF was not updated between February and June; parsed count matches the PDF's stated total as of its
publication date. Fetch again after the next PDF update to detect additions.

**²** licensedlawyer.org is an opt-in directory; LPPs may choose not to list. The Utah State Bar
does not publish a separate authoritative total. Parsed count is a lower bound.

---

## Reconciliation status legend

| Status | Meaning |
|---|---|
| ✅ `full` | parsed == source-stated total; reconciliation complete |
| ⚠️ `no_source_total` | source does not publish a count; external reference used |
| ⚠️ `opt_in_dir` | directory is opt-in; source total is unavailable; parsed count is a lower bound |
| ✅ `zero_documented` | 0 providers expected by design; reason recorded in per-source validation doc |

---

## Provider breakdown by program (cumulative, all snapshots)

| program\_id | Total | Active | Exited | Suspended | Unknown/Other |
|---|---|---|---|---|---|
| prog\_az\_abs | 203 | 160 | 43 | 0 | 0 |
| prog\_az\_lp | 120 | 113 | 7 | 0 | 0 |
| prog\_ca\_lda | 0 | — | — | — | — |
| prog\_co\_llp | 126 | 126 | 0 | 0 | 0 |
| prog\_mn\_lp | 42 | 42 | 0 | 0 | 0 |
| prog\_tx\_alp | 0 | — | — | — | — |
| prog\_ut\_lpp | 52 | 52 | 0 | 0 | 0 |
| prog\_ut\_sandbox | 70 | 8 | 62 | 0 | 0 |
| prog\_wa\_entity\_pilot | 0 | — | — | — | — |
| prog\_wa\_lllt | 95 | 68 | 10 | 4 | 13 |
| **Total** | **708** | **569** | **122** | **4** | **13** |

AZ ABS's cumulative total (203) exceeds its latest-snapshot parse count (167) because a
2024-11-08 Wayback capture (77 entities) and diffing against the 2026-06-28 own-scrape
contributed 36 additional providers that have since disappeared from the roster
(`disappeared_from_roster` events). UT Sandbox's cumulative total (70) similarly reflects
9 snapshots (1 Wayback + 8 own-scrape) rather than a single point-in-time count. See
`validation/longitudinal_validity.md` for the full reconstruction.

---

## Per-source notes

### prog\_az\_abs — Arizona ABS (✅ full)

Single-page HTML table; all entities fit on one page (no pagination). Row count reconciled
against AZ Supreme Court directory. 160 active (authorized), 43 exited (7 status = Inactive
per AZ directory at first insert; 36 via `disappeared_from_roster` events from diffing the
2024-11-08 Wayback capture against the 2026-06-28 own-scrape). Source does not publish a
separate stated total but the single-page structure makes enumeration complete.

### prog\_az\_lp — Arizona LP (⚠️ no\_source\_total)

Directory renders as a single HTML table with no pagination and no "N results" count.
Coverage relies on: (a) no visible pagination in the HTML; (b) external reference: the
2024 AZ LP Annual Report (December 31, 2024) cited 79 licensed LPs across 83 practice
area slots; the June 2026 scrape returned 120, consistent with documented program growth.
No error-rate risk from pagination; risk is residual if the directory is not complete.

### prog\_ca\_lda — California LDA (✅ zero\_documented)

No statewide LDA registry exists. Cal. Bus. & Prof. Code § 6400 registration is
administered by 58 independent county clerks; no central aggregator. Source page snapshotted
is the B&P Code § 6400 statute page on leginfo.legislature.ca.gov.
See `validation/california_lda.md`.

### prog\_co\_llp — Colorado LLP (✅ full ¹)

PDF published by the CO Office of Attorney Regulation Counsel. PDF header reads "As of
February 6, 2026." Registration numbers run consecutively from 600000 to 600125 (no gaps),
confirming 126 entries are all entries in the PDF. Note: the PDF is updated periodically;
the fetch date (2026-06-29) does not mean the PDF reflects that date. Re-fetch to detect
new LLPs added after February 2026.

### prog\_dc\_rule54 — removed 2026-07-06

Was documented here through v1.0.1 as ✅ `zero_documented` (permissive ethics rule, no
registration requirement, no roster maintained by the D.C. Court of Appeals or the D.C.
Bar). Removed from scope entirely 2026-07-06 rather than kept as a documented zero: unlike
every other zero-provider program in this table, there is no roster that could ever come
to exist for a self-executing rule with no application step. See `docs/sampling_frame.md
§4` and `validation/dc_rule54.md` for the full reasoning.

### prog\_mn\_lp — Minnesota LP (✅ full)

PDF updated June 25, 2026 (PDF header). IDs run 1001–1044 with two confirmed gaps
(1009 and 1028, IDs not issued), yielding exactly 42 entries (44 IDs in range − 2 gaps = 42,
confirmed against the scraper's own parsed output — see `docs/audit/coverage_confidence.md
§2` for the live re-verification that caught this range being mis-stated as 1001–1046
previously). Row count matches the
named count in the PDF.

### prog\_tx\_alp — Texas ALP (✅ zero\_documented)

Program paused by Misc. Docket 24-9095 (November 4, 2024); no effective date set as of
June 2026; no licensees issued. Source snapshotted is texasbar.com/paraprofessionals/
(program status page), loaded to DB 2026-07-04. See `validation/texas_alp.md`.

### prog\_ut\_lpp — Utah LPP (⚠️ opt\_in\_dir)

licensedlawyer.org is the Utah State Bar's opt-in attorney directory. LPPs may choose not
to list. The directory returned 53 entries under the `LPPActive` filter; 1 test account
(Testacct, LPP) was filtered, leaving 52. No authoritative count from the Utah State Bar
is publicly available. Parsed count is a confirmed lower bound; true population may be
higher.

### prog\_ut\_sandbox — Utah Sandbox (✅ full)

Roster page lists 8 active entities in five HTML sections; 62 exited entities are recorded
in the same page under "Provisional Authorization," "Previously Authorized," etc. Latest
own-scrape reconciled to 69 by manually counting all sections; cumulative DB total is 70
across 9 snapshots (1 Wayback capture from 2025-06-12 + 8 own-scrapes). 8 activity-report
PDFs were also snapshotted for longitudinal tracking but do not add provider rows.

### prog\_wa\_entity\_pilot — Washington Entity Regulation Pilot Project (✅ zero\_documented)

WA Supreme Court Order 25700-B-721 pilot; one program resolves both the IAALS "WA ABS" and
"WA sandbox" listings (`docs/sampling_frame.md §6`). WSBA publishes a full applicant list
(4 entities as of 2026-07-04), all "Under Review" — zero authorized. Roster scraper is
live (`scrapers/washington_entity_pilot.py`) and will load authorized entities as providers
the moment any applicant's status changes; re-run `scripts/run_wa_entity_pilot.py`
periodically. See `validation/washington_entity_pilot.md`, including the flagged v2 decision
on tracking pre-authorization applicant status.

### prog\_wa\_lllt — Washington LLLT (✅ full)

WSBA Legal Directory filtered to LLLT credential. Source displays a `lblRowCount` span
showing 95 total after Telerik RadAjax renders results. Directory paginated across 5 pages
(20 + 20 + 20 + 20 + 15); synthetic combined HTML snapshot built via Playwright. Status
breakdown: 68 active (67 Active + 1 PRO BONO), 10 exited (9 Voluntarily Resigned + 1
Retired), 13 unknown (Inactive), 4 suspended.

---

## Programs with outstanding coverage gaps

| program\_id | Gap | Action required |
|---|---|---|
| prog\_az\_lp | No source-stated total | Monitor for AZ ACS annual report (published Dec each year) to cross-check count |
| prog\_ut\_lpp | Opt-in directory; total unknown | Request Utah State Bar official LPP count via records request |
| prog\_ca\_lda | 58-county fragmentation | Implement county-level scrapers in v2, starting with LA/SF/SD |
| prog\_tx\_alp | Program paused | Re-run when TX Sup. Ct. sets new effective date |
| prog\_co\_llp | PDF as-of date lags fetch | Re-fetch after each CO OARC PDF update |
| prog\_wa\_entity\_pilot | No applicant authorized yet | Re-run `scripts/run_wa_entity_pilot.py` periodically to detect the first authorization |
