# Validation: Oregon Licensed Paralegal (LP) Program

**Status: DEFERRED — no licensees exist as of 2026-06-29**  
**Revisit after: 2026-08-28 (first Family Law exam) / 2026-10-24 (first Landlord-Tenant exam)**  
**Researched:** 2026-06-29

---

## Finding

The Oregon LP program has **not yet issued any licenses** as of the research date. No scraper
was written; no data exists to validate.

---

## Evidence

### 1. Program is in pre-launch state

The OSB LP home page (`https://www.osbar.org/lp`) says:

> *"We look forward to welcoming these new providers into the bar and the legal profession."*

Future tense. The Rules for Licensing Paralegals took effect January 1, 2025. Applications
are currently being accepted, but licensing requires passing a subject matter exam (or
completing a portfolio track assessment).

### 2. No pending LP applicants visible

The OSB admissions page (`https://www.osbar.org/admissions`) has an "Oregon Licensed
Paralegals" section with an empty applicant list:

```html
<h4>Oregon Licensed Paralegals</h4>
<p><strong>The following names will expire on Sunday, May 3, 2026:</strong></p>
<dir><p></p></dir>
```

Zero names. No LP applications currently pending in the public-facing admissions system.

### 3. First exams are upcoming, not past

The OSB LP home page lists upcoming exam dates:

| Exam | Date | Application Deadline |
|---|---|---|
| Family Law Subject Matter Exam | August 28, 2026 | June 29, 2026 |
| Landlord-Tenant Subject Matter Exam | October 24, 2026 | August 17, 2026 |

These are the next scheduled exams. Whether prior cohorts have sat for exams is unknown,
but if any licensees were admitted through the exam track, they would have appeared in the
admissions page and the admissions page is empty.

### 4. No LP-specific directory exists

The general OSB member search (`https://www.osbar.org/members/membersearch.asp`) has no
license-type filter — only last name, first name, bar number, city. All license categories
(attorneys, LPs, SPPE, etc.) are mixed together with no way to programmatically filter to
LP-only results.

No LP-specific roster URL exists. All candidate paths (`/lp/roster`, `/lp/directory`,
`/lp/licensed`, `/members/lpsearch.asp`) return 404.

No consumer-facing "Find an LP" page exists.

### 5. LP profile format unknown

Because no LP licensees were found in the directory, the format of an LP member profile
(specifically: whether the `Status` field distinguishes "Licensed Paralegal - Active" from
"Active" attorney status) could not be verified.

---

## What to do when revisiting

After the August 28, 2026 Family Law exam cohort is licensed (expected: September 2026 or
later, after character/fitness review):

1. **Re-check the admissions page** (`osbar.org/admissions`) to see if LP names appear.
2. **Re-check the LP home page** for a newly added "Find an LP" consumer directory.
3. **Probe the member search** with known LP bar numbers (if published in OSB news or the
   admissions page). Compare the member profile `Status` field to see how LP status is
   displayed vs. attorney status.
4. **If LP members are distinguishable in the general directory**: implement
   `scrapers/oregon_lp.py` using `HeadlessFetcher` (Playwright), fetch all members matching
   LP-type status, and parse into Provider rows: `provider_type=individual`,
   `program_id=prog_or_lp`, capturing `legal_name`, `authorization_date` (= admit date if
   shown), `practice_areas_raw` (family law and/or landlord-tenant, per endorsement area).
5. **If a separate LP directory is published**: use that as the source URL instead.

---

## Program metadata (for future `prog_or_lp` row)

| Field | Value |
|---|---|
| `program_id` | `prog_or_lp` |
| `jurisdiction` | `OR` |
| `program_name` | Oregon Licensed Paralegal Program |
| `program_type` | `alp_license` |
| `regulator` | Oregon State Bar |
| `regulator_url` | `https://www.osbar.org/lp` |
| `authorizing_rule` | Rules for Licensing Paralegals (RLPs), eff. January 1, 2025; Oregon Supreme Court |
| `launch_date` | 2025-01-01 (rules effective; first licenses TBD) |
| `program_status` | `active` (accepting applications) |
| `allows_nonlawyer_ownership` | False (individual licensees only) |
| `allows_upl_waiver` | True (LPs perform limited legal services in family law / landlord-tenant) |
| `allows_software_provider` | False |
| `practice_areas` | Family Law; Landlord-Tenant (Residential only) |

---

## Source URLs researched

- LP program home: `https://www.osbar.org/lp`
- LP FAQ: `https://www.osbar.org/lp/faq.html`
- LP About: `https://www.osbar.org/lp/about.html`
- LP Apply: `https://www.osbar.org/lp/apply.html`
- OSB Admissions: `https://www.osbar.org/admissions`
- OSB Member Search: `https://www.osbar.org/members/membersearch_start.asp`
- Rules PDF: `https://www.osbar.org/_docs/rulesregs/RulesforLIcensingParalegals.pdf`
- Paraprofessional committee site: `https://paraprofessional.osbar.org/`
