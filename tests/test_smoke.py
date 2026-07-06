"""Smoke tests — verify the scaffold imports cleanly."""

from __future__ import annotations


def test_enums_import() -> None:
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

    assert ProgramType.abs == "abs"
    assert ProviderType.entity == "entity"
    assert CurrentStatus.unknown == "unknown"
    assert EventType.disappeared_from_roster == "disappeared_from_roster"
    assert MediaType.html == "html"
    assert MatchMethod.fuzzy == "fuzzy"
    assert ProgramStatus.sunset == "sunset"
    assert AliasSource.roster == "roster"


def test_normalize_name() -> None:
    from resolve.normalize import normalize_name

    assert normalize_name("The Legal Solutions, LLC") == "legal solutions"
    assert normalize_name("Smith & Jones P.C.") == "smith and jones"
    assert normalize_name("Ávila Law Group PLLC") == "avila law group"


def test_schema_imports() -> None:
    from models.schema import (
        CrosswalkCourtlistener,
        Program,
        Provider,
        ProviderAlias,
        ProviderStatusEvent,
        SourceSnapshot,
    )

    assert Program is not None
    assert Provider is not None
    assert ProviderStatusEvent is not None
    assert ProviderAlias is not None
    assert SourceSnapshot is not None
    assert CrosswalkCourtlistener is not None
