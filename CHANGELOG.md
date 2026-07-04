# Changelog

All notable changes to this dataset and its pipeline are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); versioning applies to the dataset
release as a whole (schema + data + pipeline), not to individual scrapers, which carry
their own `scraper_version` in every row's provenance fields.

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
- CI (`.github/workflows/`) running `ruff`, `pytest` (443 tests, fixture-only — no live
  network calls), and the reproduce pipeline on every push.
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
