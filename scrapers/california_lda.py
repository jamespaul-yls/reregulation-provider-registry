"""Scraper for the California Legal Document Assistant (LDA) program.

Source: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=6400.&lawCode=BPC
Fetch strategy: StaticFetcher (static HTML — statute page only)

Program status as of June 2026: ACTIVE (statute in force) but provider coverage = 0.

Background:
  California Business & Professions Code § 6400 et seq. (enacted 1999) requires LDAs to
  register with the county clerk in each county where they do business and post a $25,000
  bond. LDAs may assist self-represented litigants with document preparation only — no legal
  advice.

  There is no statewide LDA registry. Each of California's 58 counties maintains its own
  registration list. Some county clerks post PDFs; others require in-person lookup. The
  landscape is highly fragmented.

Why provider count is zero in v1:
  - No centralized state database or API exists.
  - 50-county scraping effort is out of scope for v1 (distinct sources × distinct formats).
  - The authorizing statute page is snapshotted to document the program's existence and
    legal basis.
  - Future v2 work: county-level scrapes for largest counties (LA, SF, San Diego, etc.).

Note on paralegal title rules (B&P Code § 6450):
  This is a title-protection statute (requires 3 years experience + continuing education
  to call oneself a "paralegal"), NOT a licensing or registration program with any registry.
  No roster of California paralegals exists. Covered separately if needed.

Note on ABS / sandbox:
  As of June 2026, California has no approved ABS or regulatory sandbox program. The
  State Bar's Board of Trustees rejected a proposed ABS framework in 2022. Covered
  separately if a new proposal advances.
"""

from __future__ import annotations

from models.schema import Provider, SourceSnapshot
from scrapers.base import BaseScraper
from scrapers.fetchers import StaticFetcher

_STATUTE_URL = (
    "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
    "?sectionNum=6400.&lawCode=BPC"
)


class CaliforniaLdaScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_ca_lda"
    source_url = _STATUTE_URL
    default_fetcher_class = StaticFetcher

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        # No statewide LDA registry exists — county-level registration under B&P Code
        # § 6400 et seq. is administered by 58 independent county clerks. Provider
        # scraping is deferred to v2 (county-level effort).
        return []
