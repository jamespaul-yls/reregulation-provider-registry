"""Tests for pipeline.wayback — all offline via mocks.

No network calls: CDX API and Wayback content fetches are mocked with
unittest.mock. DB writes use a tmp-path in-memory DuckDB.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.enums import CurrentStatus, MediaType
from models.schema import Program, Provider, SourceSnapshot
from pipeline.db import RegistryStore
from pipeline.wayback import (
    _WAYBACK_SCRAPER_VERSION,
    CdxCapture,
    backfill_program,
    fetch_cdx,
    fetch_wayback_content,
)

_UTC = datetime.UTC
_SOURCE_URL = "https://example.gov/roster"


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_program(program_id: str = "prog_az_abs") -> Program:
    return Program(
        program_id=program_id,
        jurisdiction="AZ",
        program_name="Test Program",
        program_type="abs",
        regulator="Test Regulator",
        regulator_url="https://example.gov/",
        authorizing_rule="Rule 1",
        launch_date=datetime.date(2020, 1, 1),
        program_status="active",
        allows_nonlawyer_ownership=True,
        allows_upl_waiver=False,
        allows_software_provider=True,
        source_url=_SOURCE_URL,
        retrieved_at=datetime.datetime(2026, 6, 29, tzinfo=_UTC),
        scraper_version="0.1.0",
    )


def _make_capture(ts: str, original_url: str = _SOURCE_URL) -> CdxCapture:
    retrieved_at = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=_UTC)
    return CdxCapture(
        timestamp=ts,
        original_url=original_url,
        status_code=200,
        digest=f"DIGEST{ts[:8]}",
        retrieved_at=retrieved_at,
    )


def _mock_scraper(
    program_id: str = "prog_az_abs",
    providers_per_call: list[list[Provider]] | None = None,
) -> MagicMock:
    """Minimal mock BaseScraper. providers_per_call controls what parse returns."""
    scraper = MagicMock()
    scraper.program_id = program_id
    scraper.source_url = _SOURCE_URL
    scraper.default_fetcher_class = MagicMock()  # not PdfFetcher → html
    # _wayback_parse is NOT overridden (use default behaviour)
    scraper._wayback_parse = scraper._wayback_parse  # keep mock's auto-attribute

    if providers_per_call is not None:
        scraper._wayback_parse.side_effect = providers_per_call
    else:
        scraper._wayback_parse.return_value = []

    return scraper


def _make_provider(
    provider_id: str,
    program_id: str = "prog_az_abs",
    status: CurrentStatus = CurrentStatus.active,
    sha: str = "a" * 64,
) -> Provider:
    ts = datetime.datetime(2020, 6, 1, tzinfo=_UTC)
    return Provider(
        provider_id=provider_id,
        program_id=program_id,
        provider_type="entity",
        legal_name=f"Provider {provider_id}",
        normalized_name=f"provider {provider_id}",
        jurisdiction="AZ",
        current_status=status,
        first_seen_snapshot_id=f"snap_{sha[:16]}",
        last_seen_snapshot_id=f"snap_{sha[:16]}",
        source_url=_SOURCE_URL,
        retrieved_at=ts,
        scraper_version="0.1.0",
    )


@pytest.fixture()
def store(tmp_path: Path) -> RegistryStore:
    s = RegistryStore(tmp_path / "registry.duckdb")
    s.init_schema()
    return s


# ── fetch_cdx ────────────────────────────────────────────────────────────────


class TestFetchCdx:
    def _cdx_response(self, rows: list[list[str]]) -> MagicMock:
        resp = MagicMock()
        resp.json.return_value = [
            ["timestamp", "original", "statuscode", "digest"],
            *rows,
        ]
        resp.raise_for_status = MagicMock()
        return resp

    def test_parses_captures_correctly(self) -> None:
        row = ["20200615120000", "https://example.gov/roster", "200", "ABCDEF"]
        mock_resp = self._cdx_response([row])
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            captures = fetch_cdx("https://example.gov/roster")

        assert len(captures) == 1
        c = captures[0]
        assert c.timestamp == "20200615120000"
        assert c.original_url == "https://example.gov/roster"
        assert c.status_code == 200
        assert c.digest == "ABCDEF"
        expected_dt = datetime.datetime(2020, 6, 15, 12, 0, 0, tzinfo=_UTC)
        assert c.retrieved_at == expected_dt

    def test_skips_header_row(self) -> None:
        rows = [
            ["20200101000000", "https://example.gov/", "200", "DIG1"],
            ["20201201000000", "https://example.gov/", "200", "DIG2"],
        ]
        mock_resp = self._cdx_response(rows)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            captures = fetch_cdx("https://example.gov/")

        # Only the two data rows; header is stripped
        assert len(captures) == 2

    def test_empty_response_returns_empty_list(self) -> None:
        resp = MagicMock()
        resp.json.return_value = []
        resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            assert fetch_cdx("https://example.gov/") == []

    def test_sorted_chronologically(self) -> None:
        rows = [
            ["20201201000000", "https://example.gov/", "200", "DIG2"],
            ["20200101000000", "https://example.gov/", "200", "DIG1"],
        ]
        resp = MagicMock()
        resp.json.return_value = [["timestamp", "original", "statuscode", "digest"], *rows]
        resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            captures = fetch_cdx("https://example.gov/")

        assert captures[0].timestamp == "20200101000000"
        assert captures[1].timestamp == "20201201000000"

    def test_passes_date_filters_and_limit(self) -> None:
        resp = MagicMock()
        resp.json.return_value = []
        resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        from_dt = datetime.date(2018, 1, 1)
        to_dt = datetime.date(2021, 12, 31)

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            fetch_cdx("https://example.gov/", from_dt=from_dt, to_dt=to_dt, max_captures=50)

        _, kwargs = mock_client.get.call_args
        params = kwargs.get("params", {})
        assert params["from"] == "20180101"
        assert params["to"] == "20211231"
        assert params["limit"] == 50


# ── fetch_wayback_content ─────────────────────────────────────────────────────


class TestFetchWaybackContent:
    def _capture(self, ts: str = "20200615120000") -> CdxCapture:
        return _make_capture(ts)

    def test_returns_bytes_on_success(self) -> None:
        content = b"<html>roster</html>"
        resp = MagicMock()
        resp.content = content
        resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            result = fetch_wayback_content(self._capture())

        assert result == content

    def test_returns_none_on_http_error(self) -> None:
        import httpx as _httpx

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = _httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            result = fetch_wayback_content(self._capture())

        assert result is None

    def test_uses_id_modifier_in_url(self) -> None:
        resp = MagicMock()
        resp.content = b"ok"
        resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = resp

        cap = _make_capture("20200615120000", "https://example.gov/roster")
        with (
            patch("pipeline.wayback.httpx.Client", return_value=mock_client),
            patch("pipeline.wayback.time.sleep"),
        ):
            fetch_wayback_content(cap)

        call_url = mock_client.get.call_args[0][0]
        assert "id_" in call_url
        assert "20200615120000" in call_url
        assert "example.gov/roster" in call_url


# ── backfill_program ──────────────────────────────────────────────────────────


class TestBackfillProgram:
    """All tests use in-memory DuckDB + mocked HTTP. No real network calls."""

    def _seed_store(self, store: RegistryStore, program_id: str = "prog_az_abs") -> None:
        store.upsert_program(_make_program(program_id))

    def _providers(self, program_id: str = "prog_az_abs", n: int = 2) -> list[Provider]:
        ts = datetime.datetime(2020, 1, 1, tzinfo=_UTC)
        return [
            Provider(
                provider_id=f"prov_{i}",
                program_id=program_id,
                provider_type="entity",
                legal_name=f"Provider {i}",
                normalized_name=f"provider {i}",
                jurisdiction="AZ",
                current_status=CurrentStatus.active,
                first_seen_snapshot_id=None,
                last_seen_snapshot_id=None,
                source_url=_SOURCE_URL,
                retrieved_at=ts,
                scraper_version="0.1.0",
            )
            for i in range(n)
        ]

    def test_dry_run_produces_no_db_writes(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        providers = self._providers()
        cap = _make_capture("20200615120000")

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.return_value = providers
        # _stamp must produce usable Provider objects
        from scrapers.base import BaseScraper

        scraper._stamp = BaseScraper._stamp

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=[cap]),
            patch("pipeline.wayback.fetch_wayback_content", return_value=b"<html>ok</html>"),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.status == "ok"
        assert report.captures_ingested == 1
        # No snapshot rows written
        count = store.conn.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0]
        assert count == 0
        # No provider rows written
        count = store.conn.execute("SELECT COUNT(*) FROM provider").fetchone()[0]
        assert count == 0

    def test_filters_captures_after_first_own_snapshot(
        self, store: RegistryStore, tmp_path: Path
    ) -> None:
        self._seed_store(store)
        # Insert an "own" snapshot dated 2021-01-01
        own_sha = "c" * 64
        own_snap = SourceSnapshot(
            snapshot_id=f"snap_{own_sha[:16]}",
            program_id="prog_az_abs",
            source_url=_SOURCE_URL,
            retrieved_at=datetime.datetime(2021, 1, 1, tzinfo=_UTC),
            content_sha256=own_sha,
            storage_path=f"/data/raw/{own_sha}.html",
            media_type=MediaType.html,
            scraper_version="0.1.0",
        )
        store.upsert_snapshot(own_snap)

        # Wayback has captures before AND after 2021-01-01
        captures = [
            _make_capture("20190615120000"),  # before → should be included
            _make_capture("20200615120000"),  # before → included
            _make_capture("20211015120000"),  # after  → excluded
        ]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.return_value = self._providers()
        from scrapers.base import BaseScraper

        scraper._stamp = BaseScraper._stamp

        distinct_bytes = [
            b"<html>roster v1</html>",
            b"<html>roster v2</html>",
            b"<html>roster v3</html>",
        ]
        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", side_effect=distinct_bytes),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        # Only the 2 captures before the own snapshot should be processed
        assert report.captures_ingested == 2

    def test_deduplicates_identical_content(self, store: RegistryStore, tmp_path: Path) -> None:
        """Two captures with the same sha256 → only 1 ingested, 1 dedup-skipped."""
        self._seed_store(store)
        # Same raw bytes for both captures
        raw = b"<html>identical roster</html>"

        captures = [
            _make_capture("20200101000000"),
            _make_capture("20200601000000"),
        ]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.return_value = self._providers()
        from scrapers.base import BaseScraper

        scraper._stamp = BaseScraper._stamp

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", return_value=raw),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.captures_ingested == 1
        assert report.captures_skipped_dedup == 1

    def test_detects_gap_between_captures(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        # Captures with a 200-day gap (> 90-day threshold)
        captures = [
            _make_capture("20190101000000"),
            _make_capture("20190720000000"),  # 200 days later
        ]

        raw_bytes = [b"<html>roster v1</html>", b"<html>roster v2</html>"]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.return_value = self._providers()
        from scrapers.base import BaseScraper

        scraper._stamp = BaseScraper._stamp

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", side_effect=raw_bytes),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.captures_ingested == 2
        assert len(report.gaps) == 1
        _, _, gap_days = report.gaps[0]
        assert gap_days > 90

    def test_parse_error_counted_and_skipped(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        captures = [_make_capture("20200101000000")]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.side_effect = ValueError("parse failed")

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", return_value=b"<html>bad</html>"),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.captures_ingested == 0
        assert report.captures_parse_error == 1

    def test_fetch_failure_counted_as_error(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        captures = [_make_capture("20200101000000")]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", return_value=None),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.captures_ingested == 0
        assert report.captures_parse_error == 1

    def test_no_captures_status(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL

        with patch("pipeline.wayback.fetch_cdx", return_value=[]):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.status == "no_captures"
        assert report.captures_found == 0

    def test_all_covered_when_all_captures_after_own_snap(
        self, store: RegistryStore, tmp_path: Path
    ) -> None:
        self._seed_store(store)
        own_sha = "e" * 64
        own_snap = SourceSnapshot(
            snapshot_id=f"snap_{own_sha[:16]}",
            program_id="prog_az_abs",
            source_url=_SOURCE_URL,
            retrieved_at=datetime.datetime(2019, 1, 1, tzinfo=_UTC),
            content_sha256=own_sha,
            storage_path=f"/data/raw/{own_sha}.html",
            media_type=MediaType.html,
            scraper_version="0.1.0",
        )
        store.upsert_snapshot(own_snap)

        # All Wayback captures are AFTER the own snapshot
        captures = [_make_capture("20200101000000"), _make_capture("20210101000000")]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL

        with patch("pipeline.wayback.fetch_cdx", return_value=captures):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.status == "all_covered"
        assert report.captures_ingested == 0

    def test_date_range_reported_correctly(self, store: RegistryStore, tmp_path: Path) -> None:
        self._seed_store(store)
        captures = [
            _make_capture("20180301000000"),
            _make_capture("20191015000000"),
            _make_capture("20201201000000"),
        ]
        raw_bytes = [
            b"<html>v1</html>",
            b"<html>v2</html>",
            b"<html>v3</html>",
        ]

        scraper = MagicMock()
        scraper.program_id = "prog_az_abs"
        scraper.source_url = _SOURCE_URL
        scraper.default_fetcher_class = MagicMock()
        scraper._wayback_parse.return_value = self._providers()
        from scrapers.base import BaseScraper

        scraper._stamp = BaseScraper._stamp

        with (
            patch("pipeline.wayback.fetch_cdx", return_value=captures),
            patch("pipeline.wayback.fetch_wayback_content", side_effect=raw_bytes),
        ):
            report = backfill_program(scraper, store, tmp_path, dry_run=True)

        assert report.date_range == (
            datetime.date(2018, 3, 1),
            datetime.date(2020, 12, 1),
        )
        assert report.captures_ingested == 3


# ── WashingtonLlltScraper._wayback_parse ─────────────────────────────────────


class TestWaLlltWaybackParse:
    """Verify the WA LLLT override handles single-page Wayback HTML."""

    def _make_snap(self) -> SourceSnapshot:
        sha = "f" * 64
        return SourceSnapshot(
            snapshot_id=f"snap_{sha[:16]}",
            program_id="prog_wa_lllt",
            source_url="https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx"
            "?ShowSearchResults=TRUE&LicenseType=LLLT",
            retrieved_at=datetime.datetime(2019, 6, 15, tzinfo=_UTC),
            content_sha256=sha,
            storage_path=f"/data/raw/{sha}.html",
            media_type=MediaType.html,
            scraper_version=_WAYBACK_SCRAPER_VERSION,
        )

    def _single_page_html(self, n_rows: int = 5) -> bytes:
        """Minimal WSBA directory HTML with n_rows data rows (single Wayback page)."""
        rows = "\n".join(
            f"<tr>"
            f"<td>{i}LLLT</td>"
            f"<td>First{i}</td>"
            f"<td>Last{i}</td>"
            f"<td>Seattle</td>"
            f"<td>Active</td>"
            f"<td>206-000-000{i}</td>"
            f"</tr>"
            for i in range(101, 101 + n_rows)
        )
        table_id = "dnn_ctr2972_DNNWebControlContainer_ctl00_dg"
        return (f'<html><body><table id="{table_id}">{rows}</table></body></html>').encode()

    def test_wayback_parse_extracts_partial_page(self) -> None:
        from scrapers.washington_lllt import WashingtonLlltScraper

        scraper = WashingtonLlltScraper.__new__(WashingtonLlltScraper)
        scraper.program_id = "prog_wa_lllt"
        snap = self._make_snap()
        raw = self._single_page_html(n_rows=5)

        providers = scraper._wayback_parse(snap, raw)

        # 5 rows < _MIN_EXPECTED_ROWS=50, but _wayback_parse doesn't enforce the floor
        assert len(providers) == 5
        assert all(p.jurisdiction == "WA" for p in providers)
        assert all(p.program_id == "prog_wa_lllt" for p in providers)

    def test_wayback_parse_returns_empty_on_unrecognised_structure(self) -> None:
        from scrapers.washington_lllt import WashingtonLlltScraper

        scraper = WashingtonLlltScraper.__new__(WashingtonLlltScraper)
        scraper.program_id = "prog_wa_lllt"
        snap = self._make_snap()

        # HTML with no WSBA table structure
        raw = b"<html><body><p>503 Service Unavailable</p></body></html>"
        providers = scraper._wayback_parse(snap, raw)
        assert providers == []

    def test_standard_parse_still_enforces_min_rows(self) -> None:
        """parse() must still raise for < 50 rows; _wayback_parse() must not."""
        from scrapers.washington_lllt import WashingtonLlltScraper

        scraper = WashingtonLlltScraper.__new__(WashingtonLlltScraper)
        scraper.program_id = "prog_wa_lllt"
        snap = self._make_snap()

        # Build a combined-format HTML that parse() accepts (has _COMBINED_TABLE_ID)
        # but with only 5 rows — should raise
        rows = "\n".join(
            f"<tr>"
            f"<td>{i}LLLT</td>"
            f"<td>First{i}</td>"
            f"<td>Last{i}</td>"
            f"<td>Seattle</td>"
            f"<td>Active</td>"
            f"</tr>"
            for i in range(101, 106)
        )
        combined_html = (
            f'<html><body><table id="wsba-lllt-combined-roster">{rows}</table></body></html>'
        ).encode()

        with pytest.raises(ValueError, match="only 5 providers"):
            scraper.parse(snap, combined_html)
