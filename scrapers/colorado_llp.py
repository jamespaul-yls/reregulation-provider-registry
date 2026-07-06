"""Scraper for the Colorado OARC Limited License Professional (LLP) admitted roster.

Source: https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf
Fetch strategy: StaticFetcher (PdfFetcher) — direct PDF download, no JS rendering needed.

PDF layout (3 pages, as of 2026-02-06):
  Column 1 — Registration Number (6-digit, prefix 600xxx)
  Column 2 — Name (First Last format — no conversion needed)

Fields NOT available in source:
  authorization_date  → None for all rows
  practice_areas_raw  → ["Domestic Relations"] (program-level constant; all CO LLPs
                         are licensed in domestic relations only)
  website             → None
  ownership_structure → None (individual practitioners)
"""

from __future__ import annotations

import io
import re

import pdfplumber

from models.enums import CurrentStatus, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import PdfFetcher

_PDF_URL = "https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf"

_MIN_EXPECTED_ROWS = 50

# Registration numbers from the source ("600000", "600001", …) form stable unique IDs.
_REG_RE = re.compile(r"^(6\d{5})\s+(.+)$")


def _provider_id(reg_num: str) -> str:
    return f"prov_co_llp_{reg_num}"


class ColoradoLlpScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_co_llp"
    source_url = _PDF_URL
    default_fetcher_class = PdfFetcher

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        providers: list[Provider] = []

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if not pdf.pages:
                raise ValueError("CO LLP PDF: no pages found — download may have failed")

            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    m = _REG_RE.match(line.strip())
                    if not m:
                        continue
                    reg_num, legal_name = m.group(1), m.group(2).strip()
                    if not legal_name:
                        continue

                    providers.append(
                        Provider(
                            provider_id=_provider_id(reg_num),
                            program_id=self.program_id,
                            provider_type=ProviderType.individual,
                            legal_name=legal_name,
                            normalized_name=normalize_name(legal_name),
                            jurisdiction="CO",
                            authorization_date=None,
                            current_status=CurrentStatus.active,
                            practice_areas_raw=["Domestic Relations"],
                            source_url=snapshot.source_url,
                            retrieved_at=snapshot.retrieved_at,
                            scraper_version=snapshot.scraper_version,
                        )
                    )

        if len(providers) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"CO LLP: only {len(providers)} providers parsed "
                f"(expected ≥ {_MIN_EXPECTED_ROWS}) — PDF structure may have changed."
            )

        return providers
