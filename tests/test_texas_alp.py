"""Regression tests for scrapers.texas_alp.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/tx_alp_program_snap1.html
  sha256  : d043c95a4aac2571479c7f5226188d6e15e76691a0cf2371dce2835bb7b31bdf
  fetched : 2026-06-29 (first production snapshot via TexasAlpScraper)
  source  : https://www.texasbar.com/paraprofessionals/

Program status: PAUSED — preliminary rules approved 2024-08-06 (Misc. Docket 24-9050);
effective date delayed 2024-11-04 (Misc. Docket 24-9095); no individual roster as of
June 2026. parse() returns [] by design; this test locks that behaviour.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import MediaType
from models.schema import SourceSnapshot
from scrapers.texas_alp import TexasAlpScraper

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "tx_alp_program_snap1.html"
_FIXTURE_SHA256 = "d043c95a4aac2571479c7f5226188d6e15e76691a0cf2371dce2835bb7b31bdf"
_SOURCE_URL = "https://www.texasbar.com/paraprofessionals/"
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
        program_id="prog_tx_alp",
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
    scraper = TexasAlpScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── parse() contract: no roster → empty list ─────────────────────────────────


def test_parse_returns_empty_list(providers):
    """Program is paused; no individuals licensed. parse() must return []."""
    assert providers == []


def test_parse_returns_list_type(providers):
    assert isinstance(providers, list)


# ── scraper metadata ──────────────────────────────────────────────────────────


def test_scraper_program_id(tmp_path):
    scraper = TexasAlpScraper(raw_dir=tmp_path)
    assert scraper.program_id == "prog_tx_alp"


def test_scraper_source_url(tmp_path):
    scraper = TexasAlpScraper(raw_dir=tmp_path)
    assert scraper.source_url == _SOURCE_URL


def test_scraper_version(tmp_path):
    scraper = TexasAlpScraper(raw_dir=tmp_path)
    assert scraper.version == "0.1.0"
