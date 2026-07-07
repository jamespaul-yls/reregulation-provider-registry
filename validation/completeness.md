# Completeness Audit

Reproducible adversarial coverage checks for the reregulation provider registry — turns the manual coverage pass into provenance-backed, re-runnable code (`make completeness`). See `completeness/` and the CLAUDE.md working agreement.

<!-- BEGIN frame_reconcile -->

## 1. Frame reconciliation

_Last run: 2026-07-06_

**Sources checked:**
- `iaals`: <https://iaals.du.edu/projects/unlocking-legal-regulation/knowledge-center>

**Ledger state:** 17 row(s) in `validation/residual_gaps.csv` — 17 resolved (human-classified), 0 still `unresolved` pending review. This module only ever proposes new candidates as `unresolved`; classification and `resolved` are set by a human and are never overwritten by a re-run (see `completeness/ledger.py`).

| Item | Jurisdiction | Classification | Proposed action / resolution |
|---|---|---|---|
| Community-Based Justice Worker Models — Alaska | AK | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Arizona | AZ | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Alternative Business Structures — Washington, D.C. | DC | `intentionally_excluded` | IAALS lists this under "Implemented Programs" — a claim a program currently operates. It was previously matched by our own prog_dc_rule54 row (D.C. Rule of Professional Conduct 5.4(b)), which this frame_reconcile check treated as covering the listing. prog_dc_rule54 was removed from v1 scope 2026-07-06: Rule 5.4(b) is a permissive ethics rule with no registration requirement, so unlike every other zero-provider program in this dataset there is no roster or provider list that could ever be built for it -- a structural, permanent exclusion, not a coverage gap to close later. Confirmed by James 2026-07-06 -- see docs/sampling_frame.md §4 and validation/dc_rule54.md for the full reasoning. |
| Alternative Business Structures — Washington, D.C. | DC | `intentionally_excluded` | Same real-world item as the manual-dc-rule54-removal row below: prog_dc_rule54 (D.C. Rule of Professional Conduct 5.4(b)) was removed from v1 scope 2026-07-06 -- Rule 5.4(b) is a self-executing ethics rule with no application/registration step, so no roster or provider list can ever be built for it. This row exists separately because frame_reconcile's automated key (detected_by=frame_reconcile) does not match the manually-added disposition's key (detected_by=manual-dc-rule54-removal) -- a known ledger-keying gap, documented in docs/audit/coverage_confidence.md §1. Resolved identically (intentionally_excluded) the same day this run surfaced it, 2026-07-06. See docs/sampling_frame.md §4 and validation/dc_rule54.md for the full reasoning. |
| Community-Based Justice Worker Models — Washington, D.C. | DC | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Delaware | DE | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Hawaii | HI | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Community-Based Justice Worker Models — Illinois | IL | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Regulatory Sandbox — Indiana | IN | `deferred_to_v2` | Deferred to v2: IAALS lists this under "Programs Being Implemented" (not yet "Implemented") — pre-launch by the source's own classification, so no roster can exist yet. Distinct from the Puerto Rico ABS gap below, which IAALS lists as already "Implemented." Confirmed by James 2026-07-04 — added to the v2 new-program backlog rather than built now. |
| Regulatory Sandbox — Minnesota | MN | `deferred_to_v2` | Deferred to v2: IAALS lists this under "Programs Being Implemented" (not yet "Implemented") — pre-launch by the source's own classification, so no roster can exist yet. This is a distinct candidate program from the existing prog_mn_lp (paraprofessional pilot) already in v1 — do not conflate the two. Distinct from the Puerto Rico ABS gap below, which IAALS lists as already "Implemented." Confirmed by James 2026-07-04 — added to the v2 new-program backlog rather than built now. |
| Community-Based Justice Worker Models — Montana | MT | `deferred_to_v2` | Deferred to v2: community_justice_worker is defined in the v1 program_type taxonomy for forward compatibility, but no v1 scraper covers any CJW program. Confirmed by James 2026-07-04 — building CJW scrapers is out of scope for v1. |
| Allied Legal Professional — Oregon Licensed Paralegal Program | OR | `deferred_to_v2` | Deferred to v2: OSB Rules for Licensing Paralegals took effect 2025-01-01 but zero licenses had been issued as of 2026-06-29 research (first subject-matter exams not until 2026-08-28 / 2026-10-24); no roster or consumer-facing directory exists yet to scrape. Identified via direct manual research (validation/oregon_lp.md), NOT via the automated IAALS frame_reconcile check — alp_license programs are out of that check's scope (docs/methodology.md §10e). Confirmed by James 2026-06-29 — revisit after the first exam cohort is licensed (~September 2026 or later); see validation/oregon_lp.md "What to do when revisiting." |
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

**Note on provenance mix (this paragraph is outside the auto-generated block above, so it
survives future `make completeness` re-runs — anything inside `BEGIN`/`END frame_reconcile`
gets fully rewritten, not merged, on every run):** 14 of the 17 rows above were surfaced by
this module's automated cross-check in its first real run, 2026-07-01
(`detected_by=frame_reconcile`). The other 3 were added afterward: Oregon LP
(`detected_by=manual-oregon-research` — `alp_license` programs are out of this check's
scope by design, see §2 of `docs/methodology.md §10e`) and **two rows for the same
real-world item**, Alternative Business Structures — Washington, D.C.
(`detected_by=manual-dc-rule54-removal` and `detected_by=frame_reconcile` respectively).
The second D.C. row exists because the ledger's dedup key is `(item, jurisdiction,
detected_by)`: a live re-run on 2026-07-06 (during the pre-publication finalize pass)
surfaced this listing again as a fresh `unresolved` candidate, since its automated key
didn't match the manually-added row's key. Resolved the same way the same day — but this
**will keep recurring** on every future live run until that keying gap is fixed. Full
account: `docs/sampling_frame.md §6`.

## 2. Legislative-scan flags

_Not yet implemented — see `completeness/legislative_scan.py` (TODO)._

## 3. Within-program reconciliation

_Not yet implemented — see `completeness/within_program.py` (TODO)._
