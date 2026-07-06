# Longitudinal Validity Report

**Date produced:** 2026-06-30 · **Updated:** 2026-07-06
**Analyst:** pipeline/wayback.py + manual reconciliation
**Status:** v1.0.2 close-out. One Wayback capture is now persisted for AZ ABS
(2024-11-08) and UT Sandbox (2025-06-12) — enough to seed each program's
`first_seen_snapshot_id` earlier than the first own-scrape and produce real
`disappeared_from_roster`/`status_change` events for UT Sandbox (8 own-scrape
snapshots since deepened the diff chain). The fuller historical CDX chain
described in §3/§4 below (2022, 2025-04, 2025-12, etc.) was a dry run and was
never persisted to the DB; those rows remain useful context for the trajectory
narrative but are not reflected in `source_snapshot`. See
`docs/methodology.md §8` for the backfill design and `validation/summary.md`
for the consolidated, current-as-of-release view.

---

## 1. Summary table (current DB state, 2026-07-06)

| Program | Latest snapshot | Our count | Published benchmark | Divergence | Diagnosis |
|---------|----------------|-----------|---------------------|------------|-----------|
| AZ ABS | 2026-06-28 (+ 1 Wayback: 2024-11-08) | 203 total (160 active, 43 exited) | ~136 active (Apr 2025) | Active count now exceeds the Apr-2025 benchmark — expected continued growth | Consistent with program growth (§3) |
| UT Sandbox | 2026-06-29 (+ 1 Wayback: 2025-06-12; 8 own-scrape snapshots) | 70 total (8 active, 62 exited) | ~11 active (Apr 2025) | −3 active vs. Apr 2025 benchmark | Consistent with continued exits; total includes all historical participants (§4) |
| AZ LP | 2026-06-29 | 120 total (113 active, 7 exited) | — | — | No published benchmark located |
| CA LDA | 2026-06-29 | 0 (structural; see `docs/sampling_frame.md §3`) | — | — | No statewide roster exists |
| CO LLP | 2026-06-29 | 126 total (all active) | — | — | No published benchmark located |
| MN LP | 2026-06-29 | 42 total (all active) | — | — | No published benchmark located |
| TX ALP | 2026-07-04 | 0 (temporal; see `docs/sampling_frame.md §3`) | — | — | Program not yet effective |
| UT LPP | 2026-06-29 | 52 total (all active) | — | — | No published benchmark located |
| WA Entity Pilot | 2026-07-04 | 0 (temporal; see `docs/sampling_frame.md §3`) | — | — | 4 applicants, all "Under Review" — none authorized yet |
| WA LLLT | 2026-06-29 | 95 total (68 active, 13 unknown, 10 exited, 4 suspended) | — | — | Sunset 2021; deeper Wayback backfill would refine pre-sunset peak |

`prog_dc_rule54` appeared in this table through v1.0.1 (0, structural, same treatment as
CA LDA above). It was removed from scope 2026-07-06 — see `docs/sampling_frame.md §4` —
rather than kept as a documented zero, so it no longer has a DB row to report here at all.

---

## 2. DB state as of this report

```
program_id            n_providers  n_snapshots  event types (authorized / disappeared / status_change)
prog_az_abs            203          2            203 / 36 / 0
prog_az_lp             120          1            120 / 0 / 0
prog_ca_lda              0          1            0 / 0 / 0
prog_co_llp            126          1            126 / 0 / 0
prog_mn_lp              42          1            42 / 0 / 0
prog_tx_alp              0          1            0 / 0 / 0
prog_ut_lpp             52          1            52 / 0 / 0
prog_ut_sandbox         70          9            70 / 1 / 3
prog_wa_entity_pilot     0          1            0 / 0 / 0
prog_wa_lllt            95          1            95 / 0 / 0
```

Total: 708 providers, 748 events, 19 snapshots across 10 programs. AZ ABS's 43
exited providers break down as 36 explicit `disappeared_from_roster` events
(from diffing the two snapshots) plus 7 seeded `exited` at bootstrap from the
roster's own status field (§4b of `docs/methodology.md`) — not a
discrepancy, just two different seeding paths for the same status value.

---

## 3. Arizona ABS — longitudinal reconstruction (Wayback dry-run)

Source: CDX dry-run from 2026-06-29 session (not yet in DB; IA is down).  
Roster URL: `https://www.azcourts.gov/admissions/Alternative-Business-Structures/Current-List-of-Authorized-ABS`

| Date | Our count | Published / AZ SC annual report | Notes |
|------|-----------|----------------------------------|-------|
| 2022 | — | ~19 active | Published: AZ SC 2022 annual report; Wayback captures not yet retrieved |
| 2024-11-08 | 77 | — | Earliest Wayback capture parsed (17 total CDX captures found) |
| 2025-04-04 | 128 | ~136 active | **Divergence: −8 (5.9%)** |
| 2025-12-15 | 157 | — | |
| 2026-06-16 | 163 | — | Last Wayback capture before own scrape |
| 2026-06-28 | **167** | — | Own scrape → validates scraper vs. last Wayback (+4, 2 weeks) |

### AZ ABS: divergence diagnosis — Apr 2025 (−8 from published 136)

**Possible explanations (in order of likelihood):**

1. **Counting methodology:** The AZ Supreme Court's published ~136 figure likely comes from their internal database, which may include recently approved entities not yet appearing on the public roster page. Our scraper counts only entities listed on the public-facing roster. A lag of days to weeks between approval and public listing could explain 8 missing entries.

2. **Wayback capture timing:** Our April 2025 Wayback capture (2025-04-04) predates the exact date of the published benchmark. If the published figure is from late April 2025, additional authorizations in mid-to-late April would account for the gap.

3. **Coverage gap:** The public roster is paginated (we capture all pages in our own scraper, but Wayback captures only page 1 for the Wayback backfill — however AZ ABS is not headless/paginated in the same way as WA LLLT, so this should not apply here).

**Target accuracy status:** the 5.9% divergence figure itself is **not independently verifiable** — it depends on the 2025-04-04 dry-run capture, which (per the notice at the top of this document) was never persisted to `source_snapshot`. Treat it as context for why a gap of this size is plausible, not as a validated reconciliation; there is no snapshot in `data/raw/` to check it against. What *is* verified, and what actually supports "no indication of a scraper bug," is the AZ ABS accuracy sample: zero errors on identity fields across 17 sampled rows (see `validation/arizona_abs.md`) — that conclusion rests on the accuracy sample, not on the unpersisted trajectory numbers above.

### AZ ABS: coverage gap assessment

- Earliest Wayback capture: 2024-11-08 (77 providers)
- Gap between program launch (~2021) and first Wayback capture: **~3 years of history unavailable**
- The "~19 in 2022" benchmark is not yet verifiable from our data; Wayback captures from 2021–2024 are needed (blocked by IA downtime)
- No gap between last Wayback (2026-06-16, 163) and own scrape (2026-06-28, 167): 12-day gap, +4 providers — plausible

---

## 4. Utah Sandbox — longitudinal reconstruction

Source: Own scrape 2026-06-29 only (IA downtime + early Wayback captures had parse errors due to site structure change pre-2022).

| Date | Our count (active) | Our count (total) | Published | Notes |
|------|-------------------|-------------------|-----------|-------|
| 2022 | — | — | ~39 | Parse errors on 2022 Wayback captures (site structure incompatible) |
| 2025-04 | — | — | ~11 active | Published: Utah Office of Legal Services Innovation annual report |
| 2026-06-29 | **8 active** | **69 total** | — | Own scrape; 61 show "exited" status |

### UT Sandbox: interpretation

The UT Sandbox figures require careful interpretation:
- **Published "~39 in 2022"** likely counts cumulative approved entities, not active at a moment in time.
- **Published "~11 active in Apr 2025"** is a point-in-time active count.
- **Our 8 active in June 2026** is consistent with continued exits from the sandbox (Utah's sandbox has a defined duration for each entity).
- **Our 69 total** includes all 69 providers ever scraped — including 61 that have exited. This is a broader scope than the published "active" benchmarks.
- **Declining trend is genuine:** The UT Sandbox was designed with a 2-year pilot window per entity. Many early-admitted entities have now cycled out.

### UT Sandbox: divergence diagnosis

- 8 active (June 2026) vs. 11 active (Apr 2025): **−3 over ~14 months** — plausible exits, no coverage or diffing bug.
- "~39 in 2022" benchmark is likely cumulative participants, not comparable to our point-in-time roster scrape. The 2022 figure cannot be verified from our Wayback data (IA downtime + parse errors).

---

## 5. Washington LLLT — sunset reconstruction (deferred to v2)

- Program sunset July 31, 2021 (no new applicants).
- Own scrape June 2026: 95 total (68 active, 13 unknown/inactive, 10 exited, 4 suspended).
- No Wayback capture is yet persisted for WA LLLT — `_wayback_parse()` override is
  implemented and tested (offline, fixture-based), but the live backfill run has not been
  executed. Reconstructing the pre-sunset roster peak and post-sunset decay curve is
  deferred to v2; v1 publishes the current (post-sunset) roster state only.

---

## 6. Remaining work (deferred to v2 — not blockers for v1.0.0)

v1.0.0 does not depend on completing any of these; each is a genuine enhancement to
historical depth, not a correctness gap in what's published.

| Task | Status | Deferred to |
|------|--------|-------------|
| WA LLLT Wayback backfill | Not yet run live | v2 |
| Deeper AZ ABS Wayback chain (2021–2024, to verify the ~19-in-2022 benchmark) | Only 1 capture persisted (2024-11-08); earlier captures dry-run only | v2 |
| Deeper UT Sandbox Wayback chain (2021–2023, to verify the ~39-in-2022 benchmark) | Only 1 capture persisted (2025-06-12); 2021–2022 captures have parse errors (pre-redesign HTML) | v2 |
| Longitudinal plot / sparkline | Depends on deeper Wayback chains above | v2 |

---

## 7. Technical notes

### DuckDB 1.5.x FK constraint bug (resolved)

During this session, we discovered that DuckDB 1.5.x enforces FK constraints during `ON CONFLICT DO UPDATE` (internally delete+reinsert) even when the referenced column is not being changed. Additionally, updating `VARCHAR[]` columns on FK-referenced rows triggers the same error. Fixed by:

1. Removing FK constraint declarations from the `provider` table DDL (Python-layer enforcement via `_require_program()` / `_require_snapshot()` guards is retained).
2. Excluding `practice_areas_raw` and `practice_areas_list` (`VARCHAR[]` types) from the `ON CONFLICT DO UPDATE SET` clause — they are set on first insert and not updated on re-scrape.
3. Migration: `scripts/migrate_remove_provider_fk.py` (run 2026-06-30, 671 providers + 671 events migrated with zero data loss).

### Wayback coverage limitations

- **AZ ABS:** Roster page is static HTML (no headless required). Wayback captures are full-page (not partial). 17 CDX captures found, oldest 2024-11-08.
- **UT Sandbox:** Early Wayback captures (2021–2022) have 0 active entity cards — the site used a different HTML structure (likely a list-based layout before the card-based redesign). Captures from 2023+ may be parseable; not yet verified.
- **WA LLLT:** Headless/paginated; `_wayback_parse()` captures page 1 only (~20 of 95 rows). Marked as partial in the report.
