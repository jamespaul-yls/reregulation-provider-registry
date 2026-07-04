# Completeness Audit

Reproducible adversarial coverage checks for the reregulation provider registry — turns the manual coverage pass into provenance-backed, re-runnable code (`make completeness`). See `completeness/` and the CLAUDE.md working agreement.

<!-- BEGIN frame_reconcile -->

## 1. Frame reconciliation

_Last run: 2026-07-04_

**Sources checked:**
- `iaals`: <https://iaals.du.edu/projects/unlocking-legal-regulation/knowledge-center>

**Ledger state:** 14 row(s) in `validation/residual_gaps.csv` — 14 resolved (human-classified), 0 still `unresolved` pending review. This module only ever proposes new candidates as `unresolved`; classification and `resolved` are set by a human and are never overwritten by a re-run (see `completeness/ledger.py`).

| Item | Jurisdiction | Classification | Proposed action / resolution |
|---|---|---|---|
| Community-Based Justice Worker Models — Alaska | AK | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Arizona | AZ | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Washington, D.C. | DC | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Delaware | DE | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Hawaii | HI | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Illinois | IL | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Regulatory Sandbox — Indiana | IN | `deferred_to_v2` | Deferred to v2: IAALS lists this under "Programs Being Implemented" (not yet "Implemented") — pre-launch by the source's own classification, so no roster can exist yet. Distinct from the Puerto Rico ABS gap below, which IAALS lists as already "Implemented." Confirmed by James 2026-07-04 — added to the v2 new-program backlog rather than built now. |
| Regulatory Sandbox — Minnesota | MN | `deferred_to_v2` | Deferred to v2: IAALS lists this under "Programs Being Implemented" (not yet "Implemented") — pre-launch by the source's own classification, so no roster can exist yet. This is a distinct candidate program from the existing prog_mn_lp (paraprofessional pilot) already in v1 — do not conflate the two. Distinct from the Puerto Rico ABS gap below, which IAALS lists as already "Implemented." Confirmed by James 2026-07-04 — added to the v2 new-program backlog rather than built now. |
| Community-Based Justice Worker Models — Montana | MT | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Alternative Business Structures — Puerto Rico | PR | `deferred_to_v2` | Deferred to v2: IAALS lists this under "Implemented Programs" (unlike the IN/MN sandbox gaps, which are only "Being Implemented"), so a program plausibly already operates — the open question is whether a public registry/roster exists to scrape at all, not whether the program has launched. Distinguish from IN/MN: this is a possible-registry-gap, not a pre-launch gap. Confirmed by James 2026-07-04 — added to the v2 new-program backlog rather than built now. |
| Alternative Business Structures — Utah | UT | `intentionally_excluded` | Confirmed by James: UT ABS-like entities already covered under prog_ut_sandbox. |
| Community-Based Justice Worker Models — Utah (through its Sandbox) | UT | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Alternative Business Structures — Washington | WA | `intentionally_excluded` | Resolved 2026-07-04: covered by prog_wa_entity_pilot (WA Supreme Court Order 25700-B-721), which grants ABS-style nonlawyer-entity relief. Same resolution pattern as UT ABS / prog_ut_sandbox — one pilot program absorbs both the sandbox and ABS IAALS listings. Confirmed by James 2026-07-04. |
| Regulatory Sandbox — Washington | WA | `resolved_built` | Resolved 2026-07-04: prog_wa_entity_pilot built (scrapers/washington_entity_pilot.py), program_type=sandbox, matching this listing directly. No longer a gap. |

**Informational (non-actionable) IAALS signals:** 22 row(s) under status buckets other than Implemented/Being Implemented (Programs Under Consideration, Not Moving Forward, Litigation, Resolutions, Data & Evaluation) — recorded for visibility, not written to the ledger since they are not claims that a program currently operates.

| Model type | Status bucket | Jurisdiction |
|---|---|---|
| Regulatory Sandbox | Programs Under Consideration | Virginia |
| Regulatory Sandbox | Programs Not Moving Forward | California |
| Regulatory Sandbox | Programs Not Moving Forward | Florida |
| Regulatory Sandbox | Programs Not Moving Forward | Virginia |
| Regulatory Sandbox | Data & Evaluation | Utah |
| Alternative Business Structures | Programs Under Consideration | Tennessee |
| Alternative Business Structures | Programs Under Consideration | Texas |
| Alternative Business Structures | Data & Evaluation | Arizona |
| Alternative Business Structures | Data & Evaluation | Utah |
| Allied Legal Professionals | Data & Evaluation | Arizona |
| Allied Legal Professionals | Data & Evaluation | Minnesota |
| Allied Legal Professionals | Data & Evaluation | Washington |
| Community-Based Justice Worker Models | Programs Under Consideration | California |
| Community-Based Justice Worker Models | Programs Under Consideration | Georgia |
| Community-Based Justice Worker Models | Programs Under Consideration | Michigan |
| Community-Based Justice Worker Models | Programs Under Consideration | Montana |
| Community-Based Justice Worker Models | Programs Under Consideration | Texas |
| Community-Based Justice Worker Models | Programs Under Consideration | Virginia |
| Community-Based Justice Worker Models | Data & Evaluation | Alaska |
| Community-Based Justice Worker Models | Data & Evaluation | Arizona |
| Community-Based Justice Worker Models | Data & Evaluation | Utah |
| Community-Based Justice Worker Models | Data & Evaluation | United Kingdom |

**Unmapped domestic jurisdiction name(s) (1):** United Kingdom

<!-- END frame_reconcile -->

## 2. Legislative-scan flags

_Not yet implemented — see `completeness/legislative_scan.py` (TODO)._

## 3. Within-program reconciliation

_Not yet implemented — see `completeness/within_program.py` (TODO)._
