"""Regression tests for scrapers.washington_entity_pilot.

All tests run against the saved fixture — no network calls.

Fixture: tests/fixtures/wa_entity_pilot_snap1.html
  sha256  : 07d353745a809627d7e009ad132fb766ca6f0c4dd845a55ebbcbdf4d6a42b969
  fetched : 2026-07-04 (first production snapshot via WashingtonEntityPilotScraper)
  source  : https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants

As of this snapshot, all 4 listed applicants are "Under Review" — zero are authorized.
parse() returns [] by design (see scrapers/washington_entity_pilot.py module docstring
and validation/washington_entity_pilot.md). parse_applicants() is tested separately
against a synthetic fixture to prove the authorized-status loading path actually works,
since the live data doesn't currently exercise it.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest

from models.enums import MediaType, ProviderType
from models.schema import SourceSnapshot
from scrapers.washington_entity_pilot import (
    ApplicantRow,
    WashingtonEntityPilotScraper,
    _is_authorized_status,
    _is_unrecognized_status,
    parse_applicants,
)

# ── fixture metadata ──────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "wa_entity_pilot_snap1.html"
_FIXTURE_SHA256 = "07d353745a809627d7e009ad132fb766ca6f0c4dd845a55ebbcbdf4d6a42b969"
_SOURCE_URL = "https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants"
_RETRIEVED_AT = datetime.datetime(2026, 7, 4, 0, 0, 0, tzinfo=datetime.UTC)

_EXPECTED_APPLICANTS = [
    ApplicantRow(datetime.date(2025, 10, 22), "Legata, Inc.", "Under Review"),
    ApplicantRow(datetime.date(2026, 1, 8), "Law on Call, LLC", "Under Review"),
    ApplicantRow(datetime.date(2026, 3, 10), "Wrk Legal, LLC", "Under Review"),
    ApplicantRow(datetime.date(2026, 1, 27), "Confido Inc.", "Under Review"),
]

# ── pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_raw() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_snapshot() -> SourceSnapshot:
    sha = _FIXTURE_SHA256
    return SourceSnapshot(
        snapshot_id=f"snap_{sha[:16]}",
        program_id="prog_wa_entity_pilot",
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
    scraper = WashingtonEntityPilotScraper(raw_dir=raw_dir)
    return scraper.parse(fixture_snapshot, fixture_raw)


# ── fixture integrity ─────────────────────────────────────────────────────────


def test_fixture_sha256():
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256


# ── parse_applicants(): full list, every status ──────────────────────────────


def test_parse_applicants_full_list(fixture_raw: bytes):
    """The FULL applicant list is captured regardless of review status."""
    applicants = parse_applicants(fixture_raw)
    assert applicants == _EXPECTED_APPLICANTS


def test_parse_applicants_all_under_review(fixture_raw: bytes):
    applicants = parse_applicants(fixture_raw)
    assert {a.status for a in applicants} == {"Under Review"}


# ── parse(): zero authorized → empty provider list ───────────────────────────


def test_parse_returns_empty_list(providers):
    """No applicant is yet authorized — documented zero, not a scraping gap."""
    assert providers == []


def test_parse_returns_list_type(providers):
    assert isinstance(providers, list)


# ── authorized-status loading path (synthetic — not yet exercised by live data) ──


def test_parse_loads_authorized_applicants_as_providers(tmp_path):
    """Prove the authorized-loading branch works, since live data has no such row yet."""
    synthetic_html = b"""
    <table>
      <tr><td>Date Received</td><td>Entity Name</td><td>Status</td><td>Application</td></tr>
      <tr><td>Oct. 22, 2025</td><td>Legata, Inc.</td><td>Under Review</td><td>x</td></tr>
      <tr><td>Jan. 8, 2026</td><td>Test Authorized Co.</td><td>Authorized</td><td>x</td></tr>
    </table>
    """

    snap = SourceSnapshot(
        snapshot_id="snap_synthetic0000",
        program_id="prog_wa_entity_pilot",
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256="0" * 64,
        storage_path="synthetic",
        media_type=MediaType.html,
        scraper_version="0.1.0",
    )
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    providers = scraper.parse(snap, synthetic_html)

    assert len(providers) == 1
    p = providers[0]
    assert p.legal_name == "Test Authorized Co."
    assert p.provider_type == ProviderType.entity
    assert p.jurisdiction == "WA"
    assert p.authorization_date == datetime.date(2026, 1, 8)
    assert p.program_id == "prog_wa_entity_pilot"


def test_parse_applicants_raises_on_missing_table():
    with pytest.raises(ValueError, match="no <table>"):
        parse_applicants(b"<html><body>no table here</body></html>")


def test_parse_applicants_raises_on_unexpected_header():
    bad_html = b"<table><tr><td>Foo</td><td>Bar</td></tr></table>"
    with pytest.raises(ValueError, match="unexpected table header"):
        parse_applicants(bad_html)


# ── scraper metadata ──────────────────────────────────────────────────────────


def test_scraper_program_id(tmp_path):
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    assert scraper.program_id == "prog_wa_entity_pilot"


def test_scraper_source_url(tmp_path):
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    assert scraper.source_url == _SOURCE_URL


def test_scraper_version(tmp_path):
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    assert scraper.version == "0.1.0"


# ── _is_authorized_status(): token-based classification (adversarial_review.md S4) ──
#
# _AUTHORIZED_STATUSES used to be an exact-string set, so any real label WSBA might
# actually print other than the four guessed words ("authorized", "approved",
# "participating", "active") would go undetected even though it obviously means
# "authorized." These tests cover plausible real-world variants, and the negative-override
# guard that stops a token match from misfiring on the opposite meaning.


@pytest.mark.parametrize(
    "status",
    [
        "Authorized",
        "Approved",
        "Board Approved",
        "Authorized — Active",
        "Active/Authorized",
        "Participating",
    ],
)
def test_is_authorized_status_matches_plausible_variants(status: str) -> None:
    assert _is_authorized_status(status) is True


@pytest.mark.parametrize(
    "status",
    [
        "Under Review",
        "Not Authorized",
        "Application Denied",
        "Inactive",
        "Withdrawn",
        "Pending Board Review",
    ],
)
def test_is_authorized_status_rejects_negative_and_pending_variants(status: str) -> None:
    """The negative-override tokens must win even when an authorized-token substring/word
    is also present (e.g. "Not Authorized" contains "authorized")."""
    assert _is_authorized_status(status) is False


def test_is_unrecognized_status_true_for_novel_label() -> None:
    """A label that's neither the known 'Under Review' nor an authorized-token match
    should be flagged for human attention, not silently absorbed either way."""
    assert _is_unrecognized_status("Conditionally Certified") is True


def test_is_unrecognized_status_false_for_known_pending_label() -> None:
    assert _is_unrecognized_status("Under Review") is False


def test_is_unrecognized_status_false_for_authorized_label() -> None:
    assert _is_unrecognized_status("Authorized") is False


def test_parse_logs_warning_for_unrecognized_status(tmp_path, caplog) -> None:
    """An entity with a status that's neither 'Under Review' nor an authorized-token
    match should produce a warning log, per the S4 fix — silence is exactly what let the
    original exact-match set go untested against real-world label drift."""
    synthetic_html = b"""
    <table>
      <tr><td>Date Received</td><td>Entity Name</td><td>Status</td><td>Application</td></tr>
      <tr>
        <td>Jan. 8, 2026</td><td>Mystery Legal, LLC</td>
        <td>Conditionally Certified</td><td>x</td>
      </tr>
    </table>
    """
    snap = SourceSnapshot(
        snapshot_id="snap_synthetic0001",
        program_id="prog_wa_entity_pilot",
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256="0" * 64,
        storage_path="synthetic",
        media_type=MediaType.html,
        scraper_version="0.1.0",
    )
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    with caplog.at_level("WARNING"):
        providers = scraper.parse(snap, synthetic_html)

    assert providers == []  # "Conditionally Certified" doesn't match an authorized token
    assert any("unrecognized applicant status" in r.message for r in caplog.records)
    assert any("Mystery Legal, LLC" in r.message for r in caplog.records)


def test_parse_does_not_warn_for_known_under_review_status(tmp_path, caplog) -> None:
    synthetic_html = b"""
    <table>
      <tr><td>Date Received</td><td>Entity Name</td><td>Status</td><td>Application</td></tr>
      <tr><td>Jan. 8, 2026</td><td>Ordinary Co.</td><td>Under Review</td><td>x</td></tr>
    </table>
    """
    snap = SourceSnapshot(
        snapshot_id="snap_synthetic0002",
        program_id="prog_wa_entity_pilot",
        source_url=_SOURCE_URL,
        retrieved_at=_RETRIEVED_AT,
        content_sha256="0" * 64,
        storage_path="synthetic",
        media_type=MediaType.html,
        scraper_version="0.1.0",
    )
    scraper = WashingtonEntityPilotScraper(raw_dir=tmp_path)
    with caplog.at_level("WARNING"):
        providers = scraper.parse(snap, synthetic_html)

    assert providers == []
    assert not any("unrecognized applicant status" in r.message for r in caplog.records)
