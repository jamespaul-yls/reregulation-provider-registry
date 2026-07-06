"""Scraper for the Utah Office of Legal Services Innovation authorized-entity roster.

Source: https://utahinnovationoffice.org/authorized-entities/
Static HTML — Elementor page builder; no JavaScript rendering required.

Five entity populations, each with a different page layout and status:

  Currently Authorized          (Elementor inner-section cards)  → active  (7)
  Authorized through Standing Order (flat ul list)               → active  (1)
  Provisionally Authorized      (flat ul list)                   → exited  (7)
  Previously Authorized w/ Rule 5.4 Waivers  (flat ul)          → exited  (19)
  Previously Authorized         (flat ul — follows heading-only section) → exited (35)

Fields captured from cards (currently authorized only):
  practice_areas_raw, website, ownership_structure (service-model dict),
  uses_technology, uses_ai.

Authorization date is NOT published on the roster — all rows get None.

Activity-report PDFs are snapshotted in snapshot_activity_reports() but not
parsed; captured now as v4 denominator data.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from selectolax.parser import HTMLParser

from models.enums import CurrentStatus, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import PdfFetcher

log = logging.getLogger(__name__)

_ROSTER_URL = "https://utahinnovationoffice.org/authorized-entities/"

# Known activity-report PDFs discovered via web search (archive page 404s as of 2026-06-29).
# Snapshot-only; not parsed.  Update this list as new reports are published.
_ACTIVITY_REPORT_URLS: list[str] = [
    "https://utahinnovationoffice.org/wp-content/uploads/2024/03/January-2024-Activity-Report.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2024/01/2023_April_IO_Monthly-Report.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2023/05/2023.3-Public-Report.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2024/01/2022_May_Monthly-Report.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2024/01/2021_December_IO_Monthly-Report.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2021/07/Innovation-Office-Public-Report-June-2021.pdf",
    "https://utahinnovationoffice.org/wp-content/uploads/2024/01/2021_Jan_IO_Monthly-Report.pdf",
]

# Minimum cards we expect in the Currently Authorized section.
_MIN_ACTIVE_CARDS = 5

# AI keyword pattern — word-boundary on "ai" prevents matching "mail", "trail", etc.
_AI_RE = re.compile(r"\bai\b|artificial intelligence|chatbot|machine learning", re.IGNORECASE)


# ── helpers ───────────────────────────────────────────────────────────────────


def _provider_id(legal_name: str) -> str:
    digest = hashlib.sha256(f"prog_ut_sandbox\x00{legal_name}".encode()).hexdigest()
    return f"prov_ut_sandbox_{digest[:12]}"


def _clean_name(text: str) -> str:
    """Strip parenthetical status notes, non-breaking spaces, and trailing asterisk footnotes.

    Periods are intentionally preserved — "Corp.", "J.", "Inc." are legal abbreviations,
    not stray punctuation.
    """
    text = text.replace("\xa0", "")
    text = re.sub(r"\s*\((?:expired|withdrew|withdrawn)\)\.?\s*", "", text, flags=re.IGNORECASE)
    return text.rstrip("*").strip()


def _extract_li_name(li: object) -> str:
    """Return cleaned entity name from a list-item node."""
    a = li.css_first("a")
    raw = a.text(strip=True) if a else li.text(strip=True)
    return _clean_name(raw)


def _parse_service_models(text: str) -> tuple[dict[str, Any] | None, bool | None]:
    """Parse comma-separated service-model text → (ownership_structure dict, uses_technology).

    Returns (None, None) when text is empty (no data available).
    """
    if not text:
        return None, None
    models = [m.strip().rstrip(".") for m in text.split(",") if m.strip().rstrip(".")]
    if not models:
        return None, None
    owns: dict[str, Any] = {"service_models": models}
    uses_tech = any("software" in m.lower() or "technology" in m.lower() for m in models)
    return owns, uses_tech


# ── scraper ───────────────────────────────────────────────────────────────────


class UtahSandboxScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_ut_sandbox"
    source_url = _ROSTER_URL

    # ── parse ─────────────────────────────────────────────────────────────────

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        tree = HTMLParser(raw)
        providers: list[Provider] = []

        # 1. Currently authorized: Elementor inner-section cards
        active_cards = tree.css("section.elementor-inner-section")
        for sec in active_cards:
            p = self._parse_card(sec, snapshot)
            if p is not None:
                providers.append(p)

        if len(providers) < _MIN_ACTIVE_CARDS:
            raise ValueError(
                f"UT Sandbox: only {len(providers)} active cards found "
                f"(expected ≥ {_MIN_ACTIVE_CARDS}) — page structure may have changed."
            )

        # 2. List-based sections in top-level Elementor sections
        top_sections = tree.css("section.elementor-top-section")
        prev_auth_header_seen = False

        for sec in top_sections:
            h2 = sec.css_first("h2")

            if h2 is None:
                # If the "Previously Authorized Entities" heading was just seen,
                # this is the sibling section that holds the actual list.
                if prev_auth_header_seen:
                    for li in sec.css("li"):
                        name = _extract_li_name(li)
                        if name:
                            providers.append(
                                self._make_list_provider(name, CurrentStatus.exited, snapshot)
                            )
                    prev_auth_header_seen = False
                continue

            h2_text = h2.text(strip=True)

            if "Provisionally Authorized" in h2_text:
                for li in sec.css("li"):
                    name = _extract_li_name(li)
                    if name:
                        providers.append(
                            self._make_list_provider(name, CurrentStatus.exited, snapshot)
                        )

            elif "Standing Order" in h2_text:
                for li in sec.css("li"):
                    name = _extract_li_name(li)
                    if name:
                        providers.append(
                            self._make_list_provider(name, CurrentStatus.active, snapshot)
                        )

            elif "5.4 Waiver" in h2_text:
                for li in sec.css("li"):
                    name = _extract_li_name(li)
                    if name:
                        providers.append(
                            self._make_list_provider(name, CurrentStatus.exited, snapshot)
                        )

            elif h2_text == "Previously Authorized Entities":
                prev_auth_header_seen = True

        return providers

    def _parse_card(self, section: object, snapshot: SourceSnapshot) -> Provider | None:
        """Parse one 2-column Elementor card (currently-authorized entity)."""
        cols = section.css("div.elementor-inner-column")
        if len(cols) < 2:
            return None

        left_col, right_col = cols[0], cols[1]

        # Entity name — h2 in right column; strip trailing asterisk footnote
        h2 = right_col.css_first("h2")
        if h2 is None:
            return None
        legal_name = _clean_name(h2.text(strip=True))
        if not legal_name:
            return None

        right_eds = right_col.css('div[data-widget_type="text-editor.default"]')
        left_eds = left_col.css('div[data-widget_type="text-editor.default"]')

        # Service categories (left column, first text-editor)
        service_cats_text = left_eds[0].text(strip=True) if left_eds else ""
        practice_areas_raw = [p.strip() for p in service_cats_text.split(",") if p.strip()]

        # Right column editor[0]: website link paragraph + description paragraph
        website: str | None = None
        description = ""
        if right_eds:
            first_ed = right_eds[0]
            for p_node in first_ed.css("p"):
                p_text = p_node.text(strip=True)
                a_nodes = p_node.css("a")
                # A link-only paragraph is the entity's website
                if len(a_nodes) == 1 and a_nodes[0].text(strip=True) == p_text:
                    href = (a_nodes[0].attributes.get("href") or "").strip()
                    external = "utahinnovationoffice.org" not in href
                    if href.startswith(("http://", "https://")) and external:
                        website = href
                else:
                    if p_text:
                        description = p_text

        # Right column editor[2]: service models (comma-separated)
        service_models_text = right_eds[2].text(strip=True) if len(right_eds) >= 3 else ""
        ownership_structure, uses_technology = _parse_service_models(service_models_text)
        uses_ai = bool(_AI_RE.search(description)) if description else None

        return Provider(
            provider_id=_provider_id(legal_name),
            program_id=self.program_id,
            provider_type=ProviderType.entity,
            legal_name=legal_name,
            normalized_name=normalize_name(legal_name),
            jurisdiction="UT",
            authorization_date=None,
            current_status=CurrentStatus.active,
            practice_areas_raw=practice_areas_raw,
            ownership_structure=ownership_structure,
            uses_technology=uses_technology,
            uses_ai=uses_ai,
            website=website,
            source_url=snapshot.source_url,
            retrieved_at=snapshot.retrieved_at,
            scraper_version=snapshot.scraper_version,
        )

    def _make_list_provider(
        self,
        legal_name: str,
        current_status: CurrentStatus,
        snapshot: SourceSnapshot,
    ) -> Provider:
        return Provider(
            provider_id=_provider_id(legal_name),
            program_id=self.program_id,
            provider_type=ProviderType.entity,
            legal_name=legal_name,
            normalized_name=normalize_name(legal_name),
            jurisdiction="UT",
            authorization_date=None,
            current_status=current_status,
            practice_areas_raw=[],
            ownership_structure=None,
            uses_technology=None,
            uses_ai=None,
            website=None,
            source_url=snapshot.source_url,
            retrieved_at=snapshot.retrieved_at,
            scraper_version=snapshot.scraper_version,
        )

    # ── activity-report PDF snapshots ─────────────────────────────────────────

    def snapshot_activity_reports(self) -> list[SourceSnapshot]:
        """Download and snapshot known activity-report PDFs. No parsing.

        Failures are logged and skipped — a 404 on a historical PDF should not
        abort the full run.
        """
        pdf_fetcher = PdfFetcher(rate_limit=self.default_rate_limit)
        snapshots: list[SourceSnapshot] = []
        for url in _ACTIVITY_REPORT_URLS:
            try:
                result = pdf_fetcher.fetch(url)
                snap, _ = self.snapshot(result.content, result.url, result.media_type)
                snapshots.append(snap)
                log.info("Snapshotted PDF: %s → %s", url, snap.snapshot_id)
            except Exception as exc:
                log.warning("Could not snapshot PDF %s: %s", url, exc)
        return snapshots
