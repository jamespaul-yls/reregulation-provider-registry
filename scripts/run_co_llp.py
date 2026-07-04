"""Fetch the Colorado LLP admitted roster, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_co_llp.py
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
from scrapers.colorado_llp import ColoradoLlpScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_CO_LLP_PROGRAM = Program(
    program_id="prog_co_llp",
    jurisdiction="CO",
    program_name="Colorado Limited License Professional Program",
    program_type=ProgramType.alp_license,
    regulator="Colorado Office of Attorney Regulation Counsel",
    regulator_url="https://www.coloradolegalregulation.com/",
    authorizing_rule="C.R.C.P. Chapter 20 Rule 220 (eff. 2023)",
    launch_date=datetime.date(2023, 1, 1),
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url="https://www.coloradolegalregulation.com/PDF/LLP/Admitted%20LLP%20Roster.pdf",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = ColoradoLlpScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_CO_LLP_PROGRAM)
        print("Program row upserted: prog_co_llp")

        print(f"Fetching {scraper.source_url!r} …")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}…")
        print(f"  Providers parsed: {len(providers)}")

        store.upsert_snapshot(snap)
        for p in providers:
            store.upsert_provider(p)
        print("Loaded to DuckDB.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    df = pl.read_parquet(_RELEASE / "provider.parquet").filter(
        pl.col("program_id") == "prog_co_llp"
    )
    sample = df.select(["provider_id", "legal_name", "current_status", "practice_areas_raw"]).head(
        10
    )

    print("\n--- 10-row sample (CO LLP providers) ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or []) or "(none)"
        pid = row["provider_id"]
        name = row["legal_name"]
        print(f"  [{row['current_status']:8s}] {pid:20s}  {name:<40s}  pa={pa}")

    n_total = len(providers)
    n_active = df.filter(pl.col("current_status") == "active").height
    source_total = 126  # PDF "As of February 6, 2026", reg 600000–600125

    coverage_pct = n_total / source_total * 100
    print("\n--- Reconciliation ---")
    print(f"  Source stated total : {source_total}  (PDF reg 600000–600125, as of 2026-02-06)")
    print(f"  Parsed total        : {n_total}")
    print(f"  DB active           : {n_active}")
    print(f"  Coverage            : {n_total}/{source_total} ({coverage_pct:.1f}%)")


if __name__ == "__main__":
    main()
