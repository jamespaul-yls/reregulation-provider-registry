"""Regression tests for scrapers.utah_lpp.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/ut_lpp_directory_snap1.html
  sha256  : 9b77f407c978302867e320397065aabdbe311a46975d4bf30fd8c1956db6f3b7
  fetched : 2026-06-29 (first production scrape via UtahLppScraper)
  source  : licensedlawyer.org iframe content (ClearVantage CGI, RANGE=1/100)

Expected row set is fully determined by that fixed snapshot; update counts
and re-pin sha256 if the fixture is ever refreshed from a new live scrape.

Coverage note: licensedlawyer.org may be an opt-in directory; 52 real LPPs
captured (53 entries minus 1 test account "Testacct, LPP").
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.utah_lpp import UtahLppScraper, _last_first_to_first_last, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "ut_lpp_directory_snap1.html"
_FIXTURE_SHA256 = "9b77f407c978302867e320397065aabdbe311a46975d4bf30fd8c1956db6f3b7"
# The snapshot source_url is the iframe CGI URL (where data actually lives)
_IFRAME_URL = (
    "https://www.licensedlawyer.org/cv/cgi-bin/memberdll.dll/CustomList"
    "?WHP=lawyers_header.htm&WBP=lawyers_list.htm&SQLNAME=GETDIRSEARCH"
    "&SRCHOPT=I%7cPOLITICALPARTY%7cLPPActive%7c%3d%5eI%7cCHAPTERID%7cUT-BAR%7c%3d"
    "&SORTOPT=LASTNAME&GETCOUNT=0&GETSIM=0&RANGE=1%2f100&WEM=search_error.htm"
)
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 52  # 53 raw − 1 test account "Testacct, LPP"
_ACTIVE_ROWS = 52  # all LPPActive filter → all active

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_ut_lpp",
        source_url=_IFRAME_URL,
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
    scraper = UtahLppScraper(raw_dir=raw_dir)
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
    """All LPPActive-filtered entries are active; no exited expected."""
    exited = [p for p in providers if p.current_status == CurrentStatus.exited]
    assert exited == []


# ── test account filtering ────────────────────────────────────────────────────


def test_test_account_filtered_out(providers) -> None:
    """'Testacct, LPP' system entry must not appear in output."""
    names = [p.legal_name.lower() for p in providers]
    assert not any("testacct" in n for n in names)


# ── schema invariants ─────────────────────────────────────────────────────────


def test_all_providers_are_individuals(providers) -> None:
    assert all(p.provider_type == ProviderType.individual for p in providers)


def test_all_jurisdiction_ut(providers) -> None:
    assert all(p.jurisdiction == "UT" for p in providers)


def test_all_program_id_ut_lpp(providers) -> None:
    assert all(p.program_id == "prog_ut_lpp" for p in providers)


def test_authorization_date_always_none(providers) -> None:
    assert all(p.authorization_date is None for p in providers)


def test_practice_areas_always_empty_list(providers) -> None:
    """Directory does not publish per-individual areas; all rows get []."""
    assert all(p.practice_areas_raw == [] for p in providers)


def test_no_empty_legal_names(providers) -> None:
    assert all(p.legal_name for p in providers)


def test_all_normalized_names_nonempty(providers) -> None:
    assert all(p.normalized_name for p in providers)


def test_provider_ids_unique(providers) -> None:
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_provider_ids_use_ut_lpp_prefix(providers) -> None:
    assert all(p.provider_id.startswith("prov_ut_lpp_") for p in providers)


def test_website_null(providers) -> None:
    assert all(p.website is None for p in providers)


def test_ownership_structure_null(providers) -> None:
    assert all(p.ownership_structure is None for p in providers)


def test_uses_technology_null(providers) -> None:
    assert all(p.uses_technology is None for p in providers)


def test_uses_ai_null(providers) -> None:
    assert all(p.uses_ai is None for p in providers)


# ── name format ───────────────────────────────────────────────────────────────


def test_names_are_first_last_not_last_first(providers) -> None:
    """Names must be converted from 'Last, First' → 'First Last'."""
    for p in providers:
        assert "," not in p.legal_name, (
            f"{p.legal_name!r} still contains a comma — Last-First conversion may have failed."
        )


def test_last_first_to_first_last_simple() -> None:
    assert _last_first_to_first_last("Adams, Michelle") == "Michelle Adams"


def test_last_first_to_first_last_compound_last() -> None:
    assert _last_first_to_first_last("Alas Servellon, Francesca") == "Francesca Alas Servellon"


def test_last_first_to_first_last_no_comma_passthrough() -> None:
    assert _last_first_to_first_last("Michelle Adams") == "Michelle Adams"


def test_last_first_to_first_last_trailing_space() -> None:
    assert _last_first_to_first_last("Brewer, Paula ") == "Paula Brewer"


# ── spot-check named rows ─────────────────────────────────────────────────────


def _by_name(providers, name: str):
    matches = [p for p in providers if p.legal_name == name]
    assert len(matches) == 1, f"Expected exactly 1 row for {name!r}, got {len(matches)}"
    return matches[0]


def test_spot_check_michelle_adams(providers) -> None:
    p = _by_name(providers, "Michelle Adams")
    assert p.current_status == CurrentStatus.active
    assert p.provider_id == _provider_id("Michelle Adams")
    assert p.practice_areas_raw == []


def test_spot_check_susan_astle(providers) -> None:
    p = _by_name(providers, "Susan Astle")
    assert p.current_status == CurrentStatus.active
    assert p.jurisdiction == "UT"


def test_spot_check_jill_bohn(providers) -> None:
    p = _by_name(providers, "Jill Bohn")
    assert p.current_status == CurrentStatus.active


def test_spot_check_paula_brewer_trailing_space_stripped(providers) -> None:
    """Source has 'Brewer, Paula ' (trailing space) — must normalize to 'Paula Brewer'."""
    p = _by_name(providers, "Paula Brewer")
    assert p.current_status == CurrentStatus.active


def test_spot_check_francesca_alas_servellon(providers) -> None:
    """Compound last name 'Alas Servellon, Francesca' must convert correctly."""
    p = _by_name(providers, "Francesca Alas Servellon")
    assert p.current_status == CurrentStatus.active


def test_spot_check_amanda_thomas(providers) -> None:
    p = _by_name(providers, "Amanda Thomas")
    assert p.current_status == CurrentStatus.active
    assert p.provider_id == _provider_id("Amanda Thomas")


def test_spot_check_peter_vanderhooft(providers) -> None:
    p = _by_name(providers, "Peter Vanderhooft")
    assert p.current_status == CurrentStatus.active


def test_spot_check_tonya_wright(providers) -> None:
    p = _by_name(providers, "Tonya Wright")
    assert p.current_status == CurrentStatus.active


def test_spot_check_heather_zamora(providers) -> None:
    """Last alphabetically — confirms full roster was parsed."""
    p = _by_name(providers, "Heather Zamora")
    assert p.current_status == CurrentStatus.active
    assert p.provider_id == _provider_id("Heather Zamora")


def test_spot_check_lindsey_brandt(providers) -> None:
    p = _by_name(providers, "Lindsey Brandt")
    assert p.current_status == CurrentStatus.active


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
