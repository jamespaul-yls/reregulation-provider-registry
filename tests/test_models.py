"""Model validation tests.

Every test is self-contained and offline — no network, no filesystem I/O.
Factory functions return plain dicts so individual tests can surgically mutate
one field without affecting others.
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from models.enums import (
    AliasSource,
    CurrentStatus,
    EventType,
    MatchMethod,
    MediaType,
    ProgramStatus,
    ProgramType,
    ProviderType,
)
from models.schema import (
    CrosswalkCourtlistener,
    Program,
    Provider,
    ProviderAlias,
    ProviderStatusEvent,
    SourceSnapshot,
)

# A valid sha-256 digest (all 'a's — placeholder, not a real hash).
_SHA256 = "a" * 64


# ── factories ─────────────────────────────────────────────────────────────────
#
# Each returns a dict of *all* required fields so that any single deletion or
# substitution produces a test with one failure mode.


def _program(**kw: object) -> dict:
    return {
        "program_id": "prog_az_abs",
        "jurisdiction": "AZ",
        "program_name": "Alternative Business Structure",
        "program_type": "abs",
        "regulator": "Arizona Supreme Court, Clerk of Court",
        "regulator_url": "https://www.azcourts.gov/",
        "authorizing_rule": "ACJA §7-209",
        "launch_date": "2021-01-01",
        "program_status": "active",
        "allows_nonlawyer_ownership": True,
        "allows_upl_waiver": False,
        "allows_software_provider": True,
        "source_url": "https://www.azcourts.gov/abs-roster",
        "retrieved_at": "2026-06-28T00:00:00",
        "scraper_version": "0.1.0",
        **kw,
    }


def _provider(**kw: object) -> dict:
    return {
        "provider_id": "prov_000001",
        "program_id": "prog_az_abs",
        "provider_type": "entity",
        "legal_name": "Smith Legal Solutions LLC",
        "normalized_name": "smith legal solutions",
        "jurisdiction": "AZ",
        "authorization_date": "2022-03-15",
        "current_status": "active",
        "source_url": "https://www.azcourts.gov/abs-roster",
        "retrieved_at": "2026-06-28T00:00:00",
        "scraper_version": "0.1.0",
        **kw,
    }


def _event(**kw: object) -> dict:
    return {
        "event_id": "evt_000001",
        "provider_id": "prov_000001",
        "event_date": "2022-03-15",
        "event_type": "authorized",
        "new_status": "active",
        "source_snapshot_id": "snap_abc123abc123abc1",
        "source_url": "https://www.azcourts.gov/abs-roster",
        "retrieved_at": "2026-06-28T00:00:00",
        "scraper_version": "0.1.0",
        **kw,
    }


def _alias(**kw: object) -> dict:
    return {
        "provider_id": "prov_000001",
        "alias_name": "Smith Legal",
        "alias_source": "website",
        "source_url": "https://www.smithlegal.com/",
        "retrieved_at": "2026-06-28T00:00:00",
        "scraper_version": "0.1.0",
        **kw,
    }


def _snapshot(**kw: object) -> dict:
    return {
        "snapshot_id": "snap_abc123abc123abc1",
        "program_id": "prog_az_abs",
        "source_url": "https://www.azcourts.gov/abs-roster",
        "retrieved_at": "2026-06-28T12:00:00",
        "content_sha256": _SHA256,
        "storage_path": "/data/raw/abs-roster.html",
        "media_type": "html",
        "scraper_version": "0.1.0",
        **kw,
    }


def _crosswalk(**kw: object) -> dict:
    return {
        "provider_id": "prov_000001",
        "cl_docket_id": 42,
        "match_score": 0.95,
        "match_method": "fuzzy",
        **kw,
    }


# ── Program ───────────────────────────────────────────────────────────────────


class TestProgram:
    def test_valid_constructs(self) -> None:
        p = Program(**_program())
        assert p.program_id == "prog_az_abs"
        assert p.jurisdiction == "AZ"
        assert p.program_type is ProgramType.abs
        assert p.program_status is ProgramStatus.active
        assert p.allows_nonlawyer_ownership is True
        assert p.allows_upl_waiver is False

    def test_date_coercion_from_string(self) -> None:
        p = Program(**_program())
        assert isinstance(p.launch_date, datetime.date)
        assert p.launch_date == datetime.date(2021, 1, 1)

    def test_null_dates_allowed(self) -> None:
        p = Program(**_program(launch_date=None, sunset_date=None))
        assert p.launch_date is None
        assert p.sunset_date is None

    def test_enum_coercion_from_string(self) -> None:
        # pydantic should accept the raw string "abs" and coerce to ProgramType.abs
        p = Program(**_program(program_type="abs", program_status="sunset"))
        assert p.program_type is ProgramType.abs
        assert p.program_status is ProgramStatus.sunset

    def test_invalid_program_type(self) -> None:
        with pytest.raises(ValidationError, match="program_type"):
            Program(**_program(program_type="traditional_law_firm"))

    def test_invalid_program_status(self) -> None:
        with pytest.raises(ValidationError, match="program_status"):
            Program(**_program(program_status="cancelled"))

    def test_invalid_jurisdiction_too_long(self) -> None:
        with pytest.raises(ValidationError, match="jurisdiction"):
            Program(**_program(jurisdiction="USA"))

    def test_invalid_jurisdiction_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="jurisdiction"):
            Program(**_program(jurisdiction="az"))

    def test_invalid_jurisdiction_digit(self) -> None:
        with pytest.raises(ValidationError, match="jurisdiction"):
            Program(**_program(jurisdiction="A1"))

    def test_missing_source_url(self) -> None:
        data = _program()
        del data["source_url"]
        with pytest.raises(ValidationError, match="source_url"):
            Program(**data)

    def test_missing_retrieved_at(self) -> None:
        data = _program()
        del data["retrieved_at"]
        with pytest.raises(ValidationError, match="retrieved_at"):
            Program(**data)

    def test_missing_scraper_version(self) -> None:
        data = _program()
        del data["scraper_version"]
        with pytest.raises(ValidationError, match="scraper_version"):
            Program(**data)

    def test_invalid_source_url_not_http(self) -> None:
        with pytest.raises(ValidationError, match="source_url"):
            Program(**_program(source_url="ftp://example.com"))

    def test_invalid_regulator_url_not_http(self) -> None:
        with pytest.raises(ValidationError, match="regulator_url"):
            Program(**_program(regulator_url="not-a-url"))

    def test_empty_program_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="program_name"):
            Program(**_program(program_name=""))

    def test_whitespace_only_name_rejected(self) -> None:
        # strip_whitespace=True reduces "   " to "" which fails min_length=1
        with pytest.raises(ValidationError, match="program_name"):
            Program(**_program(program_name="   "))


# ── Provider ──────────────────────────────────────────────────────────────────


class TestProvider:
    def test_valid_constructs(self) -> None:
        p = Provider(**_provider())
        assert p.provider_id == "prov_000001"
        assert p.provider_type is ProviderType.entity
        assert p.current_status is CurrentStatus.active

    def test_current_status_defaults_to_unknown(self) -> None:
        data = _provider()
        del data["current_status"]
        p = Provider(**data)
        assert p.current_status is CurrentStatus.unknown

    def test_date_coercion_from_string(self) -> None:
        p = Provider(**_provider())
        assert isinstance(p.authorization_date, datetime.date)
        assert p.authorization_date == datetime.date(2022, 3, 15)

    def test_practice_areas_raw_defaults_to_empty_list(self) -> None:
        p = Provider(**_provider())
        assert p.practice_areas_raw == []

    def test_invalid_current_status(self) -> None:
        with pytest.raises(ValidationError, match="current_status"):
            Provider(**_provider(current_status="approved"))

    def test_invalid_provider_type(self) -> None:
        with pytest.raises(ValidationError, match="provider_type"):
            Provider(**_provider(provider_type="firm"))

    def test_invalid_jurisdiction(self) -> None:
        with pytest.raises(ValidationError, match="jurisdiction"):
            Provider(**_provider(jurisdiction="Arizona"))

    def test_missing_source_url(self) -> None:
        data = _provider()
        del data["source_url"]
        with pytest.raises(ValidationError, match="source_url"):
            Provider(**data)

    def test_missing_scraper_version(self) -> None:
        data = _provider()
        del data["scraper_version"]
        with pytest.raises(ValidationError, match="scraper_version"):
            Provider(**data)

    def test_website_valid_https_url(self) -> None:
        p = Provider(**_provider(website="https://smithlegal.com"))
        assert p.website == "https://smithlegal.com"

    def test_website_invalid_url_rejected(self) -> None:
        with pytest.raises(ValidationError, match="website"):
            Provider(**_provider(website="smithlegal.com"))

    def test_website_none_allowed(self) -> None:
        p = Provider(**_provider(website=None))
        assert p.website is None

    def test_all_current_status_values_accepted(self) -> None:
        for status in CurrentStatus:
            p = Provider(**_provider(current_status=status.value))
            assert p.current_status is status


# ── ProviderStatusEvent ───────────────────────────────────────────────────────


class TestProviderStatusEvent:
    def test_valid_constructs(self) -> None:
        e = ProviderStatusEvent(**_event())
        assert e.event_type is EventType.authorized
        assert e.new_status is CurrentStatus.active

    def test_date_coercion(self) -> None:
        e = ProviderStatusEvent(**_event())
        assert isinstance(e.event_date, datetime.date)
        assert e.event_date == datetime.date(2022, 3, 15)

    def test_detail_optional(self) -> None:
        e = ProviderStatusEvent(**_event(detail=None))
        assert e.detail is None

    def test_invalid_event_type(self) -> None:
        with pytest.raises(ValidationError, match="event_type"):
            ProviderStatusEvent(**_event(event_type="added"))

    def test_invalid_new_status(self) -> None:
        with pytest.raises(ValidationError, match="new_status"):
            ProviderStatusEvent(**_event(new_status="approved"))

    def test_missing_source_url_provenance(self) -> None:
        data = _event()
        del data["source_url"]
        with pytest.raises(ValidationError, match="source_url"):
            ProviderStatusEvent(**data)

    def test_missing_scraper_version_provenance(self) -> None:
        data = _event()
        del data["scraper_version"]
        with pytest.raises(ValidationError, match="scraper_version"):
            ProviderStatusEvent(**data)

    def test_disappeared_from_roster_is_distinct_from_revoked(self) -> None:
        # Key design invariant: disappeared_from_roster is an observation only.
        # new_status must be set separately (typically 'unknown' until confirmed).
        e = ProviderStatusEvent(
            **_event(event_type="disappeared_from_roster", new_status="unknown")
        )
        assert e.event_type is EventType.disappeared_from_roster
        assert e.new_status is CurrentStatus.unknown

    def test_all_event_types_accepted(self) -> None:
        for et in EventType:
            e = ProviderStatusEvent(**_event(event_type=et.value))
            assert e.event_type is et


# ── ProviderAlias ─────────────────────────────────────────────────────────────


class TestProviderAlias:
    def test_valid_constructs(self) -> None:
        a = ProviderAlias(**_alias())
        assert a.alias_source is AliasSource.website

    def test_invalid_alias_source(self) -> None:
        with pytest.raises(ValidationError, match="alias_source"):
            ProviderAlias(**_alias(alias_source="social_media"))

    def test_all_alias_sources_accepted(self) -> None:
        for src in AliasSource:
            a = ProviderAlias(**_alias(alias_source=src.value))
            assert a.alias_source is src

    def test_missing_retrieved_at_provenance(self) -> None:
        data = _alias()
        del data["retrieved_at"]
        with pytest.raises(ValidationError, match="retrieved_at"):
            ProviderAlias(**data)

    def test_missing_source_url_provenance(self) -> None:
        data = _alias()
        del data["source_url"]
        with pytest.raises(ValidationError, match="source_url"):
            ProviderAlias(**data)

    def test_empty_alias_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="alias_name"):
            ProviderAlias(**_alias(alias_name=""))


# ── SourceSnapshot ────────────────────────────────────────────────────────────


class TestSourceSnapshot:
    def test_valid_constructs(self) -> None:
        s = SourceSnapshot(**_snapshot())
        assert s.media_type is MediaType.html
        assert len(s.content_sha256) == 64

    def test_retrieved_at_coercion(self) -> None:
        s = SourceSnapshot(**_snapshot())
        assert isinstance(s.retrieved_at, datetime.datetime)

    def test_invalid_sha256_wrong_length(self) -> None:
        with pytest.raises(ValidationError, match="content_sha256"):
            SourceSnapshot(**_snapshot(content_sha256="a" * 63))

    def test_invalid_sha256_too_long(self) -> None:
        with pytest.raises(ValidationError, match="content_sha256"):
            SourceSnapshot(**_snapshot(content_sha256="a" * 65))

    def test_invalid_sha256_uppercase(self) -> None:
        # SHA-256 must be lowercase hex — uppercase fails the pattern.
        with pytest.raises(ValidationError, match="content_sha256"):
            SourceSnapshot(**_snapshot(content_sha256="A" * 64))

    def test_invalid_sha256_non_hex_char(self) -> None:
        with pytest.raises(ValidationError, match="content_sha256"):
            SourceSnapshot(**_snapshot(content_sha256="z" * 64))

    def test_invalid_media_type(self) -> None:
        with pytest.raises(ValidationError, match="media_type"):
            SourceSnapshot(**_snapshot(media_type="csv"))

    def test_scraper_version_required(self) -> None:
        data = _snapshot()
        del data["scraper_version"]
        with pytest.raises(ValidationError, match="scraper_version"):
            SourceSnapshot(**data)

    def test_all_media_types_accepted(self) -> None:
        for mt in MediaType:
            s = SourceSnapshot(**_snapshot(media_type=mt.value))
            assert s.media_type is mt


# ── CrosswalkCourtlistener ────────────────────────────────────────────────────


class TestCrosswalkCourtlistener:
    def test_valid_constructs(self) -> None:
        c = CrosswalkCourtlistener(**_crosswalk())
        assert c.verified is False
        assert c.cl_party_id is None
        assert c.reviewer is None

    def test_match_score_boundary_zero(self) -> None:
        c = CrosswalkCourtlistener(**_crosswalk(match_score=0.0))
        assert c.match_score == 0.0

    def test_match_score_boundary_one(self) -> None:
        c = CrosswalkCourtlistener(**_crosswalk(match_score=1.0))
        assert c.match_score == 1.0

    def test_match_score_too_high(self) -> None:
        with pytest.raises(ValidationError, match="match_score"):
            CrosswalkCourtlistener(**_crosswalk(match_score=1.01))

    def test_match_score_too_low(self) -> None:
        with pytest.raises(ValidationError, match="match_score"):
            CrosswalkCourtlistener(**_crosswalk(match_score=-0.01))

    def test_invalid_match_method(self) -> None:
        with pytest.raises(ValidationError, match="match_method"):
            CrosswalkCourtlistener(**_crosswalk(match_method="approximate"))

    def test_all_match_methods_accepted(self) -> None:
        for mm in MatchMethod:
            c = CrosswalkCourtlistener(**_crosswalk(match_method=mm.value))
            assert c.match_method is mm

    def test_verified_defaults_false(self) -> None:
        c = CrosswalkCourtlistener(**_crosswalk())
        assert c.verified is False

    def test_verified_true_with_reviewer(self) -> None:
        c = CrosswalkCourtlistener(
            **_crosswalk(
                verified=True,
                reviewer="james.paul@yale.edu",
                reviewed_at="2026-06-28T12:00:00",
            )
        )
        assert c.verified is True
        assert c.reviewer == "james.paul@yale.edu"
        assert isinstance(c.reviewed_at, datetime.datetime)
