# Data Dictionary — Reregulation Provider Registry

**Generated from:** `models/schema.py`, `models/enums.py`, `pipeline/db.py`
**Schema version:** 1 (Pydantic v2; DuckDB dev store)
**Last updated:** 2026-07-04

This document is authoritative for the field-level schema. The Pydantic models in
`models/schema.py` are the single source of truth; this document is derived from them and
must be kept in sync. Every inference rule that touches these fields is in
`docs/methodology.md`.

---

## Contents

- [Primitive types and constraints](#primitive-types-and-constraints)
- [Enum vocabularies](#enum-vocabularies)
- [Tables](#tables)
  - [program](#program)
  - [source_snapshot](#source_snapshot)
  - [provider](#provider)
  - [provider_status_event](#provider_status_event)
  - [provider_alias](#provider_alias)
  - [crosswalk_courtlistener](#crosswalk_courtlistener-v3-stub)
- [Provenance fields](#provenance-fields)
- [Storage notes](#storage-notes)

---

## Primitive types and constraints

The following annotated types appear across multiple models. They are defined once in
`models/schema.py` and imported elsewhere.

| Name | Python type | Constraint | Example |
|---|---|---|---|
| `NonEmptyStr` | `str` | `min_length=1`, leading/trailing whitespace stripped | `"active"` |
| `JurisdictionStr` | `str` | Regex `^[A-Z]{2}$`; USPS two-letter code including territories | `"AZ"`, `"DC"`, `"GU"` |
| `Sha256Str` | `str` | Regex `^[0-9a-f]{64}$`; lowercase hex | `"a3f1..."` |
| `HttpUrlStr` | `str` | `min_length=1`; must start with `http://` or `https://` | `"https://azcourts.gov/..."` |

All models inherit `str_strip_whitespace=True` — whitespace is stripped from every string
field on validation.

---

## Enum vocabularies

Enums are defined in `models/enums.py` and stored as their string value in DuckDB
(`VARCHAR`). There is no separate lookup table in the database.

### `ProgramType`

What kind of reform program the program row represents.

| Value | Meaning |
|---|---|
| `abs` | Alternative Business Structure — non-lawyer ownership of law firm permitted |
| `sandbox` | Regulatory sandbox — temporary UPL waiver for approved entities |
| `alp_license` | Allied legal professional license — individual practitioner license |
| `paraprofessional_pilot` | Court-supervised paraprofessional pilot (e.g. MN LP pilot) |
| `community_justice_worker` | Community-based navigators authorized by court rule |
| `document_preparer` | Licensed document-preparation services (e.g. CA LDA) |

### `ProgramStatus`

Operational state of the program itself, not individual providers.

| Value | Meaning |
|---|---|
| `active` | Program is accepting and licensing providers |
| `sunset` | Program has formally ended; no new authorizations (e.g. WA LLLT, effective 2021-07-31) |
| `proposed` | Authorizing legislation enacted but implementing rules not yet adopted (e.g. TX ALP as of 2026) |
| `paused` | Program has been temporarily suspended or frozen |

**Source:** `resolve/program_status.py` surfaces legislative signals that may update this
field. For court-rule programs (AZ ABS, AZ LP, CO LLP, MN LP, WA LLLT) the status is set
from a `status_override` in the resolver config and does not depend on the legislative API.

### `ProviderType`

Whether the provider row represents an organization or a licensed individual.

| Value | Meaning |
|---|---|
| `entity` | Corporate or organizational entity (ABS licensee, sandbox applicant) |
| `individual` | Individual practitioner (ALP, LPP, LLLT, etc.) |

### `CurrentStatus`

Point-in-time authorization state of a provider. **Computed** from the event log — never
scraped directly.

| Value | Meaning |
|---|---|
| `active` | Appears on the current roster; no revocation or suspension event |
| `exited` | No longer on the roster and no revocation/suspension event; reason unknown |
| `suspended` | Regulatory action suspended the authorization; may be reinstated |
| `revoked` | Authorization formally revoked; terminal |
| `unknown` | No events yet (bootstrap state); or first snapshot only |

See `docs/methodology.md §4` for the full computation rules.

### `EventType`

What kind of change a `provider_status_event` row documents.

| Value | Meaning |
|---|---|
| `authorized` | Provider first appeared on a roster snapshot (entry) |
| `status_change` | Explicit status change observed between two consecutive snapshots |
| `disappeared_from_roster` | Provider was on the previous snapshot but absent from the current one |
| `disciplined` | Regulatory discipline observed (not yet populated from discipline sources) |
| `reinstated` | Provider restored to active status after suspension |

**Critical distinction:** `disappeared_from_roster` is an observation — the provider is
absent from the public roster. It does **not** mean the provider was revoked. Revocation
requires a separate regulatory action documented in a `disciplined` or `revoked` event.
Analysts who want to treat disappearances as exits must make that assumption explicit and
document it. See `docs/methodology.md §4c`.

### `AliasSource`

Where an alias name was found.

| Value | Meaning |
|---|---|
| `roster` | Appeared on the official regulatory roster |
| `website` | Found on provider's public website |
| `litigation` | Found in court filing (v3 litigation layer) |
| `manual` | Manually entered by a researcher |

### `MediaType`

Raw file format of a `source_snapshot` capture.

| Value | Meaning |
|---|---|
| `html` | HTML document (static or headless-rendered) |
| `pdf` | PDF document |
| `json` | JSON API response |
| `xlsx` | Excel spreadsheet |

### `MatchMethod`

How a `crosswalk_courtlistener` row was produced.

| Value | Meaning |
|---|---|
| `exact` | Legal name matched exactly after normalization |
| `fuzzy` | Fuzzy name match via `rapidfuzz` token-set ratio |
| `manual` | Human-verified match; row is immutable |

---

## Tables

Tables are created in FK-dependency order: `program` → `source_snapshot` → `provider`
→ `provider_status_event`, `provider_alias`, `crosswalk_courtlistener`.

---

### `program`

One row per reform program. Programs are seeded via `scripts/seed_programs.py` and
updated by `resolve/program_status.py` when the legislative resolver surfaces changes.

**Primary key:** `program_id`

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `program_id` | `NonEmptyStr` | `VARCHAR PK` | no | Stable opaque ID, e.g. `prog_az_abs`. Never changes. |
| `jurisdiction` | `JurisdictionStr` | `VARCHAR` | no | Two-letter USPS code, uppercase. `CHECK (length(jurisdiction) = 2)`. |
| `program_name` | `NonEmptyStr` | `VARCHAR` | no | Human-readable full name. |
| `program_type` | `ProgramType` | `VARCHAR` | no | See enum table above. |
| `regulator` | `NonEmptyStr` | `VARCHAR` | no | Regulating body name, e.g. `"Arizona Supreme Court"`. |
| `regulator_url` | `HttpUrlStr` | `VARCHAR` | no | Landing page, not a deep link to any specific document. |
| `authorizing_rule` | `NonEmptyStr` | `VARCHAR` | no | Canonical citation, e.g. `"ACJA §7-210"`, `"APR 28"`, `"Utah Code §78A-9-101"`. |
| `launch_date` | `date \| None` | `DATE` | yes | Date the program first issued authorizations. `NULL` if unknown or not yet launched. |
| `program_status` | `ProgramStatus` | `VARCHAR` | no | See enum table above. Maintained by `resolve/program_status.py`. |
| `sunset_date` | `date \| None` | `DATE` | yes | For sunset/proposed programs: the effective end date or anticipated launch date. |
| `allows_nonlawyer_ownership` | `bool` | `BOOLEAN` | no | True if non-lawyers may own equity in a licensed entity. Rule 5.4 relief. |
| `allows_upl_waiver` | `bool` | `BOOLEAN` | no | True if non-lawyer providers may engage in acts that would otherwise constitute UPL. Distinguishes Utah (ABS + UPL) from Arizona (ABS only). |
| `allows_software_provider` | `bool` | `BOOLEAN` | no | True if software platforms may be licensed as providers. Key for AI/LLM-adjacent analysis. |
| `source_url` | `HttpUrlStr` | `VARCHAR` | no | URL of the source document that produced this row. |
| `retrieved_at` | `datetime` | `TIMESTAMPTZ` | no | UTC timestamp of the scrape that produced this row. |
| `scraper_version` | `NonEmptyStr` | `VARCHAR` | no | Semantic version of the scraper that produced this row. |

---

### `source_snapshot`

One row per unique raw capture. Snapshots are **immutable** — the same `snapshot_id`
always refers to the same bytes on disk. The snapshot is the provenance document; all
derived tables reference it via FK.

**Primary key:** `snapshot_id`
**FK:** `program_id` → `program(program_id)`

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `snapshot_id` | `NonEmptyStr` | `VARCHAR PK` | no | `snap_<sha256[:16]>`. Content-addressed; deterministic from file bytes. |
| `program_id` | `NonEmptyStr` | `VARCHAR` | no | FK → `program`. |
| `source_url` | `HttpUrlStr` | `VARCHAR` | no | Canonical URL that was fetched. May differ from the Wayback wrapper URL. |
| `retrieved_at` | `datetime` | `TIMESTAMPTZ` | no | UTC fetch time. For Wayback captures, this is the **Wayback archive timestamp**, not the time the CDX query ran. |
| `content_sha256` | `Sha256Str` | `VARCHAR` | no | SHA-256 of the raw bytes, lowercase hex. Used for deduplication. `CHECK (length(content_sha256) = 64)`. |
| `storage_path` | `NonEmptyStr` | `VARCHAR` | no | Relative path from the repo root to the blob file in `data/raw/`. |
| `media_type` | `MediaType` | `VARCHAR` | no | See enum table. Determines the parser invoked. |
| `scraper_version` | `NonEmptyStr` | `VARCHAR` | no | For Wayback captures, the version is `wayback-{version}`. |

**Deduplication note:** `ON CONFLICT (snapshot_id) DO NOTHING` — if the same content hash
is ingested twice, the second write is silently dropped. This is safe because
`snapshot_id` is derived from `content_sha256`; identical IDs guarantee identical bytes.

---

### `provider`

One row per authorized entity or individual. Slowly-changing dimensions (status history)
live in `provider_status_event`, not here. This table holds the latest observed state.

**Primary key:** `provider_id`
**Soft FK (Python-enforced):** `program_id` → `program(program_id)`.
`first_seen_snapshot_id`, `last_seen_snapshot_id` → `source_snapshot(snapshot_id)`.

> **DuckDB constraint note:** FK declarations are intentionally omitted from `provider`.
> DuckDB 1.5.x enforces FKs during `ON CONFLICT DO UPDATE` (delete+reinsert path), which
> spuriously triggers when child rows in `provider_status_event` reference the provider
> being updated. FK integrity is enforced at the Python layer via `_require_program()` and
> `_require_snapshot()` guards in `pipeline/db.py`.

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `provider_id` | `NonEmptyStr` | `VARCHAR PK` | no | Deterministic content-addressed ID. See `docs/methodology.md §7`. |
| `program_id` | `NonEmptyStr` | `VARCHAR` | no | Soft FK → `program`. Enforced in Python. |
| `provider_type` | `ProviderType` | `VARCHAR` | no | `entity` or `individual`. |
| `legal_name` | `NonEmptyStr` | `VARCHAR` | no | Name exactly as it appears on the regulatory roster. |
| `normalized_name` | `NonEmptyStr` | `VARCHAR` | no | Deterministic normalized form for entity resolution. See `docs/methodology.md §3`. |
| `jurisdiction` | `JurisdictionStr` | `VARCHAR` | no | USPS code; `CHECK (length(jurisdiction) = 2)`. |
| `authorization_date` | `date \| None` | `DATE` | yes | First date the provider was authorized, from the roster if available. |
| `current_status` | `CurrentStatus` | `VARCHAR` | no | **Computed** from `provider_status_event` via `_recompute_statuses()`. Default `unknown`. Never scraped directly. |
| `practice_areas_raw` | `list[str]` | `VARCHAR[]` | yes | Practice areas in the source's own terminology. E.g. `["family law", "landlord-tenant"]`. Stored as a native DuckDB array; not updated on re-scrape (DuckDB 1.5.x `VARCHAR[]` bug — see note). Published CSV: JSON-array string (`""` if empty); published Parquet: native list. |
| `practice_areas_list` | `list[str] \| None` | `VARCHAR[]` | yes | JusticeBench LIST taxonomy codes. `NULL` until the mapping step runs. Not updated on re-scrape for the same reason. Same CSV/Parquet representation split as `practice_areas_raw`. |
| `ownership_structure` | `dict \| None` | `VARCHAR` | yes | Entities only: JSON blob recording lawyer/non-lawyer ownership percentages and capital source when the source publishes them. |
| `uses_technology` | `bool \| None` | `BOOLEAN` | yes | `True` if the provider's application describes technology-assisted service delivery. `NULL` if unknown. |
| `uses_ai` | `bool \| None` | `BOOLEAN` | yes | `True` if the provider describes AI/LLM use. `NULL` if unknown. The column that connects to the UPL/AI policy question. |
| `website` | `HttpUrlStr \| None` | `VARCHAR` | yes | Provider's public website; used in v3 entity matching. |
| `first_seen_snapshot_id` | `str \| None` | `VARCHAR` | yes | Soft FK → `source_snapshot`. Set on first insert; preserved on subsequent upserts via `COALESCE`. Earliest confirmed observation of this provider. |
| `last_seen_snapshot_id` | `str \| None` | `VARCHAR` | yes | Soft FK → `source_snapshot`. Updated to the latest snapshot each time the provider appears. For Wayback-only providers, this is the most recent Wayback capture, not the own-scrape snapshot. |
| `source_url` | `HttpUrlStr` | `VARCHAR` | no | URL of the snapshot that last updated this row. |
| `retrieved_at` | `datetime` | `TIMESTAMPTZ` | no | `retrieved_at` of the snapshot that last updated this row. |
| `scraper_version` | `NonEmptyStr` | `VARCHAR` | no | Scraper version that last wrote this row. |

**`practice_areas_raw` / `practice_areas_list` immutability note:** These `VARCHAR[]`
columns are set on first insert and excluded from `ON CONFLICT DO UPDATE`. DuckDB 1.5.x
triggers the same delete+reinsert path for `VARCHAR[]` updates on FK-referenced rows,
producing a spurious constraint violation. A dedicated update step is required to refresh
these fields when a re-scrape changes them. In practice the fields are stable.

---

### `provider_status_event`

The longitudinal core. Every row documents a discrete change in a provider's
authorization status. All events are **generated by diffing successive snapshots** via
`pipeline/diff.py` — they are never manually authored.

**Primary key:** `event_id`
**FK:** `provider_id` → `provider(provider_id)`, `source_snapshot_id` → `source_snapshot(snapshot_id)`

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `event_id` | `NonEmptyStr` | `VARCHAR PK` | no | Deterministic: `"evt_" + sha256("{provider_id}:{snapshot_id}:{event_type}")[:24]`. Idempotent — re-running the same diff never creates duplicate rows. |
| `provider_id` | `NonEmptyStr` | `VARCHAR` | no | FK → `provider`. |
| `event_date` | `date` | `DATE` | no | Date of the new snapshot, i.e. when the change was **first observed**, not necessarily when it occurred on the ground. |
| `event_type` | `EventType` | `VARCHAR` | no | See enum table above. |
| `new_status` | `CurrentStatus` | `VARCHAR` | no | The provider's `current_status` after this event. Used by `_recompute_statuses()` to update `provider.current_status`. |
| `detail` | `str \| None` | `VARCHAR` | yes | Free text. For `status_change` events: `"{old_status} → {new_status}"`. For `disciplined`/`reinstated` events: description from the discipline source. |
| `source_snapshot_id` | `NonEmptyStr` | `VARCHAR` | no | FK → `source_snapshot`. The specific capture that revealed this change. |
| `source_url` | `HttpUrlStr` | `VARCHAR` | no | Provenance. |
| `retrieved_at` | `datetime` | `TIMESTAMPTZ` | no | Provenance. |
| `scraper_version` | `NonEmptyStr` | `VARCHAR` | no | Provenance. |

**`disappeared_from_roster` vs. `revoked`:** `disappeared_from_roster` records a
factual observation — the provider was absent from the roster in the new snapshot. It
does not imply any legal action. The `new_status` for this event is always `exited`.
A formal `revoked` status requires a separate `disciplined` event sourced from the
regulator's discipline records. Analysts who want to treat disappearances as revocations
must make that assumption explicit and document it.

**Idempotency:** `event_id` is a deterministic hash of `(provider_id, snapshot_id, event_type)`.
Re-running `diff_snapshots()` on the same pair of snapshots will attempt to insert the
same event IDs, which the `ON CONFLICT DO UPDATE` resolves as a logical no-op.

---

### `provider_alias`

Alternative names for a provider. Seeded from roster data and supplemented in v3 from
litigation records. Used as input to entity resolution.

**Primary key:** `(provider_id, alias_name)`
**FK:** `provider_id` → `provider(provider_id)`

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `provider_id` | `NonEmptyStr` | `VARCHAR` | no | FK → `provider`. |
| `alias_name` | `NonEmptyStr` | `VARCHAR` | no | DBA name, former legal name, or brand name. |
| `alias_source` | `AliasSource` | `VARCHAR` | no | See enum table above. |
| `source_url` | `HttpUrlStr` | `VARCHAR` | no | Provenance. |
| `retrieved_at` | `datetime` | `TIMESTAMPTZ` | no | Provenance. |
| `scraper_version` | `NonEmptyStr` | `VARCHAR` | no | Provenance. |

---

### `crosswalk_courtlistener` _(v3 stub)_

Links `provider` rows to CourtListener dockets and party records. Not populated in v1.
Schema defined now for forward compatibility — v1 scrapers must store `legal_name` in a
form compatible with the normalization described in `docs/methodology.md §3`.

**Primary key:** `(provider_id, cl_docket_id)`
**FK:** `provider_id` → `provider(provider_id)`

| Field | Python type | DB type | Nullable | Notes |
|---|---|---|---|---|
| `provider_id` | `NonEmptyStr` | `VARCHAR` | no | FK → `provider`. |
| `cl_docket_id` | `int` | `BIGINT` | no | CourtListener docket ID. |
| `cl_party_id` | `int \| None` | `BIGINT` | yes | CourtListener party ID if resolved to a specific party record. |
| `match_score` | `float` | `DOUBLE` | no | Composite match confidence, 0.0–1.0. `CHECK (match_score >= 0.0 AND match_score <= 1.0)`. |
| `match_method` | `MatchMethod` | `VARCHAR` | no | See enum table above. |
| `verified` | `bool` | `BOOLEAN` | no | `True` if a human has confirmed the match. Default `False`. |
| `reviewer` | `str \| None` | `VARCHAR` | yes | Identifier of the reviewer who set `verified=True`. |
| `reviewed_at` | `datetime \| None` | `TIMESTAMPTZ` | yes | When the verification was recorded. |

**Immutability rule:** Rows with `verified=True` are **never overwritten** by automated
pipeline runs. `RegistryStore.upsert_crosswalk()` silently returns without writing if the
existing row has `verified=True`. Human judgment is the moat; protect it.

---

## Provenance fields

Three provenance fields appear on every row derived from a scraped source. They form the
traceable chain from raw capture to derived table.

| Field | Type | Meaning |
|---|---|---|
| `source_url` | `HttpUrlStr` | Canonical URL of the page/document that produced this row |
| `retrieved_at` | `datetime (UTC)` | Timestamp of the raw fetch. For Wayback captures, the **archive timestamp** (not the time the backfill script ran) |
| `scraper_version` | `NonEmptyStr` | Semver string, e.g. `"0.1.0"`. For Wayback captures: `"wayback-0.1.0"` |

These fields are stamped onto every `Provider` row by `BaseScraper._stamp()` after
`parse()` returns, so individual scrapers never have to copy them manually.

---

## Storage notes

**Dev store:** DuckDB `data/db/registry.duckdb`. Schema initialized via
`RegistryStore.init_schema()` (idempotent `CREATE TABLE IF NOT EXISTS`).

**Release store:** Flat CSV + Parquet in `data/release/`, packaged with a Frictionless
`datapackage.json`. Never hand-edit files in `data/release/`.

**Raw blobs:** `data/raw/<program_id>/<sha256[:2]>/<sha256>.{html,pdf,...}`. Keyed by
content hash; one file per unique content regardless of how many times it was fetched.

**Array columns:** `practice_areas_raw`, `practice_areas_list` are DuckDB `VARCHAR[]`
native arrays in the dev DB and round-trip cleanly through polars/Parquet as native lists
in the **published Parquet**. The **published CSV** cannot represent nested types, so
`pipeline/export.py` serializes each list as a JSON-array string (e.g. `["family law"]`);
an empty or `NULL` list is written as `""`. Parquet and CSV therefore differ in
representation for these two columns only — always prefer Parquet for programmatic reuse.
Because of a DuckDB 1.5.x bug, the underlying `VARCHAR[]` columns are set on first insert
and excluded from `ON CONFLICT DO UPDATE`. See `pipeline/db.py:upsert_provider()` docstring
for details.

**Dictionary columns:** `ownership_structure` is stored as a `VARCHAR` JSON string
(serialized via `json.dumps`). Parse with `json.loads` when reading.
