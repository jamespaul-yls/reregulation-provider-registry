"""Tests for pipeline.db (RegistryStore) and pipeline.export.

All tests are offline — no network calls, no access to data/.
Each test gets an isolated DuckDB file under pytest's tmp_path.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import polars as pl
import pytest

from models.enums import AliasSource, CurrentStatus, EventType, MediaType
from models.schema import (
    Program,
    Provider,
    ProviderAlias,
    ProviderStatusEvent,
    SourceSnapshot,
)
from pipeline.db import _ROOT, RegistryStore, _normalize_storage_path
from pipeline.export import export

# ── UTC constant ──────────────────────────────────────────────────────────────

_UTC = datetime.UTC
_NOW = datetime.datetime(2026, 6, 28, 12, 0, 0, tzinfo=_UTC)
_SHA = "a" * 64


# ── shared factories ──────────────────────────────────────────────────────────


def _make_program(**kw: object) -> Program:
    return Program(
        **{
            "program_id": "prog_az_abs",
            "jurisdiction": "AZ",
            "program_name": "Alternative Business Structure",
            "program_type": "abs",
            "regulator": "Arizona Supreme Court",
            "regulator_url": "https://www.azcourts.gov/",
            "authorizing_rule": "ACJA §7-209",
            "launch_date": datetime.date(2021, 1, 1),
            "program_status": "active",
            "allows_nonlawyer_ownership": True,
            "allows_upl_waiver": False,
            "allows_software_provider": True,
            "source_url": "https://www.azcourts.gov/abs-roster",
            "retrieved_at": _NOW,
            "scraper_version": "0.1.0",
            **kw,
        }
    )


def _make_snapshot(**kw: object) -> SourceSnapshot:
    return SourceSnapshot(
        **{
            "snapshot_id": "snap_abc123abc123abc1",
            "program_id": "prog_az_abs",
            "source_url": "https://www.azcourts.gov/abs-roster",
            "retrieved_at": _NOW,
            "content_sha256": _SHA,
            "storage_path": "/data/raw/abs-roster.html",
            "media_type": MediaType.html,
            "scraper_version": "0.1.0",
            **kw,
        }
    )


def _make_provider(provider_id: str, legal_name: str, **kw: object) -> Provider:
    return Provider(
        **{
            "provider_id": provider_id,
            "program_id": "prog_az_abs",
            "provider_type": "entity",
            "legal_name": legal_name,
            "normalized_name": legal_name.lower(),
            "jurisdiction": "AZ",
            "authorization_date": datetime.date(2022, 3, 15),
            "current_status": "active",
            "practice_areas_raw": ["family law", "landlord-tenant"],
            "first_seen_snapshot_id": "snap_abc123abc123abc1",
            "last_seen_snapshot_id": "snap_abc123abc123abc1",
            "source_url": "https://www.azcourts.gov/abs-roster",
            "retrieved_at": _NOW,
            "scraper_version": "0.1.0",
            **kw,
        }
    )


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def store(tmp_path: Path) -> RegistryStore:
    s = RegistryStore(tmp_path / "registry.duckdb")
    s.init_schema()
    return s


@pytest.fixture()
def seeded_store(store: RegistryStore) -> RegistryStore:
    """Store pre-loaded with a program and snapshot (FK prerequisites)."""
    store.upsert_program(_make_program())
    store.upsert_snapshot(_make_snapshot())
    return store


# ── round-trip ────────────────────────────────────────────────────────────────


def test_roundtrip_two_providers(seeded_store: RegistryStore, tmp_path: Path) -> None:
    """Load 2 providers, export to Parquet, re-import, assert identical rows."""
    p1 = _make_provider("prov_000001", "Smith Legal Solutions LLC")
    p2 = _make_provider(
        "prov_000002",
        "Justice Access Partners",
        practice_areas_raw=["immigration", "asylum"],
    )
    seeded_store.upsert_provider(p1)
    seeded_store.upsert_provider(p2)
    seeded_store.close()

    release_dir = tmp_path / "release"
    export(db_path=tmp_path / "registry.duckdb", release_dir=release_dir)

    df = pl.read_parquet(release_dir / "provider.parquet")
    assert len(df) == 2

    rows = {r["provider_id"]: r for r in df.to_dicts()}

    def _reconstruct(row: dict) -> Provider:
        # practice_areas_raw / _list come back as native Python lists from Parquet.
        # ownership_structure comes back as a JSON string or None.
        if row.get("ownership_structure"):
            row["ownership_structure"] = json.loads(row["ownership_structure"])
        # DuckDB localizes TIMESTAMPTZ to the system tz on read; normalize to UTC
        # so model_dump(mode="json") produces the same Z-suffix string as the original.
        for key, val in row.items():
            if isinstance(val, datetime.datetime) and val.tzinfo is not None:
                row[key] = val.astimezone(datetime.UTC)
        return Provider.model_validate(row)

    p1_back = _reconstruct(rows["prov_000001"])
    p2_back = _reconstruct(rows["prov_000002"])

    # Compare as JSON-serialisable dicts: avoids datetime-timezone repr differences.
    assert p1_back.model_dump(mode="json") == p1.model_dump(mode="json")
    assert p2_back.model_dump(mode="json") == p2.model_dump(mode="json")


def test_export_writes_csv_and_parquet_and_datapackage(
    seeded_store: RegistryStore, tmp_path: Path
) -> None:
    seeded_store.upsert_provider(_make_provider("prov_000001", "Smith Legal Solutions LLC"))
    seeded_store.close()

    release_dir = tmp_path / "release"
    counts = export(db_path=tmp_path / "registry.duckdb", release_dir=release_dir)

    assert (release_dir / "provider.csv").exists()
    assert (release_dir / "provider.parquet").exists()
    assert (release_dir / "datapackage.json").exists()

    pkg = json.loads((release_dir / "datapackage.json").read_text())
    assert pkg["name"] == "reregulation-registry"
    resource_names = {r["name"] for r in pkg["resources"]}
    assert "provider" in resource_names
    assert "program" in resource_names

    assert counts["provider"] == 1
    assert counts["program"] == 1


# ── upsert idempotency ────────────────────────────────────────────────────────


def test_upsert_program_idempotent(store: RegistryStore) -> None:
    prog = _make_program()
    store.upsert_program(prog)
    store.upsert_program(prog)  # second insert must not raise or duplicate

    count = store.conn.execute("SELECT COUNT(*) FROM program").fetchone()[0]
    assert count == 1


def test_upsert_provider_idempotent(seeded_store: RegistryStore) -> None:
    p = _make_provider("prov_000001", "Smith Legal Solutions LLC")
    seeded_store.upsert_provider(p)
    seeded_store.upsert_provider(p)

    count = seeded_store.conn.execute("SELECT COUNT(*) FROM provider").fetchone()[0]
    assert count == 1


def test_upsert_provider_updates_existing(seeded_store: RegistryStore) -> None:
    p = _make_provider("prov_000001", "Smith Legal Solutions LLC")
    seeded_store.upsert_provider(p)

    p_updated = _make_provider(
        "prov_000001", "Smith Legal Solutions LLC", current_status="suspended"
    )
    seeded_store.upsert_provider(p_updated)

    row = seeded_store.conn.execute(
        "SELECT current_status FROM provider WHERE provider_id = 'prov_000001'"
    ).fetchone()
    assert row is not None
    assert row[0] == "suspended"


# ── FK enforcement ────────────────────────────────────────────────────────────


def test_provider_fk_program_enforced(store: RegistryStore) -> None:
    """Inserting a provider whose program_id doesn't exist must raise."""
    p = _make_provider("prov_000001", "Orphan Provider")  # program not inserted
    with pytest.raises(ValueError, match="program_id"):
        store.upsert_provider(p)


def test_snapshot_fk_program_enforced(store: RegistryStore) -> None:
    snap = _make_snapshot()  # program not inserted
    with pytest.raises(ValueError, match="program_id"):
        store.upsert_snapshot(snap)


def test_alias_fk_provider_enforced(store: RegistryStore) -> None:
    """Inserting an alias whose provider doesn't exist must raise."""
    store.upsert_program(_make_program())
    alias = ProviderAlias(
        provider_id="prov_nonexistent",
        alias_name="Ghost Firm",
        alias_source=AliasSource.roster,
        source_url="https://www.azcourts.gov/abs-roster",
        retrieved_at=_NOW,
        scraper_version="0.1.0",
    )
    with pytest.raises(ValueError, match="provider_id"):
        store.upsert_alias(alias)


def test_event_fk_provider_enforced(store: RegistryStore) -> None:
    store.upsert_program(_make_program())
    store.upsert_snapshot(_make_snapshot())
    event = ProviderStatusEvent(
        event_id="evt_000001",
        provider_id="prov_nonexistent",
        event_date=datetime.date(2022, 3, 15),
        event_type=EventType.authorized,
        new_status=CurrentStatus.active,
        source_snapshot_id="snap_abc123abc123abc1",
        source_url="https://www.azcourts.gov/abs-roster",
        retrieved_at=_NOW,
        scraper_version="0.1.0",
    )
    with pytest.raises(ValueError, match="provider_id"):
        store.upsert_event(event)


def test_event_fk_snapshot_enforced(seeded_store: RegistryStore) -> None:
    seeded_store.upsert_provider(_make_provider("prov_000001", "Smith Legal Solutions LLC"))
    event = ProviderStatusEvent(
        event_id="evt_000001",
        provider_id="prov_000001",
        event_date=datetime.date(2022, 3, 15),
        event_type=EventType.authorized,
        new_status=CurrentStatus.active,
        source_snapshot_id="snap_nonexistent",
        source_url="https://www.azcourts.gov/abs-roster",
        retrieved_at=_NOW,
        scraper_version="0.1.0",
    )
    with pytest.raises(ValueError, match="snapshot_id"):
        seeded_store.upsert_event(event)


# ── alias round-trip ──────────────────────────────────────────────────────────


def test_alias_upsert_and_query(seeded_store: RegistryStore) -> None:
    seeded_store.upsert_provider(_make_provider("prov_000001", "Smith Legal Solutions LLC"))
    alias = ProviderAlias(
        provider_id="prov_000001",
        alias_name="Smith Legal",
        alias_source=AliasSource.website,
        source_url="https://smithlegal.com/",
        retrieved_at=_NOW,
        scraper_version="0.1.0",
    )
    seeded_store.upsert_alias(alias)
    seeded_store.upsert_alias(alias)  # idempotent

    count = seeded_store.conn.execute(
        "SELECT COUNT(*) FROM provider_alias WHERE provider_id = 'prov_000001'"
    ).fetchone()[0]
    assert count == 1


# ── status event round-trip ───────────────────────────────────────────────────


def test_event_upsert_and_query(seeded_store: RegistryStore) -> None:
    seeded_store.upsert_provider(_make_provider("prov_000001", "Smith Legal Solutions LLC"))
    event = ProviderStatusEvent(
        event_id="evt_000001",
        provider_id="prov_000001",
        event_date=datetime.date(2022, 3, 15),
        event_type=EventType.authorized,
        new_status=CurrentStatus.active,
        source_snapshot_id="snap_abc123abc123abc1",
        source_url="https://www.azcourts.gov/abs-roster",
        retrieved_at=_NOW,
        scraper_version="0.1.0",
    )
    seeded_store.upsert_event(event)
    seeded_store.upsert_event(event)  # idempotent

    row = seeded_store.conn.execute(
        "SELECT event_type, new_status FROM provider_status_event WHERE event_id = 'evt_000001'"
    ).fetchone()
    assert row is not None
    assert row[0] == "authorized"
    assert row[1] == "active"


# ── schema completeness ───────────────────────────────────────────────────────


def test_all_tables_exist(store: RegistryStore) -> None:
    tables = {
        row[0]
        for row in store.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    assert {
        "program",
        "source_snapshot",
        "provider",
        "provider_status_event",
        "provider_alias",
        "crosswalk_courtlistener",
    }.issubset(tables)


# ── storage_path normalization (docs/audit/adversarial_review.md, finding B2) ──
#
# pipeline.snapshot.ingest() always returns an absolute blob_path (it's a
# generic content-addressed store, tested against tmp_path fixtures outside
# the repo — see tests/test_snapshot.py — so it can't assume a repo root).
# RegistryStore.upsert_snapshot() is the single point where that absolute path
# gets rewritten to a repo-relative string before it's persisted, so the
# published source_snapshot.csv/.parquet and `make reproduce`/`make audit`
# work regardless of where the repo is cloned.


def test_normalize_storage_path_rewrites_absolute_path_under_root() -> None:
    absolute = _ROOT / "data" / "raw" / "deadbeef.html"
    assert _normalize_storage_path(str(absolute)) == "data/raw/deadbeef.html"


def test_normalize_storage_path_leaves_relative_path_untouched() -> None:
    assert _normalize_storage_path("data/raw/deadbeef.html") == "data/raw/deadbeef.html"


def test_normalize_storage_path_leaves_absolute_path_outside_root_untouched() -> None:
    # e.g. a raw_dir passed in from outside the repo (tmp_path in a test, or a
    # custom --raw location) — normalization is a portability improvement, not
    # something that should ever raise or silently corrupt an unrelated path.
    outside = "/some/other/machine/scratch/deadbeef.html"
    assert _normalize_storage_path(outside) == outside


def test_upsert_snapshot_normalizes_absolute_storage_path_under_root(
    store: RegistryStore,
) -> None:
    """An absolute, repo-rooted storage_path is stored (and read back) relative."""
    store.upsert_program(_make_program())
    absolute_path = _ROOT / "data" / "raw" / "deadbeef.html"
    store.upsert_snapshot(_make_snapshot(storage_path=str(absolute_path)))

    row = store.conn.execute(
        "SELECT storage_path FROM source_snapshot WHERE snapshot_id = ?",
        ["snap_abc123abc123abc1"],
    ).fetchone()
    assert row[0] == "data/raw/deadbeef.html"

    # get_first_snapshot() reads it back unchanged (still relative).
    snap = store.get_first_snapshot("prog_az_abs")
    assert snap is not None
    assert snap.storage_path == "data/raw/deadbeef.html"
