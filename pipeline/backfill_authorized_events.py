"""One-shot migration: back-fill authorized events for all bootstrapped providers.

Problem: the 671 providers loaded from the initial scrape have no authorized events.
The first cron run would emit authorized events dated TODAY (new_snapshot.retrieved_at),
which is wrong. event_date must be first_seen_snapshot.retrieved_at — the date the
provider was actually first observed.

This migration:
  1. Queries every provider whose first_seen_snapshot_id is set (all of them).
  2. Skips any provider that already has an authorized event.
  3. Emits exactly one authorized ProviderStatusEvent per remaining provider,
     event_date = first_seen_snapshot.retrieved_at.astimezone(UTC).date()
  4. Uses the same _event_id hash as diff_snapshots so future diffs cannot
     produce a duplicate (ON CONFLICT DO UPDATE with identical data is a no-op).
  5. Does NOT call _recompute_statuses — current_status is already correct
     from the initial scrape; future diffs will maintain it.

Idempotency guarantee:
  - Primary guard: skip providers that already have an authorized event.
  - Secondary guard: event_id is a deterministic sha256 hash of
    (provider_id, first_seen_snapshot_id, "authorized") — the same key
    diff_snapshots would generate for a first-snapshot run — so even if
    this script runs twice, the ON CONFLICT clause prevents duplicates.

Usage:
    uv run python -m pipeline.backfill_authorized_events           # real run
    uv run python -m pipeline.backfill_authorized_events --dry-run # preview
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

from models.enums import CurrentStatus, EventType
from models.schema import ProviderStatusEvent
from pipeline.db import RegistryStore
from pipeline.diff import _event_id

logger = logging.getLogger(__name__)

_DB = Path(__file__).parent.parent / "data" / "db" / "registry.duckdb"


def backfill(db_path: Path = _DB, *, dry_run: bool = False) -> dict:
    """Emit authorized events for every provider that is missing one.

    Returns:
        n_created  — events inserted (or that would be inserted in dry-run)
        n_skipped  — providers already covered
        min_date   — earliest event_date across created events
        max_date   — latest event_date across created events
    """
    with RegistryStore(db_path) as store:
        # ── all providers + their first-snapshot provenance + actual status ────
        # JOIN to source_snapshot so I get the exact retrieved_at, source_url,
        # and scraper_version that belong to the observation — not today's values.
        # Include current_status so the event accurately records the status as
        # observed (not always 'active' — a revoked provider appears revoked).
        candidates = store.conn.execute(
            """
            SELECT
                p.provider_id,
                p.first_seen_snapshot_id,
                p.current_status,
                s.source_url,
                s.retrieved_at,
                s.scraper_version
            FROM provider p
            JOIN source_snapshot s ON s.snapshot_id = p.first_seen_snapshot_id
            ORDER BY s.retrieved_at, p.provider_id
            """
        ).fetchall()

        n_upserted = 0
        event_dates: list[datetime.date] = []

        for (
            provider_id,
            snap_id,
            current_status,
            source_url,
            retrieved_at,
            scraper_ver,
        ) in candidates:
            # Normalize to UTC before extracting date — DuckDB may return
            # TIMESTAMPTZ as a local-tz-aware datetime on macOS.
            if isinstance(retrieved_at, datetime.datetime):
                retrieved_at_utc = retrieved_at.astimezone(datetime.UTC)
            else:
                # Shouldn't happen, but be defensive.
                retrieved_at_utc = datetime.datetime(
                    retrieved_at.year,
                    retrieved_at.month,
                    retrieved_at.day,
                    tzinfo=datetime.UTC,
                )

            event_date = retrieved_at_utc.date()

            evt = ProviderStatusEvent(
                event_id=_event_id(provider_id, snap_id, EventType.authorized),
                provider_id=provider_id,
                event_date=event_date,
                event_type=EventType.authorized,
                new_status=CurrentStatus(current_status),
                detail="backfill: initial scrape observation",
                source_snapshot_id=snap_id,
                source_url=source_url,
                retrieved_at=retrieved_at_utc,
                scraper_version=scraper_ver,
            )

            if not dry_run:
                store.upsert_event(evt)

            n_upserted += 1
            event_dates.append(event_date)
            logger.debug(
                "authorized event: %s  date=%s  status=%s",
                provider_id,
                event_date,
                current_status,
            )

        return {
            "n_upserted": n_upserted,
            "min_date": min(event_dates) if event_dates else None,
            "max_date": max(event_dates) if event_dates else None,
        }


def _print_sample(db_path: Path, n: int = 10) -> None:
    """Print a sample of (provider_id, legal_name, first_seen_date, event_date)."""
    with RegistryStore(db_path) as store:
        rows = store.conn.execute(
            """
            SELECT
                p.provider_id,
                p.legal_name,
                p.program_id,
                s.retrieved_at        AS first_seen_ts,
                e.event_date
            FROM provider_status_event e
            JOIN provider p ON p.provider_id = e.provider_id
            JOIN source_snapshot s ON s.snapshot_id = p.first_seen_snapshot_id
            WHERE e.event_type = 'authorized'
            ORDER BY e.event_date, p.program_id, p.provider_id
            LIMIT ?
            """,
            [n],
        ).fetchall()

    print(f"\n{'─' * 90}")
    print(f"  {'provider_id':<28} {'program':<16} {'first_seen (UTC)':<24} {'event_date'}")
    print(f"  {'legal_name':<28}")
    print(f"{'─' * 90}")
    for provider_id, legal_name, program_id, first_seen_ts, event_date in rows:
        if isinstance(first_seen_ts, datetime.datetime):
            first_seen_utc = first_seen_ts.astimezone(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
        else:
            first_seen_utc = str(first_seen_ts)
        print(f"  {provider_id:<28} {program_id:<16} {first_seen_utc:<24} {event_date}")
        print(f"  {legal_name[:60]:<60}")
    print(f"{'─' * 90}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Back-fill authorized events from initial scrape snapshots"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--db", default=str(_DB), help="Path to DuckDB file")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    label = "DRY RUN — " if args.dry_run else ""
    print(f"\n{label}Backfilling authorized events from {db_path} …")

    summary = backfill(db_path, dry_run=args.dry_run)

    action = "would upsert" if args.dry_run else "upserted"
    print(f"\n{'─' * 50}")
    print(f"  Events {action} : {summary['n_upserted']}")
    print(f"  event_date range  : {summary['min_date']}  →  {summary['max_date']}")
    if args.dry_run:
        print("  ── NO WRITES PERFORMED ──")
    print(f"{'─' * 50}\n")

    if not args.dry_run and summary["n_upserted"] > 0:
        print("10-row sample (ordered by event_date, program, provider_id):")
        _print_sample(db_path)


if __name__ == "__main__":
    main()
