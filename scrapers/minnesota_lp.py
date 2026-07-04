"""Scraper for the Minnesota Legal Paraprofessional Program (LPP) roster.

Source: https://mncourts.gov/_media/migration/appellate/supreme-court/Roster-of-Approved-Legal-Paraprofessionals.pdf
Fetch strategy: PdfFetcher — static PDF download.

PDF layout (multi-page table, 15 columns due to merged-cell expansion):
  col 0  — ID No. (4-digit, e.g., "1041")
  col 3  — LP cell (name\\naddress\\nemail\\nphone)
  col 6  — Supervising Attorney(s) cell (not captured in schema)
  col 9  — Approval Date + Case Types ("Month Day, Year\\n• Area1\\n• Area2 ...")
  col 12 — Areas Served (geographic region, not captured in schema)

Multi-line bullets: practice-area lines starting with '•' may continue on following
lines without a bullet prefix. Continuation lines are joined with a space to the
preceding bullet. Example:
  "• Domestic Violence, Child Abuse,\\nOrders for Protection (OFP)..."
  → "Domestic Violence, Child Abuse, Orders for Protection (OFP)..."

ID gaps: IDs 1009 and 1028 are absent from the June 25, 2026 roster (not parsing
errors — those IDs were apparently never issued or have been removed).

All roster entries are treated as active (the roster lists only approved participants).
Attorney supervision is a program-wide requirement; it is not stored per-row.
"""

from __future__ import annotations

import datetime
import io
import re

import pdfplumber

from models.enums import CurrentStatus, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import PdfFetcher

_PDF_URL = (
    "https://mncourts.gov/_media/migration/appellate/supreme-court/"
    "Roster-of-Approved-Legal-Paraprofessionals.pdf"
)

_MIN_EXPECTED_ROWS = 30

_ID_RE = re.compile(r"^\d{4}$")
_DATE_RE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}$")

# Column indices in the pdfplumber-extracted table rows (15 cols from merged cells)
_COL_ID = 0
_COL_LP = 3
_COL_APPROVAL = 9


def _provider_id(lp_id: str) -> str:
    return f"prov_mn_lp_{lp_id}"


def _parse_approval_cell(cell: str) -> tuple[datetime.date | None, list[str]]:
    """Return (authorization_date, practice_areas_raw) from the approval cell."""
    lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
    if not lines:
        return None, []

    auth_date: datetime.date | None = None
    if _DATE_RE.match(lines[0]):
        try:
            auth_date = datetime.datetime.strptime(lines[0], "%B %d, %Y").date()
        except ValueError:
            pass

    areas: list[str] = []
    current: str | None = None
    for line in lines[1:]:
        if line.startswith("•"):
            if current is not None:
                areas.append(current.strip())
            current = line.lstrip("•").strip()
        else:
            # Continuation of the previous bullet
            if current is not None:
                current = current + " " + line
    if current is not None:
        areas.append(current.strip())

    return auth_date, areas


class MinnesotaLpScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_mn_lp"
    source_url = _PDF_URL
    default_fetcher_class = PdfFetcher

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        providers: list[Provider] = []

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if not pdf.pages:
                raise ValueError("MN LP PDF: no pages found — download may have failed")

            for page in pdf.pages:
                table = page.extract_table()
                if not table:
                    continue

                for row in table:
                    if not row or len(row) <= _COL_APPROVAL:
                        continue

                    lp_id = (row[_COL_ID] or "").strip()
                    if not _ID_RE.match(lp_id):
                        continue  # header row or empty row

                    lp_cell = (row[_COL_LP] or "").strip()
                    approval_cell = (row[_COL_APPROVAL] or "").strip()

                    # Legal name is the first line of the LP cell
                    legal_name = lp_cell.split("\n")[0].strip()
                    if not legal_name:
                        continue

                    auth_date, practice_areas = _parse_approval_cell(approval_cell)

                    providers.append(
                        Provider(
                            provider_id=_provider_id(lp_id),
                            program_id=self.program_id,
                            provider_type=ProviderType.individual,
                            legal_name=legal_name,
                            normalized_name=normalize_name(legal_name),
                            jurisdiction="MN",
                            authorization_date=auth_date,
                            current_status=CurrentStatus.active,
                            practice_areas_raw=practice_areas,
                            source_url=snapshot.source_url,
                            retrieved_at=snapshot.retrieved_at,
                            scraper_version=snapshot.scraper_version,
                        )
                    )

        if len(providers) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"MN LP: only {len(providers)} providers parsed "
                f"(expected ≥ {_MIN_EXPECTED_ROWS}) — PDF structure may have changed."
            )

        return providers
