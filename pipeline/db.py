"""DuckDB-backed dev store for the registry.

Three-layer separation (CLAUDE.md rule 5):
  raw/  →  this store  →  release/

Design:
- Single persistent DuckDB connection per RegistryStore instance.
- Tables are created in FK-dependency order.
- DuckDB 1.5.x enforces FK constraints during ON CONFLICT DO UPDATE (it
  internally does delete+reinsert, which violates an incoming FK from child
  tables).  To avoid this, FK declarations are OMITTED from the `provider`
  table — the table most frequently upserted — and enforced in Python instead
  via _require_program() / _require_snapshot().  All other tables keep their
  FK declarations for schema documentation.
- list[str] columns use DuckDB's native VARCHAR[] type (round-trips cleanly
  through polars/Parquet without JSON serialisation).
- dict columns (ownership_structure) use VARCHAR (JSON string).
- Pydantic models are the source of truth; this module never constructs raw
  rows manually.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import duckdb

from models.enums import CurrentStatus, MediaType, ProgramStatus, ProgramType
from models.schema import (
    CrosswalkCourtlistener,
    Program,
    Provider,
    ProviderAlias,
    ProviderRef,
    ProviderStatusEvent,
    SourceSnapshot,
)

# ── DDL ───────────────────────────────────────────────────────────────────────
# Tables in FK-dependency order: program → source_snapshot → provider
# → provider_status_event, provider_alias, crosswalk_courtlistener.

_DDL = """
CREATE TABLE IF NOT EXISTS program (
    program_id                 VARCHAR  PRIMARY KEY,
    jurisdiction               VARCHAR  NOT NULL CHECK (length(jurisdiction) = 2),
    program_name               VARCHAR  NOT NULL,
    program_type               VARCHAR  NOT NULL,
    regulator                  VARCHAR  NOT NULL,
    regulator_url              VARCHAR  NOT NULL,
    authorizing_rule           VARCHAR  NOT NULL,
    launch_date                DATE,
    program_status             VARCHAR  NOT NULL,
    sunset_date                DATE,
    allows_nonlawyer_ownership BOOLEAN  NOT NULL,
    allows_upl_waiver          BOOLEAN  NOT NULL,
    allows_software_provider   BOOLEAN  NOT NULL,
    source_url                 VARCHAR  NOT NULL,
    retrieved_at               TIMESTAMPTZ NOT NULL,
    scraper_version            VARCHAR  NOT NULL
);

CREATE TABLE IF NOT EXISTS source_snapshot (
    snapshot_id    VARCHAR  PRIMARY KEY,
    program_id     VARCHAR  NOT NULL REFERENCES program(program_id),
    source_url     VARCHAR  NOT NULL,
    retrieved_at   TIMESTAMPTZ NOT NULL,
    content_sha256 VARCHAR  NOT NULL CHECK (length(content_sha256) = 64),
    storage_path   VARCHAR  NOT NULL,
    media_type     VARCHAR  NOT NULL,
    scraper_version VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS provider (
    provider_id            VARCHAR     PRIMARY KEY,
    program_id             VARCHAR     NOT NULL,
    provider_type          VARCHAR     NOT NULL,
    legal_name             VARCHAR     NOT NULL,
    normalized_name        VARCHAR     NOT NULL,
    jurisdiction           VARCHAR     NOT NULL CHECK (length(jurisdiction) = 2),
    authorization_date     DATE,
    current_status         VARCHAR     NOT NULL DEFAULT 'unknown',
    practice_areas_raw     VARCHAR[],
    practice_areas_list    VARCHAR[],
    ownership_structure    VARCHAR,
    uses_technology        BOOLEAN,
    uses_ai                BOOLEAN,
    website                VARCHAR,
    first_seen_snapshot_id VARCHAR,
    last_seen_snapshot_id  VARCHAR,
    source_url             VARCHAR     NOT NULL,
    retrieved_at           TIMESTAMPTZ NOT NULL,
    scraper_version        VARCHAR     NOT NULL
    -- FK constraints omitted intentionally: DuckDB 1.5.x enforces FKs on
    -- ON CONFLICT DO UPDATE (delete+reinsert path) even for non-PK columns,
    -- violating provider_status_event→provider when events already exist.
    -- program_id and first/last_seen_snapshot_id are enforced in Python.
);

CREATE TABLE IF NOT EXISTS provider_status_event (
    event_id           VARCHAR     PRIMARY KEY,
    provider_id        VARCHAR     NOT NULL REFERENCES provider(provider_id),
    event_date         DATE        NOT NULL,
    event_type         VARCHAR     NOT NULL,
    new_status         VARCHAR     NOT NULL,
    detail             VARCHAR,
    source_snapshot_id VARCHAR     NOT NULL REFERENCES source_snapshot(snapshot_id),
    source_url         VARCHAR     NOT NULL,
    retrieved_at       TIMESTAMPTZ NOT NULL,
    scraper_version    VARCHAR     NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_alias (
    provider_id     VARCHAR     NOT NULL REFERENCES provider(provider_id),
    alias_name      VARCHAR     NOT NULL,
    alias_source    VARCHAR     NOT NULL,
    source_url      VARCHAR     NOT NULL,
    retrieved_at    TIMESTAMPTZ NOT NULL,
    scraper_version VARCHAR     NOT NULL,
    PRIMARY KEY (provider_id, alias_name)
);

CREATE TABLE IF NOT EXISTS crosswalk_courtlistener (
    provider_id  VARCHAR     NOT NULL REFERENCES provider(provider_id),
    cl_docket_id BIGINT      NOT NULL,
    cl_party_id  BIGINT,
    match_score  DOUBLE      NOT NULL CHECK (match_score >= 0.0 AND match_score <= 1.0),
    match_method VARCHAR     NOT NULL,
    verified     BOOLEAN     NOT NULL DEFAULT FALSE,
    reviewer     VARCHAR,
    reviewed_at  TIMESTAMPTZ,
    PRIMARY KEY (provider_id, cl_docket_id)
);
"""


# ── helpers ───────────────────────────────────────────────────────────────────


def _upsert_sql(table: str, pk: list[str], cols: list[str]) -> str:
    """Build an INSERT … ON CONFLICT DO UPDATE statement."""
    non_pk = [c for c in cols if c not in pk]
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(['?'] * len(cols))}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET "
        + ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
    )


def _opt_json(v: object) -> str | None:
    return json.dumps(v) if v is not None else None


# ── RegistryStore ─────────────────────────────────────────────────────────────


class RegistryStore:
    """Persistent DuckDB store for registry data.

    Usage::

        with RegistryStore(db_path) as store:
            store.init_schema()
            store.upsert_program(prog)
            store.upsert_provider(provider)
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = str(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    # ── connection ────────────────────────────────────────────────────────────

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> RegistryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── schema ────────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """Create all tables (idempotent — uses CREATE TABLE IF NOT EXISTS)."""
        self.conn.execute(_DDL)

    # ── FK guards (Python-layer, since DuckDB defines but doesn't enforce) ────

    def _require_program(self, program_id: str) -> None:
        row = self.conn.execute(
            "SELECT 1 FROM program WHERE program_id = ?", [program_id]
        ).fetchone()
        if row is None:
            raise ValueError(f"program_id {program_id!r} not found — upsert the Program first")

    def _require_provider(self, provider_id: str) -> None:
        row = self.conn.execute(
            "SELECT 1 FROM provider WHERE provider_id = ?", [provider_id]
        ).fetchone()
        if row is None:
            raise ValueError(f"provider_id {provider_id!r} not found — upsert the Provider first")

    def _require_snapshot(self, snapshot_id: str) -> None:
        row = self.conn.execute(
            "SELECT 1 FROM source_snapshot WHERE snapshot_id = ?", [snapshot_id]
        ).fetchone()
        if row is None:
            raise ValueError(
                f"snapshot_id {snapshot_id!r} not found — upsert the SourceSnapshot first"
            )

    # ── upserts ───────────────────────────────────────────────────────────────

    def upsert_program(self, p: Program) -> None:
        _COLS = [
            "program_id",
            "jurisdiction",
            "program_name",
            "program_type",
            "regulator",
            "regulator_url",
            "authorizing_rule",
            "launch_date",
            "program_status",
            "sunset_date",
            "allows_nonlawyer_ownership",
            "allows_upl_waiver",
            "allows_software_provider",
            "source_url",
            "retrieved_at",
            "scraper_version",
        ]
        self.conn.execute(
            _upsert_sql("program", ["program_id"], _COLS),
            [
                p.program_id,
                p.jurisdiction,
                p.program_name,
                str(p.program_type),
                p.regulator,
                p.regulator_url,
                p.authorizing_rule,
                p.launch_date,
                str(p.program_status),
                p.sunset_date,
                p.allows_nonlawyer_ownership,
                p.allows_upl_waiver,
                p.allows_software_provider,
                p.source_url,
                p.retrieved_at,
                p.scraper_version,
            ],
        )

    def upsert_snapshot(self, s: SourceSnapshot) -> None:
        # Snapshots are content-addressed and immutable: same snapshot_id means
        # identical bytes on disk.  Use DO NOTHING to avoid a FK violation when
        # providers already reference this snapshot on a re-run.
        self._require_program(s.program_id)
        _COLS = [
            "snapshot_id",
            "program_id",
            "source_url",
            "retrieved_at",
            "content_sha256",
            "storage_path",
            "media_type",
            "scraper_version",
        ]
        self.conn.execute(
            f"INSERT INTO source_snapshot ({', '.join(_COLS)}) "
            f"VALUES ({', '.join(['?'] * len(_COLS))}) "
            f"ON CONFLICT (snapshot_id) DO NOTHING",
            [
                s.snapshot_id,
                s.program_id,
                s.source_url,
                s.retrieved_at,
                s.content_sha256,
                s.storage_path,
                str(s.media_type),
                s.scraper_version,
            ],
        )

    def _provider_vals(self, p: Provider) -> tuple[list[str], list]:
        """Return (_COLS, vals) for provider INSERT/UPDATE statements."""
        _COLS = [
            "provider_id",
            "program_id",
            "provider_type",
            "legal_name",
            "normalized_name",
            "jurisdiction",
            "authorization_date",
            "current_status",
            "practice_areas_raw",
            "practice_areas_list",
            "ownership_structure",
            "uses_technology",
            "uses_ai",
            "website",
            "first_seen_snapshot_id",
            "last_seen_snapshot_id",
            "source_url",
            "retrieved_at",
            "scraper_version",
        ]
        vals = [
            p.provider_id,
            p.program_id,
            str(p.provider_type),
            p.legal_name,
            p.normalized_name,
            p.jurisdiction,
            p.authorization_date,
            str(p.current_status),
            p.practice_areas_raw,
            p.practice_areas_list,
            _opt_json(p.ownership_structure),
            p.uses_technology,
            p.uses_ai,
            p.website,
            p.first_seen_snapshot_id,
            p.last_seen_snapshot_id,
            p.source_url,
            p.retrieved_at,
            p.scraper_version,
        ]
        return _COLS, vals

    def upsert_provider(self, p: Provider) -> None:
        """Insert or fully update a provider row.

        On conflict, updates all mutable fields from the new scrape.
        Exceptions:
          - first_seen_snapshot_id: preserved via COALESCE (earliest observation wins).
          - practice_areas_raw, practice_areas_list: DuckDB 1.5.x cannot update VARCHAR[]
            columns on rows referenced by incoming FK constraints (delete+reinsert path
            triggers FK violation even without outgoing FKs).  These are set on first
            insert and left unchanged on re-scrape.  They don't change frequently in
            practice; a dedicated update step can refresh them when needed.
        """
        self._require_program(p.program_id)
        if p.first_seen_snapshot_id is not None:
            self._require_snapshot(p.first_seen_snapshot_id)
        if p.last_seen_snapshot_id is not None:
            self._require_snapshot(p.last_seen_snapshot_id)

        _COLS, vals = self._provider_vals(p)
        # Columns excluded from ON CONFLICT DO UPDATE:
        #   provider_id          — PK, never updated
        #   first_seen_*         — handled via COALESCE below
        #   practice_areas_*     — VARCHAR[]: DuckDB 1.5.x bug (see docstring)
        _NO_UPDATE = {
            "provider_id",
            "first_seen_snapshot_id",
            "practice_areas_raw",
            "practice_areas_list",
        }
        _MUTABLE = [c for c in _COLS if c not in _NO_UPDATE]
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _MUTABLE)
        # Preserve earliest observation: only fill in first_seen when NULL.
        set_clause += (
            ", first_seen_snapshot_id = COALESCE(provider.first_seen_snapshot_id,"
            " EXCLUDED.first_seen_snapshot_id)"
        )
        self.conn.execute(
            f"INSERT INTO provider ({', '.join(_COLS)}) "
            f"VALUES ({', '.join(['?'] * len(_COLS))}) "
            f"ON CONFLICT (provider_id) DO UPDATE SET {set_clause}",
            vals,
        )

    def insert_provider_if_new(self, p: Provider) -> None:
        """Insert a provider only if it doesn't already exist; skip existing rows.

        Used by the Wayback backfill so that historical captures insert new
        (historical-only) providers without overwriting last_seen_snapshot_id
        for providers already tracked from our own scraping.
        """
        self._require_program(p.program_id)
        if p.first_seen_snapshot_id is not None:
            self._require_snapshot(p.first_seen_snapshot_id)
        if p.last_seen_snapshot_id is not None:
            self._require_snapshot(p.last_seen_snapshot_id)

        _COLS, vals = self._provider_vals(p)
        self.conn.execute(
            f"INSERT INTO provider ({', '.join(_COLS)}) "
            f"VALUES ({', '.join(['?'] * len(_COLS))}) "
            f"ON CONFLICT (provider_id) DO NOTHING",
            vals,
        )

    def upsert_event(self, e: ProviderStatusEvent) -> None:
        self._require_provider(e.provider_id)
        self._require_snapshot(e.source_snapshot_id)

        _COLS = [
            "event_id",
            "provider_id",
            "event_date",
            "event_type",
            "new_status",
            "detail",
            "source_snapshot_id",
            "source_url",
            "retrieved_at",
            "scraper_version",
        ]
        self.conn.execute(
            _upsert_sql("provider_status_event", ["event_id"], _COLS),
            [
                e.event_id,
                e.provider_id,
                e.event_date,
                str(e.event_type),
                str(e.new_status),
                e.detail,
                e.source_snapshot_id,
                e.source_url,
                e.retrieved_at,
                e.scraper_version,
            ],
        )

    def upsert_alias(self, a: ProviderAlias) -> None:
        self._require_provider(a.provider_id)

        _COLS = [
            "provider_id",
            "alias_name",
            "alias_source",
            "source_url",
            "retrieved_at",
            "scraper_version",
        ]
        self.conn.execute(
            _upsert_sql("provider_alias", ["provider_id", "alias_name"], _COLS),
            [
                a.provider_id,
                a.alias_name,
                str(a.alias_source),
                a.source_url,
                a.retrieved_at,
                a.scraper_version,
            ],
        )

    # ── read helpers (used by orchestrate + diff) ─────────────────────────────

    def list_programs(self) -> list[Program]:
        """Return every row in `program`, reconstructed as validated Program models.

        Used by completeness/frame_reconcile.py to diff our program table
        against external inventories; read-only, no release-schema impact.
        """
        rows = self.conn.execute(
            """SELECT program_id, jurisdiction, program_name, program_type, regulator,
                      regulator_url, authorizing_rule, launch_date, program_status,
                      sunset_date, allows_nonlawyer_ownership, allows_upl_waiver,
                      allows_software_provider, source_url, retrieved_at, scraper_version
               FROM program
               ORDER BY program_id"""
        ).fetchall()
        programs: list[Program] = []
        for row in rows:
            (
                pid,
                jx,
                name,
                ptype,
                regulator,
                regulator_url,
                rule,
                launch,
                status,
                sunset,
                own,
                upl,
                sw,
                url,
                ts,
                ver,
            ) = row
            if isinstance(ts, datetime.datetime) and ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.UTC)
            programs.append(
                Program(
                    program_id=pid,
                    jurisdiction=jx,
                    program_name=name,
                    program_type=ProgramType(ptype),
                    regulator=regulator,
                    regulator_url=regulator_url,
                    authorizing_rule=rule,
                    launch_date=launch,
                    program_status=ProgramStatus(status),
                    sunset_date=sunset,
                    allows_nonlawyer_ownership=own,
                    allows_upl_waiver=upl,
                    allows_software_provider=sw,
                    source_url=url,
                    retrieved_at=ts,
                    scraper_version=ver,
                )
            )
        return programs

    def get_latest_snapshot(self, program_id: str) -> SourceSnapshot | None:
        """Return the most recent SourceSnapshot for *program_id*, or None."""
        row = self.conn.execute(
            """SELECT snapshot_id, program_id, source_url, retrieved_at,
                      content_sha256, storage_path, media_type, scraper_version
               FROM source_snapshot
               WHERE program_id = ?
               ORDER BY retrieved_at DESC
               LIMIT 1""",
            [program_id],
        ).fetchone()
        if row is None:
            return None
        sid, pid, url, ts, sha, path, mtype, ver = row
        if isinstance(ts, datetime.datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.UTC)
        return SourceSnapshot(
            snapshot_id=sid,
            program_id=pid,
            source_url=url,
            retrieved_at=ts,
            content_sha256=sha,
            storage_path=path,
            media_type=MediaType(mtype),
            scraper_version=ver,
        )

    def get_first_snapshot(self, program_id: str) -> SourceSnapshot | None:
        """Return the earliest SourceSnapshot for *program_id*, or None."""
        row = self.conn.execute(
            """SELECT snapshot_id, program_id, source_url, retrieved_at,
                      content_sha256, storage_path, media_type, scraper_version
               FROM source_snapshot
               WHERE program_id = ?
               ORDER BY retrieved_at ASC
               LIMIT 1""",
            [program_id],
        ).fetchone()
        if row is None:
            return None
        sid, pid, url, ts, sha, path, mtype, ver = row
        if isinstance(ts, datetime.datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.UTC)
        return SourceSnapshot(
            snapshot_id=sid,
            program_id=pid,
            source_url=url,
            retrieved_at=ts,
            content_sha256=sha,
            storage_path=path,
            media_type=MediaType(mtype),
            scraper_version=ver,
        )

    def list_providers_by_snapshot(self, snapshot_id: str) -> list[ProviderRef]:
        """Return (provider_id, current_status) for providers last seen in *snapshot_id*.

        Querying before upserting the new batch gives the exact set that appeared
        in the previous snapshot — the correct left-hand side for a diff.
        """
        rows = self.conn.execute(
            "SELECT provider_id, current_status FROM provider WHERE last_seen_snapshot_id = ?",
            [snapshot_id],
        ).fetchall()
        return [ProviderRef(provider_id=r[0], current_status=CurrentStatus(r[1])) for r in rows]

    # ── upserts ───────────────────────────────────────────────────────────────

    def upsert_crosswalk(self, c: CrosswalkCourtlistener) -> None:
        self._require_provider(c.provider_id)

        # Never overwrite a human-verified row programmatically.
        existing = self.conn.execute(
            "SELECT verified FROM crosswalk_courtlistener "
            "WHERE provider_id = ? AND cl_docket_id = ?",
            [c.provider_id, c.cl_docket_id],
        ).fetchone()
        if existing and existing[0]:
            return

        _COLS = [
            "provider_id",
            "cl_docket_id",
            "cl_party_id",
            "match_score",
            "match_method",
            "verified",
            "reviewer",
            "reviewed_at",
        ]
        self.conn.execute(
            _upsert_sql(
                "crosswalk_courtlistener",
                ["provider_id", "cl_docket_id"],
                _COLS,
            ),
            [
                c.provider_id,
                c.cl_docket_id,
                c.cl_party_id,
                c.match_score,
                str(c.match_method),
                c.verified,
                c.reviewer,
                c.reviewed_at,
            ],
        )
