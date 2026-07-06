"""Scraper for the Arizona ABS (Alternative Business Structure) roster.

Source: https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory
Static HTML table — no JavaScript rendering required.

Column order: Status | License Name | Business Information | Counties Served | Practice Areas

Notes:
- Authorization date: not published on the roster; all rows get None.
- Counties Served: not in the registry schema; silently dropped.
- Emails: Cloudflare-obfuscated (/cdn-cgi/l/email-protection#…); not captured.
- current_status is seeded from the roster's Status column for snapshot 1
  (Active → active, Inactive → exited). See docs/methodology.md §AZ-ABS.
"""

from __future__ import annotations

import hashlib

from selectolax.parser import HTMLParser

from models.enums import CurrentStatus, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper

# Minimum rows we expect; raise if the page structure has changed.
_MIN_EXPECTED_ROWS = 50


def _provider_id(legal_name: str) -> str:
    digest = hashlib.sha256(f"prog_az_abs\x00{legal_name}".encode()).hexdigest()
    return f"prov_az_abs_{digest[:12]}"


def _map_status(text: str) -> CurrentStatus:
    t = text.strip().lower()
    if t == "active":
        return CurrentStatus.active
    if t == "inactive":
        return CurrentStatus.exited
    return CurrentStatus.unknown


def _extract_website(cell: object) -> str | None:
    """Return the first external http(s) link in the business-info cell."""
    for a in cell.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if href.startswith(("http://", "https://")):
            return href
    return None


def _extract_practice_areas(cell: object) -> list[str]:
    text = cell.text(strip=True)
    if not text:
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


_URL = "https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory"


class ArizonaAbsScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_az_abs"
    source_url = _URL

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        tree = HTMLParser(raw)
        table = tree.css_first("table")
        if table is None:
            raise ValueError(
                "AZ ABS roster: expected <table> not found — page structure may have changed"
            )

        rows = table.css("tr")[1:]  # skip header row
        if len(rows) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"AZ ABS roster: only {len(rows)} rows found (expected ≥ {_MIN_EXPECTED_ROWS}) "
                "— page structure may have changed"
            )

        providers: list[Provider] = []
        for row in rows:
            cells = row.css("td")
            if len(cells) < 2:
                continue

            legal_name = cells[1].text(strip=True)
            if not legal_name:
                continue

            current_status = _map_status(cells[0].text(strip=True))
            website = _extract_website(cells[2]) if len(cells) > 2 else None
            practice_areas_raw = _extract_practice_areas(cells[4]) if len(cells) > 4 else []

            providers.append(
                Provider(
                    provider_id=_provider_id(legal_name),
                    program_id=self.program_id,
                    provider_type=ProviderType.entity,
                    legal_name=legal_name,
                    normalized_name=normalize_name(legal_name),
                    jurisdiction="AZ",
                    authorization_date=None,
                    current_status=current_status,
                    practice_areas_raw=practice_areas_raw,
                    website=website,
                    # provenance fields — _stamp() will override these from the snapshot,
                    # but Provider requires them at construction time.
                    source_url=snapshot.source_url,
                    retrieved_at=snapshot.retrieved_at,
                    scraper_version=snapshot.scraper_version,
                )
            )

        return providers
