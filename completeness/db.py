"""Dev-only DuckDB extension for completeness-audit snapshots.

Deliberately a separate table (and separate DDL) from pipeline/db.py:
completeness_snapshot records external-inventory fetches (frame_reconcile,
later legislative_scan) that are not scoped to a single program_id and must
never participate in the v1 release schema or its FK graph. Same DuckDB
file, same connection pattern as RegistryStore — no new infrastructure to
operate, but zero coupling to program/provider constraints.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from completeness.models import CompletenessSnapshot

_DDL = """
CREATE TABLE IF NOT EXISTS completeness_snapshot (
    snapshot_id     VARCHAR PRIMARY KEY,
    subject         VARCHAR NOT NULL,
    source_url      VARCHAR NOT NULL,
    retrieved_at    TIMESTAMPTZ NOT NULL,
    content_sha256  VARCHAR NOT NULL CHECK (length(content_sha256) = 64),
    storage_path    VARCHAR NOT NULL,
    media_type      VARCHAR NOT NULL,
    fetcher_version VARCHAR NOT NULL
);
"""


class CompletenessStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = str(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> CompletenessStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def init_schema(self) -> None:
        self.conn.execute(_DDL)

    def upsert_snapshot(self, s: CompletenessSnapshot) -> None:
        # Content-addressed and immutable: same snapshot_id means identical
        # bytes on disk, so a duplicate insert on re-run is a no-op.
        self.conn.execute(
            """INSERT INTO completeness_snapshot
               (snapshot_id, subject, source_url, retrieved_at, content_sha256,
                storage_path, media_type, fetcher_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (snapshot_id) DO NOTHING""",
            [
                s.snapshot_id,
                s.subject,
                s.source_url,
                s.retrieved_at,
                s.content_sha256,
                s.storage_path,
                s.media_type.value,
                s.fetcher_version,
            ],
        )
