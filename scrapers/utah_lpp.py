"""Scraper for the Utah State Bar Licensed Paralegal Practitioner (LPP) directory.

Source: https://www.licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners
(Official Utah State Bar LPP public referral directory, powered by LicensedLawyer / Euclid
Technology on behalf of the Utah State Bar.)

Fetch strategy notes:
- The parent page embeds a ClearVantage CGI iframe that is JS-rendered; static httpx returns
  an empty template with no record data.
- Cloudflare bot management blocks subsequent page navigations within the iframe, making
  standard pagination unusable.
- Solution: Playwright route interception rewrites the initial iframe request from
  RANGE=1/10 (10 records, page 1) to RANGE=1/100 (all records, single request) before the
  first response is received.  This is the only approach that successfully retrieves all
  records without triggering Cloudflare's block.

Coverage note:
- licensedlawyer.org is described as "provided by the Utah State Bar" for the LPP program.
  It may be an opt-in referral directory rather than a mandatory roster of ALL licensed LPPs.
  See validation/utah_lpp.md for the comprehensiveness caveat.

Fields available in source:
- legal_name (Last, First format — converted to First Last)
- organization / employer (not in registry schema, dropped)
- job_title (varies: "Licensed Paralegal Practitioner" / "LPP" / blank)

Fields NOT available:
- authorization_date  → None for all rows
- practice_areas_raw  → [] for all rows (directory does not publish per-individual areas)
- website, ownership_structure, uses_technology, uses_ai → None / not applicable
"""

from __future__ import annotations

import hashlib
import re
import time

from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import _USER_AGENT, FetchResult  # noqa: PLC2701

_PARENT_URL = "https://www.licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners"

# Minimum real rows expected; guards against silent scraping failure.
_MIN_EXPECTED_ROWS = 25

# Wait seconds after networkidle for the iframe JS hydration to complete.
_IFRAME_RENDER_WAIT = 8

# Row is a test / system account — drop from output.
_TEST_ACCOUNT_NAMES = frozenset({"testacct"})


def _provider_id(legal_name: str) -> str:
    digest = hashlib.sha256(f"prog_ut_lpp\x00{legal_name}".encode()).hexdigest()
    return f"prov_ut_lpp_{digest[:12]}"


def _last_first_to_first_last(name: str) -> str:
    """Convert 'Last, First' → 'First Last'.  Pass through names with no comma."""
    if "," not in name:
        return name.strip()
    last, _, first = name.partition(",")
    return f"{first.strip()} {last.strip()}".strip()


class _LppFetcher:
    """Custom Playwright fetcher for the LPP iframe directory.

    Intercepts the initial iframe request and rewrites RANGE=1/10 → RANGE=1/100
    so all records load in a single request, bypassing Cloudflare pagination blocks.
    Returns the iframe's rendered HTML (not the parent shell page).
    """

    def __init__(self, rate_limit: float = 1.0, timeout: float = 60.0) -> None:
        self.rate_limit = rate_limit
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        time.sleep(self.rate_limit)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=_USER_AGENT)
                page = context.new_page()

                def _on_route(route, request):
                    req_url = request.url
                    if "CustomList" in req_url and "RANGE=1%2f10" in req_url:
                        route.continue_(url=req_url.replace("RANGE=1%2f10", "RANGE=1%2f100"))
                    else:
                        route.continue_()

                page.route("**/*", _on_route)
                page.goto(url, wait_until="networkidle", timeout=self.timeout * 1_000)
                time.sleep(_IFRAME_RENDER_WAIT)

                lp_frame = next(
                    (f for f in page.frames if "cv/cgi-bin" in f.url and "CustomList" in f.url),
                    None,
                )
                if lp_frame is None:
                    raise ValueError(
                        "Utah LPP: ClearVantage iframe not found after page load — "
                        "licensedlawyer.org page structure may have changed."
                    )

                content = lp_frame.content().encode()
                final_url = lp_frame.url
            finally:
                browser.close()

        return FetchResult(content=content, url=final_url, media_type=MediaType.html)


class UtahLppScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_ut_lpp"
    source_url = _PARENT_URL
    default_fetcher_class = _LppFetcher  # type: ignore[assignment]

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        tree = HTMLParser(raw)

        # Verify we got data rows, not a Cloudflare block page.
        if tree.css_first("tr.nqCustContainer") is None:
            page_text = tree.body.text(strip=True)[:200] if tree.body else ""
            raise ValueError(
                f"Utah LPP: no member rows found in snapshot — "
                f"possible Cloudflare block or page structure change. "
                f"Page text preview: {page_text!r}"
            )

        providers: list[Provider] = []

        for row in tree.css("tr.nqCustContainer"):
            # ── name ──────────────────────────────────────────────────────────
            name_td = row.css_first("td[data-label='Name']")
            if name_td is None:
                continue
            raw_name = name_td.text(strip=True)
            # Strip embedded JS: "Adams, Michelleif ('Y'=='N') {..."
            name_last_first = re.split(r"if \('", raw_name)[0].strip()
            if not name_last_first or name_last_first == "-":
                continue

            # Drop test/system accounts
            if name_last_first.split(",")[0].strip().lower() in _TEST_ACCOUNT_NAMES:
                continue

            legal_name = _last_first_to_first_last(name_last_first)

            providers.append(
                Provider(
                    provider_id=_provider_id(legal_name),
                    program_id=self.program_id,
                    provider_type=ProviderType.individual,
                    legal_name=legal_name,
                    normalized_name=normalize_name(legal_name),
                    jurisdiction="UT",
                    authorization_date=None,
                    # All records returned by the LPPActive filter are active.
                    current_status=CurrentStatus.active,
                    # Directory does not publish per-individual practice areas.
                    practice_areas_raw=[],
                    # Not published in the directory listing.
                    source_url=snapshot.source_url,
                    retrieved_at=snapshot.retrieved_at,
                    scraper_version=snapshot.scraper_version,
                )
            )

        if len(providers) < _MIN_EXPECTED_ROWS:
            raise ValueError(
                f"Utah LPP: only {len(providers)} providers parsed "
                f"(expected ≥ {_MIN_EXPECTED_ROWS}) — possible partial load or "
                f"site structure change."
            )

        return providers
