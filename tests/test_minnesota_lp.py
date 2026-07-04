"""Regression tests for scrapers.minnesota_lp.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/mn_lp_roster_snap1.pdf
  sha256  : 65dee7a93a241e8f724313bf5803cfec7b1bee6d09c25c95d5aea5b0df3a9379
  fetched : 2026-06-29 (first production scrape via MinnesotaLpScraper)
  source  : https://mncourts.gov/_media/migration/appellate/supreme-court/Roster-of-Approved-Legal-Paraprofessionals.pdf
  updated : 2026-06-25 (PDF header "Updated June 25, 2026")

Expected row set is fully determined by the fixed snapshot; update counts and
re-pin sha256 if the fixture is ever refreshed from a new live scrape.

Known source limitations captured in this fixture:
  - prov_mn_lp_1001: PDF drops the bullet character before "Unemployment Benefits",
    causing it to join to "Office of Admin Hearings – Licensing" as a continuation line.
  - prov_mn_lp_1044: practice area reads "Family" (not "Family Law") — PDF rendering
    artifact; stored verbatim.
  - IDs 1009 and 1028 are absent from the roster (not parsing errors).
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.minnesota_lp import MinnesotaLpScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "mn_lp_roster_snap1.pdf"
_FIXTURE_SHA256 = "65dee7a93a241e8f724313bf5803cfec7b1bee6d09c25c95d5aea5b0df3a9379"
_PDF_URL = (
    "https://mncourts.gov/_media/migration/appellate/supreme-court/"
    "Roster-of-Approved-Legal-Paraprofessionals.pdf"
)
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 42  # IDs 1001–1046 with gaps at 1009 and 1028; updated 2026-06-25
_ACTIVE_ROWS = 42  # roster lists only approved (active) participants

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_mn_lp",
        source_url=_PDF_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256=_FIXTURE_SHA256,
        storage_path=str(_FIXTURE),
        media_type=MediaType.pdf,
        scraper_version="0.1.0",
    )


@pytest.fixture(scope="module")
def providers(
    fixture_snapshot: SourceSnapshot,
    fixture_raw: bytes,
    tmp_path_factory: pytest.TempPathFactory,
):
    raw_dir = tmp_path_factory.mktemp("raw")
    scraper = MinnesotaLpScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── row counts ────────────────────────────────────────────────────────────────


def test_total_row_count(providers):
    assert len(providers) == _TOTAL_ROWS


def test_all_active(providers):
    assert all(p.current_status == CurrentStatus.active for p in providers)


def test_all_individual(providers):
    assert all(p.provider_type == ProviderType.individual for p in providers)


def test_all_mn_jurisdiction(providers):
    assert all(p.jurisdiction == "MN" for p in providers)


def test_all_mn_lp_program(providers):
    assert all(p.program_id == "prog_mn_lp" for p in providers)


def test_provider_ids_unique(providers):
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


# ── missing IDs confirm ID gaps are not parsing errors ────────────────────────


def test_id_1009_absent(providers):
    assert _provider_id("1009") not in {p.provider_id for p in providers}


def test_id_1028_absent(providers):
    assert _provider_id("1028") not in {p.provider_id for p in providers}


# ── spot checks: simple cases ─────────────────────────────────────────────────


def test_provider_1041(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1041")]
    assert p.legal_name == "Phylis M. Adolph"
    assert p.authorization_date == datetime.date(2026, 4, 15)
    assert p.practice_areas_raw == [
        "Housing Law",
        "Family Law",
        "Conciliation Court",
        "Probate & Estate Administration",
    ]


def test_provider_1006_family_only(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1006")]
    assert p.legal_name == "Rachel A. Mitchell"
    assert p.authorization_date == datetime.date(2021, 6, 21)
    assert p.practice_areas_raw == ["Family Law"]


def test_provider_1005_housing_only(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1005")]
    assert p.legal_name == "Mary J. Vrieze"
    assert p.authorization_date == datetime.date(2021, 5, 26)
    assert p.practice_areas_raw == ["Housing Law"]


# ── spot check: multi-line OFP bullet joined correctly ────────────────────────


def test_provider_1002_multiline_bullet(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1002")]
    assert p.legal_name == "Sheila Bokelman"
    assert p.authorization_date == datetime.date(2021, 4, 21)
    assert p.practice_areas_raw == [
        "Housing Law",
        "Family Law",
        "Domestic Violence, Child Abuse, Orders for Protection (OFP), and"
        " Harassment Restraining Orders (HRO)",
    ]


def test_provider_1022_ofp_bullet(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1022")]
    assert p.legal_name == "Vanessa F. Briese"
    assert "Domestic Violence, Child Abuse, Orders for Protection (OFP), and"
    " Harassment Restraining Orders (HRO)" in p.practice_areas_raw


# ── spot check: 1001 PDF artifact (missing bullet before "Unemployment Benefits") ──


def test_provider_1001_artifact(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1001")]
    assert p.legal_name == "Nacole L. Carlson"
    assert p.authorization_date == datetime.date(2021, 4, 21)
    # PDF drops the bullet before "Unemployment Benefits" — it joins to the preceding area
    assert "Office of Admin Hearings – Licensing Unemployment Benefits" in p.practice_areas_raw
    assert "Department of Human Services" in p.practice_areas_raw


# ── spot check: 1044 "Family" truncation (not "Family Law") ──────────────────


def test_provider_1044_family_truncation(providers):
    by_id = {p.provider_id: p for p in providers}
    p = by_id[_provider_id("1044")]
    assert p.legal_name == "Donna R. Storer"
    assert p.authorization_date == datetime.date(2026, 6, 25)
    assert "Family" in p.practice_areas_raw
    assert "Family Law" not in p.practice_areas_raw
    ofp_area = "Orders for Protection (OFP), and Harassment Restraining Orders (HRO)"
    assert ofp_area in p.practice_areas_raw


# ── spot check: earliest and latest authorization dates ───────────────────────


def test_earliest_authorization_date(providers):
    earliest = min(p.authorization_date for p in providers if p.authorization_date)
    assert earliest == datetime.date(2021, 4, 21)


def test_latest_authorization_date(providers):
    latest = max(p.authorization_date for p in providers if p.authorization_date)
    assert latest == datetime.date(2026, 6, 25)


def test_all_have_authorization_date(providers):
    assert all(p.authorization_date is not None for p in providers)


# ── spot check: names are not inverted (Last, First) ────────────────────────


def test_names_not_last_first(providers):
    # MN roster uses First Last order (unlike some sources); no commas expected in names
    for p in providers:
        assert "," not in p.legal_name, (
            f"{p.provider_id}: name appears inverted or has unexpected comma: {p.legal_name!r}"
        )


# ── normalized_name populated ────────────────────────────────────────────────


def test_normalized_names_populated(providers):
    assert all(p.normalized_name for p in providers)


# ── practice areas: all providers have at least one ──────────────────────────


def test_all_have_practice_areas(providers):
    assert all(p.practice_areas_raw for p in providers)


# ── provenance fields ─────────────────────────────────────────────────────────


def test_provenance_fields(providers, fixture_snapshot: SourceSnapshot):
    for p in providers:
        assert p.source_url == _PDF_URL
        assert p.retrieved_at == _RETRIEVED_AT
        assert p.scraper_version == "0.1.0"
