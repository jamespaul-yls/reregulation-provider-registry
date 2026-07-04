"""Regression tests for scrapers.arizona_lp.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/az_lp_directory_snap1.html
  sha256 : 26827600c4012050abb7f8eb58abd307890449888ee84ebae596a7cd8638e4b4
  fetched: 2026-06-29 (first production scrape via ArizonaLpScraper)

Expected row set is fully determined by that fixed snapshot; update the
counts below and re-pin if the fixture is ever refreshed from a new scrape.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.arizona_lp import ArizonaLpScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "az_lp_directory_snap1.html"
_FIXTURE_SHA256 = "26827600c4012050abb7f8eb58abd307890449888ee84ebae596a7cd8638e4b4"
_SOURCE_URL = "https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory"
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 120
_ACTIVE_ROWS = 113
_EXITED_ROWS = 7
_MULTI_AREA_ROWS = 12  # rows with more than one practice area

# Canonical practice area counts (after normalization)
_FAMILY_ROWS = 90
_CIVIL_ROWS = 20
_CRIMINAL_ROWS = 18
_ADMINISTRATIVE_ROWS = 3
_JUVENILE_ROWS = 3

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_az_lp",
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
    scraper = ArizonaLpScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256_matches() -> None:
    digest = hashlib.sha256(_FIXTURE.read_bytes()).hexdigest()
    assert digest == _FIXTURE_SHA256, (
        f"Fixture sha256 mismatch — file may have been edited. "
        f"Expected {_FIXTURE_SHA256}, got {digest}. "
        "Refresh from a new scraper run and update _FIXTURE_SHA256."
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


def test_multi_area_row_count(providers) -> None:
    multi = [p for p in providers if len(p.practice_areas_raw) > 1]
    assert len(multi) == _MULTI_AREA_ROWS


# ── practice area counts ──────────────────────────────────────────────────────


def test_family_area_count(providers) -> None:
    family = [p for p in providers if "Family" in p.practice_areas_raw]
    assert len(family) == _FAMILY_ROWS


def test_civil_area_count(providers) -> None:
    civil = [p for p in providers if "Civil" in p.practice_areas_raw]
    assert len(civil) == _CIVIL_ROWS


def test_criminal_area_count(providers) -> None:
    criminal = [p for p in providers if "Criminal" in p.practice_areas_raw]
    assert len(criminal) == _CRIMINAL_ROWS


def test_administrative_area_count(providers) -> None:
    admin = [p for p in providers if "Administrative" in p.practice_areas_raw]
    assert len(admin) == _ADMINISTRATIVE_ROWS


def test_juvenile_area_count(providers) -> None:
    juvenile = [p for p in providers if "Juvenile" in p.practice_areas_raw]
    assert len(juvenile) == _JUVENILE_ROWS


# ── schema invariants ─────────────────────────────────────────────────────────


def test_all_providers_are_individuals(providers) -> None:
    assert all(p.provider_type == ProviderType.individual for p in providers)


def test_all_jurisdiction_az(providers) -> None:
    assert all(p.jurisdiction == "AZ" for p in providers)


def test_all_program_id_az_lp(providers) -> None:
    assert all(p.program_id == "prog_az_lp" for p in providers)


def test_authorization_date_always_none(providers) -> None:
    assert all(p.authorization_date is None for p in providers)


def test_no_empty_legal_names(providers) -> None:
    assert all(p.legal_name for p in providers)


def test_all_normalized_names_nonempty(providers) -> None:
    assert all(p.normalized_name for p in providers)


def test_provider_ids_unique(providers) -> None:
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_provider_ids_use_az_lp_prefix(providers) -> None:
    assert all(p.provider_id.startswith("prov_az_lp_") for p in providers)


def test_all_practice_areas_nonempty(providers) -> None:
    """Every LP must have at least one normalized area."""
    assert all(p.practice_areas_raw for p in providers)


def test_practice_areas_only_canonical_values(providers) -> None:
    """No raw area string leaks into the normalized list; no typos."""
    canonical = {"Family", "Civil", "Criminal", "Administrative", "Juvenile"}
    for p in providers:
        for area in p.practice_areas_raw:
            assert area in canonical, (
                f"{p.legal_name!r}: unexpected area {area!r} — "
                "update _AREA_ALIASES if the source added a new area"
            )


def test_no_website_fields(providers) -> None:
    """LP directory does not publish websites; all must be None."""
    assert all(p.website is None for p in providers)


def test_ownership_structure_null(providers) -> None:
    assert all(p.ownership_structure is None for p in providers)


def test_uses_technology_null(providers) -> None:
    assert all(p.uses_technology is None for p in providers)


def test_uses_ai_null(providers) -> None:
    assert all(p.uses_ai is None for p in providers)


# ── spot-check named rows ─────────────────────────────────────────────────────


def _by_name(providers, name: str):
    matches = [p for p in providers if p.legal_name == name]
    assert len(matches) == 1, f"Expected exactly 1 row for {name!r}, got {len(matches)}"
    return matches[0]


def test_spot_check_trey_boblett(providers) -> None:
    p = _by_name(providers, "Trey Boblett")
    assert p.current_status == CurrentStatus.active
    assert p.practice_areas_raw == ["Family"]
    assert p.provider_id == _provider_id("Trey Boblett")


def test_spot_check_jared_gunn_active_as_attorney_exited(providers) -> None:
    """'Active as an attorney' must map to exited."""
    p = _by_name(providers, "Jared Gunn")
    assert p.current_status == CurrentStatus.exited
    assert "Juvenile" in p.practice_areas_raw


def test_spot_check_siegrid_burton_not_active(providers) -> None:
    """'Not Active' maps to exited."""
    p = _by_name(providers, "Siegrid Burton")
    assert p.current_status == CurrentStatus.exited
    assert "Criminal" in p.practice_areas_raw


def test_spot_check_criminial_typo_normalized(providers) -> None:
    """The live roster has 'Criminial' (typo); must normalize to 'Criminal'."""
    criminal = [p for p in providers if "Criminal" in p.practice_areas_raw]
    # If the typo row is present it must have been normalized — 'Criminial' must never appear
    for p in criminal:
        assert "Criminial" not in p.practice_areas_raw


def test_spot_check_multi_area_victoria_castro(providers) -> None:
    p = _by_name(providers, "Victoria Castro")
    assert p.current_status == CurrentStatus.active
    assert "Family" in p.practice_areas_raw
    assert "Criminal" in p.practice_areas_raw


def test_spot_check_multi_area_paul_gladden(providers) -> None:
    p = _by_name(providers, "Paul Gladden")
    assert p.current_status == CurrentStatus.active
    assert "Civil" in p.practice_areas_raw
    assert "Family" in p.practice_areas_raw


def test_legal_name_format_first_last(providers) -> None:
    """Names must be 'First Last', not 'Last, First' or 'Last First'."""
    # Trey Boblett: First="Trey", Last="Boblett" → "Trey Boblett"
    p = _by_name(providers, "Trey Boblett")
    parts = p.legal_name.split()
    assert parts[0] == "Trey"
    assert parts[-1] == "Boblett"


# ── provenance stamped from snapshot ─────────────────────────────────────────


def test_provenance_source_url(providers, fixture_snapshot) -> None:
    assert all(p.source_url == fixture_snapshot.source_url for p in providers)


def test_provenance_retrieved_at(providers, fixture_snapshot) -> None:
    assert all(p.retrieved_at == fixture_snapshot.retrieved_at for p in providers)


def test_provenance_scraper_version(providers, fixture_snapshot) -> None:
    assert all(p.scraper_version == fixture_snapshot.scraper_version for p in providers)


def test_first_seen_snapshot_id_none_from_parse(providers) -> None:
    assert all(p.first_seen_snapshot_id is None for p in providers)


def test_last_seen_snapshot_id_none_before_stamp(providers) -> None:
    assert all(p.last_seen_snapshot_id is None for p in providers)
