# Changelog

All notable changes to this dataset and its pipeline are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versioning applies to the dataset
release as a whole (schema + data + pipeline), not to individual scrapers, which carry
their own `scraper_version` in every row's provenance fields.

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
