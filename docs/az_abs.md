# Source Notes — Arizona Alternative Business Structures

## Overview

| Field | Value |
|---|---|
| Program | Arizona Alternative Business Structures (ABS) |
| Program ID | `prog_az_abs` |
| Regulator | Arizona Supreme Court, Certification & Licensing Division |
| Authorizing rule | ACJA §7-209; AZ Sup. Ct. Rule 33.1 |
| Launch date | 2021-01-01 |
| Scraper | `scrapers/arizona_abs.py` |
| Fetch strategy | Static HTML (`httpx`) — no JavaScript rendering required |

---

## Source URLs

| Purpose | URL | Stability |
|---|---|---|
| ABS Directory (roster) | https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory | Stable — has been at this path since at least 2021 |
| Program landing page | https://www.azcourts.gov/cld/Alternative-Business-Structure | Stable |
| Authorizing rule (PDF) | https://www.azcourts.gov/Portals/0/0/admcode/pdfcurrentcode/7-209%20Alternative%20Business%20Structures%2003_2026.pdf | Versioned — URL changes with each rule amendment |

---

## Robots.txt

**Checked:** 2026-06-28
**Result:** Compliant — `/cld/` path is not disallowed.

Relevant disallow rules (none apply to our path):
```
Disallow: /*/ctl/
Disallow: /admin/
Disallow: /Activity-Feed/userId/
Disallow: /Password-Reset/userid/*
```

The ABS Directory at `/cld/Alternative-Business-Structure/Directory` is fully permitted.

---

## Terms of Use

**Checked:** 2026-06-28
**URL:** https://www.azcourts.gov/terms
**Result:** Compliant — no prohibition on automated access to public records.

Relevant clauses and our compliance:

| Clause | Our compliance |
|---|---|
| "may not overburden or impair the site" | 1 HTTP GET per scrape run; `sleep(1.0)` before request |
| "means not intentionally made available" | The ABS Directory is a publicly published regulatory roster, intentionally available |
| No explicit prohibition on automated/bulk access | N/A — not prohibited |

This is a public government records page served under a generic DNN CMS terms template.
The ABS roster is a regulatory disclosure, not proprietary data.

---

## Page structure

- **Format:** Single static HTML page; one `<table>` element.
- **Columns:** Status | License Name | Business Information | Counties Served | Practice Areas
- **Pagination:** None — all rows on one page.
- **JavaScript required:** No — full table present in initial HTML response.
- **Authentication required:** No.

As of 2026-06-28: **167 rows** (160 Active, 7 Inactive).

---

## Field availability

| Field | Available | Notes |
|---|---|---|
| `legal_name` | ✅ | "License Name" column; verbatim text |
| `current_status` | ✅ | "Status" column: Active → `active`, Inactive → `exited` (bootstrap; see methodology.md §4a) |
| `practice_areas_raw` | ✅ partial | "Practice Areas" column; populated in 31/167 rows as of first scrape |
| `website` | ✅ partial | External `<a href>` in "Business Information" cell; 25/167 rows |
| `authorization_date` | ❌ | Not published on the roster |
| `ownership_structure` | ❌ | Not published |
| `uses_technology` / `uses_ai` | ❌ | Not published |

---

## Known data quality issues

### Sophos security-proxy URLs
Some provider website `<a href>` values are wrapped in a Sophos gateway URL
(`https://us-west-2.protection.sophos.com?d=<domain>&u=...`). The scraper captures
the literal href (correct per provenance rules). The canonical domain is recoverable
from the `d=` query parameter if needed.

Affected as of 2026-06-28: at least 1 provider (Bergman Basha, LLC). See
`validation/arizona_abs.md` §3.

### Cloudflare email obfuscation
All email addresses are rendered as Cloudflare `/cdn-cgi/l/email-protection#…` hrefs.
The scraper skips these (correct — they are not http/https URLs and cannot be decoded
client-side without JavaScript execution). Email addresses are not captured.

### Counties Served column
Not captured — not in the registry schema. The column contains values like
"All Arizona Counties", "Maricopa", "Pima". Dropped silently.

---

## Update frequency

The Arizona Supreme Court updates the roster on an irregular basis as new ABS licenses
are granted or revoked. Based on observation, changes occur on a weekly-to-monthly
cadence. Recommend scraping **weekly** once M3 (longitudinal) is active.

---

## Backfill

No Wayback Machine backfill has been attempted for AZ ABS. The program launched
2021-01-01. Historical captures exist on the Wayback Machine at
`https://web.archive.org/web/*/https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory`.
Backfill is deferred to M3.

---

## Related sources (future)

- **Arizona LP roster** — `scrapers/arizona_lp.py` (not yet implemented). ACJA §7-210.
  Individuals, not entities. Same regulator, different path on azcourts.gov.
- **Arizona State Bar discipline** — discipline orders are published by the AZ Supreme
  Court and the State Bar. Relevant for v2 outcomes layer. Check ToS before bulk access.
