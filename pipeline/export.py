"""Entrypoint: python -m pipeline.export

Reads the dev DuckDB → writes data/release/ as CSV + Parquet + datapackage.json.

Never hand-edit anything in release/ (CLAUDE.md rule 5).
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


def export(
    db_path: Path = _DEFAULT_DB,
    release_dir: Path = _DEFAULT_RELEASE,
) -> dict[str, int]:
    """Export all tables from *db_path* to *release_dir*.

    Returns a mapping of table name → row count for each exported table.
    """
    release_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    try:
        counts: dict[str, int] = {}

        for table in _TABLES:
            df: pl.DataFrame = conn.execute(f"SELECT * FROM {table}").pl()  # noqa: S608
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
