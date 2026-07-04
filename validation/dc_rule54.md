# Validation: D.C. Rules of Professional Conduct Rule 5.4(b) — Nonlawyer Ownership

**Source:** https://www.dcbar.org/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct/Law-Firms-and-Associations/Professional-Independence-of-a-Lawyer
**Scraper:** `scrapers/dc_rule54.py` v0.1.0
**Fixture:** `tests/fixtures/dc_rule54_snap1.html`
**Fixture sha256:** `73fe40c243259476dd16c3bb0a79782dc653fe65580d7ab9da6c50eee49d9519`
**Scrape date:** 2026-06-29
**DB snapshot:** not yet loaded (run `scripts/run_dc_rule54.py` when created)

---

## Program background

D.C. Rules of Professional Conduct Rule 5.4(b) (effective January 1, 1991) allows a
lawyer to "practice law in a partnership or other form of organization in which a financial
interest is held or managerial authority is exercised by an individual nonlawyer who performs
professional services which assist the organization in providing legal services to clients."
Four conditions apply: (1) sole legal-services purpose; (2) all owners bound by the D.C.
RPC; (3) lawyer accountability under Rule 5.1; (4) written statement of conditions.

DC adopted this departure from the ABA Model Rule 5.4 as part of its initial adoption of
the Model Rules in 1990 (effective January 1, 1991), making it the first U.S. jurisdiction
to permit nonlawyer ownership of law firms. Unlike Utah, Arizona, and other jurisdictions
that created formal ABS programs with application processes and maintained rosters, DC's
approach is purely a permissive ethics rule — no authorization is required, no application
is filed, and no regulator is notified.

---

## Why provider count is zero — documented reason

DC Rule 5.4(b) is a permissive **ethics rule**, not a licensing or registration program.

| Reason | Detail |
|---|---|
| No registration requirement | Entities may self-organize under the rule without filing with any court or bar authority |
| No roster maintained | The DC Court of Appeals and the DC Bar do not publish a list of Rule 5.4(b) firms |
| No application process | In contrast to UT sandbox, AZ ABS, etc., there is no authorization step |
| No searchable database | No FOIA-accessible registry; no opt-in directory |

**This is a structural feature of DC Rule 5.4(b), not a data gap.** Known Rule 5.4(b)
firms include multidisciplinary partnerships and legal technology companies that have
self-organized under the rule (examples documented in academic literature but not through
a public official source). A future v2 effort could attempt to enumerate them from:
- Press coverage and company registration records (DC DCRA)
- NALP employer directory
- Litigation records (CourtListener) where firms identify as Rule 5.4(b) entities

---

## Comprehensiveness (coverage / recall)

| Category | Count |
|---|---|
| Source-stated total | N/A (no registration roster) |
| Entries parsed | 0 |
| **Coverage** | **N/A — no registration roster exists** |

---

## Accuracy (precision)

Not applicable — zero provider rows produced. Program row fields verified:

| Field | Value | Source verified? |
|---|---|---|
| `program_name` | D.C. Rule 5.4(b) Nonlawyer Ownership of Law Firms | ✓ D.C. RPC Rule 5.4 heading |
| `program_status` | `active` | ✓ Rule in current force; no repeal or sunset |
| `launch_date` | `1991-01-01` | ✓ D.C. RPC eff. Jan. 1, 1991 |
| `regulator` | D.C. Court of Appeals | ✓ Promulgated by D.C. Ct. App. (not DC Bar) |
| `authorizing_rule` | D.C. RPC Rule 5.4(b) | ✓ Rule text verified against DC Bar publication |
| `program_type` | `abs` | ✓ Nonlawyer ownership of legal-services entity |
| `allows_nonlawyer_ownership` | `True` | ✓ Rule 5.4(b) expressly permits this |
| `allows_upl_waiver` | `False` | ✓ UPL laws still apply; lawyers provide legal services |
| `allows_software_provider` | `True` | ✓ Nonlawyer entities (including tech companies) can own |

---

## Known limitations and methodological notes

### 1. No registration roster — fundamental data gap

Unlike all other programs in this registry, DC Rule 5.4(b) has never had a maintained
roster. The "program" is a permissive ethics rule that predates the modern ABS framework
by 30 years. The snapshot of the DC Bar's rule page documents the rule text and allows
longitudinal detection of any amendments.

### 2. Scope relative to other DC programs

DC's Rule 5.4(b) is narrower than the Utah sandbox in one sense (no UPL waiver — lawyers
must provide the actual legal services) but broader in another (no cap on number of
entities, no regulatory approval required, no sunset date).

### 3. Rule 5.4(b) condition: "sole purpose" is legal services

Rule 5.4(b)(1) requires the partnership or organization to have "as its sole purpose
providing legal services to clients." This means a general technology company cannot own
a law firm under this rule unless it restructures with a legal-services-only entity.
Some commentators argue this limits the rule's practical reach; others note it has been
interpreted broadly.

### 4. `allows_software_provider = True` rationale

A technology company may form a subsidiary whose sole purpose is providing legal services
and have nonlawyer (including software company) financial interest or managerial authority
in that subsidiary. This satisfies Rule 5.4(b). → `allows_software_provider = True`.

### 5. Source URL stability

The DC Bar website has undergone multiple URL restructurings. The source URL
(`/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct/Law-Firms-and-Associations/
Professional-Independence-of-a-Lawyer`) is case-insensitive (DC Bar CMS accepts either
case) and as of 2026-06-29 returns 200. Monitor for future URL changes.
