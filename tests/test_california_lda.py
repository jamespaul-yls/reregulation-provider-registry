"""Regression tests for scrapers.california_lda.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/ca_lda_program_snap1.html
  sha256  : ff8e81c925f3fbfe23c66546a04f557005ac554e8f8703dd7b8162d1cd2651ef
  fetched : 2026-06-29 (first production snapshot via CaliforniaLdaScraper)
  source  : https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml
              ?sectionNum=6400.&lawCode=BPC

Provider count is zero by design: California LDA registration is county-level
(B&P Code § 6400 et seq.), administered by 58 independent county clerks. No
statewide registry exists. County-level scraping is deferred to v2.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import MediaType
from models.schema import SourceSnapshot
from scrapers.california_lda import CaliforniaLdaScraper

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "ca_lda_program_snap1.html"
_FIXTURE_SHA256 = "ff8e81c925f3fbfe23c66546a04f557005ac554e8f8703dd7b8162d1cd2651ef"
_SOURCE_URL = (
    "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
    "?sectionNum=6400.&lawCode=BPC"
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
        program_id="prog_ca_lda",
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
    scraper = CaliforniaLdaScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── parse() contract: no roster → empty list ─────────────────────────────────


def test_parse_returns_empty_list(providers):
    """County-level registration; no statewide roster. parse() must return []."""
    assert providers == []


def test_parse_returns_list_type(providers):
    assert isinstance(providers, list)


# ── scraper metadata ──────────────────────────────────────────────────────────


def test_scraper_program_id(tmp_path):
    scraper = CaliforniaLdaScraper(raw_dir=tmp_path)
    assert scraper.program_id == "prog_ca_lda"


def test_scraper_source_url(tmp_path):
    scraper = CaliforniaLdaScraper(raw_dir=tmp_path)
    assert scraper.source_url == _SOURCE_URL


def test_scraper_version(tmp_path):
    scraper = CaliforniaLdaScraper(raw_dir=tmp_path)
    assert scraper.version == "0.1.0"
