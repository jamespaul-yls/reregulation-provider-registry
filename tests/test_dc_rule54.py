"""Regression tests for scrapers.dc_rule54.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/dc_rule54_snap1.html
  sha256  : 73fe40c243259476dd16c3bb0a79782dc653fe65580d7ab9da6c50eee49d9519
  fetched : 2026-06-29 (first production snapshot via DcRule54Scraper)
  source  : https://www.dcbar.org/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct
              /Law-Firms-and-Associations/Professional-Independence-of-a-Lawyer

DC Rule 5.4(b) is a permissive ethics rule (eff. Jan. 1, 1991), not a licensing scheme.
No registration roster exists. parse() returns [] by design.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import MediaType
from models.schema import SourceSnapshot
from scrapers.dc_rule54 import DcRule54Scraper

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "dc_rule54_snap1.html"
_FIXTURE_SHA256 = "73fe40c243259476dd16c3bb0a79782dc653fe65580d7ab9da6c50eee49d9519"
_SOURCE_URL = (
    "https://www.dcbar.org/For-Lawyers/Legal-Ethics/Rules-of-Professional-Conduct"
    "/Law-Firms-and-Associations/Professional-Independence-of-a-Lawyer"
)
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    sha = _FIXTURE_SHA256
    return SourceSnapshot(
        snapshot_id=f"snap_{sha[:16]}",
        program_id="prog_dc_rule54",
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256=sha,
        storage_path=str(_FIXTURE),
        media_type=MediaType.html,
        scraper_version="0.1.0",
    )


@pytest.fixture(scope="module")
def providers(
    fixture_snapshot: SourceSnapshot,
    fixture_raw: bytes,
    tmp_path_factory: pytest.TempPathFactory,
):
    raw_dir = tmp_path_factory.mktemp("raw")
    scraper = DcRule54Scraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── parse() contract: no roster → empty list ─────────────────────────────────


def test_parse_returns_empty_list(providers):
    """No registration roster exists for Rule 5.4(b) — permissive ethics rule only."""
    assert providers == []


def test_parse_returns_list_type(providers):
    assert isinstance(providers, list)


# ── scraper metadata ──────────────────────────────────────────────────────────


def test_scraper_program_id(tmp_path):
    scraper = DcRule54Scraper(raw_dir=tmp_path)
    assert scraper.program_id == "prog_dc_rule54"


def test_scraper_source_url(tmp_path):
    scraper = DcRule54Scraper(raw_dir=tmp_path)
    assert scraper.source_url == _SOURCE_URL


def test_scraper_version(tmp_path):
    scraper = DcRule54Scraper(raw_dir=tmp_path)
    assert scraper.version == "0.1.0"
