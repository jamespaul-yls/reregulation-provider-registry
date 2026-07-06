# Sampling Frame — Reregulation Provider Registry v1.0.0

This document is the frame: what population of programs v1 claims to cover, what is
excluded and why, and the residual gaps surfaced by the completeness audit and their
disposition. It is the companion to `docs/methodology.md §1` (Scope) and
`docs/methodology.md §10e` (completeness-audit method) — read together they answer
"what should be in this dataset, and how do we know we didn't miss anything obvious."

**Version:** 1.0.0 · **Last updated:** 2026-07-04

---

## 1. What is in scope

The frame is every U.S. legal-services **reregulation program** — a formal regulatory
structure (court rule, statute, or administrative program) that authorizes a defined class
of entities or individuals to provide legal or law-adjacent services outside the
traditional lawyer-licensing regime. Concretely, a program is in-frame if it has:

1. A formal authorizing instrument (court rule, statute, or administrative order), and
2. A named regulator responsible for administering it (even if that regulator maintains no
   public roster — see `prog_dc_rule54` below).

## 2. In-scope programs (v1.0.0: 11 programs, 8 jurisdictions)

| program_id | Jurisdiction | program_type | program_status | Roster? |
|---|---|---|---|---|
| `prog_az_abs` | AZ | abs | active | yes |
| `prog_az_lp` | AZ | alp_license | active | yes |
| `prog_ca_lda` | CA | document_preparer | active | no (county-fragmented; see §3) |
| `prog_co_llp` | CO | alp_license | active | yes |
| `prog_dc_rule54` | DC | abs | active | no (permissive rule; see §3) |
| `prog_mn_lp` | MN | paraprofessional_pilot | active | yes |
| `prog_tx_alp` | TX | alp_license | paused | no (not yet effective; see §3) |
| `prog_ut_lpp` | UT | alp_license | active | yes |
| `prog_ut_sandbox` | UT | sandbox | active | yes |
| `prog_wa_entity_pilot` | WA | sandbox | active | **scraper live** — 0 authorized yet (see §3) |
| `prog_wa_lllt` | WA | alp_license | sunset | yes |

8 jurisdictions = 7 states (AZ, CA, CO, MN, TX, UT, WA) + DC. `prog_wa_entity_pilot`
resolves both the IAALS "WA ABS" and "WA sandbox" listings as one program (§6) — the same
pattern as `prog_ut_sandbox` for Utah.

## 3. Programs in-frame with zero providers — documented, not ambiguous

Four programs are correctly in-frame but contribute zero `provider` rows. Each has its own
`validation/<source>.md` with the full reasoning; summarized here so no zero reads as
"not checked":

| Program | Why zero | Detail |
|---|---|---|
| `prog_ca_lda` | Structural — no statewide registry | California LDA registration is county-level (58 independent county clerks, no consolidated roster). Scraping all 58 is deferred to v2. The statute page (§6400 et seq.) is snapshotted to document the program's legal basis. |
| `prog_dc_rule54` | Structural — permissive ethics rule, no roster | D.C. Rule 5.4(b) requires no registration, application, or regulator notice. No roster exists to scrape. The rule page is snapshotted so the "why it's zero" claim is itself immutably captured (not just asserted). |
| `prog_tx_alp` | Temporal — program not yet effective | Rules received preliminary approval (2024-08-06) but the effective date was indefinitely delayed (2024-11-04, Misc. Docket 24-9095). No roster exists because the licensing category is not yet live. The Texas Bar program page is snapshotted; re-run `scripts/run_tx_alp.py` when a new effective date is set. |
| `prog_wa_entity_pilot` | Temporal — no applicant authorized yet | 4 entities have applied under WA Supreme Court Order 25700-B-721; all 4 are "Under Review" as of 2026-07-04. The full applicant list (with status) is snapshotted; re-run `scripts/run_wa_entity_pilot.py` periodically to detect the first authorization. See `validation/washington_entity_pilot.md` for the flagged v2 decision on tracking pre-authorization applicant status (our `current_status` enum has no "pending" value). |

## 3a. A candidate program researched and deferred — no program row at all

The four programs in §3 at least have a `program` row (zero providers, but the program's own
authorizing source is captured). One candidate program doesn't even get that: **Oregon
Licensed Paralegal Program (OR, `alp_license`)**, named as a source to verify in `CLAUDE.md`
and `reregulation-registry-v1-spec.md`, was researched on 2026-06-29
(`validation/oregon_lp.md`) and found to have issued **zero licenses** — the Rules for
Licensing Paralegals took effect 2025-01-01, but the first subject-matter exams aren't until
2026-08-28 (Family Law) and 2026-10-24 (Landlord-Tenant), and no roster or consumer-facing
directory exists yet. No `prog_or_lp` row was created for v1.

This section exists because that decision previously lived only in `validation/oregon_lp.md`
— absent from this document, which `docs/methodology.md §1` calls "the authoritative
statement of exactly which programs are in scope for v1." It's now also
recorded in the same ledger as every other scope decision:
`validation/residual_gaps.csv` (`detected_by=manual-oregon-research`, distinct from the
automated `frame_reconcile` rows below, since `alp_license` programs are outside that
check's scope — see §6 and `docs/methodology.md §10e`).

**Why this isn't in §3 alongside TX ALP:** TX ALP already has a formally-adopted rule with
a docket number pausing it (Misc. Docket 24-9095) and an authorizing regulator actively
administering a paused program — enough of an institutional footprint to warrant a
`program` row documenting that legal basis even at zero providers. Oregon's rule is newer
and has issued literally nothing yet — no applicants, no pending roster, no rejected
applications — so there's no comparable "authorizing instrument in active administration"
to document with a stub row. This is a judgment call, revisit-able the same way TX ALP is;
flagging the reasoning explicitly here rather than leaving it implicit.

**Revisit:** after the first exam cohort is licensed (expected September 2026 or later) —
see `validation/oregon_lp.md` "What to do when revisiting" for the specific re-check steps.

## 4. Excluded from the frame, by design

- **Traditional law firms and traditional bar licensees.** The frame is reregulation
  programs specifically; ordinary bar-licensed practice is the baseline the registry
  measures departures from, not a subject of its own rows.
- **Unlicensed document preparers with no formal license class.** In scope only where a
  jurisdiction has created a document-preparer license class with regulatory oversight
  (California LDA — see §3). Unregulated "document prep" services with no license class
  anywhere are out of frame entirely; there is no regulator and no roster to reconcile
  against.
- **Passive rule waivers with no regulator and no accompanying roster.** DC Rule 5.4(b) is
  the boundary case: it has a named regulator (DC Court of Appeals / DC Bar) and a formal
  rule, so it is in-frame with a documented zero (§3). A hypothetical waiver with no
  regulator at all would be excluded outright.

## 5. Territory scope

v1's frame is not restricted to the 50 states + DC by design (`JurisdictionStr` in
`models/schema.py` accepts any USPS two-letter code, including territories), but v1 does
not independently survey U.S. territories for candidate programs. The only territory
signal in the frame-reconciliation check (§6) is Puerto Rico (IAALS lists an ABS-type
program there); it is deferred to v2 (§6). Guam, American Samoa, the Northern Mariana
Islands, and the U.S. Virgin Islands were not checked against any external inventory in
v1 — this is a known residual gap, not a finding of "no programs exist" there.

## 6. Completeness-audit residual gaps (15 items in the ledger, 100% resolved)

`make completeness` (`completeness/frame_reconcile.py`) cross-checks the `program` table
against the IAALS Unlocking Legal Regulation knowledge center — the closest thing to an
authoritative external inventory of reregulation programs. It surfaced 14 candidate gaps
(programs IAALS lists as "Implemented" or "Being Implemented" with no matching row in our
`program` table, plus the reverse check for our own program types IAALS enumerates
thoroughly). The full ledger lives in `validation/residual_gaps.csv`; every row is now
resolved:

| Disposition | Count | Items |
|---|---|---|
| `intentionally_excluded` | 2 | UT ABS — covered by `prog_ut_sandbox`; WA ABS — covered by `prog_wa_entity_pilot` (in both cases, one sandbox-type pilot grants ABS-style relief too, so a separate ABS program row would double-count the same providers) |
| `resolved_built` | 1 | WA sandbox — `prog_wa_entity_pilot` was built 2026-07-04 (`scrapers/washington_entity_pilot.py`), matching this listing directly; the completeness check no longer even surfaces it as a fresh candidate |
| `deferred_to_v2` — new-program backlog | 3 | IN sandbox, MN sandbox (distinct from the existing `prog_mn_lp` paraprofessional pilot) — both IAALS "Programs Being Implemented" (pre-launch by the source's own classification, so no roster can exist yet); PR ABS — IAALS "Implemented Programs" (unlike IN/MN, a program plausibly already operates — the open question is whether a public registry exists to scrape, not whether it has launched) |
| `deferred_to_v2` — CJW taxonomy gap | 8 | Community-Based Justice Worker Models in AK, AZ, DC, DE, HI, IL, MT, and UT (via its sandbox) — `community_justice_worker` exists in the v1 `program_type` enum for forward compatibility, but no v1 scraper covers any CJW program |

That's 14 rows, all surfaced by the automated IAALS cross-check (`detected_by=frame_reconcile`).
The ledger carries a **15th row** the automated check cannot see at all: Oregon LP
(`deferred_to_v2`, `detected_by=manual-oregon-research`) — `alp_license` programs are
outside this check's scope by design (bullet 2 of `docs/methodology.md §10e`), so this row
was added from direct manual research instead. See §3a above and `validation/oregon_lp.md`.

**None of the 15 are open.** The WA rows were resolved 2026-07-04 by building
`prog_wa_entity_pilot`; the CJW/new-program-backlog rows were resolved 2026-07-04 by James
Paul as an explicit v1 scope decision, not a default of the audit tool
(`completeness/frame_reconcile.py` always writes new candidates as `unresolved` — it
proposes, it does not decide; see the module docstring and `completeness/ledger.py`); the
Oregon row was resolved 2026-06-29, the date of the research in `validation/oregon_lp.md`.

Re-running `make completeness` will not re-open any of these: the ledger merge is keyed on
`(item, jurisdiction, detected_by)` and never overwrites a row that already exists,
mirroring the `crosswalk_courtlistener` "verified rows are immutable" rule. Oregon's row
uses a `detected_by` the automated tool never writes (`manual-oregon-research`), so it can
never collide with — or be silently regenerated by — a future `frame_reconcile` run either.

---

## 7. What this frame does not attempt

Per `docs/methodology.md §12h`, the frame answers "which programs and providers exist,"
not "what did they do" or "did they cause harm." See methodology.md for the full list of
explicit v1 deferrals (outcomes, rates, harm measures, litigation linkage).
