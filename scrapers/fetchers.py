"""Pluggable fetch strategies for BaseScraper.

Each fetcher implements the Fetcher protocol: fetch(url) -> FetchResult.
All three share the same rate-limiting and User-Agent conventions.

- StaticFetcher   — httpx GET for plain HTML/JSON pages.
- HeadlessFetcher — playwright chromium for JS-rendered directories.
- PdfFetcher      — httpx GET with an extended timeout for PDF downloads.
- RetryingFetcher — wraps any Fetcher with bounded exponential-backoff retries.
                    Retries only on httpx.TransportError (timeouts, connection
                    failures). HTTP 4xx/5xx and parse errors propagate immediately.
                    Raises SourceUnreachableError after all retries are exhausted.
"""

from __future__ import annotations

import logging
import time
from typing import NamedTuple, Protocol, runtime_checkable

import httpx
from playwright.sync_api import sync_playwright

from models.enums import MediaType

logger = logging.getLogger(__name__)

_USER_AGENT = "reregulation-registry/0.1 (academic research; contact: james.paul@yale.edu)"


class SourceUnreachableError(Exception):
    """Raised by RetryingFetcher when all retry attempts are exhausted.

    Signals a transient network failure, not a code bug — the orchestrator
    logs a WARNING and continues without marking the overall run as failed.
    """


class FetchResult(NamedTuple):
    content: bytes
    url: str
    media_type: MediaType


@runtime_checkable
class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...


class StaticFetcher:
    """httpx-based fetcher for static HTML and JSON sources."""

    def __init__(self, rate_limit: float = 1.0, timeout: float = 30.0) -> None:
        self.rate_limit = rate_limit
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        time.sleep(self.rate_limit)
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=self.timeout,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
        return FetchResult(
            content=resp.content,
            url=str(resp.url),
            media_type=MediaType.html,
        )


class HeadlessFetcher:
    """Playwright-based fetcher for JavaScript-rendered pages."""

    def __init__(self, rate_limit: float = 1.0, timeout: float = 30.0) -> None:
        self.rate_limit = rate_limit
        self.timeout = timeout  # seconds; converted to ms for Playwright

    def fetch(self, url: str) -> FetchResult:
        time.sleep(self.rate_limit)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=_USER_AGENT)
                page.goto(url, wait_until="networkidle", timeout=self.timeout * 1_000)
                content = page.content().encode()
                final_url = page.url
            finally:
                browser.close()
        return FetchResult(
            content=content,
            url=final_url,
            media_type=MediaType.html,
        )


class PdfFetcher:
    """httpx-based fetcher for PDF document downloads."""

    def __init__(self, rate_limit: float = 1.0, timeout: float = 60.0) -> None:
        self.rate_limit = rate_limit
        self.timeout = timeout

    def fetch(self, url: str) -> FetchResult:
        time.sleep(self.rate_limit)
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=self.timeout,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
        return FetchResult(
            content=resp.content,
            url=str(resp.url),
            media_type=MediaType.pdf,
        )


class RetryingFetcher:
    """Wraps any Fetcher with bounded exponential-backoff retries.

    Only retries on httpx.TransportError (timeouts, connection failures).
    HTTP errors (4xx/5xx) and all other exceptions propagate immediately —
    those are meaningful responses or code bugs, not transient network issues.

    After max_retries failed attempts, raises SourceUnreachableError so the
    caller can distinguish "site was down" from "our code broke".

    Backoff: sleep(backoff_base ** attempt) between attempts, so with the
    default base=2 the waits are 1 s, 2 s, 4 s (no sleep after the final
    failure — it's about to raise, not retry).
    """

    def __init__(
        self,
        inner: Fetcher,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ) -> None:
        self._inner = inner
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def fetch(self, url: str) -> FetchResult:
        last_exc: httpx.TransportError | None = None
        for attempt in range(self.max_retries):
            try:
                return self._inner.fetch(url)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    wait = self.backoff_base**attempt
                    logger.warning(
                        "fetch %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        url,
                        attempt + 1,
                        self.max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "fetch %s failed (attempt %d/%d): %s — all retries exhausted",
                        url,
                        attempt + 1,
                        self.max_retries,
                        exc,
                    )
        raise SourceUnreachableError(
            f"source unreachable after {self.max_retries} attempts: {url}"
        ) from last_exc
