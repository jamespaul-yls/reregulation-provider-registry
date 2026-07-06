"""Regression tests for scrapers.utah_sandbox.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/ut_sandbox_roster_snap1.html
  sha256 : f0624d67fe0ad9d1fd4eda92edb13ccbb225f8272f8204ecf48887403a663134
  fetched: 2026-06-29 (first production scrape via UtahSandboxScraper)

Entity population captured from this snapshot:
  Currently Authorized        7   active  (full card data)
  Authorized – Standing Order 1   active  (i4J, list-only)
  Provisionally Authorized    7   exited  (list-only)
  Previously Auth. – Rule 5.4 19  exited  (list-only)
  Previously Authorized       35  exited  (list-only)
  ─────────────────────────────────────────────────────
  Total                       69

Expected row counts are locked to this fixture sha256; update and re-pin if
the fixture is ever refreshed from a new scrape.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import CurrentStatus, MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.utah_sandbox import UtahSandboxScraper, _provider_id

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "ut_sandbox_roster_snap1.html"
_FIXTURE_SHA256 = "f0624d67fe0ad9d1fd4eda92edb13ccbb225f8272f8204ecf48887403a663134"
_SOURCE_URL = "https://utahinnovationoffice.org/authorized-entities/"
_RETRIEVED_AT = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.UTC)

# ── expected counts (locked to _FIXTURE_SHA256) ───────────────────────────────

_TOTAL_ROWS = 69
_ACTIVE_ROWS = 8
_EXITED_ROWS = 61
_ROWS_WITH_WEBSITE = 7  # currently-authorized cards only
_ROWS_WITH_PRACTICE_AREAS = 7  # currently-authorized cards only
_ROWS_USES_TECH_TRUE = 3  # 1Law, Rasa, Superlegal
_ROWS_USES_AI_TRUE = 2  # 1Law, Superlegal

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=f"snap_{_FIXTURE_SHA256[:16]}",
        program_id="prog_ut_sandbox",
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
    scraper = UtahSandboxScraper(raw_dir=raw_dir)
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


def test_website_count(providers) -> None:
    with_website = [p for p in providers if p.website is not None]
    assert len(with_website) == _ROWS_WITH_WEBSITE


def test_practice_areas_count(providers) -> None:
    with_pa = [p for p in providers if p.practice_areas_raw]
    assert len(with_pa) == _ROWS_WITH_PRACTICE_AREAS


def test_uses_technology_true_count(providers) -> None:
    tech_true = [p for p in providers if p.uses_technology is True]
    assert len(tech_true) == _ROWS_USES_TECH_TRUE


def test_uses_ai_true_count(providers) -> None:
    ai_true = [p for p in providers if p.uses_ai is True]
    assert len(ai_true) == _ROWS_USES_AI_TRUE


# ── schema invariants ─────────────────────────────────────────────────────────


def test_all_providers_are_entities(providers) -> None:
    assert all(p.provider_type == ProviderType.entity for p in providers)


def test_all_jurisdiction_ut(providers) -> None:
    assert all(p.jurisdiction == "UT" for p in providers)


def test_all_program_id_ut_sandbox(providers) -> None:
    assert all(p.program_id == "prog_ut_sandbox" for p in providers)


def test_authorization_date_always_none(providers) -> None:
    assert all(p.authorization_date is None for p in providers)


def test_no_empty_legal_names(providers) -> None:
    assert all(p.legal_name for p in providers)


def test_all_normalized_names_nonempty(providers) -> None:
    assert all(p.normalized_name for p in providers)


def test_provider_ids_unique(providers) -> None:
    ids = [p.provider_id for p in providers]
    assert len(ids) == len(set(ids))


def test_provider_ids_use_ut_sandbox_prefix(providers) -> None:
    assert all(p.provider_id.startswith("prov_ut_sandbox_") for p in providers)


def test_websites_are_http_urls(providers) -> None:
    for p in providers:
        if p.website is not None:
            assert p.website.startswith(("http://", "https://"))


def test_list_only_providers_have_null_ownership(providers) -> None:
    """Providers from simple list sections (no card) carry no derived fields."""
    list_only = [p for p in providers if not p.practice_areas_raw]
    assert all(p.ownership_structure is None for p in list_only)
    assert all(p.uses_technology is None for p in list_only)
    assert all(p.uses_ai is None for p in list_only)


# ── spot-check named rows ─────────────────────────────────────────────────────


def _by_name(providers, name: str):
    matches = [p for p in providers if p.legal_name == name]
    assert len(matches) == 1, f"Expected exactly 1 row for {name!r}, got {len(matches)}"
    return matches[0]


def test_spot_check_1law(providers) -> None:
    p = _by_name(providers, "1Law")
    assert p.current_status == CurrentStatus.active
    assert p.uses_technology is True
    assert p.uses_ai is True
    assert p.website == "https://www.1law.com/"
    assert "Accident / Injury" in p.practice_areas_raw
    assert p.provider_id == _provider_id("1Law")


def test_spot_check_superlegal(providers) -> None:
    p = _by_name(providers, "Superlegal (LawGeex / Legalogic)")
    assert p.current_status == CurrentStatus.active
    assert p.uses_technology is True
    assert p.uses_ai is True
    assert p.website == "https://www.lawgeex.com/"
    assert "Business" in p.practice_areas_raw


def test_spot_check_rasa(providers) -> None:
    p = _by_name(providers, "Rasa Public Benefit Corp.")
    assert p.current_status == CurrentStatus.active
    assert p.uses_technology is True
    assert p.uses_ai is False
    assert p.website == "https://rasa-legal.com/"
    assert "Expungement" in p.practice_areas_raw


def test_spot_check_cjau(providers) -> None:
    p = _by_name(providers, "Community Justice Advocates of Utah")
    assert p.current_status == CurrentStatus.active
    assert p.uses_technology is False
    assert p.uses_ai is False
    assert p.website == "https://www.cjau.org/"
    assert "Housing" in p.practice_areas_raw


def test_spot_check_pearson_butler_asterisk_stripped(providers) -> None:
    """Pearson Butler appears as 'Pearson Butler*' in the HTML; asterisk must be stripped."""
    p = _by_name(providers, "Pearson Butler")
    assert p.current_status == CurrentStatus.active
    assert p.website == "https://www.pearsonbutler.com/"


def test_spot_check_i4j_standing_order(providers) -> None:
    """i4J is authorized through Standing Order — should be active."""
    p = _by_name(providers, "i4J")
    assert p.current_status == CurrentStatus.active
    assert p.ownership_structure is None
    assert p.uses_technology is None


def test_spot_check_legal_assistance_j_period(providers) -> None:
    """'Legal Assistance J.' must preserve the trailing period (abbreviation)."""
    p = _by_name(providers, "Legal Assistance J.")
    assert p.current_status == CurrentStatus.exited


def test_spot_check_nuttall_dba(providers) -> None:
    """DBA annotation in name must be preserved, not stripped as a status note."""
    p = _by_name(providers, "Nuttall, Brown & Coutts (dba ZAF Legal)")
    assert p.current_status == CurrentStatus.exited


def test_spot_check_robert_debry_no_link(providers) -> None:
    """Robert DeBry has no hyperlink in the HTML — should still parse."""
    p = _by_name(providers, "Robert DeBry")
    assert p.current_status == CurrentStatus.exited


def test_spot_check_xira_connect_period_not_in_name(providers) -> None:
    """'Xira Connect Inc' — the period after the </a> tag must NOT enter the name."""
    p = _by_name(providers, "Xira Connect Inc")
    assert p.current_status == CurrentStatus.exited


def test_spot_check_centro_hispano_expired(providers) -> None:
    """(expired) annotation in HTML must be stripped from the name."""
    p = _by_name(providers, "Centro Hispano")
    assert p.current_status == CurrentStatus.exited


# ── provenance stamped from snapshot ─────────────────────────────────────────


def test_provenance_source_url(providers, fixture_snapshot) -> None:
    assert all(p.source_url == fixture_snapshot.source_url for p in providers)


def test_provenance_retrieved_at(providers, fixture_snapshot) -> None:
    assert all(p.retrieved_at == fixture_snapshot.retrieved_at for p in providers)


def test_provenance_scraper_version(providers, fixture_snapshot) -> None:
    assert all(p.scraper_version == fixture_snapshot.scraper_version for p in providers)


def test_first_seen_snapshot_id_none_from_parse(providers) -> None:
    """parse() does not stamp first_seen_snapshot_id; that is run()'s job via _stamp()."""
    assert all(p.first_seen_snapshot_id is None for p in providers)


def test_last_seen_snapshot_id_none_before_stamp(providers) -> None:
    assert all(p.last_seen_snapshot_id is None for p in providers)
