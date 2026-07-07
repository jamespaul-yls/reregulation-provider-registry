# Validation: Washington Entity Regulation Pilot Project

**Source:** https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants
**Scraper:** `scrapers/washington_entity_pilot.py` v0.1.0
**Fixture:** `tests/fixtures/wa_entity_pilot_snap1.html`
**Fixture sha256:** `07d353745a809627d7e009ad132fb766ca6f0c4dd845a55ebbcbdf4d6a42b969`
**Scrape date:** 2026-07-04

---

## Program background

Washington Supreme Court Order No. 25700-B-721 (Dec. 5, 2024) established a Framework-driven
pilot project — administered jointly by the Washington State Bar Association (WSBA) and its
Practice of Law Board — testing "entity regulation": limited exemptions from RCW 2.48.180,
RPC 5.4, and LLLT RPC 5.4 that would let entities provide legal and law-related services
(whether or not doing so constitutes the practice of law) under individual, time-boxed court
orders. The pilot runs up to 10 years from the date the **first** entity is authorized.

**This one program resolves two IAALS completeness-audit listings.** IAALS's knowledge
center double-lists Washington under both "Regulatory Sandbox" and "Alternative Business
Structures" — the same pattern as Utah, where `prog_ut_sandbox` alone covers both listings
because a single Framework-style pilot grants both sandbox-style oversight and ABS-style
nonlawyer-entity relief. `prog_wa_entity_pilot` (`program_type=sandbox`) is the single program
row for Washington's pilot; see `docs/sampling_frame.md §6` for the resolution of both
residual-gap ledger rows. **Do not create a second Washington program row for either model
type.**

---

## Applicant list vs. authorized-provider table

The WSBA publishes the **full applicant list** — every entity that has applied, regardless of
review status — with an explicit disclaimer on the page itself: *"Inclusion on this list does
NOT mean the entity is authorized to practice law in Washington."* Authorized entities are
promised separately on the WSBA legal directory once authorized, which does not yet list any
Entity Regulation Pilot participants.

**As of 2026-07-04, the full applicant list is:**

| Date Received | Entity Name | Status |
|---|---|---|
| 2025-10-22 | Legata, Inc. | Under Review |
| 2026-01-08 | Law on Call, LLC | Under Review |
| 2026-03-10 | Wrk Legal, LLC | Under Review |
| 2026-01-27 | Confido Inc. | Under Review |

**Status breakdown:** 4 / 4 applicants "Under Review." **Zero applicants have been
authorized.**

---

## Why provider count is zero

| Reason | Detail |
|---|---|
| No applicant has cleared review yet | All 4 listed applicants are "Under Review" as of the WSBA page's stated update date (June 26, 2026) and this scraper's run date (2026-07-04) |
| Structural, not a scraping gap | The program row (`prog_wa_entity_pilot`) and its evidentiary source page are both correctly present and snapshotted; there is simply no authorized entity yet to load as a provider |

**Coverage: 0/4 applicants authorized (0%) — expected zero, not a gap.** The full applicant
list (all 4, including their "Under Review" status) is preserved in the raw snapshot
(`data/raw/07d353745a809627d7e009ad132fb766ca6f0c4dd845a55ebbcbdf4d6a42b969.html`) so the
pipeline as of this date is captured even though nothing is loaded as a `provider` row.

This scraper should be re-run periodically (`uv run python scripts/run_wa_entity_pilot.py`)
to detect the first authorization — at which point `_AUTHORIZED_TOKENS` in
`scrapers/washington_entity_pilot.py` should be checked against whatever status label the
WSBA actually prints for an authorized entity (not yet observed on the live page; the current
token set — `authorized`, `approved`, `participating`, `active`, matched per-word rather than
as an exact string so a plausible real label still matches — is a reasonable guess, not a
confirmed label). As of 2026-07-05, any status that doesn't match a known token and isn't the
observed "Under Review" label also logs a warning (`_is_unrecognized_status()`), so a
genuinely new label is surfaced rather than silently misclassified either way — see
`docs/audit/adversarial_review.md` S4.

---

## ⚑ Flagged for a v2 scope decision — do NOT extend the enum now

The applicant list includes a real, useful signal I am **not** capturing as structured data:
each applicant's pre-authorization pipeline status ("Under Review," and potentially others
such as "Denied" or "Withdrawn" as the pilot matures). Our `current_status` enum
(`models/enums.py::CurrentStatus`) has exactly five values — `active`, `exited`, `suspended`,
`revoked`, `unknown` — none of which correctly represents "applied, not yet decided."

Per instruction, this scraper does **not** invent a status value or otherwise force
pre-authorization applicants into the `provider` table. Options for v2, to be decided later:

1. Add a `pending` (or similarly named) value to `CurrentStatus` — the most direct fix, but
   changes a v1-published enum's meaning for every table that uses it, not just this program.
2. Add a separate `program_applicant` table (parallel to `provider`, no `current_status`
   dependency) — more schema surface, but keeps the v1 enum semantics untouched.
3. Leave applicant-pipeline tracking as raw-snapshot-only (current v1 behavior) and only
   promote entities to `provider` rows once authorized — simplest, but loses the "how long did
   review take" signal as structured data (it remains recoverable from snapshot diffing, since
   every snapshot captures the full list with dates).

This is exactly the kind of scope/schema decision `docs/sampling_frame.md` and
`docs/methodology.md` reserve for a human call, not a scraper default — flagging here rather
than deciding it.

---

## Comprehensiveness (coverage / recall)

| Category | Count |
|---|---|
| Source-stated applicant total | 4 |
| Applicants parsed | 4 |
| Authorized entities parsed | 0 |
| **Coverage (applicant list)** | **4 / 4 (100%)** |
| **Coverage (authorized providers)** | **0 / 0 (N/A — none authorized yet)** |

## Accuracy (precision)

No stratified accuracy sample is applicable — there are zero provider rows to sample.
Identity-field accuracy will be assessed against the standard ≥15-row / ≥10% protocol once
the first entity is authorized and loaded as a provider.

---

## Reconciliation summary

```
Source: https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants
Source-stated applicant total: 4
Authorized (loaded as providers): 0
Coverage: 0/4 applicants authorized — expected zero until the Board/Court authorizes a participant
```
