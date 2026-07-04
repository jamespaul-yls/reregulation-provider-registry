"""Regression tests for scrapers.colorado_llp.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/co_llp_roster_snap1.pdf
  sha256  : 49941ce75946f286e969d218ae59576187c563434113d9e00a2096b40a931bf0
  fetched : 2026-06-29 (first production scrape via ColoradoLlpScraper)
  source  : https://www.coloradolegalregulation.com/PDF/LLP/Admitted LLP Roster.pdf
  as_of   : 2026-02-06 (stated in PDF footer)

Expected row set is fully determined by the fixed snapshot; update counts and
re-pin sha256 if the fixture is ever refreshed from a new live scrape.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.colorado_llp import ColoradoLlpScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "co_llp_roster_snap1.pdf"
_FIXTURE_SHA256 = "49941ce75946f286e969d218ae59576187c563434113d9e00a2096b40a931bf0"
_PDF_URL = "https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf"
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 126  # reg 600000–600125, consecutive, no gaps
_ACTIVE_ROWS = 126  # "Admitted LLP Roster" — all entries are active

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_co_llp",
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
    scraper = ColoradoLlpScraper(raw_dir=raw_dir)
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


def test_no_exited_rows(providers) -> None:
    """Admitted roster contains only active LLPs; no exited expected."""
    exited = [p for p in providers if p.current_status == CurrentStatus.exited]
    assert exited == []


# ── schema invariants ─────────────────────────────────────────────────────────


def test_all_providers_are_individuals(providers) -> None:
    assert all(p.provider_type == ProviderType.individual for p in providers)


def test_all_jurisdiction_co(providers) -> None:
    assert all(p.jurisdiction == "CO" for p in providers)


def test_all_program_id_co_llp(providers) -> None:
    assert all(p.program_id == "prog_co_llp" for p in providers)


def test_authorization_date_always_none(providers) -> None:
    assert all(p.authorization_date is None for p in providers)


def test_practice_areas_always_domestic_relations(providers) -> None:
    """CO LLP is domestic-relations-only; every row gets that constant."""
    assert all(p.practice_areas_raw == ["Domestic Relations"] for p in providers)


def test_no_empty_legal_names(providers) -> None:
    assert all(p.legal_name for p in providers)


def test_all_normalized_names_nonempty(providers) -> None:
    assert all(p.normalized_name for p in providers)


def test_provider_ids_unique(providers) -> None:
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_provider_ids_use_co_llp_prefix(providers) -> None:
    assert all(p.provider_id.startswith("prov_co_llp_") for p in providers)


def test_provider_ids_encode_reg_number(providers) -> None:
    """IDs are prov_co_llp_<reg_num> — stable across re-scrapes of same individual."""
    first = providers[0]
    assert first.provider_id == "prov_co_llp_600000"
    last = providers[-1]
    assert last.provider_id == f"prov_co_llp_6{(len(providers) - 1):05d}"


def test_reg_numbers_consecutive(providers) -> None:
    """Registration numbers 600000–600125 must be consecutive — no gaps."""
    ids = sorted(p.provider_id for p in providers)
    nums = [int(pid.split("_")[-1]) for pid in ids]
    assert nums == list(range(600000, 600000 + _TOTAL_ROWS))


def test_website_null(providers) -> None:
    assert all(p.website is None for p in providers)


def test_ownership_structure_null(providers) -> None:
    assert all(p.ownership_structure is None for p in providers)


def test_uses_technology_null(providers) -> None:
    assert all(p.uses_technology is None for p in providers)


def test_uses_ai_null(providers) -> None:
    assert all(p.uses_ai is None for p in providers)


# ── names are First Last (no conversion needed) ───────────────────────────────


def test_names_are_first_last_not_last_first(providers) -> None:
    """PDF publishes names in First Last order.

    Commas are only allowed as part of name suffixes (Jr., Sr., III, IV, etc.)
    — i.e., the comma must appear near the end of the string, not in the middle
    where it would indicate a Last, First inversion.
    """
    import re as _re

    _suffix_re = _re.compile(r",\s*(Jr\.|Sr\.|II|III|IV|V)$", _re.IGNORECASE)
    for p in providers:
        if "," in p.legal_name:
            assert _suffix_re.search(p.legal_name), (
                f"{p.legal_name!r} contains a comma that is not a name suffix — "
                "PDF may have changed to Last, First format."
            )


# ── spot-check named rows ─────────────────────────────────────────────────────


def _by_name(providers, name: str):
    matches = [p for p in providers if p.legal_name == name]
    assert len(matches) == 1, f"Expected exactly 1 row for {name!r}, got {len(matches)}"
    return matches[0]


def _by_id(providers, provider_id: str):
    matches = [p for p in providers if p.provider_id == provider_id]
    assert len(matches) == 1, f"Expected exactly 1 row for {provider_id!r}, got {len(matches)}"
    return matches[0]


def test_spot_check_first_entry(providers) -> None:
    """Registration 600000 — first admitted LLP."""
    p = _by_id(providers, "prov_co_llp_600000")
    assert p.legal_name == "Catherine Joy McClaugherty"
    assert p.current_status == CurrentStatus.active
    assert p.practice_areas_raw == ["Domestic Relations"]


def test_spot_check_second_entry(providers) -> None:
    p = _by_id(providers, "prov_co_llp_600001")
    assert p.legal_name == "Ronni Nicole Victorino"
    assert p.current_status == CurrentStatus.active


def test_spot_check_last_entry(providers) -> None:
    """Registration 600125 — last entry in PDF."""
    p = _by_id(providers, "prov_co_llp_600125")
    assert p.legal_name == "Teresa Detton"
    assert p.current_status == CurrentStatus.active


def test_spot_check_name_with_suffix(providers) -> None:
    """'Bobby Coe Jones, Jr.' — suffix after comma must be preserved, not treated as last-first."""
    p = _by_name(providers, "Bobby Coe Jones, Jr.")
    assert p.provider_id == "prov_co_llp_600100"
    assert p.current_status == CurrentStatus.active


def test_spot_check_name_with_roman_numeral(providers) -> None:
    """'Harry C. Green, IV' — Roman numeral suffix."""
    p = _by_name(providers, "Harry C. Green, IV")
    assert p.provider_id == "prov_co_llp_600104"
    assert p.current_status == CurrentStatus.active


def test_spot_check_compound_last_name(providers) -> None:
    """'Sarah Lynn Del Rio-Garcia' — hyphenated compound last name."""
    p = _by_name(providers, "Sarah Lynn Del Rio-Garcia")
    assert p.provider_id == "prov_co_llp_600043"


def test_spot_check_long_name(providers) -> None:
    """'Fernanda Victoria Soto Gonzalez' — four-part name."""
    p = _by_name(providers, "Fernanda Victoria Soto Gonzalez")
    assert p.provider_id == "prov_co_llp_600091"


def test_spot_check_dill_meinzer(providers) -> None:
    """'Meghan Nicole Dill-Meinzer' — hyphen within last name."""
    p = _by_name(providers, "Meghan Nicole Dill-Meinzer")
    assert p.provider_id == "prov_co_llp_600047"


def test_spot_check_midrange_entry(providers) -> None:
    """Spot-check a mid-roster entry to confirm page 2 was parsed."""
    p = _by_id(providers, "prov_co_llp_600061")
    assert p.legal_name == "Mark David Smith"
    assert p.current_status == CurrentStatus.active


def test_spot_check_page3_entry(providers) -> None:
    """Spot-check a page-3 entry to confirm all pages parsed."""
    p = _by_id(providers, "prov_co_llp_600094")
    assert p.legal_name == "Charles David Shisler"


# ── provider_id helper ────────────────────────────────────────────────────────


def test_provider_id_helper() -> None:
    assert _provider_id("600000") == "prov_co_llp_600000"
    assert _provider_id("600125") == "prov_co_llp_600125"


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
