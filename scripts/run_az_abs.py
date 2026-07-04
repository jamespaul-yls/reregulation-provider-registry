"""Fetch the AZ ABS roster, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_az_abs.py
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from models.enums import ProgramStatus, ProgramType
from models.schema import Program
from pipeline.db import RegistryStore
from pipeline.export import export
from scrapers.arizona_abs import ArizonaAbsScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_AZ_ABS_PROGRAM = Program(
    program_id="prog_az_abs",
    jurisdiction="AZ",
    program_name="Arizona Alternative Business Structures",
    program_type=ProgramType.abs,
    regulator="Arizona Supreme Court",
    regulator_url="https://www.azcourts.gov/cld/Alternative-Business-Structure",
    authorizing_rule="ACJA §7-209; AZ Sup. Ct. Rule 33.1",
    launch_date=datetime.date(2021, 1, 1),
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=True,
    allows_upl_waiver=False,
    allows_software_provider=True,
    source_url="https://www.azcourts.gov/cld/Alternative-Business-Structure",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    store = RegistryStore(_DB)
    store.init_schema()

    # Seed program row (idempotent upsert).
    store.upsert_program(_AZ_ABS_PROGRAM)
    print("Program row upserted: prog_az_abs")

    # Fetch, snapshot, parse.
    scraper = ArizonaAbsScraper(raw_dir=_RAW)
    from scrapers.arizona_abs import _URL as _AZ_URL

    print(f"Fetching {_AZ_URL!r} …")
    snap, providers = scraper.run()
    print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}…")
    print(f"  Providers: {len(providers)}")

    # Load to DuckDB.
    store.upsert_snapshot(snap)
    for p in providers:
        store.upsert_provider(p)
    store.close()
    print("Loaded to DuckDB.")

    # Export.
    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    # ── 10-row sample ──────────────────────────────────────────────────────────
    df = pl.read_parquet(_RELEASE / "provider.parquet")
    sample = df.select(["legal_name", "current_status", "practice_areas_raw", "website"]).head(10)
    print("\n--- 10-row sample ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or [])
        website = row["website"] or ""
        print(
            f"  [{row['current_status']:8s}] {row['legal_name'][:45]:<45s}"
            f"  pa={pa[:30]:<30s}  web={website[:30]}"
        )

    # ── reconciliation ─────────────────────────────────────────────────────────
    n_active = df.filter(pl.col("current_status") == "active").height
    n_exited = df.filter(pl.col("current_status") == "exited").height
    source_active = 160
    source_inactive = 7
    source_total = source_active + source_inactive

    ok_a = "OK" if n_active == source_active else "MISMATCH"
    ok_e = "OK" if n_exited == source_inactive else "MISMATCH"
    coverage_pct = len(providers) / source_total * 100
    print("\n--- Reconciliation ---")
    print(
        f"  Source stated total : {source_total}  "
        f"({source_active} active / {source_inactive} inactive)"
    )
    print(f"  Parsed total        : {len(providers)}")
    print(f"  DB active           : {n_active}  (source: {source_active})  {ok_a}")
    print(f"  DB exited           : {n_exited}  (source: {source_inactive})  {ok_e}")
    print(f"  Coverage            : {len(providers)}/{source_total} ({coverage_pct:.1f}%)")


if __name__ == "__main__":
    main()
