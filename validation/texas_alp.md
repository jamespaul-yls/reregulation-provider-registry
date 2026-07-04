# Validation: Texas Licensed Legal Paraprofessionals and Licensed Court-Access Assistants

**Source:** https://www.texasbar.com/paraprofessionals/
**Scraper:** `scrapers/texas_alp.py` v0.1.0
**Fixture:** `tests/fixtures/tx_alp_program_snap1.html`
**Fixture sha256:** `d043c95a4aac2571479c7f5226188d6e15e76691a0cf2371dce2835bb7b31bdf`
**Scrape date:** 2026-06-29

---

## Program background

The Texas Supreme Court issued preliminary approval of rules creating two new license
categories on **August 6, 2024** (Misc. Docket No. 24-9050):

- **Licensed Legal Paraprofessional (LLP)** — provides limited legal services in
  family law, estate planning/probate, consumer debt, and justice court matters.
- **Licensed Court-Access Assistant (LCAA)** — assists pro se litigants in court
  proceedings.

The original effective date was **December 1, 2024**. On **November 4, 2024**, the
Court issued Misc. Docket No. 24-9095, delaying the effective date indefinitely
"in order to give due consideration to the comments received" during the public comment
period (deadline: November 1, 2024).

**As of June 2026, no new effective date has been announced.** The program is classified
as `paused`.

### Rulemaking docket

| Date | Docket | Action |
|---|---|---|
| 2024-08-06 | Misc. Docket 24-9050 | Preliminary approval; effective date 2024-12-01 |
| 2024-11-04 | Misc. Docket 24-9095 | Effective date delayed pending further order |
| *TBD* | *TBD* | *Final effective date — not set as of 2026-06-29* |

### Source URLs

- Texas Bar program page: `https://www.texasbar.com/paraprofessionals/`
- Preliminary approval order (PDF): `https://www.txcourts.gov/media/1458990/249050.pdf`
- txcourts.gov news: `https://www.txcourts.gov/supreme/news/supreme-court-advances-access-to-justice-efforts-with-proposed-new-rules-to-license-legal-paraprofessionals/`
- Delay announcement: `https://blog.texasbar.com/2024/11/articles/texas-supreme-court/supreme-court-delays-effective-date-of-proposed-rules-governing-licensed-legal-paraprofessionals/`

---

## Comprehensiveness (coverage / recall)

| Category | Count |
|---|---|
| Source-stated total | 0 (no roster published; program not yet effective) |
| Entries parsed | 0 |
| **Coverage** | **N/A (0/0)** |

No individual roster exists. The Texas Bar's paraprofessionals page as of 2026-06-29
contains program information only — no licensee list.

### Monitoring for roster publication

When the program goes effective, the State Bar of Texas will administer licensing. The
likely location for a future roster is `https://www.texasbar.com/paraprofessionals/` or
a linked licensee-lookup page. Re-run `scripts/run_tx_alp.py` to snapshot the page and
detect structural changes.

---

## Accuracy (precision)

Not applicable — zero provider rows produced.

The program row itself was verified against primary sources:

| Field | Value | Source verified? |
|---|---|---|
| `program_name` | Texas Licensed Legal Paraprofessionals and Licensed Court-Access Assistants | ✓ Docket 24-9050 |
| `program_status` | `paused` | ✓ Docket 24-9095 (delay order) |
| `launch_date` | `None` | ✓ Program never became effective |
| `regulator` | State Bar of Texas | ✓ Docket 24-9050 assigns licensing to SBOT |
| `authorizing_rule` | Docket 24-9050 + 24-9095 citations | ✓ |
| `program_type` | `alp_license` | ✓ Individual licensing scheme |
| `allows_upl_waiver` | `True` | ✓ Authorizes limited legal services by non-attorneys |
| `allows_nonlawyer_ownership` | `False` | ✓ No ABS structure proposed |

---

## Known limitations and methodological notes

### 1. `program_status = paused` vs. `proposed`

The rules have received preliminary (not final) Supreme Court approval, distinguishing
this from a purely proposed program. "Paused" reflects that the rules exist and were
nearly effective but implementation was halted. If the Court withdraws the preliminary
approval, change to `proposed`.

### 2. Program name vs. user-facing naming

The program is formally called "Licensed Legal Paraprofessionals and Licensed
Court-Access Assistants" — not "Allied Legal Professionals" or "ALP." The file and
program_id use "alp" for brevity and consistency with the user's requested naming
convention, but the `program_name` field carries the formal name.

### 3. Practice areas

Proposed practice areas (from preliminary approval order): family law, estate
planning and probate, consumer debt, and justice court matters. These may change
when the final rules are issued.

### 4. No `launch_date` set

`launch_date = None` because the program has not gone into effect. Set this field
when the Court issues a final effective date.

### 5. Comments received

The public comment period (open August–November 2024) generated substantial response.
The delay order indicates the Court is actively reconsidering the rules. The program
may be amended, re-proposed, or withdrawn. Monitor txcourts.gov and texasbar.com.
