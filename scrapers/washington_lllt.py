"""Scraper for the WSBA Legal Directory, filtered to Limited License Legal Technicians (LLLT).

Source: https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx?ShowSearchResults=TRUE&LicenseType=LLLT
Fetch strategy: HeadlessFetcher (Playwright) — required for pagination via Telerik RadAjax.

Background:
  The Washington LLLT program was sunset by the WA Supreme Court in 2020 (effective
  July 31, 2021 for new applicants). Existing LLLTs may continue to maintain their license.
  As of June 2026, 67 of 95 LLLTs show "Active" status.

Page structure:
  The WSBA Legal Directory is a Personify CRM module embedded in DotNetNuke.
  Telerik RadAjax handles pagination via __doPostBack. A Chrome-like User-Agent is
  required for Telerik's JS bundle to initialize properly (academic UA is blocked at
  script level). Results pages: 5 pages × 20 rows (last page: 15 rows) = 95 total.

Snapshot format:
  run() collects all 5 pages via Playwright, builds a single combined HTML document
  (id="wsba-lllt-combined-roster"), and snapshots that. parse() works offline from it.

Pagination safety (docs/audit/pagination_audit.md §1):
  _fetch_all_pages() raises instead of silently truncating in two cases: (1) the
  "Next Page >" link is still present after _MAX_PAGES pages (_check_page_cap), and
  (2) the final parsed row count disagrees with the source's own '.results-count'
  total, read once before pagination starts (_check_source_total). No snapshot is
  taken in either case.

License number format:
  Directory displays "101LLLT", "102LLLT", etc. Provider IDs use the stripped number:
  prov_wa_lllt_101.

Fields NOT available in source:
  authorization_date → None for all rows (not shown in directory listing)
  practice_areas_raw → ["Family Law"] (program-level constant; WA LLLT board only
                        approved family law practice area before sunset)

Status mapping (directory string → CurrentStatus enum):
  Active           → active
  PRO BONO         → active   (still licensed; pro-bono rate member)
  Inactive         → unknown  (voluntarily inactive; not authorized to practice)
  Voluntarily Resigned → exited
  Retired          → exited
  Suspended        → suspended
  Revoked          → revoked
  Disbarred        → revoked
  Resigned in Lieu of Discipline → revoked
  Deceased         → exited
  Terminated       → exited
"""

from __future__ import annotations

import logging
import re
import time

from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import HeadlessFetcher

logger = logging.getLogger(__name__)

_RESULTS_URL = (
    "https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx"
    "?ShowSearchResults=TRUE&LicenseType=LLLT"
)

_MIN_EXPECTED_ROWS = 50

# Chrome-like UA required for Telerik JS bundle initialization
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TELERIK_INIT_WAIT = 6.0  # seconds for __doPostBack to be defined after page load
_PAGE_TURN_WAIT = 4.0  # seconds after clicking "Next Page >"

# Safety cap on pagination. A real scrape terminates in 5 pages (~95 rows); reaching
# this many means the "Next Page >" link never disappeared — a stuck postback or a
# WSBA markup change, not a genuinely larger roster. Raise loudly rather than silently
# stopping (docs/audit/pagination_audit.md §1).
_MAX_PAGES = 20

_LIC_RE = re.compile(r"^(\d+)LLLT$")
_COUNT_RE = re.compile(r"(\d+)")

_STATUS_MAP: dict[str, CurrentStatus] = {
    "Active": CurrentStatus.active,
    "PRO BONO": CurrentStatus.active,
    "Inactive": CurrentStatus.unknown,
    "Voluntarily Resigned": CurrentStatus.exited,
    "Retired": CurrentStatus.exited,
    "Suspended": CurrentStatus.suspended,
    "Revoked": CurrentStatus.revoked,
    "Disbarred": CurrentStatus.revoked,
    "Resigned in Lieu of Discipline": CurrentStatus.revoked,
    "Deceased": CurrentStatus.exited,
    "Terminated": CurrentStatus.exited,
}

_TABLE_ID = "dnn_ctr2972_DNNWebControlContainer_ctl00_dg"
_COMBINED_TABLE_ID = "wsba-lllt-combined-roster"


def _provider_id(lic_num: str) -> str:
    return f"prov_wa_lllt_{lic_num}"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _check_page_cap(pg_num: int, rows_so_far: int) -> None:
    """Raise if pagination has run past the safety cap instead of breaking silently.

    Extracted as a standalone function so this decision is unit-testable without a
    live Playwright session — the loop itself requires a browser, but "should we stop
    now" does not. See docs/audit/pagination_audit.md §1.
    """
    if pg_num >= _MAX_PAGES:
        raise ValueError(
            f"WA LLLT: pagination did not terminate within {_MAX_PAGES} pages "
            f"({rows_so_far} rows collected) — the 'Next Page >' link never disappeared. "
            "This is the safety cap failing loudly rather than silently truncating the "
            "roster; investigate the live page structure before re-running."
        )


def _check_source_total(parsed_count: int, source_total: int | None, pg_num: int) -> None:
    """Raise if the parsed row count disagrees with the source's own stated total.

    source_total is read once from the page's own '.results-count' span before any
    pagination happens. If pagination stops early for any reason — a page silently
    failing to load, a premature "no next page" read — this catches the undercount
    instead of shipping it. If the count element itself couldn't be read, that's logged
    (not fatal): there's no independent total to check against, but that's a distinct,
    already-documented situation, not a pagination failure. See
    docs/audit/pagination_audit.md §1.
    """
    if source_total is not None and parsed_count != source_total:
        raise ValueError(
            f"WA LLLT: parsed {parsed_count} rows across {pg_num} page(s), but the "
            f"source's own '.results-count' element states {source_total} — pagination "
            "may have stopped early, or the roster changed mid-scrape. Refusing to build "
            "a snapshot from a count that disagrees with the source's own total."
        )
    if source_total is None:
        logger.warning(
            "WA LLLT: could not read a row count from '.results-count' — proceeding "
            "with %d parsed rows with no independent total to verify completeness against.",
            parsed_count,
        )


class WashingtonLlltScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_wa_lllt"
    source_url = _RESULTS_URL
    default_fetcher_class = HeadlessFetcher

    def run(self) -> tuple[SourceSnapshot, list[Provider]]:
        """Override: collect all pages via Playwright, snapshot combined HTML, parse offline."""
        combined_html = self._fetch_all_pages()
        raw = combined_html.encode()
        snap, _ = self.snapshot(raw, self.source_url, MediaType.html)
        rows = self.parse(snap, raw)
        return snap, [self._stamp(row, snap) for row in rows]

    def _fetch_all_pages(self) -> str:
        all_data_rows: list[list[str]] = []
        source_total: int | None = None

        pg_num = 0
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context = browser.new_context(user_agent=_BROWSER_UA)
                page = context.new_page()

                page.goto(self.source_url, wait_until="networkidle", timeout=60000)
                time.sleep(_TELERIK_INIT_WAIT)

                # Parse source-stated total from results-count span
                count_el = page.locator(".results-count")
                if count_el.count():
                    m = _COUNT_RE.search(count_el.inner_text())
                    if m:
                        source_total = int(m.group(1))

                while True:
                    pg_num += 1
                    rows = _extract_rows_from_html(page.content())
                    all_data_rows.extend(rows)

                    next_btn = page.locator('a:has-text("Next Page >")')
                    if next_btn.count() == 0:
                        break

                    _check_page_cap(pg_num, len(all_data_rows))

                    next_btn.click()
                    time.sleep(_PAGE_TURN_WAIT)
            finally:
                browser.close()

        _check_source_total(len(all_data_rows), source_total, pg_num)
        return _build_combined_html(all_data_rows, source_total)

    def _parse_providers_from_table(self, tbl, snapshot: SourceSnapshot) -> list[Provider]:
        """Extract providers from a combined-format roster table. No row-count guard."""
        providers: list[Provider] = []
        for row in tbl.css("tr"):
            cells = [td.text(strip=True).replace("\xa0", " ") for td in row.css("td")]
            if not cells or len(cells) < 5:
                continue
            m = _LIC_RE.match(cells[0])
            if not m:
                continue
            lic_num = m.group(1)
            first_name = cells[1].strip()
            last_name = cells[2].strip()
            legal_name = f"{first_name} {last_name}".strip()
            if not legal_name:
                continue
            status_raw = cells[4].strip()
            current_status = _STATUS_MAP.get(status_raw, CurrentStatus.unknown)
            providers.append(
                Provider(
                    provider_id=_provider_id(lic_num),
                    program_id=self.program_id,
                    provider_type=ProviderType.individual,
                    legal_name=legal_name,
                    normalized_name=normalize_name(legal_name),
                    jurisdiction="WA",
                    authorization_date=None,
                    current_status=current_status,
                    practice_areas_raw=["Family Law"],
                    source_url=snapshot.source_url,
                    retrieved_at=snapshot.retrieved_at,
                    scraper_version=snapshot.scraper_version,
                )
            )
        return providers

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        html = raw.decode("utf-8", errors="replace")
        tree = HTMLParser(html)
        tbl = tree.css_first(f"#{_COMBINED_TABLE_ID}")
        if tbl is None:
            raise ValueError(
                "WA LLLT: combined roster table not found — snapshot may be corrupt "
                f"or wrong fixture (expected table id={_COMBINED_TABLE_ID!r})"
            )
        providers = self._parse_providers_from_table(tbl, snapshot)
        if len(providers) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"WA LLLT: only {len(providers)} providers parsed "
                f"(expected ≥ {_MIN_EXPECTED_ROWS}) — roster may have changed."
            )
        return providers

    def _wayback_parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        """Parse a single Wayback-captured WSBA page.

        Wayback captures only the first page of the paginated WSBA directory
        (~20 rows vs. 95 total). This method preprocesses the single-page HTML
        into the combined format that _parse_providers_from_table() expects,
        then extracts whatever rows are present without enforcing the minimum
        row count (the partial-capture limitation is documented in the report).
        """
        html = raw.decode("utf-8", errors="replace")
        rows = _extract_rows_from_html(html)
        combined = _build_combined_html(rows, source_total=None)
        tree = HTMLParser(combined)
        tbl = tree.css_first(f"#{_COMBINED_TABLE_ID}")
        if tbl is None:
            return []
        return self._parse_providers_from_table(tbl, snapshot)


def _extract_rows_from_html(html: str) -> list[list[str]]:
    tree = HTMLParser(html)
    tbl = tree.css_first(f"#{_TABLE_ID}")
    if tbl is None:
        return []
    rows: list[list[str]] = []
    for row in tbl.css("tr"):
        cells = [td.text(strip=True) for td in row.css("td")]
        if cells and len(cells) >= 5 and cells[0] and cells[0][0].isdigit():
            rows.append(cells)
    return rows


def _build_combined_html(rows: list[list[str]], source_total: int | None) -> str:
    total_str = str(source_total) if source_total is not None else str(len(rows))
    header = (
        "<tr>"
        "<th>LicenseNumber</th><th>FirstName</th><th>LastName</th>"
        "<th>City</th><th>Status</th><th>Phone</th>"
        "</tr>"
    )
    data_rows = "\n".join(
        "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    return (
        f"<!-- WSBA Legal Directory - LLLT roster, source_total={total_str} -->\n"
        "<html><body>\n"
        f'<table id="{_COMBINED_TABLE_ID}" class="search-results">\n'
        f"{header}\n"
        f"{data_rows}\n"
        "</table>\n"
        "</body></html>"
    )
