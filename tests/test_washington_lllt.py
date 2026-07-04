"""Regression tests for scrapers.washington_lllt.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/wa_lllt_roster_snap1.html
  sha256  : c700fb20a472580a9c35036ef271f96f0218289c8269a8693f35cb984abc1456
  fetched : 2026-06-29 (first production scrape via WashingtonLlltScraper)
  source  : https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx
              ?ShowSearchResults=TRUE&LicenseType=LLLT
  note    : combined HTML synthesized from 5 Playwright-paginated pages (20/20/20/20/15 rows)

The LLLT program was sunset July 31, 2021 (no new admissions). Existing licensees may
maintain their license. 68 of 95 showed Active status as of this snapshot.

Status mapping:
  Active / PRO BONO       → active   (68 total)
  Voluntarily Resigned / Retired → exited (10 total)
  Inactive                → unknown  (13 total)
  Suspended               → suspended (4 total)
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.washington_lllt import WashingtonLlltScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "wa_lllt_roster_snap1.html"
_FIXTURE_SHA256 = "c700fb20a472580a9c35036ef271f96f0218289c8269a8693f35cb984abc1456"
_RESULTS_URL = (
    "https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx"
    "?ShowSearchResults=TRUE&LicenseType=LLLT"
)
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 95  # WSBA lblRowCount as of 2026-06-29
_ACTIVE_ROWS = 68  # "Active" (67) + "PRO BONO" (1)
_EXITED_ROWS = 10  # "Voluntarily Resigned" (9) + "Retired" (1)
_UNKNOWN_ROWS = 13  # "Inactive" (13)
_SUSPENDED_ROWS = 4  # "Suspended" (4)

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_wa_lllt",
        source_url=_RESULTS_URL,
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
    scraper = WashingtonLlltScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── row counts ────────────────────────────────────────────────────────────────


def test_total_row_count(providers):
    assert len(providers) == _TOTAL_ROWS


def test_active_count(providers):
    active = [p for p in providers if p.current_status == CurrentStatus.active]
    assert len(active) == _ACTIVE_ROWS


def test_exited_count(providers):
    exited = [p for p in providers if p.current_status == CurrentStatus.exited]
    assert len(exited) == _EXITED_ROWS


def test_unknown_count(providers):
    unknown = [p for p in providers if p.current_status == CurrentStatus.unknown]
    assert len(unknown) == _UNKNOWN_ROWS


def test_suspended_count(providers):
    suspended = [p for p in providers if p.current_status == CurrentStatus.suspended]
    assert len(suspended) == _SUSPENDED_ROWS


def test_all_individual(providers):
    assert all(p.provider_type == ProviderType.individual for p in providers)


def test_all_wa_jurisdiction(providers):
    assert all(p.jurisdiction == "WA" for p in providers)


def test_all_wa_lllt_program(providers):
    assert all(p.program_id == "prog_wa_lllt" for p in providers)


def test_provider_ids_unique(providers):
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_all_family_law_practice_area(providers):
    assert all(p.practice_areas_raw == ["Family Law"] for p in providers)


def test_no_authorization_dates(providers):
    assert all(p.authorization_date is None for p in providers)


# ── spot checks: specific providers ──────────────────────────────────────────


def test_provider_101(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("101")]
    assert p.legal_name == "Michelle M Cummings"
    assert p.current_status == CurrentStatus.active


def test_provider_103_exited(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("103")]
    assert p.legal_name == "Angela K Wright"
    assert p.current_status == CurrentStatus.exited  # "Voluntarily Resigned"


def test_provider_106_unknown(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("106")]
    assert p.legal_name == "Cindy K Stewart"
    assert p.current_status == CurrentStatus.unknown  # "Inactive"


def test_provider_first_and_last(providers):
    by_id = {p.provider_id: p for p in providers}
    # First LLLT
    assert _provider_id("101") in by_id
    # Last LLLT in this fixture
    assert _provider_id("196") in by_id


# ── license number format ────────────────────────────────────────────────────


def test_provider_ids_follow_format(providers):
    import re

    pattern = re.compile(r"^prov_wa_lllt_\d+$")
    for p in providers:
        assert pattern.match(p.provider_id), f"Bad ID format: {p.provider_id!r}"


# ── name format: First Last (not Last, First) ────────────────────────────────


def test_names_not_last_first(providers):
    # WSBA directory gives FirstName + LastName separately; combined in First Last order
    # No commas expected in any name
    for p in providers:
        assert "," not in p.legal_name, (
            f"{p.provider_id}: name has unexpected comma: {p.legal_name!r}"
        )


# ── normalized names ─────────────────────────────────────────────────────────


def test_normalized_names_populated(providers):
    assert all(p.normalized_name for p in providers)


# ── provenance fields ─────────────────────────────────────────────────────────


def test_provenance_fields(providers, fixture_snapshot: SourceSnapshot):
    for p in providers:
        assert p.source_url == _RESULTS_URL
        assert p.retrieved_at == _RETRIEVED_AT
        assert p.scraper_version == "0.1.0"
