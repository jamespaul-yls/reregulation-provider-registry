"""Tests for pipeline.diff — snapshot diffing and event generation.

Three-provider scenario (no network calls, no fixtures — all in-memory):
  • Provider A: only in new snapshot  → 'authorized' event
  • Provider B: only in old snapshot  → 'disappeared_from_roster' event
  • Provider C: in both, status changed active→suspended → 'status_change' event

Assertions:
  1. Exactly three events emitted.
  2. Correct event_type and provider_id for each.
  3. provider.current_status recomputed correctly for all three providers.
  4. Idempotency: second call with the same pair produces no new DB rows.
  5. Cross-program diff is rejected with ValueError.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from models.enums import CurrentStatus, EventType, MediaType
from models.schema import Program, Provider, SourceSnapshot
from pipeline.db import RegistryStore
from pipeline.diff import diff_snapshots

_UTC = datetime.UTC
_T1 = datetime.datetime(2026, 5, 1, 12, 0, 0, tzinfo=_UTC)
_T2 = datetime.datetime(2026, 6, 1, 12, 0, 0, tzinfo=_UTC)
_SHA1 = "a" * 64
_SHA2 = "b" * 64
_SOURCE_URL = "https://www.azcourts.gov/abs-roster"


# ── factories ─────────────────────────────────────────────────────────────────


def _program(program_id: str = "prog_az_abs", jurisdiction: str = "AZ") -> Program:
    return Program(
        program_id=program_id,
        jurisdiction=jurisdiction,
        program_name="Alternative Business Structure",
        program_type="abs",
        regulator="Arizona Supreme Court",
        regulator_url="https://www.azcourts.gov/",
        authorizing_rule="ACJA §7-209",
        launch_date=datetime.date(2021, 1, 1),
        program_status="active",
        allows_nonlawyer_ownership=True,
        allows_upl_waiver=False,
        allows_software_provider=True,
        source_url=_SOURCE_URL,
        retrieved_at=_T1,
        scraper_version="0.1.0",
    )


def _snap(
    snapshot_id: str,
    sha: str,
    retrieved_at: datetime.datetime,
    program_id: str = "prog_az_abs",
) -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id=snapshot_id,
        program_id=program_id,
        source_url=_SOURCE_URL,
        retrieved_at=retrieved_at,
        content_sha256=sha,
        storage_path=f"/data/raw/{sha}.html",
        media_type=MediaType.html,
        scraper_version="0.1.0",
    )


def _provider(
    provider_id: str,
    name: str,
    snapshot_id: str,
    retrieved_at: datetime.datetime,
    status: CurrentStatus = CurrentStatus.active,
) -> Provider:
    return Provider(
        provider_id=provider_id,
        program_id="prog_az_abs",
        provider_type="entity",
        legal_name=name,
        normalized_name=name.lower(),
        jurisdiction="AZ",
        authorization_date=datetime.date(2022, 1, 1),
        current_status=status,
        first_seen_snapshot_id=snapshot_id,
        last_seen_snapshot_id=snapshot_id,
        source_url=_SOURCE_URL,
        retrieved_at=retrieved_at,
        scraper_version="0.1.0",
    )


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def store(tmp_path: Path) -> RegistryStore:
    s = RegistryStore(tmp_path / "registry.duckdb")
    s.init_schema()
    return s


@pytest.fixture()
def scenario(store: RegistryStore):
    """Seed store and return (old_snap, old_providers, new_snap, new_providers).

    prov_A: new only (snap2)                     → authorized
    prov_B: old only (snap1)                     → disappeared_from_roster
    prov_C: both snapshots, active→suspended     → status_change
    """
    snap1 = _snap("snap_1111111111111111", _SHA1, _T1)
    snap2 = _snap("snap_2222222222222222", _SHA2, _T2)

    prov_a = _provider("prov_A", "Alpha Legal LLC", snap2.snapshot_id, _T2)
    prov_b = _provider("prov_B", "Beta Partners", snap1.snapshot_id, _T1)
    prov_c_old = _provider("prov_C", "Gamma Counsel", snap1.snapshot_id, _T1, CurrentStatus.active)
    prov_c_new = _provider(
        "prov_C", "Gamma Counsel", snap2.snapshot_id, _T2, CurrentStatus.suspended
    )

    store.upsert_program(_program())
    store.upsert_snapshot(snap1)
    store.upsert_snapshot(snap2)
    # All providers that appear in either snapshot must be in the store (FK constraint).
    store.upsert_provider(prov_a)
    store.upsert_provider(prov_b)
    store.upsert_provider(prov_c_old)

    return snap1, [prov_b, prov_c_old], snap2, [prov_a, prov_c_new]


# ── tests ─────────────────────────────────────────────────────────────────────


def test_diff_emits_exactly_three_events(store: RegistryStore, scenario) -> None:
    old_snap, old_provs, new_snap, new_provs = scenario
    events = diff_snapshots(old_snap, old_provs, new_snap, new_provs, store)
    assert len(events) == 3


def test_diff_event_types_and_providers(store: RegistryStore, scenario) -> None:
    old_snap, old_provs, new_snap, new_provs = scenario
    events = diff_snapshots(old_snap, old_provs, new_snap, new_provs, store)

    by_type = {e.event_type: e for e in events}
    assert set(by_type) == {
        EventType.authorized,
        EventType.disappeared_from_roster,
        EventType.status_change,
    }
    assert by_type[EventType.authorized].provider_id == "prov_A"
    assert by_type[EventType.disappeared_from_roster].provider_id == "prov_B"
    assert by_type[EventType.status_change].provider_id == "prov_C"
    assert by_type[EventType.status_change].new_status == CurrentStatus.suspended


def test_diff_recomputes_current_status(store: RegistryStore, scenario) -> None:
    old_snap, old_provs, new_snap, new_provs = scenario
    diff_snapshots(old_snap, old_provs, new_snap, new_provs, store)

    def _status(pid: str) -> str:
        row = store.conn.execute(
            "SELECT current_status FROM provider WHERE provider_id = ?", [pid]
        ).fetchone()
        assert row is not None, f"provider {pid!r} not found"
        return row[0]

    assert _status("prov_A") == "active"  # authorized → active
    assert _status("prov_B") == "exited"  # disappeared_from_roster → exited
    assert _status("prov_C") == "suspended"  # status_change active→suspended


def test_diff_idempotent(store: RegistryStore, scenario) -> None:
    """Calling diff twice on the same snapshot pair must not add new rows."""
    old_snap, old_provs, new_snap, new_provs = scenario
    diff_snapshots(old_snap, old_provs, new_snap, new_provs, store)
    diff_snapshots(old_snap, old_provs, new_snap, new_provs, store)

    count = store.conn.execute("SELECT COUNT(*) FROM provider_status_event").fetchone()[0]
    assert count == 3


def test_diff_rejects_mismatched_programs(store: RegistryStore) -> None:
    snap1 = _snap("snap_1111111111111111", _SHA1, _T1, program_id="prog_az_abs")
    snap2 = _snap("snap_2222222222222222", _SHA2, _T2, program_id="prog_ut_sandbox")

    with pytest.raises(ValueError, match="program_id"):
        diff_snapshots(snap1, [], snap2, [], store)
