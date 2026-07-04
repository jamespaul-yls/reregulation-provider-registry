"""Scraper for the Texas Licensed Legal Paraprofessionals and Licensed Court-Access
Assistants (LLPCA) program.

Source: https://www.texasbar.com/paraprofessionals/
Fetch strategy: StaticFetcher (static HTML — program-status page only)

Program status as of June 2026: PAUSED
  - Texas Supreme Court preliminary approval: August 6, 2024 (Misc. Docket No. 24-9050)
  - Original effective date: December 1, 2024
  - Delay order: November 4, 2024 (Misc. Docket No. 24-9095) — effective date postponed
    "in order to give due consideration to the comments received"
  - No new effective date as of June 2026
  - No individual roster exists

This scraper snapshots the program-status page to document the program's state over
time. parse() returns [] because no licensees have been issued. When the program
eventually goes effective and the State Bar of Texas publishes a roster, this scraper
will be extended to parse it.

Practice areas (when effective): family law, estate planning/probate, consumer debt,
justice court.
"""

from __future__ import annotations

from models.schema import Provider, SourceSnapshot
from scrapers.base import BaseScraper
from scrapers.fetchers import StaticFetcher

_PROGRAM_URL = "https://www.texasbar.com/paraprofessionals/"


class TexasAlpScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_tx_alp"
    source_url = _PROGRAM_URL
    default_fetcher_class = StaticFetcher
    default_timeout = 90.0  # texasbar.com is slow; give it time
    default_retries = 3  # retry up to 3 times with exponential backoff

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        # No individual roster exists — program is paused pending further Texas Supreme
        # Court order. Delay order: Misc. Docket No. 24-9095 (November 4, 2024).
        # Return empty list; extend when a live roster is published.
        return []
