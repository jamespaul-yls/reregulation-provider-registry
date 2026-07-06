# CLAUDE.md — Reregulation Provider Registry

You are helping build an open, reproducible, longitudinal dataset of every authorized
provider (entity or individual) operating under a U.S. legal-services **reregulation**
program: Alternative Business Structures (ABS), regulatory sandboxes, and allied-legal-
professional / paraprofessional licenses. The full design lives in
`reregulation-registry-v1-spec.md` in this repo — read it before any architectural work.

This dataset will be used to argue a **contested empirical question** (does loosening UPL
harm consumers?). Reproducibility and provenance are the product, not a nicety. Behave
accordingly.

---

## Golden rules (never violate)

1. **Provenance on every derived row.** Every record carries `source_url`, `retrieved_at`,
   `scraper_version`. No field without a traceable origin.
2. **Raw captures are immutable.** Before parsing anything, persist the raw HTML/PDF/JSON
   exactly as fetched, content-hashed (`sha256`). All tables are *derived from* snapshots
   and must be fully re-derivable from them. Never parse a live response without snapshotting it first.
3. **Longitudinal by diffing snapshots — never trust a scraped "status" field.** Entries and
   exits are *computed* by comparing successive roster snapshots. **Documented exception:**
   a program's *first* snapshot has no prior snapshot to diff against, so its status is
   seeded from the source's own status column at insert time (`docs/methodology.md §4b`).
   This is real and heavily used — as of v1.0.0 it's the origin of most non-`active` status
   values in the dataset, not just an edge case — so treat it as part of this rule, not an
   exception nobody needs to know about: any doc or column description claiming
   `current_status` is "never scraped directly" must carry this caveat, and a future
   snapshot should still supersede a bootstrap-seeded value via a real diff the moment one
   is available.
4. **Neutral naming.** Name columns for the proxy they measure (`formal_complaint_count`,
   not `harm`). We build the spine others test harm definitions against.
5. **Three-layer separation:** `raw/` (immutable snapshots) → dev DB (normalized) →
   `release/` (published flat files). Never hand-edit anything in `release/`.
6. **A statistic without a documented method is a bug.** Every inference (temporal windows,
   status logic, reconciliation) is written down in `docs/methodology.md`.

---

## Tech stack (pin these)

- Python 3.12. Dependency mgmt with `uv`.
- Fetch: `httpx` (static + API), `playwright` (JS directories).
- Parse: `selectolax` (HTML), `pymupdf` + `pdfplumber` (PDF tables).
- Validate: `pydantic` v2 — the models ARE the schema; fail loudly on drift.
- Transform: `polars`. Dev store: `duckdb`. Raw store: local disk keyed by `content_sha256`.
- Entity resolution (v3): `rapidfuzz`, then `recordlinkage` if warranted.
- Lint/format: `ruff`. Tests: `pytest`. CI: GitHub Actions.
- Publish: CSV + Parquet + Frictionless `datapackage.json`.

---

## Repo layout

```
reregulation-registry/
  scrapers/      # one module per source; all extend BaseScraper (fetch→snapshot→parse)
  models/        # pydantic schema + enums.py (single source of truth for enums)
  resolve/       # name normalization + CourtListener matching (v3)
  pipeline/      # snapshot diffing → status_events; loaders; exporters
  data/
    raw/         # immutable snapshots (git-lfs or external store)
    db/          # dev duckdb
    release/     # published CSV/Parquet/datapackage — NEVER hand-edit
  docs/          # data_dictionary.md, methodology.md, per-source notes
  validation/    # reconciliation + sample-accuracy logs (see "Quality bars")
  tests/         # parser regression tests built from saved snapshot fixtures
```

---

## Schema summary (full detail in the spec, §1)

Tables: `program`, `provider`, `provider_status_event`, `provider_alias`,
`source_snapshot`, and a v3 stub `crosswalk_courtlistener`.

Key enums (define once in `models/enums.py`):
- `program_type`: abs | sandbox | alp_license | paraprofessional_pilot | community_justice_worker | document_preparer
- `provider_type`: entity | individual
- `current_status`: active | exited | suspended | revoked | unknown
- `event_type`: authorized | status_change | disappeared_from_roster | disciplined | reinstated

`provider.current_status` is **computed** from `provider_status_event`, never scraped directly.
`disappeared_from_roster` ≠ `revoked` — dropping off a roster is an observation, not a legal
conclusion. Keep them distinct.

Reference vocab: `jurisdiction` = USPS + FIPS crosswalk; `practice_areas_list` = JusticeBench
LIST taxonomy codes (keep `practice_areas_raw` verbatim alongside).

---

## Coding conventions

- Full type hints; pydantic models validate every row before it touches the DB.
- One scraper module per source, all extending `BaseScraper`. Fetch strategy (static / headless
  / pdf) is pluggable; the snapshot contract is identical across all of them.
- Every parser has a regression test that runs against a **saved snapshot fixture**, asserting an
  exact expected row set. A scraper without a fixture test is not done.
- Small commits, one source/feature each. Conventional-commit messages.
- No network calls in tests — tests run against fixtures only.

---

## Scraping rules

- These are public government records (strong footing), but still: descriptive User-Agent,
  honor `robots.txt`/ToS, rate-limit (default ≥1s between requests), cache, work from snapshots.
- **Never scrape PACER directly.** The litigation layer (v3) uses RECAP/CourtListener only.
- For bar discipline lookups, prefer published reports/exports over hammering a search UI; check ToS.

---

## Quality bars — self-check every data-producing step

For any step that emits data, report all three before declaring it done:

- **Completion:** artifact exists and runs clean. `ruff check` and `pytest` pass; the pipeline
  produces output without error; CI green.
- **Comprehensiveness (coverage/recall):** did we capture everything the source holds? Reconcile
  the parsed row count against the source's *own* stated total / pagination. Log the result in
  `validation/<source>.md` as `parsed N / source_total M (coverage %)`. Flag any gap.
- **Accuracy (precision):** are values correct? Pull a stratified random sample (≥15 rows or 10%,
  whichever larger), hand-verify each field against the live/archived source, and log a field-level
  error rate. **Target: zero errors on identity fields** (legal_name, jurisdiction, authorization_date,
  current_status); investigate any nonzero. Record in `validation/<source>.md` with date + sample IDs.

The `validation/` logs are part of the dataset's credibility — treat them as deliverables, not notes.

---

## Working agreement with Claude Code

- For any step beyond a trivial edit: **propose a short plan and wait for my OK** before writing code.
- Work **one playbook step at a time.** Do not jump ahead to later milestones.
- After running a scraper or pipeline step, **show me the actual output** (row counts, a sample,
  the reconciliation number) — don't just report success.
- Always write/extend the fixture-based test in the same step that adds a parser.
- If a source's structure differs from the spec's assumption, **stop and tell me** rather than
  guessing — coverage/accuracy decisions are mine to make.

---

## Key sources (verify live URLs before coding each)

- Utah sandbox: Office of Legal Services Innovation (`utahinnovationoffice.org`) — roster [HTML] + activity reports [PDF]
- Arizona ABS + LP: AZ Supreme Court / `azcourts.gov`; discipline via State Bar of Arizona
- Colorado LLP: Office of Attorney Regulation Counsel (`coloradolegalregulation.com`) [headless]
- Oregon: Oregon State Bar member directory [headless]
- Minnesota LP pilot: MN Judicial Branch / Standing Committee reports [PDF]
- Washington LLLT (sunset): WSBA legacy directory + Internet Archive Wayback [archive backfill]
- Program-status layer: Open States v3 (`v3.openstates.org`, X-API-KEY) or LegiScan (free tier)
- Litigation (v3): CourtListener REST v4 + bulk data — never PACER directly
