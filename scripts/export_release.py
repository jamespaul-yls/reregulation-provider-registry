"""Export all tables from the registry DB to data/release/ (CSV + Parquet).

Handles:
- TIMESTAMPTZ → UTC ISO-8601 strings
- VARCHAR[]   → JSON-array strings  ["a", "b"]  (empty → "[]")
- BOOLEAN     → true / false
- NULL        → empty string in CSV

Usage:
    uv run python scripts/export_release.py
    uv run python scripts/export_release.py --db path/to/registry.duckdb
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RELEASE = _ROOT / "data" / "release"

# Tables in publish order (no FK ordering needed for export).
_TABLES = [
    "program",
    "source_snapshot",
    "provider",
    "provider_status_event",
    "provider_alias",
    "crosswalk_courtlistener",
]

# Columns that are VARCHAR[] arrays in DuckDB → serialize as JSON strings.
_ARRAY_COLS: dict[str, list[str]] = {
    "provider": ["practice_areas_raw", "practice_areas_list"],
}

# TIMESTAMPTZ columns in each table.
_TS_COLS: dict[str, list[str]] = {
    "program": ["retrieved_at"],
    "source_snapshot": ["retrieved_at"],
    "provider": ["retrieved_at"],
    "provider_status_event": ["retrieved_at"],
    "provider_alias": ["retrieved_at"],
    "crosswalk_courtlistener": ["reviewed_at"],
}


def _to_utc_str(v: object) -> str:
    """Render a datetime as UTC ISO-8601 string; return '' for None."""
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(datetime.UTC)
        else:
            v = v.replace(tzinfo=datetime.UTC)
        return v.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    return str(v)


def _arr_to_json(v: object) -> str:
    """Render a list (or None) as a compact JSON array string."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return json.dumps(list(v), ensure_ascii=False)
    return str(v)


def _export_table(con: duckdb.DuckDBPyConnection, table: str, release_dir: Path) -> int:
    """Export *table* to CSV and Parquet; return row count."""
    arrow_table: pa.Table = con.execute(f"SELECT * FROM {table}").to_arrow_table()
    col_names = arrow_table.schema.names

    # ── post-process in Python ────────────────────────────────────────────────
    columns: list[pa.Array] = []
    for i, col_name in enumerate(col_names):
        col = arrow_table.column(i)

        # TIMESTAMPTZ / timestamp columns → UTC ISO-8601 string
        if col_name in _TS_COLS.get(table, []):
            new_vals = [_to_utc_str(v.as_py()) for v in col]
            columns.append(pa.array(new_vals, type=pa.string()))

        # VARCHAR[] array columns → JSON string
        elif col_name in _ARRAY_COLS.get(table, []):
            new_vals = [_arr_to_json(v.as_py()) for v in col]
            columns.append(pa.array(new_vals, type=pa.string()))

        else:
            columns.append(col)

    processed = pa.table({name: columns[i] for i, name in enumerate(col_names)})

    # ── CSV ───────────────────────────────────────────────────────────────────
    csv_path = release_dir / f"{table}.csv"
    import pyarrow.csv as pcsv

    csv_opts = pcsv.WriteOptions(
        include_header=True,
        delimiter=",",
        quoting_style="needed",
    )
    with pcsv.CSVWriter(str(csv_path), processed.schema, write_options=csv_opts) as w:
        w.write_table(processed)

    # ── Parquet ───────────────────────────────────────────────────────────────
    parquet_path = release_dir / f"{table}.parquet"
    pq.write_table(
        processed,
        str(parquet_path),
        compression="snappy",
        write_statistics=True,
    )

    n = len(processed)
    print(f"  {table:<30} {n:>6} rows  →  {csv_path.name}, {parquet_path.name}")
    return n


def main(db_path: Path = _DB) -> None:
    if not db_path.exists():
        # Fall back to .bak if live DB is locked
        bak = db_path.with_suffix(".duckdb.bak")
        if bak.exists():
            print(f"Warning: {db_path.name} not accessible; falling back to .bak")
            db_path = bak
        else:
            print(f"Error: DB not found: {db_path}", file=sys.stderr)
            sys.exit(1)

    _RELEASE.mkdir(parents=True, exist_ok=True)

    print(f"Exporting from {db_path} → {_RELEASE}/")

    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException:
        bak = db_path.with_suffix(".duckdb.bak")
        if not bak.exists():
            raise
        print(f"Warning: DB locked; falling back to {bak.name}")
        con = duckdb.connect(str(bak), read_only=True)

    counts: dict[str, int] = {}
    for table in _TABLES:
        counts[table] = _export_table(con, table, _RELEASE)

    con.close()

    print(f"\nTotal: {sum(counts.values())} rows across {len(_TABLES)} tables")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export registry to data/release/")
    parser.add_argument("--db", default=str(_DB), help="Path to registry.duckdb")
    args = parser.parse_args()
    main(Path(args.db))
