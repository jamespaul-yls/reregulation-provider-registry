"""Entrypoint: python -m pipeline.reproduce

Full reproducible rebuild from immutable raw/ snapshots — no network required.

Inputs (read-only):
  data/release/source_snapshot.csv   — snapshot manifest (program, URL, sha256, path)
  data/raw/<sha256>.<ext>            — immutable raw blobs
  scripts/seed_programs.py           — static program metadata

Outputs:
  data/db/registry_reproduced.duckdb — fresh DB (replaces registry.duckdb if writable)
  data/release/                      — CSV + Parquet + datapackage.json

Pipeline:
  1. Read snapshot manifest from source_snapshot.csv
  2. Create fresh DuckDB
  3. Seed programs (static)
  4. For each scraper: register all its snapshots, then parse roster snapshots in
     chronological order, diffing consecutive pairs → provider_status_event rows
  5. Run provenance audit (fail hard on any violation)
  6. Export to data/release/
  7. Atomic rename fresh DB → registry.duckdb (skip if locked, report path)
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import importlib
import logging
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from models.enums import MediaType
from models.schema import SourceSnapshot
from pipeline.audit import audit
from pipeline.db import RegistryStore
from pipeline.diff import diff_snapshots
from pipeline.export import export
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

# Canonical scraper for each program — must stay in sync with orchestrate.py.
_SCRAPER_MAP: dict[str, str] = {
    "prog_az_abs": "scrapers.arizona_abs.ArizonaAbsScraper",
    "prog_az_lp": "scrapers.arizona_lp.ArizonaLpScraper",
    "prog_ca_lda": "scrapers.california_lda.CaliforniaLdaScraper",
    "prog_co_llp": "scrapers.colorado_llp.ColoradoLlpScraper",
    "prog_mn_lp": "scrapers.minnesota_lp.MinnesotaLpScraper",
    "prog_tx_alp": "scrapers.texas_alp.TexasAlpScraper",
    "prog_ut_lpp": "scrapers.utah_lpp.UtahLppScraper",
    "prog_ut_sandbox": "scrapers.utah_sandbox.UtahSandboxScraper",
    "prog_wa_lllt": "scrapers.washington_lllt.WashingtonLlltScraper",
    "prog_wa_entity_pilot": "scrapers.washington_entity_pilot.WashingtonEntityPilotScraper",
}


# ── helpers ───────────────────────────────────────────────────────────────────


def _load_scraper(dotted: str, raw_dir: Path) -> BaseScraper:
    module_path, cls_name = dotted.rsplit(".", 1)
    cls: type[BaseScraper] = getattr(importlib.import_module(module_path), cls_name)
    return cls(raw_dir=raw_dir)


def _row_to_snapshot(row: dict[str, str]) -> SourceSnapshot:
    ts_raw = row["retrieved_at"]
    # CSV exports UTC strings like "2026-06-29T02:04:20.369320+00:00"
    retrieved_at = datetime.datetime.fromisoformat(ts_raw)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=datetime.UTC)
    return SourceSnapshot(
        snapshot_id=row["snapshot_id"],
        program_id=row["program_id"],
        source_url=row["source_url"],
        retrieved_at=retrieved_at,
        content_sha256=row["content_sha256"],
        storage_path=row["storage_path"],
        media_type=MediaType(row["media_type"]),
        scraper_version=row["scraper_version"],
    )


def _read_manifest(release_dir: Path) -> dict[str, list[dict[str, str]]]:
    """Read source_snapshot.csv → {program_id: [rows sorted by retrieved_at]}."""
    snap_csv = release_dir / "source_snapshot.csv"
    if not snap_csv.exists():
        raise FileNotFoundError(
            f"Snapshot manifest not found: {snap_csv}\n"
            "Run 'make export' first to generate data/release/source_snapshot.csv."
        )
    by_program: dict[str, list[dict[str, str]]] = defaultdict(list)
    with snap_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_program[row["program_id"]].append(row)
    for rows in by_program.values():
        rows.sort(key=lambda r: r["retrieved_at"])
    return dict(by_program)


def _seed_programs(store: RegistryStore) -> int:
    sys.path.insert(0, str(_ROOT))
    from scripts.seed_programs import PROGRAMS  # type: ignore[import]

    for prog in PROGRAMS:
        store.upsert_program(prog)
    return len(PROGRAMS)


def _verify_blob(storage_path: str, expected_sha: str) -> bytes:
    """Read raw bytes from storage_path; raise if missing or sha256 mismatches.

    storage_path is stored repo-relative (see pipeline/db.py::_normalize_storage_path)
    so this resolves against _ROOT rather than the process's current working
    directory — reproduce works regardless of where the repo is cloned or which
    directory `make reproduce` is invoked from.
    """
    blob = Path(storage_path)
    if not blob.is_absolute():
        blob = _ROOT / blob
    if not blob.exists():
        raise FileNotFoundError(f"Raw blob missing: {storage_path} (resolved: {blob})")
    raw = blob.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(
            f"Blob integrity failure at {storage_path}: "
            f"expected sha256={expected_sha[:16]}…, got {actual_sha[:16]}…"
        )
    return raw


# ── per-program reproduce ─────────────────────────────────────────────────────


def _reproduce_program(
    program_id: str,
    dotted: str,
    all_snaps: list[dict[str, str]],
    store: RegistryStore,
    raw_dir: Path,
) -> dict:
    """Reproduce one program's derived rows from its raw snapshots.

    Returns a summary dict.
    """
    scraper = _load_scraper(dotted, raw_dir)

    # Register every snapshot for this program (roster + auxiliary).
    # This satisfies FK references for providers whose first/last_seen
    # point to non-roster snapshots (e.g. UT Sandbox activity-report PDFs
    # are stored in source_snapshot even though they produce no providers).
    for row in all_snaps:
        store.upsert_snapshot(_row_to_snapshot(row))

    # Only parse snapshots whose source_url is the scraper's canonical roster URL.
    # This excludes UT Sandbox activity-report PDFs, CA LDA statute pages, etc.
    roster_rows = [r for r in all_snaps if r["source_url"] == scraper.source_url]

    if not roster_rows and all_snaps:
        # Fallback: if all snapshots share a single distinct source_url, treat them
        # all as roster snapshots regardless of URL mismatch.  Handles two cases:
        #   (a) URL drift — the website changed its path after the snapshot was taken
        #       (CO LLP: scraper declares .../PDF/LLP/... but snapshot has
        #       .../wp-content/uploads/PDF/LLP/...)
        #   (b) Redirect target — the fetcher followed a redirect and stored the
        #       final URL (UT LPP: scraper declares the parent page but the snapshot
        #       URL is the memberdll.dll data endpoint after redirect)
        # Programs with multiple distinct source_urls (UT Sandbox: roster + PDFs)
        # correctly fall through to the no_roster_snapshots path via the exact-match
        # filter above.
        distinct_urls = {r["source_url"] for r in all_snaps}
        if len(distinct_urls) == 1:
            roster_rows = list(all_snaps)
            logger.warning(
                "[%s] source_url mismatch — snapshot has %r, scraper declares %r. "
                "Treating all %d snapshot(s) as roster (URL drift or redirect target).",
                program_id,
                next(iter(distinct_urls)),
                scraper.source_url,
                len(roster_rows),
            )

    if not roster_rows:
        logger.info("[%s] no roster snapshots to parse", program_id)
        return {
            "program_id": program_id,
            "status": "no_roster_snapshots",
            "snapshots": 0,
            "providers": 0,
            "events": 0,
        }

    prev_snap: SourceSnapshot | None = None
    total_providers = 0
    total_events = 0

    for row in roster_rows:
        snap = _row_to_snapshot(row)

        # Integrity check + load raw bytes — no network calls.
        raw = _verify_blob(row["storage_path"], row["content_sha256"])

        # Parse providers offline.
        providers = scraper.parse(snap, raw)
        # Stamp provenance from the snapshot onto every provider row.
        providers = [BaseScraper._stamp(p, snap) for p in providers]

        # Capture the old provider set BEFORE upserting new rows so
        # list_providers_by_snapshot still sees the previous snapshot's data.
        old_providers = (
            store.list_providers_by_snapshot(prev_snap.snapshot_id) if prev_snap is not None else []
        )

        for p in providers:
            store.upsert_provider(p)

        # diff_snapshots expects an old_snapshot; for the very first snapshot
        # of a program use new_snap as old_snap with empty old_providers — every
        # provider appears as an addition and gets an 'authorized' event.
        old_snap_for_diff = prev_snap if prev_snap is not None else snap

        events = diff_snapshots(
            old_snapshot=old_snap_for_diff,
            old_providers=old_providers,
            new_snapshot=snap,
            new_providers=providers,
            store=store,
            write=True,
        )

        logger.info(
            "[%s] snap=%s  providers=%d  events=%d",
            program_id,
            snap.snapshot_id,
            len(providers),
            len(events),
        )

        total_events += len(events)
        prev_snap = snap

    # Cumulative distinct providers ever tracked for this program — NOT the
    # last-processed snapshot's roster size, which understates totals for any
    # program where Wayback-only or since-exited providers persist in the
    # table without appearing on the most recent roster.
    (total_providers,) = store.conn.execute(
        "SELECT count(*) FROM provider WHERE program_id = ?", [program_id]
    ).fetchone()

    return {
        "program_id": program_id,
        "status": "ok",
        "snapshots": len(roster_rows),
        "providers": total_providers,
        "events": total_events,
    }


# ── main reproduce pipeline ───────────────────────────────────────────────────


def reproduce(
    db_path: Path = _DB,
    raw_dir: Path = _RAW,
    release_dir: Path = _RELEASE,
) -> list[dict]:
    """Run the full reproduce pipeline.

    Returns per-program result dicts.
    Raises SystemExit(1) if the provenance audit fails.
    """
    # ── 1. Read snapshot manifest ─────────────────────────────────────────────
    logger.info("Reading snapshot manifest from %s", release_dir / "source_snapshot.csv")
    manifest = _read_manifest(release_dir)
    n_total_snaps = sum(len(v) for v in manifest.values())
    logger.info(
        "Manifest: %d program(s), %d total snapshot(s)",
        len(manifest),
        n_total_snaps,
    )

    # ── 2. Create fresh DB ────────────────────────────────────────────────────
    fresh_db = db_path.with_name("registry_reproduced.duckdb")
    if fresh_db.exists():
        fresh_db.unlink()
        logger.info("Removed stale %s", fresh_db.name)

    logger.info("Building fresh DB at %s", fresh_db)

    results: list[dict] = []

    with RegistryStore(fresh_db) as store:
        store.init_schema()

        # ── 3. Seed programs ─────────────────────────────────────────────────
        n_programs = _seed_programs(store)
        logger.info("Seeded %d program rows (static, no network)", n_programs)

        # ── 4. Reproduce each program ─────────────────────────────────────────
        for program_id, dotted in _SCRAPER_MAP.items():
            all_snaps = manifest.get(program_id, [])
            result = _reproduce_program(program_id, dotted, all_snaps, store, raw_dir)
            results.append(result)

    # ── 5. Provenance audit ───────────────────────────────────────────────────
    logger.info("Running provenance audit …")
    errors = audit(fresh_db)
    if errors:
        print(f"\n  AUDIT FAIL: {len(errors)} provenance violation(s):")
        for e in errors[:20]:
            print(f"    {e}")
        if len(errors) > 20:
            print(f"    … and {len(errors) - 20} more")
        print()
        sys.exit(1)

    logger.info("Audit passed — 0 violations")

    # ── 6. Export to release/ ─────────────────────────────────────────────────
    logger.info("Exporting to %s", release_dir)
    counts = export(db_path=fresh_db, release_dir=release_dir)
    logger.info("Exported: %s", counts)

    # ── 7. Atomic rename fresh DB → registry.duckdb ───────────────────────────
    try:
        shutil.move(str(fresh_db), str(db_path))
        logger.info("Replaced %s with reproduced DB", db_path.name)
    except (PermissionError, OSError) as exc:
        logger.warning(
            "Could not replace %s (%s). "
            "Reproduced DB left at %s — rename it manually after closing DBeaver.",
            db_path.name,
            exc,
            fresh_db,
        )

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def _print_summary(results: list[dict]) -> None:
    total_providers = sum(r.get("providers", 0) for r in results)
    total_events = sum(r.get("events", 0) for r in results)

    print(f"\n{'─' * 78}")
    print("  REPRODUCE SUMMARY")
    print(f"{'─' * 78}")
    fmt = "  {pid:<22} {status:<22} {snaps:>4} snaps  {providers:>5} providers  {events:>5} events"
    print(fmt.format(pid="program", status="status", snaps="N", providers="N", events="Δevt"))
    print(f"  {'─' * 74}")
    for r in results:
        status = r["status"]
        snaps = r.get("snapshots", 0)
        providers = r.get("providers", 0)
        events = r.get("events", 0)
        print(
            fmt.format(
                pid=r["program_id"],
                status=status,
                snaps=snaps,
                providers=providers,
                events=events,
            )
        )
    print(f"{'─' * 78}")
    print(f"  Total: {total_providers} providers  {total_events} events")
    print(f"{'─' * 78}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Reproduce all derived tables from data/raw/ — no network"
    )
    parser.add_argument("--db", default=str(_DB), help="Target DuckDB path")
    parser.add_argument("--raw", default=str(_RAW), help="Raw snapshots directory")
    parser.add_argument("--release", default=str(_RELEASE), help="Release output directory")
    args = parser.parse_args()

    print("\nReproducing registry from raw snapshots (no network) …\n")

    results = reproduce(
        db_path=Path(args.db),
        raw_dir=Path(args.raw),
        release_dir=Path(args.release),
    )

    _print_summary(results)


if __name__ == "__main__":
    main()
