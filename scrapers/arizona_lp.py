"""Scraper for the Arizona Supreme Court Legal Paraprofessional (LP) directory.

Source: https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory
Static HTML table — no JavaScript rendering required.

Column order: License Status | Last Name | First Name | Area of Practice
              | Contact Information | Counties Served

Notes:
- legal_name is constructed as "First Last" from the two separate name columns.
- Authorization date: not published on the roster; all rows get None.
- practice_areas_raw: the raw cell text is preserved verbatim alongside the
  normalized list. One typo exists on the live page ("Criminial" → "Criminal").
- Contact Information: personal data (address/phone/email) — dropped per schema.
- Counties Served: not in registry schema — dropped (same precedent as AZ ABS).
- Status mapping:
    Active               → active
    Not Active           → exited
    Active as an attorney → exited (individual has graduated to full attorney;
                            no longer operating under the LP license)
"""

from __future__ import annotations

import hashlib
import re

from selectolax.parser import HTMLParser

from models.enums import CurrentStatus, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper

_URL = "https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory"

# Minimum rows expected; raise if the page structure has changed.
_MIN_EXPECTED_ROWS = 50

# Canonical area name lookup (lowercase key → display value).
# "Criminial" is a live typo on the source page; mapped here so it round-trips
# correctly in the fixture test.
_AREA_ALIASES: dict[str, str] = {
    "administrative": "Administrative",
    "civil": "Civil",
    "criminal": "Criminal",
    "criminial": "Criminal",  # typo on the live roster
    "family": "Family",
    "juvenile": "Juvenile",
}


def _provider_id(legal_name: str) -> str:
    digest = hashlib.sha256(f"prog_az_lp\x00{legal_name}".encode()).hexdigest()
    return f"prov_az_lp_{digest[:12]}"


def _map_status(text: str) -> CurrentStatus:
    t = text.strip().lower()
    if t == "active":
        return CurrentStatus.active
    if t in ("not active", "active as an attorney"):
        return CurrentStatus.exited
    return CurrentStatus.unknown


def _split_areas(raw: str) -> list[str]:
    """Split a multi-area cell into canonical individual area names.

    Handles separators: comma, "and", "&".
    Preserves order; deduplicates.
    """
    parts = re.split(r",|\band\b|&", raw, flags=re.IGNORECASE)
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        key = part.strip().lower()
        canonical = _AREA_ALIASES.get(key)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


class ArizonaLpScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_az_lp"
    source_url = _URL

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        tree = HTMLParser(raw)
        table = tree.css_first("table")
        if table is None:
            raise ValueError(
                "AZ LP directory: expected <table> not found — page structure may have changed."
            )

        rows = table.css("tr")[1:]  # skip header
        if len(rows) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"AZ LP directory: only {len(rows)} data rows found "
                f"(expected ≥ {_MIN_EXPECTED_ROWS}) — page structure may have changed."
            )

        providers: list[Provider] = []
        for row in rows:
            cells = row.css("td")
            if len(cells) < 4:
                continue

            status_raw = cells[0].text(strip=True)
            last_name = cells[1].text(strip=True)
            first_name = cells[2].text(strip=True)
            area_raw = cells[3].text(strip=True)

            if not last_name:
                continue

            legal_name = f"{first_name} {last_name}".strip()
            current_status = _map_status(status_raw)
            practice_areas_raw = _split_areas(area_raw)

            providers.append(
                Provider(
                    provider_id=_provider_id(legal_name),
                    program_id=self.program_id,
                    provider_type=ProviderType.individual,
                    legal_name=legal_name,
                    normalized_name=normalize_name(legal_name),
                    jurisdiction="AZ",
                    authorization_date=None,
                    current_status=current_status,
                    practice_areas_raw=practice_areas_raw,
                    # provenance — overwritten by _stamp() in run()
                    source_url=snapshot.source_url,
                    retrieved_at=snapshot.retrieved_at,
                    scraper_version=snapshot.scraper_version,
                )
            )

        return providers
