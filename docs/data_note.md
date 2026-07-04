# Data Note: U.S. Legal Services Reregulation Provider Registry, v1.0.0

**Author:** James Paul, Yale Law School  
**Contact:** james.paul@yale.edu  
**Date:** July 4, 2026  
**Version:** 1.0.0 · Data: `data/release/` · Code: `github.com/jamespaul/reregulation-registry`  
**Intended audience:** IAALS, the Deborah L. Rhode Center on the Legal Profession, and other
researchers evaluating U.S. legal-services reregulation programs

---

## What this registry is

This dataset is a longitudinal census of every authorized provider operating under a
U.S. legal-services **reregulation** program — Alternative Business Structures (ABS),
regulatory sandboxes, and allied-legal-professional / paraprofessional licenses. "Provider"
means any entity or individual who holds a formal authorization from a state regulator to
deliver legal services under a program that relaxes standard UPL or Rule 5.4 restrictions.

The registry tracks **who was authorized, when, and for how long**. It does not make
harm or benefit determinations. Column names are deliberately neutral proxies
(`formal_complaint_count` is planned; `harm` is not a column name). The intent is a
reproducible spine that other evaluations — including those already underway at IAALS and
the Rhode Center — can link to their own outcome data.

Every row carries `source_url`, `retrieved_at`, and `scraper_version`. Raw HTML and PDF
captures are content-hashed (SHA-256) and stored in `data/raw/`. All derived tables
are fully re-derivable from those captures without network access, verified by a
provenance audit that fails the build on any orphan row.

---

## Coverage

Version 1.0.0 covers 11 programs in 7 states plus D.C., spanning three program types.

### Current-roster counts (latest snapshot per program)

| Program | State | Type | Active | Exited / Historical | Total unique | Coverage | Snapshot date |
|---|---|---|---:|---:|---:|---|---|
| Arizona ABS | AZ | abs | 160 | 43 | **203** | 100% of public roster | 2026-06-28 |
| Arizona LP | AZ | alp_license | 113 | 7 | **120** | ~100%† | 2026-06-29 |
| Colorado LLP | CO | alp_license | 126 | 0 | **126** | 100% | 2026-06-29‡ |
| Minnesota LP | MN | alp_license | 42 | 0 | **42** | 100% | 2026-06-29 |
| Utah LPP | UT | alp_license | 52 | 0 | **52** | ≥52 (lower bound)§ | 2026-06-29 |
| Utah Sandbox | UT | sandbox | 8 | 62 | **70** | 100% of public roster | 2026-06-29 |
| Washington LLLT | WA | alp_license | 68 | 27 | **95** | 100% | 2026-06-29 |
| California LDA | CA | document_preparer | 0 | — | 0 | N/A ¶ | 2026-06-29 |
| D.C. Rule 5.4(b) | DC | abs | 0 | — | 0 | N/A # | 2026-07-04 |
| Texas ALP | TX | alp_license | 0 | — | 0 | N/A ** | 2026-07-04 |
| WA Entity Pilot | WA | sandbox | 0 | — | 0 | 0/4 applicants authorized †† | 2026-07-04 |
| **Total** | | | **569** | **139** | **708** | | |

† The AZ LP directory does not publish a stated total. No JS-gated pagination was found;
the 2024 AZ LP Annual Report cited 79 licensed LPs (December 31, 2024); the June 2026
count of 120 is consistent with documented growth.

‡ The CO LLP PDF is dated 2026-02-06 (its own header); the fetch date is 2026-06-29.
Registration numbers 600000–600125 run with no gaps, confirming 126 entries are complete
as of the PDF's publication date. Re-fetch when OARC publishes an updated PDF.

§ licensedlawyer.org is an opt-in directory. The Utah State Bar does not publish a
separate authoritative LPP total. One test account was filtered; 52 is a confirmed
lower bound.

¶ California LDA registration is administered by 58 independent county clerks with no
central aggregator. County-level scrapers are planned for v1.1, starting with L.A., S.F.,
and San Diego.

\# D.C. Rule 5.4(b) is a permissive ethics rule; no registration requirement exists and
no roster is maintained.

\*\* The Texas ALP program was paused by Misc. Docket 24-9095 (November 4, 2024). No
effective launch date had been set as of June 2026; no licensees have been issued.

†† The Washington Entity Regulation Pilot Project (WA Supreme Court Order
25700-B-721) has 4 applicants as of 2026-07-04, all "Under Review." Inclusion on the
WSBA's applicant list explicitly does not mean an entity is authorized; zero are
authorized yet, so zero are loaded as providers. This one program covers both the "ABS"
and "sandbox" classifications a cross-jurisdiction inventory (IAALS) separately lists for
Washington — see the completeness check below.

For all four zero-provider programs, the "Snapshot date" above is the capture of the
*evidentiary source page* (the statute, rule text, program-status page, or full applicant
list that documents why the count is zero) — not a roster capture, since no roster exists
for any of the four. This means the "why it's zero" claim is itself backed by an
immutable, content-hashed snapshot, not only asserted in the program row. See
`docs/sampling_frame.md §3` for the full reasoning per program.

### Completeness check (frame reconciliation)

Beyond reconciling parsed counts against each source's own stated total (below), we ran
an independent check: does an external inventory of reregulation programs (the IAALS
Unlocking Legal Regulation knowledge center) list anything our program table doesn't have,
or vice versa? This surfaced 14 candidate gaps — 5 candidate programs we hadn't built a
scraper for yet (Washington sandbox and ABS, Indiana sandbox, Minnesota sandbox, Puerto
Rico ABS) and 8 Community-Based Justice Worker Model jurisdictions (a program type defined
in our schema for forward compatibility but not yet built for v1). All 14 are resolved:
the Washington sandbox/ABS pair is now covered by the newly built
`prog_wa_entity_pilot` (one pilot resolves both classifications, the same pattern already
used for Utah's sandbox/ABS overlap); 2 total are intentionally excluded for that reason
(Utah and Washington); the remaining 3 candidate programs (Indiana sandbox, Minnesota
sandbox, Puerto Rico ABS) and all 8 CJW jurisdictions are explicitly deferred to v2. None
are open questions. Full detail: `docs/sampling_frame.md §6` and
`validation/residual_gaps.csv`.

### Reconciliation

For programs with source-stated totals, the registry matches them exactly. For programs
without stated totals (AZ LP, UT LPP), coverage was assessed against structural properties
of the source (single non-paginated table; opt-in directory flag) and, where available,
cross-checked against published reports.

Accuracy was verified by stratified random sampling (≥15 rows or ≥10%, whichever is
larger) hand-checked against the raw snapshot or live source. **All seven programs with
accuracy samples show a 0% field-level error rate on identity fields** (legal name,
current status, jurisdiction, authorization date). See `validation/<source>.md` for
per-source tables.

---

## Longitudinal validity

### Arizona ABS

Arizona is the only program with multiple comparable public snapshots in the registry at
v1.0.0. A Wayback Machine capture dated 2024-11-08 yielded 77 authorized entities. The
own scrape on 2026-06-28 yielded 167 entities. A dry-run against an April 4, 2025 Wayback
capture produced 128 entities.

**Comparison against IAALS / AZ Supreme Court benchmarks:**

| Date | Registry count | Published benchmark | Divergence |
|---|---|---|---|
| 2024-11-08 | 77 | — | — |
| 2025-04-04 | 128 | ~136 active (AZ SC, Apr 2025) | −8 (5.9%) |
| 2026-06-28 | 167 | — | — |

The 5.9% divergence at April 2025 is attributable to a known lag between the AZ Supreme
Court's internal approval date and the entity's appearance on the public roster. Our
scraper counts only entities listed on the public-facing directory; entities approved but
not yet posted account for the gap. There is no evidence of a scraper defect: all 17
sampled rows from the 2026 snapshot show 0 errors on identity fields, and the
Wayback-to-own-scrape trajectory (+4 entities in 12 days from 2026-06-16 to 2026-06-28)
is internally consistent.

From the diff between the 2024 and 2026 snapshots: **36 entities present in November 2024
had disappeared from the roster by June 2026**, and **126 new entities were authorized**
in that period. These entry and exit events are now recorded in `provider_status_event`.

### Utah Sandbox

The sandbox was designed as a time-limited pilot. The trajectory is consistent with
program design: the population of active entities declined from approximately 11 (April
2025, published benchmark) to 8 (June 2026, own scrape). The total of 70 unique
participants reflects all entities ever authorized, including 62 that have exited.
Early Wayback captures (2021–2022) are not yet parseable due to a site structure change
before the current card-based layout; this limits reconstruction of the program's first
cohort.

### Washington LLLT

LLLT is a sunset program (effective July 31, 2021; no new applicants). The June 2026
snapshot captures the credential population mid-decay: 68 active, 10 voluntarily resigned,
4 suspended, 13 inactive (status unknown under the registry's `unknown` enum). A Wayback
backfill to reconstruct the pre-sunset peak roster is planned; the `_wayback_parse()`
override is implemented and tested but not yet loaded into the DB.

---

## Known limitations

**1. Roster lag.** Regulators update rosters on unknown schedules. An entity may have
been authorized or exited days or weeks before a snapshot records that change. The
registry dates events to the snapshot, not the regulatory action.

**2. Observation is not ground truth.** `disappeared_from_roster` is an observation, not
a legal conclusion. An entity dropping off the public roster may reflect revocation,
voluntary withdrawal, a website update, or a data error. Only the regulator knows which.
The registry preserves this ambiguity deliberately (`disappeared_from_roster ≠ revoked`).

**3. Single initial snapshots for most programs.** Five of seven programs with data have
one snapshot at v1.0.0. Entry and exit tracking becomes meaningful as successive snapshots
accumulate. The AZ ABS and UT Sandbox longitudinal comparisons are the only mature examples.

**4. Authorization-date sparsity.** Most rosters do not publish the date a provider was
first authorized. The `authorization_date` field is populated for Minnesota LP (dates in
the PDF) and partially for some other programs; it is NULL for the majority of providers.
Entry dates are instead inferred from the first snapshot in which a provider appears.

**5. Practice-area sparsity.** Most individual-practitioner rosters (AZ LP, CO LLP, MN
LP, UT LPP) do not publish practice areas per provider. The `practice_areas_raw` column is
populated only for Utah Sandbox active entities. JusticeBench LIST taxonomy mapping is not
yet applied.

**6. Opt-in directories undercount.** The UT LPP count (52) is a lower bound. Practitioners
who have not opted into the licensedlawyer.org directory are invisible to the scraper. A
public-records request to the Utah State Bar for the official LPP roster count is needed to
close this gap.

**7. Scope boundary.** This registry covers reregulation programs only. It does not cover
the full universe of legal service providers, pro se assistance programs, or document
preparers operating outside formal reregulation frameworks. Market-share computations
using this dataset as the denominator will be wrong.

**8. California and D.C.** are included as program records to document their legal
frameworks (Cal. BPC § 6400; D.C. RPC 5.4(b)) but contribute zero provider rows at
v1.0.0. Both are programmatically important for research comparisons and are retained as
stubs.

---

## Invitation for correction

This dataset will be wrong in ways the authors cannot detect from the rosters alone. We
are specifically looking for:

- **Providers who are authorized but not appearing** in this registry — including entities
  whose names differ between the regulatory record and the public directory, or who were
  issued licenses before the earliest snapshot the registry holds.

- **Providers listed as active who have since exited** — if you know of an entity or
  individual who resigned, was revoked, or otherwise left a program after our last snapshot
  date, please let us know. We will add a `disappeared_from_roster` or `revoked` event as
  appropriate, with your contact as provenance.

- **Authorization dates** we could not recover from the public roster — particularly for
  early AZ ABS cohorts (pre-2024) and Utah Sandbox participants.

- **Practice area or description errors** — especially for Utah Sandbox entities whose
  service-model descriptions have changed since the June 2026 snapshot.

- **Any program we have wrong in scope or structure** — if a program is miscategorized
  (e.g., a sandbox we coded as `alp_license`, or a program with non-lawyer ownership
  rights we coded as `allows_nonlawyer_ownership = false`), the error propagates to every
  downstream analysis.

Corrections can be submitted via GitHub issue at
`github.com/jamespaul/reregulation-registry/issues` or by email to
james.paul@yale.edu. We will document the source of every correction in the
`provider_alias` or `provider_status_event` tables with your name or organization as
`scraper_version` (e.g., `manual-iaals-2026-07`), so the provenance of corrections is
traceable in the published data.

We view the registry as an ongoing contribution to — not a replacement for — the
qualitative and institutional knowledge that IAALS, the Rhode Center, and the programs'
regulators themselves hold. Any corrections, additions, or annotations you are willing to
share will be incorporated with attribution.

---

## How to cite

```
Paul, James. (2026). U.S. Legal Services Reregulation Provider Registry (v1.0.0)
[Data set]. Yale Law School. https://github.com/jamespaul/reregulation-registry
```

Data license: CC BY 4.0. Code license: MIT.
