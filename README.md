# U.S. Legal Services Reregulation Provider Registry

An open, reproducible, longitudinal dataset of every authorized provider operating under
a U.S. legal-services reregulation program: Alternative Business Structures (ABS),
regulatory sandboxes, and allied-legal-professional / paraprofessional licenses.

**v1.0.2 · 10 programs · 7 states · 708 providers · 19 roster snapshots**

**This dataset publishes only public-record information.** Every provider record is drawn
from public regulatory rosters and official program-status pages published by each
program's own regulator — not from private, non-public, or interaction-derived data of any
kind. See `docs/methodology.md` (public-records commitment) for the full substantiation,
field-by-field.

## Purpose

This dataset provides the empirical spine for research on whether loosening unauthorized
practice of law (UPL) restrictions harms consumers. It tracks *who was authorized, when,
and for how long* — not harm outcomes, which require additional linkage. Column names are
deliberately neutral proxies (`formal_complaint_count`, not `harm`). The intent is a
resource others can test different harm definitions against.

Reproducibility and provenance are the product. Every row carries `source_url`,
`retrieved_at`, and `scraper_version`. Raw HTML/PDF captures are content-hashed and stored
in `data/raw/`; all derived tables are fully re-derivable from them.

## Coverage (v1.0.2)

| Program | State | Type | Providers (total) | Active | Snapshots | Earliest snapshot |
|---|---|---|---:|---:|---:|---|
| Arizona ABS | AZ | abs | 203 | 160 | 2 | 2024-11-08 |
| Arizona LP | AZ | alp_license | 120 | 113 | 1 | 2026-06-29 |
| Colorado LLP | CO | alp_license | 126 | 126 | 1 | 2026-06-29 |
| Minnesota LP pilot | MN | alp_license | 42 | 42 | 1 | 2026-06-29 |
| Utah LPP | UT | alp_license | 52 | 52 | 1 | 2026-06-29 |
| Utah Sandbox | UT | sandbox | 70 | 8 | 9 | 2025-06-12 |
| Washington LLLT | WA | alp_license | 95 | 68 | 1 | 2026-06-29 |
| California LDA | CA | document_preparer | 0† | — | 1 | 2026-06-29 |
| Texas ALP | TX | alp_license | 0† | — | 1 | 2026-07-04 |
| WA Entity Pilot | WA | sandbox | 0† | — | 1 | 2026-07-04 |
| **Total** | | | **708** | **569** | **19** | |

† Program correctly zero-provider: CA LDA is county-fragmented with no statewide roster;
TX ALP's licensing category is not yet effective; WA Entity Pilot has 4 applicants but none
authorized yet. Each program's evidentiary source page is still snapshotted for
provenance. See `docs/sampling_frame.md §3` for the full reasoning per
program — none of these zeros are "not yet checked."

**D.C. Rule 5.4(b)** was modeled as a fourth zero-provider program (`prog_dc_rule54`)
through v1.0.1 and removed 2026-07-06: it's a self-executing ethics rule with no
application or registration step, so unlike the three zeros above there is no roster
that could ever come to exist for it. See `docs/sampling_frame.md §4` and
`validation/dc_rule54.md` for the full reasoning, and `CHANGELOG.md [1.0.2]` for the
removal itself.

`current_status` is **computed** from the `provider_status_event` log, never scraped
directly. `disappeared_from_roster` ≠ `revoked` — see `docs/methodology.md §4c`.

## Data files

All files are in `data/release/`. The Frictionless Data Package manifest with full schema,
constraints, and foreign keys is at `data/release/datapackage.json`.

| File | Rows | Description |
|---|---:|---|
| `program.csv` / `.parquet` | 10 | One row per reregulation program |
| `source_snapshot.csv` / `.parquet` | 19 | Immutable raw-capture provenance records |
| `provider.csv` / `.parquet` | 708 | One row per unique authorized provider |
| `provider_status_event.csv` / `.parquet` | 748 | Entry/exit/discipline events |
| `provider_alias.csv` / `.parquet` | 0 | DBA / former names (populated in v1.1) |
| `crosswalk_courtlistener.csv` / `.parquet` | 0 | Litigation linkage (v3 milestone) |

## Quick start

### Python — Polars

```python
import polars as pl

providers = pl.read_parquet("data/release/provider.parquet")
events    = pl.read_parquet("data/release/provider_status_event.parquet")

# Active providers per program
providers.group_by("program_id").agg(
    pl.col("provider_id").count().alias("total"),
    (pl.col("current_status") == "active").sum().alias("active"),
).sort("program_id")
```

### Python — Pandas

```python
import pandas as pd

providers = pd.read_csv(
    "data/release/provider.csv",
    parse_dates=["authorization_date"],
    dtype={"jurisdiction": "category", "current_status": "category"},
)

# Providers authorized each year
providers["auth_year"] = pd.to_datetime(
    providers["authorization_date"], errors="coerce"
).dt.year
providers.groupby(["program_id", "auth_year"]).size()
```

### DuckDB

```sql
INSTALL httpfs; -- if reading from a remote URL
ATTACH 'data/db/registry.duckdb' AS reg (READ_ONLY);

SELECT p.program_name, count(*) AS n_providers
FROM   reg.provider pv
JOIN   reg.program p USING (program_id)
WHERE  pv.current_status = 'active'
GROUP  BY 1
ORDER  BY 2 DESC;
```

### R

```r
library(arrow)
library(dplyr)

providers <- read_parquet("data/release/provider.parquet")
events    <- read_parquet("data/release/provider_status_event.parquet")

# Entry/exit counts by month
events |>
  mutate(month = lubridate::floor_date(as.Date(event_date), "month")) |>
  count(program_id, month, event_type) |>
  arrange(program_id, month)
```

## Documentation

- `docs/data_dictionary.md` — field-by-field schema with types, constraints, and notes
- `docs/methodology.md` — all inferences documented: temporal windows, status logic,
  diff algorithm, Wayback handling, entity resolution, completeness audit, and
  limitations (§12), including an explicit "what v1 does NOT include" list (§12i)
- `docs/sampling_frame.md` — the frame: which programs are in scope, why three are
  correctly zero-provider, territory scope, and the resolved completeness-audit gap ledger
- `docs/data_note.md` — a short plain-language summary for non-technical readers
- `docs/v2_readiness.md` — forward-compatibility hooks for the planned outcomes layer
- `validation/summary.md` — consolidated coverage/accuracy/trajectory/audit overview
- `validation/<source>.md` — per-source coverage and accuracy logs (reconciled row counts
  vs source totals; stratified hand-verification samples)
- `validation/longitudinal_validity.md` — Wayback-backed trajectory reconstruction detail
- `docs/ai_use.md` — what AI tooling was and wasn't used for, and the controls (fixture
  tests, validation logs, adversarial review) that keep the process auditable
- `CHANGELOG.md` — release history
- `reregulation-registry-v1-spec.md` — full design specification

## Development process

Scrapers, pipeline, and documentation were built with AI-assisted coding (Claude Code)
against specifications and rules I authored, with fixture-based tests, per-source
coverage/accuracy validation, and adversarial review passes as checks — not AI-asserted
correctness. See `docs/ai_use.md` for what that did and didn't involve.

## How to cite

```
Paul, James. (2026). U.S. Legal Services Reregulation Provider Registry (v1.0.2)
[Data set]. Yale Law School. https://github.com/jamespaul-yls/reregulation-provider-registry
```

BibTeX:
```bibtex
@dataset{paul2026reregulation,
  author    = {Paul, James},
  title     = {U.S. Legal Services Reregulation Provider Registry},
  year      = {2026},
  version   = {1.0.2},
  publisher = {Yale Law School},
  url       = {https://github.com/jamespaul-yls/reregulation-provider-registry},
}
```

## Limitations

The seven most important limitations are documented in `docs/methodology.md §12`. The
principal ones:

1. **Roster lag.** Regulators update rosters on unknown schedules; a provider may have
   exited weeks before the snapshot that records their absence.
2. **Observation ≠ ground truth.** `disappeared_from_roster` is an observation; only
   the regulator knows if it reflects revocation, voluntary exit, or a website error.
3. **Single initial snapshots.** Most programs have one snapshot (v1.0.2). Longitudinal
   entry/exit tracking becomes meaningful only as additional snapshots accumulate.
4. **Practice area sparsity.** Most rosters do not publish practice areas. The
   `practice_areas_raw` and `practice_areas_list` columns are mostly empty in v1.0.2.
5. **Scope boundary.** This dataset covers reregulation programs only — not the full
   population of legal service providers. Do not use the denominator from this dataset
   to compute market-share statistics.

## License

**Data** (`data/release/`) — Creative Commons Attribution 4.0 International (CC BY 4.0).
See `data/release/LICENSE`.

**Code** (everything else) — MIT License. See `LICENSE`.

If you use this dataset in published research, please cite as above and note the snapshot
dates, since the longitudinal panel is still early.
