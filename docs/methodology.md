# Methodology — Reregulation Provider Registry

_A statistic without a documented method is a bug._ Every inference in this dataset
is written here. Version this document alongside the code.

**Version:** 1 · **Last updated:** 2026-07-04

---

## Contents

1. [Scope](#1-scope)
2. [Source selection and priority](#2-source-selection-and-priority)
3. [Name normalization](#3-name-normalization)
4. [Status inference (`current_status`)](#4-status-inference-current_status)
5. [Entry and exit detection (snapshot diffing)](#5-entry-and-exit-detection-snapshot-diffing)
6. [Temporal windows](#6-temporal-windows)
7. [Provider ID generation](#7-provider-id-generation)
8. [Wayback Machine backfill](#8-wayback-machine-backfill)
9. [Program status resolution (legislative layer)](#9-program-status-resolution-legislative-layer)
10. [Reconciliation and quality checks](#10-reconciliation-and-quality-checks)
11. [Entity resolution design (v3 stub)](#11-entity-resolution-design-v3-stub)
12. [Candid limitations](#12-candid-limitations)

---

## 1. Scope

This registry covers every provider — entity or individual — authorized to operate under a
U.S. legal-services **reregulation** program: Alternative Business Structures (ABS),
regulatory sandboxes with UPL relief, and allied-legal-professional / paraprofessional
licenses. It does **not** cover:

- Traditional law firms or traditional bar licensees.
- Unlicensed document preparers, except where a jurisdiction has created a document-preparer
  license class (e.g., California LDA) with formal regulatory oversight.
- Passive "law firm practice" rule waivers with no accompanying roster (excluded because
  there is no provider to track).

The registry is deliberately neutral on the policy question it is designed to inform.
Column names measure proxies (`formal_complaint_count`, not `harm`); analysts apply their
own harm definitions to the spine.

**Frame document:** `docs/sampling_frame.md` is the authoritative statement of exactly
which 11 programs are in scope for v1, why four of them are correctly zero-provider, the
territory-scope decision, the one candidate program researched and deferred with no
`program` row at all (§3a), and the disposition of every residual gap surfaced by the
completeness audit (§10e). This section states the scope in prose; `sampling_frame.md`
states it as an enumerated, reconciled list.

---

## 2. Source selection and priority

For each program, the primary source is the **official regulatory roster**. Where multiple
sources exist for the same attribute, the priority order is:

> Official regulatory roster › official activity/annual report › bar/court press release ›
> third-party media › manual researcher note

Sources are never combined into a single row without documenting which source populated each
field. Each row carries `source_url` pointing to the specific document used.

### Source types in use

| Tag | Description |
|---|---|
| `[S]` | Static HTML (fetched via `httpx`; `StaticFetcher`) |
| `[P]` | PDF document (parsed via `pymupdf`/`pdfplumber`; `PdfFetcher`) |
| `[H]` | Headless browser required (JS-rendered; `HeadlessFetcher` via Playwright) |
| `[A]` | API response (JSON) |
| `[X]` | Wayback Machine archive backfill |

### Sources per program

Every program's primary source, canonical fetch strategy, and scraper module. See
`docs/sampling_frame.md §2` for the corresponding program_id / jurisdiction / status table.

| Program | Fetch strategy | Primary source | Scraper |
|---|---|---|---|
| AZ ABS | `[S]` static HTML | AZ Supreme Court ABS/LP Certification & Licensing directory | `scrapers/arizona_abs.py` |
| AZ LP | `[S]` static HTML | `azcourts.gov/cld/Legal-Paraprofessional/Directory` | `scrapers/arizona_lp.py` |
| CA LDA | `[S]` static HTML (statute page only — no roster; see §1) | `leginfo.legislature.ca.gov` Bus. & Prof. Code §6400 | `scrapers/california_lda.py` |
| CO LLP | `[P]` static PDF download | `coloradolegalregulation.com` Admitted LLP Roster PDF | `scrapers/colorado_llp.py` |
| DC Rule 5.4(b) | `[S]` static HTML (rule page only — no roster; see §1) | `dcbar.org` Rule 5.4(b) ethics rule page | `scrapers/dc_rule54.py` |
| MN LP | `[P]` static PDF download | `mncourts.gov` Roster of Approved Legal Paraprofessionals | `scrapers/minnesota_lp.py` |
| TX ALP | `[S]` static HTML (program-status page only — no roster; see §1) | `texasbar.com/paraprofessionals/` | `scrapers/texas_alp.py` |
| UT LPP | `[S]` static HTML (custom fetcher; site redirects to a vendor directory endpoint) | `licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners` | `scrapers/utah_lpp.py` |
| UT Sandbox | `[S]` static HTML roster + `[P]` PDF activity reports | `utahinnovationoffice.org/authorized-entities/` | `scrapers/utah_sandbox.py` |
| WA Entity Pilot | `[S]` static HTML — roster scraper live (`scrapers/washington_entity_pilot.py`); parses the full applicant list, loads authorized entities as providers (0 as of 2026-07-04; see §1) | `wsba.org/about-wsba/entity-regulation-pilot/applicants` | `scrapers/washington_entity_pilot.py` |
| WA LLLT | `[H]` headless (Playwright, paginated Telerik grid) + `[X]` Wayback backfill (pre-sunset history) | `mywsba.org` legacy legal directory (`LicenseType=LLLT`) | `scrapers/washington_lllt.py` |

### Known source limitations by program

| Program | Limitation |
|---|---|
| AZ ABS | Administrative approvals lag public listing by days to weeks; our count is ≤ the regulator's internal total |
| UT Sandbox | Published "active" counts in annual reports are point-in-time; our total includes all-time participants |
| WA LLLT | Paginated JS directory; Wayback captures only page 1 (~20 of 95 rows per capture) |
| CO LLP | No direct PDF export API — parse errors possible on layout changes |
| MN LP | Roster only exists inside PDFs; OCR/layout errors possible |
| CA LDA | County-level filings; highly fragmented; no statewide consolidated roster (see §1) |
| DC Rule 5.4(b) | No roster exists at all — structural, not a scraping gap (see §1) |
| WA Entity Pilot | No applicant authorized yet as of 2026-07-04 (see §1); `_AUTHORIZED_TOKENS` (token-based match) in the scraper is an educated guess since no authorized-status label has ever appeared on the live page; an unrecognized status now logs a warning instead of failing silently (`docs/audit/adversarial_review.md` S4) |
| TX ALP | No roster exists yet — program not effective as of 2026-07 (see §1) |

---

## 3. Name normalization (`normalized_name`)

**Version:** 1. Bump when the algorithm changes and migrate existing IDs that depend on it.

`normalized_name` is a deterministic transformation of `legal_name`. It is used for entity
resolution and fuzzy matching. The raw `legal_name` is always preserved verbatim; it is the
authoritative legal identity.

Steps applied in order:

1. **Unicode normalization:** NFD decomposition, then strip combining marks (removes accents:
   `Ávila` → `Avila`).
2. **Lowercase:** `"Legal Solutions LLC"` → `"legal solutions llc"`.
3. **Punctuation collapse:** replace non-word, non-space characters with a single space.
4. **Whitespace collapse:** collapse runs of whitespace.
5. **Corporate suffix removal:** drop `pllc`, `l.l.c.`, `l.l.p.`, `p.c.`, `llc`, `llp`,
   `ltd`, `inc`, `co`, `pc` as standalone tokens.
6. **Leading "the" removal:** `"the legal group"` → `"legal group"`.
7. **Ampersand normalization:** `" & "` → `" and "`.
8. **Final whitespace collapse** and strip.

Both the raw `legal_name` and the `normalized_name` are stored. A rename (e.g., a firm
rebranding) produces a new `provider_id` (because the hash input changes) with the old name
retained in `provider_alias`. See §7 for ID generation.

---

## 4. Status inference (`current_status`)

`provider.current_status` is **computed** from the full chronological `provider_status_event`
log. It is never scraped directly from a source's "Status" column.

### 4a. Computation rule

Implemented in `pipeline/diff.py:_recompute_statuses()`:

> Take the `new_status` value from the event with the **latest `event_date`** (ties broken
> by `event_id` descending) for this provider. Write it to `provider.current_status`.

This runs after every `diff_snapshots()` call, so the provider table always reflects the
most recently observed state.

### 4b. Bootstrap exception — first snapshot

When a program has exactly one snapshot in the DB (no prior snapshot to diff against), no
`disappeared_from_roster` or `status_change` events exist yet. For programs whose rosters
carry an explicit status field (e.g., AZ ABS's "Active" / "Inactive" column), that field
is used to seed `current_status` at first insert:

| Roster value | Seeded `current_status` |
|---|---|
| `Active` | `active` |
| `Inactive` | `exited` |
| anything else | `unknown` |

This bootstrapped value is the starting point. Starting with the second snapshot, all
status values are computed by diffing, potentially overwriting the bootstrap value.

For programs whose rosters carry no explicit status field (e.g., CO LLP roster lists only
active providers), all first-snapshot providers are seeded as `active`.

**How much of v1.0.0 this actually applies to — stated plainly.** This is not a rare edge
case; as of v1.0.0 it is where most `current_status` values in the release come from.
Querying `provider_status_event` by `(program_id, event_type)`: only `prog_az_abs` (36
`disappeared_from_roster` events) and `prog_ut_sandbox` (1 `disappeared_from_roster` + 3
`status_change`) have *any* event that came from an actual cross-snapshot diff. The other
five populated programs — AZ LP, CO LLP, MN LP, UT LPP, WA LLLT — have event histories
that are 100% `authorized` events, meaning every status value on every row (WA LLLT's
active/exited/suspended/unknown four-way split included) was seeded once at first insert
from the source's own status column and has never been cross-checked against a second
snapshot. This will change as more snapshots accumulate (`docs/methodology.md §12c`); until
then, `docs/data_dictionary.md`'s "computed, not scraped" framing for `current_status`
should be read with this caveat attached, not as a blanket guarantee. See
`docs/audit/adversarial_review.md` S3.

### 4c. `disappeared_from_roster` vs. `revoked` — a critical distinction

**`disappeared_from_roster`** is a factual observation: the provider appeared in snapshot
N−1 and is absent from snapshot N. The event is recorded with `new_status = exited`.

**`revoked`** is a legal conclusion: the regulator has formally revoked the authorization.
It requires a separate discipline event sourced from the regulator's formal discipline
records (bar discipline database, court order, or official announcement).

These two things are not the same:

- A provider may disappear from a roster because of an administrative lag, a website
  reorganization, a voluntary exit, or a data entry error — not because of revocation.
- A revoked provider may remain on some roster pages longer than expected due to caching or
  manual update delays.
- Analysts who treat all disappearances as revocations will overstate disciplinary activity
  and potentially misattribute voluntary exits as regulatory failures.

**Pipeline behavior:** The diff algorithm (§5) records `disappeared_from_roster` events and
sets `current_status = exited`. A separate discipline scraper (not yet implemented in v1)
must be used to record `disciplined` / `revoked` events from official discipline sources.
Do not conflate the two in any analysis without explicit disclosure.

### 4d. Temporal ambiguity

`event_date` is set to the **snapshot date** — when we observed the change — not to when
the change actually happened. A provider who exited on, say, January 5 may not appear in a
`disappeared_from_roster` event until the next scrape on February 1. All status dates in
this dataset are observation dates, not occurrence dates, unless a specific event date is
available from a discipline record.

---

## 5. Entry and exit detection (snapshot diffing)

Implemented in `pipeline/diff.py:diff_snapshots()`.

### Algorithm

Given two consecutive snapshots for the same program — snapshot N−1 (old) and snapshot N
(new):

1. Index both provider sets by `provider_id`.
2. **Additions** (in N but not N−1): emit `EventType.authorized`, `new_status = active` (or
   whatever the source seeded for that provider).
3. **Removals** (in N−1 but not N): emit `EventType.disappeared_from_roster`,
   `new_status = exited`.
4. **Status changes** (in both, but `current_status` differs): emit
   `EventType.status_change`, `new_status = <new value>`, `detail = "{old} → {new}"`.
5. Persist all events via `RegistryStore.upsert_event()`.
6. Recompute `provider.current_status` for every affected provider (§4a).

### Idempotency

`event_id = "evt_" + sha256("{provider_id}:{new_snapshot_id}:{event_type}")[:24]`

The same snapshot pair always yields the same event IDs. Re-running the diff inserts the
same rows, which `ON CONFLICT DO UPDATE` resolves as a no-op (the values are identical).
This means the diff is safe to run multiple times and will not accumulate duplicate events.

### Identity key

The identity key used to match providers across snapshots is `provider_id`, which is a
deterministic hash of `(program_id, legal_name)` (see §7). A provider who changes their
legal name will get a new `provider_id`, which appears as an exit (the old name) and an
entry (the new name). The old-name row is preserved in `provider_alias`.

If a source provides a unique license/registration number, that number is used as the
stable identifier instead of the name hash, and the hash becomes a secondary key. This is
not yet implemented in v1; all programs currently use the name hash.

### Diff chain ordering

For Wayback backfill (§8), the diff chain runs in chronological order:
capture₁ → capture₂ → capture₃ → … → capture_n → own-scrape snapshot

Each diff compares adjacent captures. The first capture in the chain has no prior
snapshot, so all providers in it receive `authorized` events dated at that capture's
timestamp.

---

## 6. Temporal windows

### 6a. Gap detection threshold

`pipeline/wayback.py` reports any interval between consecutive ingested captures that
exceeds **90 days** (`_GAP_THRESHOLD_DAYS = 90`). Gaps are logged in the
`BackfillReport.gaps` list and reported in `validation/<source>.md`. A gap means the
dataset cannot reliably detect entries or exits during that interval — providers who entered
and exited within the gap will not appear in the event log at all.

The gap between the last Wayback capture and the first own scrape is also reported. For AZ
ABS, this gap was 12 days (acceptable). For programs with no Wayback history, this gap
spans the entire pre-registry period (unknown start → first own scrape).

### 6b. Snapshot interval

There is no fixed scraping cadence in v1. Snapshots are created opportunistically, and
`retrieved_at` documents exactly when each capture occurred. Analysts should not assume
any regularity in the snapshot interval.

### 6c. No grace window for roster absences

The diff algorithm does not implement a grace window (i.e., "a provider must be absent
from N consecutive snapshots before we record a disappearance"). Every absence triggers a
`disappeared_from_roster` event dated to the first snapshot in which the provider is
absent. This is a deliberate choice: a grace window would require us to decide what "N"
means, which is a policy judgment that varies by program. Analysts who want a grace window
should apply it in post-processing, not in the raw event log.

### 6d. Wayback cutoff

The Wayback backfill only processes captures that predate the earliest own-scrape snapshot
already in the DB (`backfill_program()` queries `store.get_first_snapshot()` and discards
any Wayback capture at or after that timestamp). This prevents Wayback from overwriting
the `last_seen_snapshot_id` of providers already tracked by own scrapes, which would
regress the "last seen" timestamp to an older date.

---

## 7. Provider ID generation

**Scheme version:** 1

`provider_id` values are deterministic and content-addressed. Given the same
`(program_id, legal_name)` pair, the same ID is always produced, making IDs stable across
re-scrapes without a sequence table.

```
provider_id = f"prov_{program_slug}_{sha256(f'{program_id}\x00{legal_name}').hexdigest()[:12]}"
```

Where `program_slug` is the program's short identifier (the portion after `prog_`).

**Example:**
`"Aiken Farrell Kroloff, LLC"` in `prog_az_abs`:

```
sha256("prog_az_abs\x00Aiken Farrell Kroloff, LLC")[:12] → "f1a68aed73dd"
provider_id = "prov_az_abs_f1a68aed73dd"
```

**Properties:**

- *Deterministic:* same `(program_id, legal_name)` → same ID across all runs and machines.
- *Collision-resistant:* 12 hex chars = 48 bits; P(any collision) < 10⁻⁹ at 10,000
  providers per program.
- *Opaque:* no information about the provider is derivable from the ID alone.
- *Name-change behavior:* if a provider's `legal_name` changes, it receives a new
  `provider_id`. This is correct: a rename typically reflects a new legal entity. The old
  name and old ID are preserved in `provider_alias` for continuity.
- *Program-scoped:* two programs licensing identically-named entities produce different
  `provider_id` values because `program_id` is included in the hash. This is intentional.

**Limitation:** if the regulator changes how it renders a name (e.g., removes a comma,
adds "Inc."), the hash changes and a spurious exit + entry pair is produced. The mitigation
is to normalize `legal_name` before hashing — but we hash `legal_name` (the raw form), not
`normalized_name`, because the raw legal identity is more stable as a key. Any name drift
observed in practice should be added to `provider_alias`.

If the scheme is ever changed (e.g., switching to UUIDs), document the migration here and
bump the scheme version.

---

## 8. Wayback Machine backfill

Implemented in `pipeline/wayback.py`. Used to reconstruct roster history predating this
registry for programs with significant pre-registry history (WA LLLT: 2015–2021; AZ ABS:
2021–; UT Sandbox: 2021–).

### 8a. CDX discovery

The Internet Archive's CDX API (`web.archive.org/cdx/search/cdx`) is queried for every
HTTP-200 capture of the roster URL. Parameters:

- `collapse=digest`: the CDX server deduplicates captures with identical Wayback content
  digest server-side, returning only one representative timestamp per unique content state.
  This is the primary deduplication mechanism.
- `output=json`, `fl=timestamp,original,statuscode,digest`: minimal field set.
- Rate limit: **1.5 seconds** between IA requests (`_IA_RATE_LIMIT`), per IA `robots.txt`
  guidance.

The CDX response is sorted oldest-first for ordered chain processing.

### 8b. Content fetch

Each unique capture is fetched via the Wayback `id_` modifier:
`http://web.archive.org/web/{timestamp}id_/{url}`

The `id_` modifier returns the **original page content** without Wayback's JS toolbar
injection. This ensures the bytes we parse are the same as the original server sent —
important for SHA-256 deduplication integrity.

### 8c. Local SHA-256 deduplication

Despite the CDX `collapse=digest`, identical content may occasionally appear at multiple
timestamps (CDX digest is a base32 SHA-1; our store uses SHA-256). If consecutive captures
produce the same `content_sha256`, the second is silently discarded. No snapshot or event
is written for a content-identical capture.

### 8d. Snapshot ingestion with Wayback timestamp

Wayback captures are ingested with `retrieved_at = capture.retrieved_at` — the archive
timestamp, not the time the backfill script ran. This is what makes the longitudinal
reconstruction accurate: each `provider_status_event.event_date` reflects when the
capture was taken, not when we processed it.

Wayback snapshots carry `scraper_version = "wayback-{version}"` to distinguish them from
own-scrape snapshots.

### 8e. INSERT-only for existing providers

When a Wayback capture is processed, providers are written via
`store.insert_provider_if_new()` (`INSERT ... ON CONFLICT DO NOTHING`) rather than
`upsert_provider()`. This ensures Wayback captures cannot overwrite the
`last_seen_snapshot_id` of a provider already tracked from an own scrape (own scrapes are
always more recent; overwriting with an older Wayback timestamp would regress the "last
seen" date).

For providers that appear only in Wayback captures (i.e., they entered and exited before
the first own scrape), this is the only write path.

### 8f. Partial captures (headless sources)

For JS-rendered, paginated directories (WA LLLT), Wayback captures only the initial page
load — typically ~20 entries of a ~95-row roster. The WA LLLT scraper overrides
`_wayback_parse()` to handle single-page captures. These captures are flagged as
`partial_captures` in the `BackfillReport` and logged in the validation report.

Partial captures produce partial event records: providers on pages 2+ appear to have
"entered" on the date of the first capture that included them (which is an artifact of
pagination, not a real entry). This is documented in `validation/washington_lllt.md` and
must be accounted for in any analysis of WA LLLT roster growth pre-2020.

Sources that use a headless fetcher but have no `_wayback_parse()` override (e.g., UT LPP)
are excluded from Wayback backfill — their parse logic expects a pre-assembled DOM from
Playwright, which Wayback cannot replay.

### 8g. Wayback backfill cutoff

Backfill processes only captures **before** the earliest own-scrape snapshot in the DB.
Any Wayback captures at or after that date are discarded. This prevents the backfill from
creating duplicate events for the period already covered by own scrapes.

---

## 9. Program status resolution (legislative layer)

Implemented in `resolve/program_status.py`.

### 9a. Data sources

- **Open States v3** (`https://v3.openstates.org/bills`): primary source. Searches by
  state jurisdiction and query terms. Requires `X-API-KEY` header.
- **LegiScan** (`https://api.legiscan.com`): fallback if Open States returns zero results
  for a query. Free tier.

Both APIs are searched with a 1-second rate limit between requests.

### 9b. Scoring

Each bill returned by the API is scored for relevance (0.0–1.0) by `_score_relevance()`:

| Signal | Weight |
|---|---|
| Exact known-bill match (e.g. `SB 1218` in `identifier`) | +0.50 |
| Query term found in bill title | +0.30 / n_queries |
| Bill was enacted (signed into law) | +0.20 |

Bills scoring below **0.30** are treated as low-relevance matches and produce no status
update.

### 9c. Direction classification

Each bill is classified as `positive` (authorizes/extends), `negative` (sunsets/repeals),
or `neutral`/`unknown` based on keyword matching against the title and abstract.

Positive tokens include: `creat`, `establish`, `authoriz`, `licens`, `pilot`, `allow`,
`enabl`, `expand`, `extend`, `continu`, `renew`, `reauthoriz`, `regulat`, `certif`.

Negative tokens include: `sunset`, `repeal`, `abolish`, `eliminate`, `terminate`,
`discontinue`, `prohibit`, `ban`, `void`, `rescind`, `revok`.

### 9d. Status mapping

| Condition | Proposed status |
|---|---|
| `negative` + `enacted` | `sunset` |
| `positive` + `enacted` + `enacted_means_proposed=True` | `proposed` |
| `positive` + `enacted` | `active` |
| `positive` + not failed | `proposed` |
| `negative` + not enacted | no change (flagged for review) |

`enacted_means_proposed` is set per-program when the authorizing bill has been signed into
law but implementing rules have not yet been adopted (e.g., TX ALP: SB 1218 signed June
2023; TX Supreme Court rules still pending as of 2026).

### 9e. Confidence and application

- **Confidence < 0.30:** no signal.
- **Confidence 0.30–0.49:** evidence recorded but no status update proposed.
- **Confidence 0.50–0.79:** status update proposed; written only when `--apply` is passed.
- **Confidence ≥ 0.80:** high-confidence update; safe for automated application.

### 9f. Court-rule programs

AZ ABS, AZ LP, CO LLP, MN LP, and WA LLLT were authorized or sunset by state supreme
court administrative rules, not by legislation. Open States does not cover court rules.
These programs use a `status_override` in the resolver config: the status and sunset date
are set from documented court orders and returned with `confidence = 1.0` regardless of
what the legislative API returns. The API is still queried for context (to surface any
related legislative activity) but the override takes precedence.

| Program | Override source |
|---|---|
| WA LLLT | `APR 28` amended 2020, effective 2021-07-31 |

---

## 10. Reconciliation and quality checks

Every data-producing step reports three metrics before being declared complete.

### 10a. Completion

The artifact exists, runs without error, and passes `ruff check` and `pytest`. CI must be
green. A scraper that produces output but fails any test is not done.

### 10b. Comprehensiveness (coverage / recall)

Compare the parsed row count against the source's own stated total:

```
coverage = parsed_N / source_total_M
```

Logged in `validation/<source>.md` as `parsed N / source_total M (coverage %)`.

If a source does not publish a total, reconcile against pagination: total pages × rows per
page, minus any known empty/partial last pages. Any gap must be explained. Unexplained
gaps indicate a parser bug, not an acceptable margin.

**Target:** 100% for all roster sources. Flag and investigate any shortfall.

### 10c. Accuracy (precision)

Pull a **stratified random sample** of at least 15 rows or 10% of the total, whichever is
larger. For each sample row, hand-verify every field against the live or archived source
and record the result in `validation/<source>.md`.

**Target:** zero field-level errors on identity fields (`legal_name`, `jurisdiction`,
`authorization_date`, `current_status`). Investigate any nonzero error rate before
publishing.

Sample selection is stratified by status (active / inactive) and, where applicable, by
practice area. Document the sample IDs and verification date. Samples are not re-verified
on subsequent scrapes unless the scraper logic changes.

**Which "total" for multi-snapshot programs:** for a program with more than one snapshot
(v1.0.0: AZ ABS, UT Sandbox), "the total" for the ≥15-or-10% rule means the **latest
roster snapshot's row count** — the population the source itself stated at the time you
sampled it — not the cumulative all-time provider count carried in the DB (which includes
providers who have since exited and are no longer on any live roster to hand-verify
against). AZ ABS's accuracy sample (`validation/arizona_abs.md`) already follows this
convention (17 rows against the 167-row latest roster, 10.2%, not the 203-row cumulative
total); this paragraph makes that convention explicit for the next multi-snapshot source.

### 10d. Longitudinal validity

When Wayback backfill is available, reconcile our computed historical counts against
published benchmarks (annual reports, press releases) at the same point in time:

```
divergence = (our_count − published_count) / published_count
```

Divergence above 10% requires investigation. Common causes: administrative vs. public
roster lag (§12b), counting methodology differences (cumulative vs. point-in-time), or a
genuine coverage gap. All explanations are documented in `validation/longitudinal_validity.md`.

### 10e. Completeness audit (frame reconciliation)

The checks in §10b–§10d ask "did we parse everything a *known* source publishes?" They
cannot catch a program we never built a scraper for at all. `completeness/frame_reconcile.py`
(`make completeness`) answers a different question: "does an *independent, external*
inventory of reregulation programs list anything our `program` table doesn't have, or vice
versa?"

**Method:**

1. Fetch and snapshot an external inventory — in v1, the IAALS Unlocking Legal Regulation
   knowledge center (`completeness/inventory_fetch.py::IaalsRegulatoryModelsFetcher`), the
   closest thing to an authoritative cross-jurisdiction survey of reregulation programs.
   The snapshot is content-hashed and stored like any other source capture (own table,
   `completeness_snapshot`, kept separate from the release schema's `source_snapshot`).
2. Restrict the "theirs vs. ours" diff to program types IAALS enumerates thoroughly enough
   to trust an absence as a signal: Regulatory Sandbox, Alternative Business Structures,
   and Community-Based Justice Worker Models. `alp_license`, `paraprofessional_pilot`, and
   `document_preparer` are excluded from this check because IAALS defers those to a
   separate resource it doesn't itself claim to enumerate — flagging their absence would be
   a false signal from a source that never made the claim.
3. Only two of IAALS's status buckets ("Implemented Programs", "Programs Being
   Implemented") are treated as a claim that a program currently operates. Everything else
   (Under Consideration, Not Moving Forward, Litigation, Resolutions, Data & Evaluation) is
   recorded for visibility in `validation/completeness.md` but never written to the gap
   ledger.
4. Every candidate gap — in either direction — is appended to `validation/residual_gaps.csv`
   with `classification="unresolved"`. The tool proposes; it never decides
   `in_frame_missing` / `out_of_frame` / `intentionally_excluded` / `deferred_to_v2`. Once a
   human sets a row's classification, `completeness/ledger.py` never overwrites it on a
   re-run (keyed on `(item, jurisdiction, detected_by)`) — the same immutability rule as
   `crosswalk_courtlistener` verified rows.

**v1.0.0 result:** 14 candidate gaps surfaced by this automated check, all 14 resolved. 2
`intentionally_excluded` (Utah ABS — covered by `prog_ut_sandbox`; Washington ABS — covered
by `prog_wa_entity_pilot`, built 2026-07-04); 1 `resolved_built` (Washington sandbox — the
same `prog_wa_entity_pilot` build resolves this listing directly); 11 `deferred_to_v2` (3
candidate programs not yet built — IN sandbox, MN sandbox, PR ABS — and 8
Community-Based Justice Worker Model jurisdictions, since `community_justice_worker` exists
in the v1 `program_type` enum for forward compatibility but no v1 scraper covers it).

`validation/residual_gaps.csv` carries one further row (15 total) beyond what this automated
check can surface: Oregon LP (`alp_license`), which is out of scope for the check above (it
only covers sandbox/abs/community_justice_worker — bullet 2 of this section) and was
identified and deferred by direct manual research instead
(`detected_by=manual-oregon-research`; see `docs/sampling_frame.md §3a` and
`validation/oregon_lp.md`).

Full disposition table and reasoning: `docs/sampling_frame.md §6`. The territory-scope decision
(v1 does not independently survey U.S. territories beyond what IAALS surfaced) is in
`docs/sampling_frame.md §5`.

---

## 11. Entity resolution design (v3 stub)

Not implemented in v1. The `crosswalk_courtlistener` table schema is defined for forward
compatibility.

### Design (for v3 implementation)

1. **Offline blocking:** compare providers against CourtListener bulk party data (quarterly
   CSV). Block on normalized-name token overlap + jurisdiction to reduce candidate pairs.
2. **Scoring:** `rapidfuzz` token-set ratio on `normalized_name` (primary); jurisdiction
   match boost; temporal plausibility (`event_date ≥ authorization_date`).
3. **Thresholds:** auto-accept ≥ 0.92 with jurisdiction match; human review 0.70–0.92;
   reject < 0.70. Log all rejects for recall auditing.
4. **Verified rows are immutable:** `upsert_crosswalk()` will not overwrite
   `verified = True` rows. Human judgment is preserved across pipeline re-runs.
5. **Measure yourself:** maintain a gold set of ≥ 200 labeled pairs to report
   precision/recall. A match score without a labeled evaluation is not a quality metric.

Access pattern: CourtListener bulk data (offline) for candidate generation; live API
(`v4/`) only for verification of high-confidence candidates. Never hammer the search UI.

---

## 12. Candid limitations

This section documents what the dataset does and does not measure. It is part of the
dataset's credibility.

### 12a. Roster-based observation, not ground truth

This dataset is built from public regulatory rosters. Rosters are the **best available
evidence** of authorization status but are not infallible:

- Regulators update rosters manually or in batch; a provider who exited on day 1 may still
  appear on the roster on day 30.
- A provider may appear on the roster after authorization has been revoked but before the
  regulator removes the listing (or vice versa).
- Rosters reflect a regulator's administrative record, which may differ from what a
  provider is actually doing in the market.

**What this means:** `current_status = active` means the provider appeared on the most
recent roster snapshot. It does not mean the provider is currently serving clients, that
no disciplinary process is underway, or that the authorization is valid as of today.

### 12b. Public roster vs. administrative record lag

Regulatory databases show a lag between administrative approval and public listing. For AZ
ABS, this lag is estimated at days to weeks based on the 5.9% divergence between our April
2025 Wayback count and the AZ Supreme Court's published ~136 figure. Our count will
systematically undercount by this lag amount at any given point in time.

This is not a scraper bug — it is a property of the source. Analysts comparing our
registration counts to published figures from the same period should account for this lag.

### 12c. Snapshot interval determines resolution

Entry and exit dates are only as precise as the snapshot interval. With monthly snapshots,
a provider who entered and exited in the same month will produce no event at all. With
weekly snapshots, a two-week tenure could be detected. Finer resolution requires more
frequent scraping.

The dataset does not assert any minimum scraping cadence. The `retrieved_at` timestamps on
each snapshot fully document the actual observation window.

### 12d. `disappeared_from_roster` is not `revoked`

As documented in §4c, disappearances are observations, not legal conclusions. The gap
between the two is significant for any analysis of disciplinary outcomes. In v1, no formal
revocation data is integrated. The `disciplined` and `reinstated` event types are defined
in the schema but not yet populated.

**Analysts who treat all disappearances as disciplinary exits will overstate the disciplinary
rate.** This assumption must be disclosed and justified.

### 12e. Practice area data is sparse and non-standardized

`practice_areas_raw` captures the terminology each program uses. These terms vary
substantially across programs and are not comparable without additional mapping:

- AZ ABS: no practice area restriction by entity; the column is empty.
- AZ LP: categories are `family law`, `limited civil`, `criminal`, `administrative`.
- WA LLLT: `family law` only (the program's single authorized practice area).
- UT LPP: `family law`, `debt collection`, `landlord-tenant`.
- CO LLP: `domestic relations` only.

`practice_areas_list` (JusticeBench LIST codes) is intended to normalize these across
programs, but the mapping is not yet implemented. Cross-program practice-area comparisons
are not valid until this mapping exists.

### 12f. Technology and AI flags are unreliable in v1

`uses_technology` and `uses_ai` are coded from providers' public application materials or
websites where published. In v1, these fields are mostly `NULL` — the coding workflow is
not yet implemented. Do not treat `NULL` as `False`. The column exists to support v2 AI
policy analysis but should not be used for quantitative comparisons until systematically
populated.

### 12g. Wayback partial captures for headless sources

For JS-rendered, paginated directories (WA LLLT), Wayback captures only page 1 of the
roster (~20% of entries per capture). The pre-sunset trajectory is reconstructed from
partial evidence. This means:

- Provider counts from WA LLLT Wayback captures are **lower bounds**, not totals.
- Entry/exit events for providers who appeared only on pages 2+ of historical captures
  are entirely absent from the event log.
- The "peak roster size" computed from Wayback data understates the true peak.

This limitation is inherent to the source type and cannot be resolved without finding
archived full-export data or building a custom historical crawl.

### 12h. Scope of the empirical question

This dataset measures authorization, not outcomes. It can support questions like:

- How many providers were authorized under program X at time T?
- What is the entry/exit rate for program X over the observation period?
- Which programs allow non-lawyer ownership, UPL waiver, or software providers?
- Did WA LLLT practitioners move to other licensing regimes after sunset?

It cannot — without additional data — support questions like:

- Did consumers experience harm under program X?
- Did the quality of legal services improve or decline?
- What happened to clients of providers who exited?
- Are ABS firms serving different client populations than traditional firms?

The outcomes layer (v2) will add complaint records, bar discipline, and judicial outcomes.
The litigation linkage (v3) will add CourtListener docket data. Even then, the dataset
measures formal regulatory activity, not actual client welfare. Interpreting disciplinary
counts as harm requires explicit assumptions that must be justified by the analyst.

### 12i. What v1 does NOT include — stated explicitly

v1 is a provider census with entry/exit tracking. It is deliberately **not** an outcomes
dataset. Stated verbatim, so no absence is mistaken for an oversight:

- **Outcomes** — complaint dispositions, discipline findings, malpractice claims, or any
  other measure of what happened to a client after engaging a provider. Deferred to **v2**.
- **Rates** — anything expressed as a rate (complaints per provider, providers per capita,
  services delivered per authorization) requires a denominator this dataset does not yet
  carry (e.g., services-delivered counts from activity reports). Deferred to **v4**.
- **Harm measures** — any column purporting to measure consumer harm, benefit, or quality
  of service. Column names in this dataset are neutral proxies by design (golden rule 4);
  v1 provides the spine, not a harm definition. Deferred to **v2**, alongside outcomes.
- **Litigation linkage** — connecting a `provider_id` to CourtListener dockets, party
  records, or case outcomes. The `crosswalk_courtlistener` table exists as a schema stub
  (§11) but is unpopulated in v1. Deferred to **v3**.

Anyone citing this dataset for a harm/outcomes claim is citing something it does not
contain.
