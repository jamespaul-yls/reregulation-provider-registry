"""Regression tests for scrapers.arizona_abs.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/az_abs_roster_snap1.html
  sha256 : 9f99d17bf219186a5c737177dbc3f9d2d92d924826dc5a687eeb7130b5fe1473
  fetched: 2026-06-28T22:04 UTC  (first production scrape via ArizonaAbsScraper)

Expected row set is fully determined by that fixed snapshot; update the
counts below and re-run if the fixture is ever refreshed from a new scrape.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.arizona_abs import ArizonaAbsScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "az_abs_roster_snap1.html"
_FIXTURE_SHA256 = "9f99d17bf219186a5c737177dbc3f9d2d92d924826dc5a687eeb7130b5fe1473"
_SOURCE_URL = "https://www.azcourts.gov/cld/Alternative-Business-Structure/Directory"
_RETRIEVED_AT = datetime.datetime(2026, 6, 28, 22, 4, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 167
_ACTIVE_ROWS = 160
_EXITED_ROWS = 7
_ROWS_WITH_WEBSITE = 25  # rows with at least one external http(s) link (not total link count)

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_az_abs",
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256=_FIXTURE_SHA256,
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
    scraper = ArizonaAbsScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256_matches() -> None:
    """Fail fast if the fixture file has been accidentally modified."""
    import hashlib

    digest = hashlib.sha256(_FIXTURE.read_bytes()).hexdigest()
    assert digest == _FIXTURE_SHA256, (
        f"Fixture sha256 mismatch — file may have been edited. "
        f"Expected {_FIXTURE_SHA256}, got {digest}. "
        "Refresh the fixture from a new scraper run and update _FIXTURE_SHA256."
    )


# ── row counts ────────────────────────────────────────────────────────────────


def test_total_row_count(providers) -> None:
    assert len(providers) == _TOTAL_ROWS


def test_active_count(providers) -> None:
    active = [p for p in providers if p.current_status == CurrentStatus.active]
    assert len(active) == _ACTIVE_ROWS


def test_exited_count(providers) -> None:
    exited = [p for p in providers if p.current_status == CurrentStatus.exited]
    assert len(exited) == _EXITED_ROWS


def test_website_count(providers) -> None:
    with_website = [p for p in providers if p.website is not None]
    assert len(with_website) == _ROWS_WITH_WEBSITE


# ── schema invariants ─────────────────────────────────────────────────────────


def test_all_providers_are_entities(providers) -> None:
    assert all(p.provider_type == ProviderType.entity for p in providers)


def test_all_jurisdiction_az(providers) -> None:
    assert all(p.jurisdiction == "AZ" for p in providers)


def test_all_program_id_az_abs(providers) -> None:
    assert all(p.program_id == "prog_az_abs" for p in providers)


def test_authorization_date_always_none(providers) -> None:
    assert all(p.authorization_date is None for p in providers)


def test_no_empty_legal_names(providers) -> None:
    assert all(p.legal_name for p in providers)


def test_all_normalized_names_nonempty(providers) -> None:
    assert all(p.normalized_name for p in providers)


def test_provider_ids_unique(providers) -> None:
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_provider_ids_use_az_abs_prefix(providers) -> None:
    assert all(p.provider_id.startswith("prov_az_abs_") for p in providers)


def test_websites_are_http_urls(providers) -> None:
    for p in providers:
        if p.website is not None:
            assert p.website.startswith(("http://", "https://"))


def test_no_cloudflare_obfuscated_urls_captured(providers) -> None:
    for p in providers:
        if p.website is not None:
            assert "/cdn-cgi/" not in p.website


# ── spot-check named rows ─────────────────────────────────────────────────────


def _by_name(providers, name: str):
    matches = [p for p in providers if p.legal_name == name]
    assert len(matches) == 1, f"Expected exactly 1 row for {name!r}, got {len(matches)}"
    return matches[0]


def test_spot_check_10xlaw(providers) -> None:
    p = _by_name(providers, "10xLaw.com, Inc.")
    assert p.current_status == CurrentStatus.active
    assert p.practice_areas_raw == []
    assert p.website is None
    assert p.provider_id == _provider_id("10xLaw.com, Inc.")


def test_spot_check_accident_recovery(providers) -> None:
    p = _by_name(providers, "Accident Recovery Law Firm, LLC")
    assert p.current_status == CurrentStatus.active
    assert p.practice_areas_raw == ["Personal Injury"]
    assert p.website is None


def test_spot_check_aiken_farrell(providers) -> None:
    p = _by_name(providers, "Aiken Farrell Kroloff, LLC")
    assert p.current_status == CurrentStatus.active
    assert p.practice_areas_raw == ["Victim Advocacy"]
    assert p.website == "https://afk-law.com"


def test_spot_check_multi_practice_area(providers) -> None:
    p = _by_name(providers, "Amborella Law, PLLC")
    assert "Civil Litigation" in p.practice_areas_raw
    assert "Subrogation" in p.practice_areas_raw


def test_spot_check_api_law(providers) -> None:
    p = _by_name(providers, "API Law of Arizona, PLLC (Formerly, Hive Legal, LLC)")
    assert p.website == "https://www.api.law/"


# ── provenance stamped from snapshot ─────────────────────────────────────────


def test_provenance_source_url(providers, fixture_snapshot) -> None:
    assert all(p.source_url == fixture_snapshot.source_url for p in providers)


def test_provenance_retrieved_at(providers, fixture_snapshot) -> None:
    assert all(p.retrieved_at == fixture_snapshot.retrieved_at for p in providers)


def test_provenance_scraper_version(providers, fixture_snapshot) -> None:
    assert all(p.scraper_version == fixture_snapshot.scraper_version for p in providers)


def test_first_seen_snapshot_id_set(providers, fixture_snapshot) -> None:
    # _stamp() sets first_seen when None; parse() leaves it None for _stamp() to fill.
    # These providers came through parse() only (not run()), so first_seen is None here.
    # This test documents that invariant explicitly.
    assert all(p.first_seen_snapshot_id is None for p in providers)


def test_last_seen_snapshot_id_none_before_stamp(providers) -> None:
    assert all(p.last_seen_snapshot_id is None for p in providers)
