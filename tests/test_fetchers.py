"""Unit tests for scrapers.fetchers — StaticFetcher, HeadlessFetcher, PdfFetcher.

All tests run offline: network calls are replaced with unittest.mock stubs.
Each test asserts FetchResult fields and verifies that rate-limit sleep is called.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from models.enums import MediaType
from scrapers.fetchers import (
    FetchResult,
    HeadlessFetcher,
    PdfFetcher,
    RetryingFetcher,
    SourceUnreachableError,
    StaticFetcher,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

_HTML_BYTES = b"<html><body><p>Hello</p></body></html>"
_PDF_BYTES = b"%PDF-1.4 1 0 obj<</Type /Catalog>>endobj"
_TARGET_URL = "https://example.gov/roster"
_FINAL_URL = "https://example.gov/roster"  # no redirect in tests


def _make_httpx_response(content: bytes, final_url: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.url = MagicMock()
    resp.url.__str__ = lambda self: final_url
    return resp


# ── StaticFetcher ─────────────────────────────────────────────────────────────


class TestStaticFetcher:
    def test_returns_fetch_result(self) -> None:
        resp = _make_httpx_response(_HTML_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            result = StaticFetcher(rate_limit=1.0).fetch(_TARGET_URL)

        assert isinstance(result, FetchResult)
        assert result.content == _HTML_BYTES
        assert result.url == _FINAL_URL
        assert result.media_type == MediaType.html

    def test_calls_get_with_correct_url(self) -> None:
        resp = _make_httpx_response(_HTML_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            StaticFetcher().fetch(_TARGET_URL)

        mock_client.get.assert_called_once_with(_TARGET_URL)

    def test_rate_limit_sleep_called(self) -> None:
        resp = _make_httpx_response(_HTML_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep") as mock_sleep,
        ):
            StaticFetcher(rate_limit=2.5).fetch(_TARGET_URL)

        mock_sleep.assert_called_once_with(2.5)

    def test_raises_on_http_error(self) -> None:
        import httpx as _httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            with pytest.raises(_httpx.HTTPStatusError):
                StaticFetcher().fetch(_TARGET_URL)


# ── HeadlessFetcher ───────────────────────────────────────────────────────────


def _make_playwright_mock(html: str, final_url: str) -> MagicMock:
    """Return a mock that mimics the playwright sync_playwright() context manager."""
    mock_page = MagicMock()
    mock_page.content.return_value = html
    mock_page.url = final_url

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_sync_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_p)
    mock_sync_playwright.return_value.__exit__ = MagicMock(return_value=False)

    return mock_sync_playwright


class TestHeadlessFetcher:
    def test_returns_fetch_result(self) -> None:
        html = "<html><body>JS page</body></html>"
        mock_sw = _make_playwright_mock(html, _FINAL_URL)

        with (
            patch("scrapers.fetchers.sync_playwright", mock_sw),
            patch("scrapers.fetchers.time.sleep"),
        ):
            result = HeadlessFetcher(rate_limit=1.0).fetch(_TARGET_URL)

        assert isinstance(result, FetchResult)
        assert result.content == html.encode()
        assert result.url == _FINAL_URL
        assert result.media_type == MediaType.html

    def test_rate_limit_sleep_called(self) -> None:
        html = "<html></html>"
        mock_sw = _make_playwright_mock(html, _FINAL_URL)

        with (
            patch("scrapers.fetchers.sync_playwright", mock_sw),
            patch("scrapers.fetchers.time.sleep") as mock_sleep,
        ):
            HeadlessFetcher(rate_limit=3.0).fetch(_TARGET_URL)

        mock_sleep.assert_called_once_with(3.0)

    def test_browser_always_closed(self) -> None:
        """browser.close() must be called even if page.content() raises."""
        mock_page = MagicMock()
        mock_page.content.side_effect = RuntimeError("render failed")

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser

        mock_sw = MagicMock()
        mock_sw.return_value.__enter__ = MagicMock(return_value=mock_p)
        mock_sw.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("scrapers.fetchers.sync_playwright", mock_sw),
            patch("scrapers.fetchers.time.sleep"),
        ):
            with pytest.raises(RuntimeError):
                HeadlessFetcher().fetch(_TARGET_URL)

        mock_browser.close.assert_called_once()

    def test_page_navigated_to_url(self) -> None:
        html = "<html></html>"
        mock_sw = _make_playwright_mock(html, _FINAL_URL)
        enter = mock_sw.return_value.__enter__.return_value
        mock_page = enter.chromium.launch.return_value.new_page.return_value

        with (
            patch("scrapers.fetchers.sync_playwright", mock_sw),
            patch("scrapers.fetchers.time.sleep"),
        ):
            HeadlessFetcher().fetch(_TARGET_URL)

        mock_page.goto.assert_called_once_with(
            _TARGET_URL, wait_until="networkidle", timeout=30_000
        )


# ── PdfFetcher ────────────────────────────────────────────────────────────────


class TestPdfFetcher:
    def test_returns_fetch_result(self) -> None:
        resp = _make_httpx_response(_PDF_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            result = PdfFetcher(rate_limit=1.0).fetch(_TARGET_URL)

        assert isinstance(result, FetchResult)
        assert result.content == _PDF_BYTES
        assert result.url == _FINAL_URL
        assert result.media_type == MediaType.pdf

    def test_media_type_is_pdf(self) -> None:
        resp = _make_httpx_response(_PDF_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            result = PdfFetcher().fetch(_TARGET_URL)

        assert result.media_type == MediaType.pdf

    def test_rate_limit_sleep_called(self) -> None:
        resp = _make_httpx_response(_PDF_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep") as mock_sleep,
        ):
            PdfFetcher(rate_limit=1.5).fetch(_TARGET_URL)

        mock_sleep.assert_called_once_with(1.5)

    def test_uses_extended_timeout(self) -> None:
        """PdfFetcher must use a 60 s timeout to handle large document downloads."""
        resp = _make_httpx_response(_PDF_BYTES, _FINAL_URL)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client) as mock_cls,
            patch("scrapers.fetchers.time.sleep"),
        ):
            PdfFetcher().fetch(_TARGET_URL)

        _, kwargs = mock_cls.call_args
        assert kwargs.get("timeout") == 60.0

    def test_raises_on_http_error(self) -> None:
        import httpx as _httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock()
        )

        with (
            patch("scrapers.fetchers.httpx.Client", return_value=mock_client),
            patch("scrapers.fetchers.time.sleep"),
        ):
            with pytest.raises(_httpx.HTTPStatusError):
                PdfFetcher().fetch(_TARGET_URL)


# ── RetryingFetcher ───────────────────────────────────────────────────────────


class TestRetryingFetcher:
    """All tests use a mock inner fetcher — no network, no real sleep."""

    def _timeout(self) -> httpx.ReadTimeout:
        return httpx.ReadTimeout("timed out", request=MagicMock())

    def test_retry_recovers_on_transient_timeout(self) -> None:
        """Two timeouts then a success → FetchResult returned, inner called 3×."""
        good = FetchResult(content=b"ok", url=_TARGET_URL, media_type=MediaType.html)
        inner = MagicMock()
        inner.fetch.side_effect = [self._timeout(), self._timeout(), good]

        with patch("scrapers.fetchers.time.sleep"):
            result = RetryingFetcher(inner, max_retries=3).fetch(_TARGET_URL)

        assert result == good
        assert inner.fetch.call_count == 3

    def test_all_retries_exhausted_raises_source_unreachable(self) -> None:
        """Persistent timeout → SourceUnreachableError, not httpx.ReadTimeout."""
        inner = MagicMock()
        inner.fetch.side_effect = self._timeout()  # always fails

        with patch("scrapers.fetchers.time.sleep"):
            with pytest.raises(SourceUnreachableError):
                RetryingFetcher(inner, max_retries=3).fetch(_TARGET_URL)

        assert inner.fetch.call_count == 3

    def test_exhausted_wraps_original_cause(self) -> None:
        """SourceUnreachableError.__cause__ must be the last transport error."""
        inner = MagicMock()
        inner.fetch.side_effect = self._timeout()

        with patch("scrapers.fetchers.time.sleep"):
            with pytest.raises(SourceUnreachableError) as exc_info:
                RetryingFetcher(inner, max_retries=1).fetch(_TARGET_URL)

        assert isinstance(exc_info.value.__cause__, httpx.TransportError)

    def test_non_transport_error_not_retried(self) -> None:
        """HTTP 4xx/5xx propagates immediately — not a transient failure."""
        inner = MagicMock()
        inner.fetch.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        with patch("scrapers.fetchers.time.sleep"):
            with pytest.raises(httpx.HTTPStatusError):
                RetryingFetcher(inner, max_retries=3).fetch(_TARGET_URL)

        assert inner.fetch.call_count == 1  # no retries on non-transport errors

    def test_backoff_sleep_called_between_attempts(self) -> None:
        """Sleep is called between failed attempts but NOT after the final one."""
        inner = MagicMock()
        inner.fetch.side_effect = self._timeout()

        with patch("scrapers.fetchers.time.sleep") as mock_sleep:
            with pytest.raises(SourceUnreachableError):
                RetryingFetcher(inner, max_retries=3, backoff_base=2.0).fetch(_TARGET_URL)

        # 3 attempts → sleep after attempt 1 (2^0=1s) and attempt 2 (2^1=2s),
        # but NOT after the final attempt 3.
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)


# ── Fetcher protocol ──────────────────────────────────────────────────────────


def test_all_fetchers_satisfy_protocol() -> None:
    from scrapers.fetchers import Fetcher

    inner = MagicMock(spec=Fetcher)
    assert isinstance(StaticFetcher(), Fetcher)
    assert isinstance(HeadlessFetcher(), Fetcher)
    assert isinstance(PdfFetcher(), Fetcher)
    assert isinstance(RetryingFetcher(inner), Fetcher)
