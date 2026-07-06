"""Provenance audit — assert 100% coverage on all published rows.

Checks:
  1. Every provider has non-NULL source_url and retrieved_at.
  2. Every provider has non-NULL first_seen_snapshot_id that resolves to source_snapshot.
  3. Every provider's last_seen_snapshot_id (when set) resolves to source_snapshot.
  4. Every provider_status_event has non-NULL source_url, retrieved_at, source_snapshot_id,
     and that snapshot_id resolves to source_snapshot.
  5. Every source_snapshot blob exists on disk and its sha256 matches content_sha256.
  6. Every program has non-NULL source_url, retrieved_at, scraper_version, and at least
     one source_snapshot row for its program_id — the program's own authorizing source
     was actually captured immutably, not just asserted in the program row.
  7. Every provider_alias has non-NULL source_url and retrieved_at, and its provider_id
     resolves to provider.

Exits 0 on pass, 1 on any failure.

Usage:
    uv run python -m pipeline.audit
    uv run python -m pipeline.audit --db data/db/registry_reproduced.duckdb
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"


# ── individual checks ─────────────────────────────────────────────────────────


def _check_provider_nulls(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every provider must have source_url and retrieved_at."""
    rows = con.execute(
        """
        SELECT provider_id
        FROM   provider
        WHERE  source_url IS NULL OR retrieved_at IS NULL
        """
    ).fetchall()
    return [f"provider {pid}: source_url or retrieved_at is NULL" for (pid,) in rows]


def _check_provider_first_seen(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every provider must have a non-NULL first_seen_snapshot_id that exists."""
    errors: list[str] = []

    # NULL first_seen_snapshot_id
    nulls = con.execute(
        "SELECT provider_id FROM provider WHERE first_seen_snapshot_id IS NULL"
    ).fetchall()
    errors += [f"provider {pid}: first_seen_snapshot_id is NULL" for (pid,) in nulls]

    # first_seen_snapshot_id doesn't resolve
    orphans = con.execute(
        """
        SELECT p.provider_id, p.first_seen_snapshot_id
        FROM   provider p
        LEFT JOIN source_snapshot s ON s.snapshot_id = p.first_seen_snapshot_id
        WHERE  p.first_seen_snapshot_id IS NOT NULL
          AND  s.snapshot_id IS NULL
        """
    ).fetchall()
    errors += [
        f"provider {pid}: first_seen_snapshot_id {sid!r} not found in source_snapshot"
        for pid, sid in orphans
    ]
    return errors


def _check_provider_last_seen(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every non-NULL last_seen_snapshot_id must resolve."""
    rows = con.execute(
        """
        SELECT p.provider_id, p.last_seen_snapshot_id
        FROM   provider p
        LEFT JOIN source_snapshot s ON s.snapshot_id = p.last_seen_snapshot_id
        WHERE  p.last_seen_snapshot_id IS NOT NULL
          AND  s.snapshot_id IS NULL
        """
    ).fetchall()
    return [
        f"provider {pid}: last_seen_snapshot_id {sid!r} not found in source_snapshot"
        for pid, sid in rows
    ]


def _check_event_provenance(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every event must have non-NULL source_url, retrieved_at, source_snapshot_id."""
    rows = con.execute(
        """
        SELECT event_id
        FROM   provider_status_event
        WHERE  source_url IS NULL
            OR retrieved_at IS NULL
            OR source_snapshot_id IS NULL
        """
    ).fetchall()
    return [
        f"event {eid}: source_url, retrieved_at, or source_snapshot_id is NULL" for (eid,) in rows
    ]


def _check_event_snapshot_fk(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every event's source_snapshot_id must resolve to source_snapshot."""
    rows = con.execute(
        """
        SELECT e.event_id, e.source_snapshot_id
        FROM   provider_status_event e
        LEFT JOIN source_snapshot s ON s.snapshot_id = e.source_snapshot_id
        WHERE  s.snapshot_id IS NULL
        """
    ).fetchall()
    return [
        f"event {eid}: source_snapshot_id {sid!r} not found in source_snapshot" for eid, sid in rows
    ]


def _check_program_nulls(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every program must have source_url, retrieved_at, and scraper_version."""
    rows = con.execute(
        """
        SELECT program_id
        FROM   program
        WHERE  source_url IS NULL OR retrieved_at IS NULL OR scraper_version IS NULL
        """
    ).fetchall()
    return [
        f"program {pid}: source_url, retrieved_at, or scraper_version is NULL" for (pid,) in rows
    ]


def _check_program_has_snapshot(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every program must be backed by at least one immutable source_snapshot row."""
    rows = con.execute(
        """
        SELECT p.program_id
        FROM   program p
        LEFT JOIN source_snapshot s ON s.program_id = p.program_id
        WHERE  s.snapshot_id IS NULL
        """
    ).fetchall()
    return [
        f"program {pid}: no source_snapshot row exists for this program_id "
        "(source_url is asserted but never captured immutably)"
        for (pid,) in rows
    ]


def _check_alias_nulls(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every provider_alias must have source_url and retrieved_at."""
    rows = con.execute(
        """
        SELECT provider_id, alias_name
        FROM   provider_alias
        WHERE  source_url IS NULL OR retrieved_at IS NULL
        """
    ).fetchall()
    return [
        f"provider_alias {pid}/{alias!r}: source_url or retrieved_at is NULL" for pid, alias in rows
    ]


def _check_alias_provider_fk(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every provider_alias.provider_id must resolve to provider."""
    rows = con.execute(
        """
        SELECT a.provider_id, a.alias_name
        FROM   provider_alias a
        LEFT JOIN provider p ON p.provider_id = a.provider_id
        WHERE  p.provider_id IS NULL
        """
    ).fetchall()
    return [
        f"provider_alias {pid}/{alias!r}: provider_id not found in provider" for pid, alias in rows
    ]


def _check_blobs(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Every source_snapshot blob must exist on disk with matching sha256.

    storage_path is stored repo-relative (pipeline/db.py::_normalize_storage_path),
    so a relative value is resolved against _ROOT rather than the process's
    current working directory — this must pass regardless of where the repo
    is cloned or which directory `make audit` is invoked from.
    """
    rows = con.execute(
        "SELECT snapshot_id, storage_path, content_sha256 FROM source_snapshot"
    ).fetchall()
    errors: list[str] = []
    for snap_id, storage_path, expected_sha in rows:
        blob = Path(storage_path)
        if not blob.is_absolute():
            blob = _ROOT / blob
        if not blob.exists():
            errors.append(f"snapshot {snap_id}: blob missing at {storage_path} (resolved: {blob})")
            continue
        actual_sha = hashlib.sha256(blob.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            errors.append(
                f"snapshot {snap_id}: sha256 mismatch "
                f"(expected {expected_sha[:16]}…, got {actual_sha[:16]}…)"
            )
    return errors


# ── public API ────────────────────────────────────────────────────────────────


def audit(db_path: Path) -> list[str]:
    """Run all provenance checks against *db_path*.

    Returns a list of error strings (empty = pass).
    Raises IOError if the DB is not readable.
    """
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        raise OSError(f"Cannot open DB at {db_path}: {exc}") from exc

    errors: list[str] = []
    checks = [
        ("program null provenance", _check_program_nulls),
        ("program has snapshot", _check_program_has_snapshot),
        ("provider null provenance", _check_provider_nulls),
        ("provider first_seen FK", _check_provider_first_seen),
        ("provider last_seen FK", _check_provider_last_seen),
        ("event null provenance", _check_event_provenance),
        ("event source_snapshot FK", _check_event_snapshot_fk),
        ("alias null provenance", _check_alias_nulls),
        ("alias provider FK", _check_alias_provider_fk),
        ("blob existence + sha256", _check_blobs),
    ]

    for label, fn in checks:
        found = fn(con)
        if found:
            logger.warning("[FAIL] %s — %d violation(s)", label, len(found))
            errors.extend(found)
        else:
            logger.info("[PASS] %s", label)

    con.close()
    return errors


# ── CLI ───────────────────────────────────────────────────────────────────────


def _summary_table(errors: list[str]) -> None:
    """Print a grouped summary of errors."""
    by_category: dict[str, list[str]] = {}
    for e in errors:
        # First word before ':' is the category key
        category = e.split(":")[0].split()[0]
        by_category.setdefault(category, []).append(e)
    for cat, msgs in by_category.items():
        print(f"\n  [{cat}] {len(msgs)} error(s)")
        for m in msgs[:10]:
            print(f"    {m}")
        if len(msgs) > 10:
            print(f"    … and {len(msgs) - 10} more")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Provenance audit for the registry DB")
    parser.add_argument("--db", default=str(_DB), help="Path to registry DuckDB file")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        # Try .bak fallback
        bak = db_path.with_suffix(".duckdb.bak")
        if bak.exists():
            print(f"Warning: {db_path.name} not found; auditing .bak instead")
            db_path = bak
        else:
            print(f"Error: DB not found at {db_path}", file=sys.stderr)
            return 1

    print(f"\nAuditing {db_path} …")

    try:
        errors = audit(db_path)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    con = duckdb.connect(str(db_path), read_only=True)
    n_prog = con.execute("SELECT count(*) FROM program").fetchone()[0]
    n_snap = con.execute("SELECT count(*) FROM source_snapshot").fetchone()[0]
    n_prov = con.execute("SELECT count(*) FROM provider").fetchone()[0]
    n_evt = con.execute("SELECT count(*) FROM provider_status_event").fetchone()[0]
    n_alias = con.execute("SELECT count(*) FROM provider_alias").fetchone()[0]
    con.close()

    print(
        f"\n  Rows audited: {n_prog} programs, {n_snap} snapshots, "
        f"{n_prov} providers, {n_evt} events, {n_alias} aliases"
    )

    if errors:
        print(f"\n  FAIL: {len(errors)} provenance violation(s)")
        _summary_table(errors)
        print()
        return 1

    print(
        f"\n  PASS: all provenance checks clean ({n_prog} programs, {n_prov} providers, "
        f"{n_evt} events, {n_alias} aliases, {n_snap} snapshots)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
