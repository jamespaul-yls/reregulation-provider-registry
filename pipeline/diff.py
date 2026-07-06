"""Snapshot diffing → provider_status_event rows.

Algorithm:
  1. Index old_providers and new_providers by provider_id.
  2. Additions (in new, not old)  → 'authorized' event, new_status=active.
  3. Removals  (in old, not new)  → 'disappeared_from_roster' event, new_status=exited.
  4. Status changes (in both, current_status differs) → 'status_change' event.
  5. Persist events via RegistryStore (idempotent: event_id is a deterministic hash).
  6. Recompute provider.current_status from the full event log for affected providers.

Event-ID stability:
  event_id = "evt_" + sha256("{provider_id}:{new_snapshot_id}:{event_type}")[:24]

  The same snapshot pair always yields the same event_ids, so re-running adds no rows
  (ON CONFLICT DO UPDATE with identical data is a logical no-op).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence

from models.enums import CurrentStatus, EventType
from models.schema import Provider, ProviderRef, ProviderStatusEvent, SourceSnapshot
from pipeline.db import RegistryStore

# Accepted by diff_snapshots: full Provider or the lightweight ProviderRef.
_ProviderLike = Provider | ProviderRef

logger = logging.getLogger(__name__)


def _event_id(provider_id: str, snapshot_id: str, event_type: EventType) -> str:
    """Stable, deterministic event PK — guarantees idempotency across re-runs."""
    raw = f"{provider_id}:{snapshot_id}:{event_type}"
    return "evt_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def diff_snapshots(
    old_snapshot: SourceSnapshot,
    old_providers: Sequence[_ProviderLike],
    new_snapshot: SourceSnapshot,
    new_providers: Sequence[_ProviderLike],
    store: RegistryStore,
    *,
    write: bool = True,
) -> list[ProviderStatusEvent]:
    """Diff two snapshots for the same program; emit and persist ProviderStatusEvent rows.

    Preconditions when write=True (caller must satisfy):
    - Both snapshots already persisted to *store* (FK constraint).
    - All providers appearing in either snapshot already persisted to *store*.
    - Both snapshots must share the same program_id.

    write=False computes events without touching the store (for dry-run/preview).
    Idempotent when write=True: same pair of snapshots → no new DB rows.

    Returns the list of events derived from this diff.
    """
    if old_snapshot.program_id != new_snapshot.program_id:
        raise ValueError(
            f"Snapshots must share program_id: "
            f"{old_snapshot.program_id!r} vs {new_snapshot.program_id!r}"
        )

    old_by_id: dict[str, Provider] = {p.provider_id: p for p in old_providers}
    new_by_id: dict[str, Provider] = {p.provider_id: p for p in new_providers}

    event_date = new_snapshot.retrieved_at.date()
    provenance = {
        "source_url": new_snapshot.source_url,
        "retrieved_at": new_snapshot.retrieved_at,
        "scraper_version": new_snapshot.scraper_version,
        "source_snapshot_id": new_snapshot.snapshot_id,
    }

    events: list[ProviderStatusEvent] = []

    # Additions — appeared in new snapshot, absent from old
    for pid in new_by_id:
        if pid not in old_by_id:
            events.append(
                ProviderStatusEvent(
                    event_id=_event_id(pid, new_snapshot.snapshot_id, EventType.authorized),
                    provider_id=pid,
                    event_date=event_date,
                    event_type=EventType.authorized,
                    new_status=new_by_id[pid].current_status,
                    detail=None,
                    **provenance,
                )
            )

    # Removals — in old snapshot, absent from new
    for pid in old_by_id:
        if pid not in new_by_id:
            eid = _event_id(pid, new_snapshot.snapshot_id, EventType.disappeared_from_roster)
            events.append(
                ProviderStatusEvent(
                    event_id=eid,
                    provider_id=pid,
                    event_date=event_date,
                    event_type=EventType.disappeared_from_roster,
                    new_status=CurrentStatus.exited,
                    detail=None,
                    **provenance,
                )
            )

    # Status changes — present in both, but current_status differs.
    # sorted(): dict_keys & dict_keys returns a set, whose iteration order depends on
    # Python's per-process hash randomization (PYTHONHASHSEED). Without sorting, two
    # otherwise-identical `make reproduce` runs from the same data/raw/ snapshots can
    # emit these events in a different order, which then shows up as spurious row-order
    # "drift" in data/release/ even though every row's content is identical — see
    # docs/audit/adversarial_review.md B3 / the CI drift gate in .github/workflows/ci.yml.
    for pid in sorted(old_by_id.keys() & new_by_id.keys()):
        old_status = old_by_id[pid].current_status
        new_status = new_by_id[pid].current_status
        if old_status != new_status:
            events.append(
                ProviderStatusEvent(
                    event_id=_event_id(pid, new_snapshot.snapshot_id, EventType.status_change),
                    provider_id=pid,
                    event_date=event_date,
                    event_type=EventType.status_change,
                    new_status=new_status,
                    detail=f"{old_status} → {new_status}",
                    **provenance,
                )
            )

    if write:
        # Persist (idempotent: ON CONFLICT DO UPDATE with identical data)
        for evt in events:
            store.upsert_event(evt)
        # Recompute provider.current_status from the full chronological event log
        _recompute_statuses({e.provider_id for e in events}, store)

    logger.info(
        "diff_snapshots(%s): %d events — %d authorized, %d disappeared, %d status_change",
        old_snapshot.program_id,
        len(events),
        sum(1 for e in events if e.event_type == EventType.authorized),
        sum(1 for e in events if e.event_type == EventType.disappeared_from_roster),
        sum(1 for e in events if e.event_type == EventType.status_change),
    )
    return events


def _recompute_statuses(provider_ids: set[str], store: RegistryStore) -> None:
    """Set provider.current_status to the new_status of the most-recent event."""
    for pid in provider_ids:
        row = store.conn.execute(
            """
            SELECT new_status
            FROM provider_status_event
            WHERE provider_id = ?
            ORDER BY event_date DESC, event_id DESC
            LIMIT 1
            """,
            [pid],
        ).fetchone()
        if row is None:
            continue
        store.conn.execute(
            "UPDATE provider SET current_status = ? WHERE provider_id = ?",
            [row[0], pid],
        )
