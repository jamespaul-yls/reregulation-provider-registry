"""Fetch the Minnesota LP approved roster, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_mn_lp.py
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
from scrapers.minnesota_lp import MinnesotaLpScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_MN_LP_PROGRAM = Program(
    program_id="prog_mn_lp",
    jurisdiction="MN",
    program_name="Minnesota Legal Paraprofessional Program",
    program_type=ProgramType.paraprofessional_pilot,
    regulator="Minnesota Judicial Branch / Minnesota Supreme Court",
    regulator_url="https://mncourts.gov/courts/supremecourt/committees/LPP.aspx",
    authorizing_rule=(
        "Minn. Stat. § 480.0591; Minn. R. Gen. Prac. 301–319 (Legal Paraprofessional Program,"
        " permanent eff. January 1, 2025)"
    ),
    launch_date=datetime.date(2021, 1, 1),
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url=(
        "https://mncourts.gov/_media/migration/appellate/supreme-court/"
        "Roster-of-Approved-Legal-Paraprofessionals.pdf"
    ),
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = MinnesotaLpScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_MN_LP_PROGRAM)
        print("Program row upserted: prog_mn_lp")

        print(f"Fetching {scraper.source_url!r} ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")
        print(f"  Providers parsed: {len(providers)}")

        store.upsert_snapshot(snap)
        for p in providers:
            store.upsert_provider(p)
        print("Loaded to DuckDB.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    df = pl.read_parquet(_RELEASE / "provider.parquet").filter(pl.col("program_id") == "prog_mn_lp")
    sample = df.select(
        ["provider_id", "legal_name", "authorization_date", "practice_areas_raw"]
    ).head(10)

    print("\n--- 10-row sample (MN LP providers) ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or []) or "(none)"
        pid = row["provider_id"]
        name = row["legal_name"]
        adate = row["authorization_date"] or "N/A"
        print(f"  {pid:20s}  {name:<35s}  auth={adate}  pa={pa}")

    n_total = len(providers)
    n_active = df.filter(pl.col("current_status") == "active").height
    source_total = 42  # PDF "Updated June 25, 2026", IDs 1001–1046 with gaps at 1009, 1028

    coverage_pct = n_total / source_total * 100
    print("\n--- Reconciliation ---")
    print(f"  Source stated total : {source_total}  (PDF updated 2026-06-25, IDs 1001–1046)")
    print(f"  Parsed total        : {n_total}")
    print(f"  DB active           : {n_active}")
    print(f"  Coverage            : {n_total}/{source_total} ({coverage_pct:.1f}%)")


if __name__ == "__main__":
    main()
