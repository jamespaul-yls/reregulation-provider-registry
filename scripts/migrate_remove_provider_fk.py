"""One-shot migration: remove FK constraint declarations from the provider table.

Background
----------
DuckDB 1.5.x enforces FK constraints during ON CONFLICT DO UPDATE because that
operation internally deletes and reinserts the row.  When any outgoing FK column
in `provider` (program_id, first_seen_snapshot_id, last_seen_snapshot_id) is
updated and the row is also referenced by provider_status_event, DuckDB raises a
spurious constraint error.

Fix: re-create the `provider` table without REFERENCES clauses.  FK integrity is
already enforced at the Python layer in RegistryStore._require_*.

Usage
-----
    uv run python scripts/migrate_remove_provider_fk.py
    uv run python scripts/migrate_remove_provider_fk.py --db path/to/custom.duckdb

The old DB file is renamed to <filename>.bak before the migration writes.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import duckdb

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"

# Ensure project root is on sys.path so `pipeline` is importable.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Tables in dependency order (children before parents for drop; parents first for insert).
_INSERT_ORDER = [
    "program",
    "source_snapshot",
    "provider",
    "provider_status_event",
    "provider_alias",
    "crosswalk_courtlistener",
]


def migrate(db_path: Path) -> None:
    bak = db_path.with_suffix(".duckdb.bak")
    print(f"Reading {db_path} …")

    conn = duckdb.connect(str(db_path))

    # ── export all rows ───────────────────────────────────────────────────────
    data: dict[str, list[tuple]] = {}
    columns: dict[str, list[str]] = {}
    for tbl in _INSERT_ORDER:
        try:
            rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
            cols = [d[0] for d in conn.description]
            data[tbl] = rows
            columns[tbl] = cols
            print(f"  {tbl}: {len(rows)} rows")
        except Exception as exc:
            print(f"  {tbl}: could not read — {exc}")
            data[tbl] = []
            columns[tbl] = []

    conn.close()

    # ── backup original ───────────────────────────────────────────────────────
    print(f"\nBacking up to {bak} …")
    shutil.copy2(db_path, bak)

    # ── delete and recreate ───────────────────────────────────────────────────
    db_path.unlink()
    print(f"Recreating {db_path} with updated schema …")

    from pipeline.db import RegistryStore

    with RegistryStore(db_path) as store:
        store.init_schema()

        # Insert in FK-dependency order.
        for tbl in _INSERT_ORDER:
            rows = data[tbl]
            cols = columns[tbl]
            if not rows or not cols:
                print(f"  {tbl}: 0 rows (skipped)")
                continue
            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join(cols)
            sql = f"INSERT INTO {tbl} ({col_list}) VALUES ({placeholders})"
            for row in rows:
                store.conn.execute(sql, list(row))
            print(f"  {tbl}: {len(rows)} rows inserted")

    # ── verify ────────────────────────────────────────────────────────────────
    print("\nVerifying row counts …")
    conn2 = duckdb.connect(str(db_path))
    ok = True
    for tbl in _INSERT_ORDER:
        orig = len(data[tbl])
        new = conn2.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        match = "✓" if orig == new else "✗ MISMATCH"
        print(f"  {tbl}: {orig} → {new}  {match}")
        if orig != new:
            ok = False
    conn2.close()

    if ok:
        print(f"\nMigration complete. Backup: {bak}")
    else:
        print(f"\nMigration FAILED — row count mismatch. Restore from {bak}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove FK constraints from provider table")
    parser.add_argument("--db", default=str(_DB), help="Path to registry.duckdb")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    migrate(db_path)


if __name__ == "__main__":
    main()
