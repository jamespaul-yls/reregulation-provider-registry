"""Entrypoint: python -m pipeline.export

Reads the dev DuckDB → writes data/release/ as CSV + Parquet + datapackage.json.

"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import duckdb
import polars as pl

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_DEFAULT_DB = _ROOT / "data" / "db" / "registry.duckdb"
_DEFAULT_RELEASE = _ROOT / "data" / "release"

# Tables exported in dependency order.  crosswalk_courtlistener is v3 (stub);
# it is exported like any other table even while empty, so the datapackage
# schema and downstream tooling can rely on the file always existing.
_TABLES = [
    "program",
    "source_snapshot",
    "provider",
    "provider_status_event",
    "provider_alias",
    "crosswalk_courtlistener",
]

# Deterministic row order for each exported table, keyed on primary key column(s).
# Without this, `SELECT * FROM table` returns DuckDB's current physical row order,
# which follows insertion order — and insertion order is not guaranteed stable across
# runs (e.g. pipeline/diff.py used to iterate a set of provider_ids; see its comment).
# Sorting by primary key here means data/release/ is byte-for-byte reproducible from
# the same data/raw/ snapshots regardless of any such upstream nondeterminism, which is
# what actually makes the CI drift gate (.github/workflows/ci.yml) reliable rather than
# flaky. See docs/audit/adversarial_review.md B3.
_ORDER_BY = {
    "program": ["program_id"],
    "source_snapshot": ["snapshot_id"],
    "provider": ["provider_id"],
    "provider_status_event": ["event_id"],
    "provider_alias": ["provider_id", "alias_name"],
    "crosswalk_courtlistener": ["provider_id", "cl_docket_id"],
}


def export(
    db_path: Path = _DEFAULT_DB,
    release_dir: Path = _DEFAULT_RELEASE,
) -> dict[str, int]:
    """Export all tables from *db_path* to *release_dir*.

    Returns a mapping of table name → row count for each exported table.
    """
    release_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    # DuckDB renders TIMESTAMPTZ columns (retrieved_at, reviewed_at) using the
    # connection's session TimeZone, which defaults to the host OS's local timezone —
    # NOT a fixed value. Every release table has a retrieved_at column, so without this,
    # the exported CSV/Parquet strings depend on which machine ran the export (e.g.
    # "-0400" on a dev laptop in America/New_York vs "+0000" on a UTC CI runner) even
    # though the underlying instant is identical. Pin it so data/release/ is
    # byte-for-byte reproducible regardless of the exporting machine's timezone —
    # this is what the CI drift gate (.github/workflows/ci.yml) actually depends on.
    conn.execute("SET TimeZone='UTC'")
    try:
        counts: dict[str, int] = {}

        for table in _TABLES:
            order_by = ", ".join(_ORDER_BY[table])
            df: pl.DataFrame = conn.execute(
                f"SELECT * FROM {table} ORDER BY {order_by}"  # noqa: S608
            ).pl()
            n = len(df)
            counts[table] = n

            df.write_parquet(release_dir / f"{table}.parquet")
            # CSV doesn't support nested types — serialize lists as JSON-array
            # strings (matches the "JSON array" contract in the data dictionary).
            # An empty/NULL list is written as "" per the same contract.
            list_cols = [
                name
                for name, dtype in zip(df.columns, df.dtypes, strict=True)
                if dtype == pl.List(pl.String)
            ]
            df_csv = (
                df.with_columns(
                    [
                        pl.col(name).map_elements(_list_to_json, return_dtype=pl.String)
                        for name in list_cols
                    ]
                )
                if list_cols
                else df
            )
            df_csv.write_csv(release_dir / f"{table}.csv")

            logger.info("exported %s: %d rows", table, n)
    finally:
        conn.close()

    # scripts/build_datapackage.py is the single source of truth for the
    # Frictionless schema (field types, enums, constraints, foreign keys).
    # Writing datapackage.json here as well would drift out of sync with it.
    sys.path.insert(0, str(_ROOT))
    from scripts.build_datapackage import build  # noqa: PLC0415

    build(release_dir=release_dir)

    return counts


def _list_to_json(v: object) -> str:
    if v is None or len(v) == 0:  # v may be a python list or a polars Series
        return ""
    return json.dumps(list(v), ensure_ascii=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    counts = export()
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
