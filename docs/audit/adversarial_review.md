# Adversarial Review — v1.0.0 Pre-Publication Audit

**Role:** Hostile peer reviewer, not the builder. Every claim below was checked against the
live DuckDB (`data/db/registry.duckdb`), the actual git history, the files on disk, and the
CI config as they exist right now — not against what the docs say should be true.

**Date of review:** 2026-07-05
**Scope:** Everything intended for publication to Stanford / IAALS: `README.md`,
`docs/*.md`, `CHANGELOG.md`, `.zenodo.json`, `validation/*.md`, `data/release/*`,
`data/db/registry.duckdb`, the pipeline/scraper code, and `.github/workflows/*`.

Every number quoted below was recomputed from the live DB or file system in this session; I
did not take any document's word for a total.

---

## Verdict

**Not publishable as-is.** The internal arithmetic is unusually clean (every count in
README/data_note/validation cross-checks against the DB — see "What actually holds up"
below), which makes this a strong dataset once the structural blockers are fixed. But two of
the five blockers mean **the thing you would actually publish today contains no data and
cannot be reproduced by anyone who isn't on this laptop**, which is disqualifying regardless
of how clean the numbers are.

**Ordered blocker list (fix in this order — each unblocks verifying the next):**

1. [B1](#b1-the-dataset-is-not-in-the-repository) — Commit the actual data (or wire up the
   git-lfs/external store CLAUDE.md's own repo layout comment says to use).
2. [B2](#b2-storage_path-is-an-absolute-machine-specific-path) — Make `storage_path`
   relative before you commit it, or B1's commit ships a dataset that only reproduces on
   this laptop.
3. [B3](#b3-ci-does-not-run-reproduce-or-audit-the-changelog-says-it-does) — Add
   `make reproduce` (against the committed data) to CI so B1/B2 can never silently regress
   again.
4. [B4](#b4-the-citation-url-does-not-match-the-actual-git-remote) — Fix the citation URL
   everywhere before anyone copies it into a paper.
5. [B5](#b5-a-dry-run-number-is-cited-as-validation-evidence-and-cannot-be-reproduced) —
   Either persist the Wayback captures behind the AZ ABS trajectory claims, or strip the
   unreproducible numbers out of `validation/summary.md` and `docs/data_note.md` and label
   the dry-run table in `validation/longitudinal_validity.md` as context-only, not evidence.

---

## What actually holds up (so this isn't read as "everything is wrong")

Before the findings: I recomputed every headline number from `data/db/registry.duckdb`
directly, independent of any doc.

- 708 providers, 748 events, 20 snapshots, 11 programs, 0 aliases, 0 crosswalk rows — matches
  README, CHANGELOG, `.zenodo.json`, and `validation/summary.md` exactly.
- Per-program active/exited/suspended/unknown breakdowns in README, `docs/data_note.md`,
  `validation/coverage_report.md`, and `validation/longitudinal_validity.md` all agree with
  the DB, including the less-obvious ones (AZ ABS's 203 = 160 active + 43 exited, split 7
  bootstrap + 36 diffed; WA LLLT's 68/10/4/13 split; UT Sandbox's 70 = 8 + 62).
- `frictionless validate` on `data/release/datapackage.json` passes clean, all 6 tables VALID.
- Every raw blob's filename matches its own SHA-256 (checked all 62 files in `data/raw/`).
- The completeness ledger (`validation/residual_gaps.csv`, 14 rows) matches the disposition
  counts quoted in `docs/sampling_frame.md §6`, `docs/methodology.md §10e`, and
  `validation/completeness.md` exactly (2 / 1 / 11 split, 11 = 3 + 8).

This is why the blockers below are worth fixing rather than a reason to start over: the
analytical layer is sound, but the publication mechanics under it are not.

---

## Blockers

### B1. The dataset is not in the repository

`git ls-files` shows exactly one commit ("Initial commit"), and `.gitignore` excludes
`data/raw/*`, `data/db/*`, and `data/release/*` wholesale (only `.gitkeep` placeholders are
tracked). Every number in this review — 708 providers, 20 snapshots, all of it — exists only
on this machine, right now.

**Why a reviewer would flag it:** README says "All files are in `data/release/`," the
citation block points at `github.com/.../reregulation-registry`, and `.zenodo.json` describes
"708 providers... raw HTML/PDF captures are content-hashed and immutable." Anyone who clones
the repo — a Stanford RA, an IAALS staffer, a peer reviewer checking the citation — gets a
directory of `.gitkeep` files and zero rows. This isn't a documentation gap; it's the absence
of the thing being described.

**File/evidence:** `.gitignore` lines 24–34; `git ls-files data/raw | wc -l` → 1 (the
`.gitkeep`); `git log --oneline` → single commit.

**Note:** `CLAUDE.md`'s own repo-layout comment anticipates this — `data/raw/` is annotated
"(git-lfs or external store)" — so the intended fix already has a design; it just was never
wired up before this looked publication-ready.

---

### B2. `storage_path` is an absolute, machine-specific path

`source_snapshot.storage_path` (and the `storage_path` column in the published
`data/release/source_snapshot.csv`) stores values like
`/Users/jamespaul/Desktop/database/data/raw/9f99d17b….html` — the literal absolute path on
this laptop, not a repo-relative path.

**Why a reviewer would flag it:** `docs/data_dictionary.md` documents this same field as
"Relative path from the repo root to the blob file in `data/raw/`" — the code and the schema
doc disagree. More importantly, `pipeline/reproduce.py::_verify_blob()` and
`pipeline/audit.py::_check_blobs()` both call `Path(storage_path)` directly on this value —
not on any `--raw`-relative path — so `make reproduce` and `make audit` will raise
`FileNotFoundError` on literally any machine other than this one, at this exact directory
location. The single most-repeated claim in this dataset's marketing — "all derived tables
are fully re-derivable from `data/raw/`... no network required" (README, CHANGELOG,
`docs/data_note.md`, `.zenodo.json`) — does not hold once B1 is fixed and someone else
actually clones the repo.

**File/evidence:** `pipeline/snapshot.py:80` (`storage_path=str(blob_path)`, absolute);
`pipeline/reproduce.py:122–134` (`_verify_blob` uses `row["storage_path"]` literally, ignoring
the `--raw` CLI arg); `pipeline/audit.py:189–206` (same pattern); `data/release/source_snapshot.csv`
column 6.

**Secondary issue:** this also leaks the author's local username and directory layout into a
CC-BY-4.0 published file — cosmetic, but worth cleaning up in the same fix.

---

### B3. CI does not run `reproduce` or `audit` — the CHANGELOG says it does

`.github/workflows/ci.yml` runs exactly two steps: `ruff check .` and `pytest -v --tb=short`.
There is no `make reproduce`, `make audit`, or `make completeness` step anywhere in CI.

**Why a reviewer would flag it:** `CHANGELOG.md` states under `[1.0.0]`: "CI
(`.github/workflows/`) running `ruff`, `pytest` (443 tests, fixture-only — no live network
calls), **and the reproduce pipeline** on every push." This is checkable in about ten seconds
by opening `ci.yml`, and it's false — and its falseness is exactly why B2 was never caught:
nothing in automation ever actually re-derives the release tables from `data/raw/` and
diffs the result. `validation/summary.md §5` also says "It runs the full provenance audit
internally" as if this happens automatically, without saying that it currently only happens
when a human types `make reproduce` locally.

**File/evidence:** `.github/workflows/ci.yml:1–33` (full file — no `reproduce`/`audit`/
`completeness` invocation); `CHANGELOG.md` line 48.

**Related minor discrepancy caught in the same check:** the CHANGELOG's parenthetical "443
tests" is stale — `pytest --collect-only -q` currently collects **445** tests. Small, but it's
a number in prose that disagreed with the number the code produces, which is exactly the
category of error this review was asked to hunt for.

---

### B4. The citation URL does not match the actual git remote

`README.md`, `docs/data_note.md`, and `.zenodo.json`'s `related_identifiers` all give the
citation/source URL as `github.com/jamespaul/reregulation-registry`. The actual configured
remote is:

```
git@github.com:jamespaul-yls/reregulation-provider-registry.git
```

Different owner (`jamespaul` vs. `jamespaul-yls`) **and** a different repo name
(`reregulation-registry` vs. `reregulation-provider-registry`).

**Why a reviewer would flag it:** this is the exact string that goes into a BibTeX entry and
gets copied into other people's papers. As written, it's a dead or wrong link the moment
anyone tries to resolve it — precisely the kind of thing a peer reviewer checks first and a
citing researcher discovers only after publication.

**File/evidence:** `README.md` "How to cite" block; `docs/data_note.md` "How to cite" block;
`.zenodo.json` `related_identifiers[0].identifier`; actual remote via `git remote -v`.

---

### B5. A dry-run number is cited as validation evidence and cannot be reproduced

`validation/longitudinal_validity.md` states plainly (lines 5–13, and again in §3): the fuller
AZ ABS Wayback chain — 2022, **2025-04-04 (128 entities)**, 2025-12-15 (157), 2026-06-16
(163) — "was a dry run and was never persisted to the DB... not reflected in
`source_snapshot`." I confirmed this against the DB directly: `prog_az_abs` has exactly two
`source_snapshot` rows (2024-11-08 and 2026-06-28). No snapshot backs any of those three
intermediate figures.

**Why a reviewer would flag it:** those same unpersisted numbers are then used as
load-bearing evidence elsewhere, stripped of the "dry run" caveat:

- `validation/summary.md §2` states "Apr-2025 benchmark ~136 active vs. our 128... 5.9%
  divergence, within tolerance" and "neither divergence... exceeds the 10% investigation
  threshold" — presenting the 128 as a registry figure with the same evidentiary standing as
  the real 160/167/203 counts, with no dry-run caveat in that table.
- `docs/data_note.md` states "the Wayback-to-own-scrape trajectory (+4 entities in 12 days
  from 2026-06-16 to 2026-06-28) is internally consistent" — this specific "internal
  consistency" claim depends on the 163-count at 2026-06-16, which is also dry-run-only and
  has no snapshot.

Golden rule 2 (`CLAUDE.md`) says raw captures are immutable and derived tables/claims must be
"fully re-derivable from them." A reviewer who goes looking for the snapshot behind the 5.9%
divergence claim — the number this dataset uses to argue "no evidence of a scraper defect" —
will not find one. That's a real problem for a dataset whose entire premise is that
reproducibility is the product, not the analysis is.

**File/evidence:** `validation/longitudinal_validity.md:5–13, 61–73`; `validation/summary.md`
§2 table; `docs/data_note.md` "Arizona ABS" section, paragraph 2; DB: `source_snapshot` rows
for `prog_az_abs` (2 rows only, confirmed via query).

---

## Should-fix

### S1. `docs/az_abs.md` directly contradicts the rest of the documentation set

The per-source doc says, under "Backfill": *"No Wayback Machine backfill has been attempted
for AZ ABS... Backfill is deferred to M3."* This is false as of the current release: the DB
contains and the whole longitudinal-validity narrative depends on a `wayback-0.1.0` snapshot
for `prog_az_abs` dated 2024-11-08.

**Why flag it:** this is the single most likely internal contradiction an outside reviewer
would trip over, because `docs/az_abs.md` is exactly the kind of per-source appendix a
careful reader checks to sanity-check a headline claim — and it says the opposite of the
headline claim. It's a stale doc, not a data problem, but it undermines confidence in
everything else that's "documented."

**File/evidence:** `docs/az_abs.md` "Backfill" section vs. `source_snapshot` row
`snap_a6e3d292014fceaf` (program `prog_az_abs`, `scraper_version=wayback-0.1.0`,
`retrieved_at=2024-11-08`).

### S2. Oregon LP is a real candidate program that falls through every documented scope check

`validation/oregon_lp.md` is a genuinely careful piece of due diligence (checked the OSB
roster, admissions page, exam calendar — concluded zero licensees exist yet, revisit after
Aug/Oct 2026 exams). Oregon also appears in `CLAUDE.md` and
`reregulation-registry-v1-spec.md` as a named source to verify. But:

- `docs/sampling_frame.md` — "the authoritative statement of exactly which programs are in
  scope" (its own words) — never mentions Oregon at all, anywhere, not even as a documented
  exclusion the way TX ALP or WA Entity Pilot are.
- The completeness audit (`completeness/frame_reconcile.py`) wouldn't catch this gap either:
  per `docs/methodology.md §10e`, the IAALS reconciliation check is deliberately restricted to
  `sandbox` / `abs` / `community_justice_worker` program types and explicitly excludes
  `alp_license` — which is exactly what Oregon LP is.

**Why flag it:** a program you actually researched and decided to exclude is invisible in the
one document that claims to enumerate every in-scope/excluded decision. That's a real gap in
"the frame is complete and reconciled," not just a missing cross-reference — nothing in the
documented process would have caught Oregon's absence if the researcher hadn't happened to
leave a validation note behind.

**File/evidence:** `validation/oregon_lp.md` (full file); absence from
`docs/sampling_frame.md §2` table (11 rows, no Oregon); `docs/methodology.md §10e` bullet 2
(scope restriction that structurally excludes `alp_license` programs like Oregon's from the
one automated gap-check that exists).

### S3. `current_status` is "computed, never scraped directly" — except for most of the dataset

`CLAUDE.md` states as a golden rule: *"Longitudinal by diffing snapshots — never trust a
scraped 'status' field. Entries and exits are computed by comparing successive roster
snapshots."* `docs/data_dictionary.md` repeats this for `current_status`: "**Computed** from
`provider_status_event`... **Never scraped directly.**"

In practice, per `docs/methodology.md §4b`'s documented "bootstrap exception," any program
with only one snapshot seeds `current_status` directly from whatever status label the source
happened to publish. Checking the actual event log: of 748 events, only 40 (36
`disappeared_from_roster` + 3 `status_change` + arguably some fraction of the 1 for UT
Sandbox) come from an actual cross-snapshot diff. Every other status value in the dataset —
including all of AZ LP, CO LLP, MN LP, UT LPP, WA LLLT, and ~89% of UT Sandbox's own
"exited" count (62 of 70, only 1 of which has a `disappeared_from_roster` event) — is a direct
copy of the source's own status column at first insert, wrapped in an `authorized` event.

**Why flag it:** this isn't wrong — it's a documented, deliberate design decision, and it's
the only sane thing to do with a single snapshot. But the "never scraped directly" language
in the data dictionary and the "never trust a scraped status field" framing of golden rule 3
both overstate what's actually true for the large majority of rows in a dataset whose central
methodological pitch is that it doesn't trust rosters' self-reported status. Nothing in the
release tables tells an analyst which rows are diff-derived vs. bootstrap-seeded — that
distinction currently only exists by cross-referencing event counts per program.

**File/evidence:** `CLAUDE.md` golden rule 3; `docs/data_dictionary.md` `CurrentStatus`
section; `docs/methodology.md §4b`; DB query — `provider_status_event` grouped by
`(program_id, event_type)`: only `prog_az_abs` (36 disappeared) and `prog_ut_sandbox` (1
disappeared + 3 status_change) have any non-`authorized` events; the other 5 populated
programs have 100% `authorized`-only event histories.

### S4. WA Entity Pilot's zero depends on an untested guess about label text

`scrapers/washington_entity_pilot.py:54`: `_AUTHORIZED_STATUSES = {"authorized", "approved",
"participating", "active"}`, matched by **exact** string equality (`.strip().lower() not in
_AUTHORIZED_STATUSES`). The code comment and `docs/methodology.md` both candidly disclose that
this set is "an educated guess... no authorized-status label has ever appeared on the live
page." There is a synthetic-fixture test proving the authorized-loading code path works in
principle (`tests/test_washington_entity_pilot.py::test_parse_loads_authorized_applicants_as_providers`),
but nothing tests against a plausible real label WSBA might actually use (e.g., "Approved —
Authorized," "Certified," "Active/Authorized") that wouldn't exact-match this set.

**Why flag it:** this is exactly the "expected zero that might be a silent scraper failure"
category the review was asked to hunt for. It's unusually well-disclosed already — better
than most of the other zero-provider programs — but the disclosure itself confirms the risk
is real: the first time WSBA actually authorizes an entity, this dataset could keep reporting
zero if the label doesn't exact-match the guessed set, and nothing in CI would catch that
because there's no live data to test it against yet.

**File/evidence:** `scrapers/washington_entity_pilot.py:49–54,140`;
`docs/methodology.md` "Known source limitations by program" table, WA Entity Pilot row.

### S5. Two overstatements of precision in `docs/data_note.md`

- **Authorization dates:** "The `authorization_date` field is populated for Minnesota LP
  (dates in the PDF) and **partially for some other programs**." Checked against the DB: MN
  LP is populated 42/42 (100%); every other program (AZ ABS, AZ LP, CO LLP, UT LPP, UT
  Sandbox, WA LLLT) is 0/N (0%). There is no "partial" case — it's binary, MN LP or nothing.
- **WA LLLT exit reasons:** "68 active, **10 voluntarily resigned**, 4 suspended, 13
  inactive." Per `validation/washington_lllt.md` and `validation/coverage_report.md`, that
  "10" is actually 9 "Voluntarily Resigned" + 1 "Retired" — collapsed into one label in the
  summary doc for a program whose entire point is distinguishing exit reasons.

**Why flag it:** both are directly checkable against this dataset's own validation logs and
DB, and both round toward a cleaner story than the data actually supports — a reviewer
skimming `data_note.md` (the plain-language summary most likely to be read first) gets a
slightly rosier picture than the underlying tables show.

**File/evidence:** `docs/data_note.md` "Known limitations," items 4 and (WA LLLT section)
paragraph "68 active..."; cross-check `validation/coverage_report.md` "prog_wa_lllt" note;
DB `authorization_date` non-null counts by program.

### S6. Unverifiable claim about third parties in the document going directly to those parties

`docs/data_note.md`: "a reproducible spine that other evaluations — **including those
already underway at IAALS and the Rhode Center** — can link to their own outcome data."

**Why flag it:** this document's stated audience is IAALS and the Rhode Center themselves.
If this specific claim about their ongoing work hasn't been confirmed with them, it's the
single easiest sentence in the whole packet for the primary recipients to immediately
fact-check — and if it's inaccurate or presumptuous, it colors how skeptically they read
everything else.

**File/evidence:** `docs/data_note.md`, "What this registry is" section, paragraph 2.

---

## Minor

### M1. AZ ABS accuracy-sample denominator isn't specified as a general rule

`validation/arizona_abs.md` correctly draws its 17-row sample against N=167 (the
latest-snapshot roster) rather than the cumulative 203, satisfying "≥15 or 10%" (10.2% of
167). This is defensible and disclosed, but `docs/methodology.md §10c`'s general rule doesn't
say which "total" to use for multi-snapshot programs (latest-snapshot vs. cumulative) — worth
one clarifying sentence so the next source with multiple snapshots doesn't have to
re-derive the convention.

### M2. WA LLLT's "Inactive → unknown" judgment call isn't cross-referenced in the reader-facing summary

`validation/washington_lllt.md` §3 explicitly and honestly labels this mapping "a judgment
call; revisit if WSBA clarifies the distinction" — good practice. But `docs/data_note.md`'s
summary table just presents "13 inactive (status unknown...)" without pointing to that
caveat, so a reader working only from the plain-language summary could read `unknown` as
"not yet classified" rather than "deliberately neither active nor exited, by design, pending
WSBA clarification."

---

## Summary table

| # | Finding | Severity | File(s) |
|---|---|---|---|
| B1 | Dataset (raw/db/release) not committed to git | Blocker | `.gitignore`, `git log` |
| B2 | `storage_path` is absolute/machine-specific; breaks `reproduce`/`audit` elsewhere | Blocker | `pipeline/snapshot.py:80`, `pipeline/reproduce.py:122-134`, `pipeline/audit.py:189-206` |
| B3 | CI doesn't run reproduce/audit despite CHANGELOG claiming it does; test count stale (443 vs 445) | Blocker | `.github/workflows/ci.yml`, `CHANGELOG.md:48` |
| B4 | Citation URL ≠ actual git remote | Blocker | `README.md`, `docs/data_note.md`, `.zenodo.json` |
| B5 | Dry-run AZ ABS numbers (128/157/163) cited as validation evidence, unreproducible | Blocker | `validation/summary.md`, `docs/data_note.md`, `validation/longitudinal_validity.md:5-13` |
| S1 | `docs/az_abs.md` says no Wayback backfill attempted; contradicted by DB + rest of docs | Should-fix | `docs/az_abs.md` |
| S2 | Oregon LP excluded but absent from the "authoritative" sampling frame | Should-fix | `docs/sampling_frame.md`, `validation/oregon_lp.md` |
| S3 | "current_status never scraped directly" overstated — true for ~5% of events, not the rest | Should-fix | `CLAUDE.md`, `docs/data_dictionary.md`, `docs/methodology.md §4b` |
| S4 | WA Entity Pilot's "0 authorized" depends on an untested exact-match label guess | Should-fix | `scrapers/washington_entity_pilot.py:54` |
| S5 | `data_note.md` overstates authorization_date coverage and collapses WA LLLT exit reasons | Should-fix | `docs/data_note.md` |
| S6 | Unverified claim about IAALS/Rhode Center's ongoing work, in a doc addressed to them | Should-fix | `docs/data_note.md` |
| M1 | Sampling-denominator convention for multi-snapshot programs not stated as a general rule | Minor | `docs/methodology.md §10c` |
| M2 | WA LLLT "unknown" judgment call not cross-referenced in the plain-language summary | Minor | `docs/data_note.md` |
