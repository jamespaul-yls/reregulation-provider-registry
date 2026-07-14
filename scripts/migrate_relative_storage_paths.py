"""One-shot migration: rewrite source_snapshot.storage_path to a repo-relative path.

Background
----------
pipeline/snapshot.py::ingest() always returns an absolute blob_path (it's a
generic content-addressed store, tested against tmp_path fixtures outside the
repo, so it can't assume a repo root). Every row written before this migration
has storage_path baked in as the absolute path on the machine that ran the
scraper (e.g. /Users/jamespaul/Desktop/code_prjcts/database/data/raw/<hash>.html).

pipeline/db.py::RegistryStore.upsert_snapshot() now normalizes storage_path to
a repo-relative POSIX string on write (_normalize_storage_path()), and
pipeline/reproduce.py / pipeline/audit.py resolve a relative storage_path
against the repo root on read. This migration applies the same normalization
to rows already sitting in the DB, so `make reproduce` / `make audit` work
after a fresh `git clone` on any machine, not just this one.

See docs/audit/adversarial_review.md, finding B2.

Usage
-----
    uv run python scripts/migrate_relative_storage_paths.py
    uv run python scripts/migrate_relative_storage_paths.py --db path/to/custom.duckdb

The old DB file is copied to <filename>.bak before the migration writes.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import duckdb

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.db import _normalize_storage_path  # noqa: E402


def migrate(db_path: Path) -> None:
    bak = db_path.with_suffix(".duckdb.bak")
    print(f"Backing up {db_path} -> {bak} …")
    shutil.copy2(db_path, bak)

    conn = duckdb.connect(str(db_path))
    rows = conn.execute("SELECT snapshot_id, storage_path FROM source_snapshot").fetchall()

    n_changed = 0
    for snapshot_id, storage_path in rows:
        normalized = _normalize_storage_path(storage_path)
        if normalized != storage_path:
            conn.execute(
                "UPDATE source_snapshot SET storage_path = ? WHERE snapshot_id = ?",
                [normalized, snapshot_id],
            )
            print(f"  {snapshot_id}: {storage_path} -> {normalized}")
            n_changed += 1

    conn.close()
    print(f"\n{n_changed}/{len(rows)} storage_path value(s) rewritten to repo-relative form.")

    # Verify: every row must now resolve relative to _ROOT (or already have
    # been relative / outside the repo, in which case it's unchanged and that's
    # reported separately, not silently swallowed as success).
    conn2 = duckdb.connect(str(db_path), read_only=True)
    remaining_absolute = conn2.execute(
        "SELECT snapshot_id, storage_path FROM source_snapshot WHERE storage_path LIKE '/%'"
    ).fetchall()
    conn2.close()

    if remaining_absolute:
        print(f"\nWARNING: {len(remaining_absolute)} row(s) still have an absolute storage_path")
        print("(not under the repo root, so normalization intentionally left them as-is):")
        for sid, path in remaining_absolute:
            print(f"  {sid}: {path}")
    else:
        print("All source_snapshot rows now have a repo-relative storage_path.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite storage_path to repo-relative form")
    parser.add_argument("--db", default=str(_DB), help="Path to registry.duckdb")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    migrate(db_path)


if __name__ == "__main__":
    main()
