# Changelog

All notable changes to this dataset and its pipeline are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versioning applies to the dataset
release as a whole (schema + data + pipeline), not to individual scrapers, which carry
their own `scraper_version` in every row's provenance fields.

## [1.0.2] — 2026-07-06

Removes `prog_dc_rule54` (D.C. Rule of Professional Conduct 5.4(b)) from scope. **10
programs, 7 states, 708 providers, 748 events, 19 snapshots** (was 11 programs, 7 states +
DC, 708 providers, 748 events, 20 snapshots — DC contributed zero providers/events either
way, so only the program/snapshot counts change). 466 tests collected (464 passed, 2
skipped), down from 472 (470 passed, 2 skipped) — the 6 tests in the deleted
`tests/test_dc_rule54.py`.

### Why

D.C. Rule 5.4(b) is a self-executing ethics rule: no application, registration, or
regulator notice of any kind is ever required for a firm to organize under it. Every
other zero-provider program in this dataset (CA LDA, TX ALP, WA Entity Pilot) is zero
*for a reason that could resolve* — a county scraper gets built, an effective date gets
set, an applicant gets authorized. D.C. Rule 5.4(b) has no comparable path to a nonzero
count: there is no administrative act for any future scraper to ever observe. Keeping it
as a `program` row misrepresented what "zero providers" means for every other row in the
table. Full reasoning: `docs/sampling_frame.md §4` and `validation/dc_rule54.md`.

### Removed

- `scrapers/dc_rule54.py`, `scripts/run_dc_rule54.py`, `tests/test_dc_rule54.py`,
  `tests/fixtures/dc_rule54_snap1.html`.
- `prog_dc_rule54` from `scripts/seed_programs.py`, `pipeline/reproduce.py`'s
  `_SCRAPER_MAP`, `pipeline/scrape.py`/`pipeline/orchestrate.py`/`pipeline/wayback.py`'s
  scraper registries, and `resolve/program_status.py`'s legislative-resolver config.
- The `prog_dc_rule54` `program` and `source_snapshot` rows from `data/db/registry.duckdb`
  (via a fresh `make reproduce` — no manual DB surgery) and its raw blob
  (`data/raw/d33cf...145a.html`) from `data/raw/`.

### Added

- A new, expected consequence of the removal: `prog_dc_rule54` had been silently
  satisfying IAALS's "Alternative Business Structures — Washington, D.C." listing
  (confirmed against the real captured completeness snapshot — it's filed under
  "Implemented Programs"). Removing the program turns that into a genuine
  completeness-audit gap. Recorded pre-emptively as `intentionally_excluded` in
  `validation/residual_gaps.csv` (`detected_by=manual-dc-rule54-removal`) rather than
  left for the next live `make completeness` run to rediscover. Ledger is now 16 rows
  (14 from the one real 2026-07-01 automated run, plus this row and the Oregon LP row
  added in the same manner in `[1.0.1]`).
- `docs/sampling_frame.md §1`'s in-scope test now states a third criterion explicitly:
  the authorizing instrument must require *some* administrative act that could in
  principle produce a roster. A named regulator alone isn't sufficient, which is exactly
  the distinction that was missing when `prog_dc_rule54` was first built.

### Changed

- Version bumped to 1.0.2 everywhere it's stated as the current release: `README.md`,
  `docs/data_note.md`, `docs/sampling_frame.md`, `validation/summary.md`, `.zenodo.json`,
  and `scripts/build_datapackage.py` (which generates `data/release/datapackage.json` —
  its program/state counts and D.C. suffix are computed dynamically from the release
  data, so those self-corrected on the next `make export`; only the hardcoded version
  string needed a manual bump).
- `tests/test_frame_reconcile.py::test_gap_detection_against_seeded_programs` updated:
  the fake program list no longer includes a DC/abs row, and "Alternative Business
  Structures — Washington, D.C." moved from the "must not appear as a gap" assertions to
  the "must surface as a gap" assertions, matching the real table's new shape.
- `tests/test_program_coverage.py`'s `_ZERO_ROSTER_PROGRAMS` no longer lists
  `prog_dc_rule54` — this test would otherwise fail on the next DB rebuild (it asserts
  every zero-provider program in the DB has a documented reason on file).
- Every prose reference to "11 programs" / "8 jurisdictions" / "four zero-provider
  programs" / "20 snapshots" updated to "10" / "7" / "three" / "19" across `README.md`,
  `docs/data_note.md`, `docs/methodology.md`, `docs/sampling_frame.md`,
  `validation/summary.md`, `validation/coverage_report.md`, and
  `validation/longitudinal_validity.md`.
- `validation/dc_rule54.md` kept (not deleted) as the research record, with a notice at
  the top pointing to the removal and a new closing section explaining why the same
  reasoning that justified building the program later justified un-building it.
- `reregulation-registry-v1-spec.md`'s original D.C. Rule 5.4 planning entry annotated
  with the eventual outcome, rather than left to silently describe a program that no
  longer exists.

## [1.0.1] — 2026-07-05

Fixes every finding from the pre-publication adversarial review
(`docs/audit/adversarial_review.md`) — 5 blockers, 6 should-fix, 2 minor. No schema
changes; no provider/program/event rows added, removed, or reclassified. 472 tests
collected (470 passed, 2 skipped), up from 443 (443 passed, 2 skipped) — 27 new tests
added covering every code change below, 2 pre-existing skips unchanged.

### Fixed

- **The dataset itself is now committed to git** (B1). `data/raw/` and `data/release/`
  were previously `.gitignore`d entirely — this repo's only commit had zero data files
  in it. `data/db/` remains gitignored (fully rebuildable from the other two via
  `make reproduce`; not part of the published three-layer chain).
- **`storage_path` is now repo-relative, not an absolute machine-specific path** (B2).
  `pipeline/db.py::_normalize_storage_path()` normalizes on write;
  `pipeline/reproduce.py`/`pipeline/audit.py` resolve a relative path against the repo
  root on read. `scripts/migrate_relative_storage_paths.py` migrated all 20 existing
  `source_snapshot` rows. Verified by running `make reproduce` and `make audit` from a
  full repo copy at a path that never previously existed — both passed, rebuilding all
  708 providers / 748 events from `data/raw/` with zero network calls.
- **CI now actually runs `make reproduce` (which runs the provenance audit internally)
  and fails the build if `data/release/` doesn't match what `data/raw/` reproduces**
  (B3, `.github/workflows/ci.yml`). Previously CI only ran `ruff` + `pytest`; the
  `storage_path` bug above went undetected because nothing in automation ever exercised
  the reproduce path against a fresh checkout.
- **Reproduce output is now byte-for-byte deterministic across runs** (found while
  building the B3 CI gate — an earlier version of this fix would have been flaky).
  `pipeline/diff.py` was iterating a Python `set` (hash-randomized per process) when
  generating `status_change` events; `pipeline/export.py` had no `ORDER BY` at all.
  Fixed both: `diff.py` sorts the set before iterating, and `export.py` now sorts every
  exported table by primary key. Verified via 5 consecutive `make reproduce` runs
  producing identical SHA-256 hashes for every CSV and Parquet file.
- **Citation URL corrected** everywhere it appeared (B4): `README.md`, `.zenodo.json`,
  `docs/data_note.md`, and `scripts/build_datapackage.py` (which generates
  `data/release/datapackage.json`) pointed to `github.com/jamespaul/reregulation-registry`;
  the actual remote is `github.com/jamespaul-yls/reregulation-provider-registry`.
- **Unpersisted dry-run numbers are no longer presented as validation evidence** (B5).
  The AZ ABS 2025-04-04/-12-15/2026-06-16 Wayback counts were disclosed as an unpersisted
  dry run in `validation/longitudinal_validity.md` but treated as verified reconciliation
  evidence in `validation/summary.md` and `docs/data_note.md` ("5.9% divergence, within
  tolerance," "internally consistent" trajectory). All three documents now clearly mark
  those numbers as context-only and attribute the "no scraper defect" conclusion to what
  is actually verifiable: the AZ ABS accuracy sample (17/167 rows, 0% error) and the two
  genuinely persisted snapshots (77 on 2024-11-08, 167 on 2026-06-28).
- **`docs/az_abs.md` no longer contradicts the rest of the documentation set** (S1) — it
  previously said no Wayback backfill had been attempted for AZ ABS, while the DB has
  (and the whole longitudinal narrative depends on) a persisted 2024-11-08 capture.
- **Oregon LP is now documented as a considered-and-deferred candidate program** (S2),
  in `docs/sampling_frame.md` (new §3a) and in `validation/residual_gaps.csv` /
  `validation/completeness.md` (15th ledger row, `detected_by=manual-oregon-research`,
  distinct from the 14 automated IAALS-check rows). Also corrected a stale cross-reference
  in `docs/methodology.md §1` ("10 programs... three of them zero-provider" → 11 / four,
  matching `sampling_frame.md` since WA Entity Pilot was added).
- **`current_status`'s "never scraped directly" framing now states the bootstrap
  exception's actual scale** (S3): as of v1.0.0, only `prog_az_abs` and `prog_ut_sandbox`
  have any event that came from a real cross-snapshot diff; the other five populated
  programs' status values are 100% bootstrap-seeded from the source's own status column.
  Clarified in `CLAUDE.md` golden rule 3, `docs/data_dictionary.md`, and
  `docs/methodology.md §4b`.
- **WA Entity Pilot's authorized-status matching is now token-based with a negative-token
  guard, and logs a warning for any unrecognized status** (S4,
  `scrapers/washington_entity_pilot.py`) instead of silently treating anything outside an
  exact-match set as not-authorized. 8 new tests cover plausible real-world label variants
  ("Board Approved", "Authorized — Active"), negative cases ("Not Authorized", "Inactive"),
  and the new warning log.
- **Two precision overstatements in `docs/data_note.md` corrected** (S5):
  `authorization_date` coverage was described as "partially" populated outside MN LP —
  it's actually 0% for every other program, not partial; and WA LLLT's "10 voluntarily
  resigned" is actually 9 Voluntarily Resigned + 1 Retired.
- **Removed an unverifiable claim about IAALS's/the Rhode Center's own ongoing work**
  (S6) from `docs/data_note.md`, a document addressed directly to those recipients.
- **Sampling-denominator convention documented** for multi-snapshot programs (M1,
  `docs/methodology.md §10c`): the ≥15-or-10% accuracy-sample rule uses the latest
  roster snapshot's count, not the cumulative all-time total.
- **WA LLLT's "unknown" judgment call now cross-referenced from the plain-language
  summary** (M2, `docs/data_note.md`), not only from the per-source validation doc.

## [1.0.0] — 2026-07-04

Initial public release: a provider census with entry/exit tracking across 11 U.S.
legal-services reregulation programs. No outcomes, rates, harm measures, or litigation
linkage — see `docs/methodology.md §12i` for what is explicitly deferred to v2/v3/v4.

### Added

- **11 programs, 7 states + DC:** AZ ABS, AZ LP, CA LDA, CO LLP, DC Rule 5.4(b), MN LP,
  TX ALP, UT LPP, UT Sandbox, WA Entity Regulation Pilot, WA LLLT.
- **708 providers, 748 status events, 20 immutable snapshots** — all derived tables
  fully re-derivable from `data/raw/` via `make reproduce` (no network required).
- Washington Entity Regulation Pilot Project scraper (`scrapers/washington_entity_pilot.py`,
  `prog_wa_entity_pilot`) — one program resolving both the IAALS "WA ABS" and "WA sandbox"
  listings. Zero applicants authorized as of this release (4 "Under Review"); the
  pre-authorization applicant pipeline is captured in the raw snapshot but not loaded as
  providers — extending `current_status` to represent "pending applicant" is flagged as a
  v2 decision, not made here (`validation/washington_entity_pilot.md`).
- Full provenance on every published row (`source_url`, `retrieved_at`,
  `scraper_version`), audited 100% clean across `program`, `provider`,
  `provider_status_event`, and `provider_alias` (`pipeline/audit.py`).
- Longitudinal entry/exit detection via snapshot diffing (`pipeline/diff.py`), with
  `disappeared_from_roster` kept distinct from `revoked` (observation vs. legal
  conclusion — `docs/methodology.md §4c`).
- Wayback Machine backfill for AZ ABS and UT Sandbox, extending historical depth beyond
  the first own-scrape snapshot (`pipeline/wayback.py`).
- Legislative-status resolution layer (`resolve/program_status.py`) surfacing Open
  States / LegiScan signals for `program_status`, with court-rule overrides for
  programs authorized by administrative rule rather than statute.
- Completeness audit (`completeness/frame_reconcile.py`, `make completeness`) reconciling
  the `program` table against the IAALS external inventory: 14 candidate gaps surfaced,
  all 14 resolved (2 `intentionally_excluded`, 1 `resolved_built`, 11 `deferred_to_v2`) —
  see `docs/sampling_frame.md §6`.
- Frictionless `datapackage.json` covering all 6 tables with full field types, enum
  constraints, and foreign keys; validated clean with `frictionless validate`.
- CSV + Parquet exports for every table, including the unpopulated `crosswalk_courtlistener`
  v3 stub (schema defined now for forward compatibility).
- Full documentation set: `docs/data_dictionary.md`, `docs/methodology.md`,
  `docs/sampling_frame.md`, `docs/data_note.md`, `docs/v2_readiness.md`, and per-source
  validation logs in `validation/`, consolidated in `validation/summary.md`.
- CI (`.github/workflows/`) running `ruff` and `pytest` (443 tests, fixture-only — no live
  network calls) on every push. **Correction (2026-07-05):** this bullet originally also
  claimed CI ran "the reproduce pipeline" on every push — it didn't; see `[1.0.1]` below
  and `docs/audit/adversarial_review.md` B3.
- Dual licensing: code under MIT (`LICENSE`), data under CC BY 4.0
  (`data/release/LICENSE`).

### Known limitations (see `docs/methodology.md §12` for full detail)

- Most programs have a single roster snapshot as of this release; longitudinal signal
  strengthens as future scrapes accumulate.
- `practice_areas_raw` / `practice_areas_list` are sparse — most source rosters don't
  publish practice-area detail, and the JusticeBench LIST-code mapping is not yet applied.
- `uses_technology` / `uses_ai` are mostly `NULL` in v1 — the coding workflow from
  provider application materials is not yet implemented (`docs/v2_readiness.md`).
- CA LDA, DC Rule 5.4(b), TX ALP, and WA Entity Pilot are correctly zero-provider
  (structural/temporal — `docs/sampling_frame.md §3`), not un-scraped gaps.
