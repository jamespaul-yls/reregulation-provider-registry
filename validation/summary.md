# Validation Summary — v1.0.2

Single consolidated entry point into the validation record. This document summarizes; the
per-source `validation/<source>.md` files and `validation/longitudinal_validity.md` remain
the detailed, hand-verified record each summary line points back to. Nothing here
supersedes those — if a number below and a source file disagree, the source file is
authoritative and this document has drifted and should be regenerated from it.

**Version:** 1.0.2 · **Last updated:** 2026-07-06

---

## 1. Per-program coverage and accuracy

"Parsed N" is the latest-snapshot roster parse (the figure reconciled against the
source's own stated total); the DB's cumulative provider count can be higher for
multi-snapshot programs (AZ ABS, UT Sandbox) — see `validation/coverage_report.md` for
both figures side by side.

| Program | Parsed N (latest snapshot) | Source-stated total | Coverage | Accuracy sample | Field-level error rate | Detail |
|---|---|---|---|---|---|---|
| AZ ABS | 167 (203 cumulative in DB) | 167 (own roster, paginated) | **100.0%** | 17 rows | **0%** (identity fields) | `validation/arizona_abs.md` |
| AZ LP | 120 | unknown (no stated total published) | N/A — no pagination count on source | 15 rows | **0%** | `validation/arizona_lp.md` |
| CA LDA | 0 | unknown (no statewide registry; county-fragmented) | **0/unknown — structural, deferred to v2** | — | — | `validation/california_lda.md` |
| CO LLP | 126 | 126 | **100%** | 15 rows | **0%** | `validation/colorado_llp.md` |
| MN LP | 42 | 42 | **100%** | 15 rows | **0%** | `validation/minnesota_lp.md` |
| TX ALP | 0 | 0 (program not yet effective) | **N/A (0/0) — temporal** | — | — | `validation/texas_alp.md` |
| UT LPP | 52 | unknown (no stated authoritative total) | N/A — no pagination count on source | 15 rows | **0%** | `validation/utah_lpp.md` |
| UT Sandbox | 69 (70 cumulative in DB) | 69 (own roster, all sections manually counted) | **100%** | 15 rows (+7 targeted on entity-only fields) | **0%** | `validation/utah_sandbox.md` |
| WA Entity Pilot | 0 | 4 applicants (0 authorized) | **N/A (0/4 authorized)** — temporal | — | — | `validation/washington_entity_pilot.md` |
| WA LLLT | 95 | 95 | **100%** | 15 rows (~16%) | **0%** | `validation/washington_lllt.md` |

**Zero field-level identity errors across every program with a roster to sample** —
`legal_name`, `jurisdiction`, `authorization_date`, `current_status` all hit the 0%-error
target in every stratified accuracy sample pulled to date. The three zero-provider
programs (CA LDA, TX ALP, WA Entity Pilot) are structural/temporal, not accuracy gaps —
see `docs/sampling_frame.md §3` for the documented reason each one is correctly zero.
(D.C. Rule 5.4(b) was a fourth such program through v1.0.1; it was removed from scope
2026-07-06 rather than kept as a documented zero — see `docs/sampling_frame.md §4`.)

Two programs (AZ LP, UT LPP) have no independently published roster total to reconcile
against; coverage is instead validated by confirming the scraper captured every row the
source page itself renders (no pagination cutoff, no truncation) — see each program's
`validation/<source>.md` "Comprehensiveness" section for the specific check performed.

---

## 2. Known trajectories reproduced

Two programs have enough historical depth (own scrapes + at least one Wayback capture) to
reproduce a published growth/decline trajectory, not just a single point-in-time count.
Full reconstruction detail, including the intermediate Wayback-derived counts and
divergence diagnosis, is in `validation/longitudinal_validity.md §3–§4`.

| Program | Earliest known count | Current count | Direction | Published benchmark match |
|---|---|---|---|---|
| AZ ABS | ~19 active (2022, AZ SC annual report) | **160 active** (2026-06-28; 203 total incl. 43 exited) | Growth | Apr-2025 benchmark ~136 active vs. an **unpersisted dry-run** count of 128 from that period — not reproducible from committed data, see caveat below |
| UT Sandbox | ~39 cumulative (2022, published) | **8 active** (2026-06-29; 70 total incl. 62 exited) | Decline | Apr-2025 benchmark ~11 active vs. our 8 (14 months later, both endpoints from persisted snapshots) — consistent with the sandbox's defined per-entity pilot duration, not a coverage gap |

Both trajectories move in the direction the underlying program design predicts (AZ ABS
keeps admitting new entities; the UT Sandbox's fixed-duration pilot structure means early
cohorts cycle out over time). The UT Sandbox comparison is fully reproducible from
persisted snapshots and stays within the 10% investigation threshold in
`docs/methodology.md §10d`.

**The AZ ABS Apr-2025 comparison is not reproducible and should not be read as validated.**
The 128-count came from a Wayback CDX scan that was a dry run and was never persisted to
`source_snapshot` (`validation/longitudinal_validity.md §3` discloses this explicitly) —
there is no snapshot in `data/raw/` to check the "5.9% divergence" figure against, so treat
it as narrative context, not a verified reconciliation. The only AZ ABS accuracy claim this
dataset actually verifies is the stratified sample in `validation/arizona_abs.md` (17/167
rows, 0% field-level error on identity fields).

Deeper Wayback reconstruction (the full 2021–2024 capture chain for both programs, plus a
first WA LLLT backfill) is deferred to v2 — see `validation/longitudinal_validity.md §6`.

---

## 3. Provenance audit

`make audit` (`pipeline/audit.py`) — **100% clean**, 0 violations, across every published
table:

```
10 programs, 19 snapshots, 708 providers, 748 events, 0 aliases
```

Checks: null provenance (`source_url`/`retrieved_at`/`scraper_version`) and FK resolution
on `program`, `provider`, `provider_status_event`, and `provider_alias`; blob
existence + sha256 integrity for every `source_snapshot`. `program` rows are additionally
required to have at least one backing `source_snapshot` row — i.e., the program's own
authorizing source must have actually been captured immutably, not merely asserted (see
`docs/methodology.md` — this closed a real gap for `prog_tx_alp` during v1 close-out,
which now has a snapshotted evidentiary page; `prog_dc_rule54` was held to the same rule
until it was removed from scope entirely 2026-07-06 — see `docs/sampling_frame.md §4`).

## 4. Completeness audit (frame reconciliation)

`make completeness` (`completeness/frame_reconcile.py`) — 14 candidate gaps surfaced
against the IAALS external inventory on its one real run (2026-07-01), **14/14 resolved**
(0 open):

- 2 `intentionally_excluded` (Utah ABS — covered by `prog_ut_sandbox`; Washington ABS —
  covered by `prog_wa_entity_pilot`)
- 1 `resolved_built` (Washington sandbox — `prog_wa_entity_pilot`, built 2026-07-04,
  matches this listing directly)
- 11 `deferred_to_v2` (3 candidate new programs — IN sandbox, MN sandbox, PR ABS; 8
  Community-Based Justice Worker Model jurisdictions — `community_justice_worker` exists
  in the v1 taxonomy but no v1 scraper covers it)

Plus **3 more rows added outside/after this automated check's first real run**:

- Oregon LP (`deferred_to_v2`, `detected_by=manual-oregon-research`) — the IAALS
  cross-check above is scoped to sandbox/abs/community_justice_worker only, so it can
  never surface an `alp_license` gap on its own. Oregon was identified and deferred via
  direct research instead (`validation/oregon_lp.md`, `docs/sampling_frame.md §3a`).
- Alternative Business Structures — Washington, D.C. (`intentionally_excluded`,
  `detected_by=manual-dc-rule54-removal`) — matched by `prog_dc_rule54` at the time of the
  2026-07-01 run; that program was removed from scope 2026-07-06 (`docs/sampling_frame.md
  §4`). Added the day of the removal, pre-empting the gap it would create.
- **The same D.C. ABS item a second time** (`intentionally_excluded`,
  `detected_by=frame_reconcile`) — a live `make completeness` run on 2026-07-06 (during the
  pre-publication finalize pass) confirmed the prediction above: the automated check
  surfaced this listing as a fresh `unresolved` candidate, since `(item, jurisdiction,
  detected_by)` keying means a different `detected_by` for the same item is a different
  ledger row. Resolved the same way, same day. **This will recur on every future live run**
  until the keying scheme is fixed — see `docs/sampling_frame.md §6` for the full account.

**17 rows total in the ledger, 17/17 resolved, 0 open** — as of the live re-run during this
finalize pass, not merely asserted from the earlier close-out.

Full disposition table and reasoning: `docs/sampling_frame.md §6`. Raw ledger:
`validation/residual_gaps.csv`. Narrative report: `validation/completeness.md`.

## 5. Reproducibility

`make reproduce` (`pipeline/reproduce.py`) rebuilds the entire dev DB and `data/release/`
export from `data/raw/` snapshots + `scripts/seed_programs.py` — no network calls. It runs
the full provenance audit internally and exits non-zero on any violation. See §7 of this
document's companion `docs/methodology.md` note, or run it directly:

```
make reproduce
```

---

## 6. Residual gaps

See §4 above and `validation/residual_gaps.csv` — all 17 rows resolved, none open. No
outstanding coverage or scope question remains unresolved for v1.0.2.
