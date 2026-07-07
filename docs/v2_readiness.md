# v2 Readiness — Forward-Compatibility Hooks

This document confirms what v1 already carries so v2 (the outcomes layer — see
`docs/methodology.md §12i`) can build on it without a breaking migration, and flags the one
piece of v1 data v2's AI-policy cut will need backfilled first.

**Version:** 1.0.2 · **Last updated:** 2026-07-06

---

## 1. Stable IDs

- **`provider_id`** — deterministic, content-addressed:
  `prov_{program_slug}_{sha256(program_id + legal_name)[:12]}` (`docs/methodology.md §7`).
  Same `(program_id, legal_name)` always produces the same ID, across re-scrapes and
  across the v1→v2 migration, with no sequence table to keep in sync. v2 outcome records
  (complaints, discipline, judicial outcomes) can key directly on `provider_id` from day
  one.
- **`program_id`** — stable opaque string (e.g. `prog_az_abs`), assigned once in
  `scripts/seed_programs.py` and never regenerated. Safe to hard-code as a foreign key in
  any v2 table.
- **`snapshot_id`** — content-addressed (`snap_{sha256[:16]}`), so re-ingesting the same
  raw bytes always resolves to the same row — no accidental duplication across a v1→v2
  re-derivation.
- **`event_id`** — deterministic hash of `(provider_id, snapshot_id, event_type)`; safe to
  re-run the diff pipeline against v1 raw snapshots inside a v2 codebase without producing
  duplicate events.

**Implication for v2:** none of these schemes need to change. A v2 outcomes table can FK
directly onto `provider_id` today.

## 2. Extensible enums

`models/enums.py` is the single source of truth for every enum, and two are already
provisioned for v2/v3 growth beyond what v1 populates:

- **`ProgramType.community_justice_worker`** — defined now, zero v1 programs use it
  (`docs/sampling_frame.md §6`). Adding a CJW program in v2 requires a new `program` row
  and scraper, not a schema or enum change.
- **`EventType.disciplined` / `EventType.reinstated`** — defined now, unpopulated in v1
  (no discipline-source scraper exists yet). v2's outcomes layer can start writing these
  event types immediately; the `provider_status_event` table and `_recompute_statuses()`
  logic already handle them (`docs/methodology.md §4a`).
- **`CurrentStatus.revoked`** — defined and distinct from `exited`
  (`disappeared_from_roster ≠ revoked`, `docs/methodology.md §4c`). v2 discipline data
  should populate `revoked` via `disciplined` events, not by reinterpreting
  `disappeared_from_roster`.

Adding a wholly new enum value (e.g., a new `program_type`) is additive and does not
require migrating existing rows — `StrEnum` values are stored as plain `VARCHAR` in
DuckDB, so old rows keep validating.

## 3. `crosswalk_courtlistener` (v3 stub, present now)

Full schema defined in `models/schema.py` and `models/enums.py::MatchMethod`, exported
(empty) in every v1 release, and documented in `docs/data_dictionary.md` and
`docs/methodology.md §11`. The design (offline blocking → `rapidfuzz` scoring →
confidence-threshold auto-accept/human-review split → immutable verified rows) is written
but unimplemented. This is a v3 (litigation-linkage) deliverable, but publishing the empty
table now means v2's outcomes work and v3's litigation-linkage work can both target a
schema that won't move under them.

**Immutability guarantee already enforced:** `RegistryStore.upsert_crosswalk()` silently
no-ops against any row with `verified=True` (`pipeline/db.py`), so v3 human review work is
safe to start against this table at any point without v2 work being able to clobber it.

## 4. Raw snapshots retained for reuse

Every raw capture in `data/raw/` is content-hashed and immutable (golden rule 2). v2 does
not need to re-fetch anything v1 already captured — `make reproduce` rebuilds the entire
v1 derived state from these snapshots with no network access, and a v2 branch can extend
the same `data/raw/` directory with new capture types (discipline records, activity
reports) without touching or invalidating what v1 already stored.

## 5. `uses_technology` / `uses_ai` — v2's AI-policy cut needs backfill

These two boolean flags exist in the schema specifically because v2's AI/UPL policy
analysis depends on them (`docs/data_dictionary.md`, `models/schema.py`). **Current
population, by program:**

| Program | Providers | `uses_technology` populated | `uses_ai` populated |
|---|---:|---:|---:|
| AZ ABS | 203 | 0 (0%) | 0 (0%) |
| AZ LP | 120 | 0 (0%) | 0 (0%) |
| CO LLP | 126 | 0 (0%) | 0 (0%) |
| MN LP | 42 | 0 (0%) | 0 (0%) |
| UT LPP | 52 | 0 (0%) | 0 (0%) |
| **UT Sandbox** | 70 | **8 (11%)** | **8 (11%)** |
| WA LLLT | 95 | 0 (0%) | 0 (0%) |

Only Utah Sandbox has any coverage (its roster publishes per-entity service-model
descriptions the scraper can read these flags from). Every other program is 100% `NULL`
— not `False`; per `docs/methodology.md §12f`, `NULL` must not be treated as a negative
signal. **Before any v2 AI-policy analysis, this needs a systematic backfill** — either by
extending each scraper to parse application/service-model descriptions where the source
publishes them, or by a manual coding pass against provider websites. Flagging here so
the backfill scope is explicit rather than discovered mid-analysis.

## 6. Branch and tag structure

The repository is currently a single `main` branch with no tags. The recommended
structure so v2 can branch cleanly off a frozen v1:

1. Tag the commit that ships the public release as `v1.0.2` on `main` (manual step — see
   the release checklist; not done by this pass). Note this is `v1.0.2`, not `v1.0.0`:
   two patch releases (`1.0.1` — reproducibility/documentation fixes; `1.0.2` — the D.C.
   Rule 5.4(b) scope removal) have landed on `main` since `1.0.0`, and `1.0.0`'s actual
   content is no longer what ships — tagging it today would tag a superseded state.
2. Branch v2 development off the `v1.0.2` tag (`git switch -c v2 v1.0.2`), not off the
   tip of `main`, so v2 work is insulated from any v1.x patch commits that land on `main`
   afterward.
3. If a v1.x bugfix is needed after v2 work has started, patch it on `main` (or a
   `v1.x` maintenance branch cut from the `v1.0.2` tag) and cherry-pick into `v2` as
   needed, rather than merging `main` wholesale into `v2`.
4. Keep `data/raw/` and the release schema additive-only across the v1→v2 boundary — no
   v1 table, column, or ID scheme should be renamed or removed in v2; only new tables
   (outcomes) and new nullable columns should be added. This is what makes "branch off
   the tag" safe: v2 is a superset, not a fork, of v1's data model.

No tag exists yet; this section describes the structure to adopt once step 1 above (the
manual `v1.0.2` tagging step) is done.
