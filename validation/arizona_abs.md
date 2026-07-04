# Validation — Arizona ABS Roster

**Source:** Arizona Supreme Court ABS Directory
**URL:** https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory
**Scraper:** `scrapers/arizona_abs.py` v0.1.0
**Snapshot:** `snap_9f99d17bf219186a` (sha256 `9f99d17bf219186a5c737177dbc3f9d2d92d924826dc5a687eeb7130b5fe1473`)
**Retrieved:** 2026-06-28T22:04 UTC
**Validated:** 2026-06-28

---

## 1. Completion

- `ruff check .` — clean
- `pytest` — 115/115 passing (including 25 tests in `test_arizona_abs.py`)
- `scripts/run_az_abs.py` — runs without error; exports CSV + Parquet

---

## 2. Comprehensiveness (coverage / recall)

The source page states no explicit total, but the table contains all rows on a single
non-paginated page. Row count from the rendered table is the authoritative total.

| Metric | Count |
|---|---|
| Rows in source table | 167 |
| Rows parsed | 167 |
| Coverage | **100.0%** |
| Active (source) | 160 |
| Active (parsed) | 160 |
| Inactive (source) | 7 |
| Inactive → exited (parsed) | 7 |

No pagination, no JS-gated content — single static table, full capture confirmed.

---

## 3. Accuracy (precision)

### Sample design

Stratified random sample, seed 42, drawn 2026-06-28:
- 10 rows from the 160 Active population
- 7 rows from the 7 Inactive population (100% of stratum)
- **Total: 17 rows (10.2% of 167)**

Minimum required: ≥15 rows or 10% — satisfied.

Verification method: compared parsed field values against the raw HTML fixture
(`az_abs_roster_snap1.html`) cell-by-cell. Fields checked: `legal_name`,
`current_status`, `practice_areas_raw`, `website`.

### Sample

| # | provider_id | legal_name | status parsed | pa parsed | website parsed |
|---|---|---|---|---|---|
| 1 | prov_az_abs_a43fc0352964 | Boundless Legal, LLC | active | [] | None |
| 2 | prov_az_abs_4672fea78df2 | All Access Advocates, LLC | active | [] | None |
| 3 | prov_az_abs_9432c63a9ad3 | Hunterbrook Law, LLC | active | [] | None |
| 4 | prov_az_abs_3cde12dc3378 | Genesis Legal Group, LLC (Formerly, HFC Legal, LLC) | active | [] | https://genesislegalgroup.com |
| 5 | prov_az_abs_9d2c5eb8be70 | Family Office Advisory, LLC | active | [] | None |
| 6 | prov_az_abs_bb525a80fa26 | Colexit Law, PLLC | active | [] | None |
| 7 | prov_az_abs_2dce6cb9f12d | BLS Law, LLC | active | [] | None |
| 8 | prov_az_abs_a366e5865ee5 | Sterling Shield Legal, LLC | active | [] | None |
| 9 | prov_az_abs_3bee264c2411 | Bergman Basha, LLC | active | ["Civil Litigation"] | ⚠ see note |
| 10 | prov_az_abs_e4e62f606aea | Turquoise Law Group, PLLC | active | [] | None |
| 11 | prov_az_abs_08054cf441e1 | Cactus Blossom Legal, LLC | exited | [] | None |
| 12 | prov_az_abs_aab707992d29 | Consumer Defense Partners, LLC | exited | [] | None |
| 13 | prov_az_abs_cf7f2670d3b0 | Corporate Immigration Attorneys, LLC | exited | ["Immigration Legal Services"] | None |
| 14 | prov_az_abs_7ed89e1f142e | Greenlight Path, Inc | exited | [] | None |
| 15 | prov_az_abs_22931e3112aa | Inmigracion Al Dia AZ, PLLC (DBA Amigos Al Dia) | exited | [] | None |
| 16 | prov_az_abs_66acb9660c35 | KWP Estate Planning, LLC (Keystone Wealth Partners) | exited | [] | None |
| 17 | prov_az_abs_3bfceaab78b9 | Trademarkia Venture Partners | exited | [] | None |

### Field-level error rates

| Field | Errors | Error rate | Target |
|---|---|---|---|
| `legal_name` | 0 / 17 | 0% | 0% ✓ |
| `current_status` | 0 / 17 | 0% | 0% ✓ |
| `practice_areas_raw` | 0 / 17 | 0% | — ✓ |
| `website` | 0 / 17\* | 0%\* | — ✓\* |

\* See known data quality issue below.

### Known data quality issues

**Row 9 — Bergman Basha, LLC — Sophos proxy URL**

The `<a href>` in the source HTML for this entity is a Sophos security-gateway redirect
URL, not the canonical domain. The scraper correctly captures what the source HTML contains.
The rendered link text reads "www.bergmanbasha.com" but the actual href is:

```
https://us-west-2.protection.sophos.com?d=bergmanbasha.com&u=...
```

This is a source-side issue (the regulator's CMS wrapped the URL in a security proxy).
The scraper behavior is correct — capturing the literal href is the only defensible
choice given provenance rules. The canonical URL (`www.bergmanbasha.com`) can be
recovered from the `d=` query parameter if needed in a later normalization pass.

**No authorization dates**

The roster does not publish authorization/license dates. All 167 rows have
`authorization_date = None`. This is a source limitation, not a scraper error.
Dates may be recoverable from annual committee reports (PDFs) in a future pass.

**Cloudflare email obfuscation**

All email addresses are rendered as Cloudflare `/cdn-cgi/l/email-protection#…` URLs.
These are not captured. This is expected behavior — the scraper explicitly skips
non-http(s) hrefs.

---

## 4. Open items

- [ ] Recover authorization dates from annual ABS committee reports (PDF backfill)
- [ ] Normalize Sophos-proxied website URLs to canonical domains
- [ ] Manual spot-check of 3 rows against the live site to confirm no scraper drift
  since snapshot clwas taken (identity fields only)
