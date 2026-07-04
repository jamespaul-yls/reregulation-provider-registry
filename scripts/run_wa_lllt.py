"""Fetch the WSBA LLLT roster, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_wa_lllt.py
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
from scrapers.washington_lllt import WashingtonLlltScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_WA_LLLT_PROGRAM = Program(
    program_id="prog_wa_lllt",
    jurisdiction="WA",
    program_name="Washington Limited License Legal Technician Program",
    program_type=ProgramType.alp_license,
    regulator="Washington State Bar Association",
    regulator_url=(
        "https://www.wsba.org/for-legal-professionals"
        "/join-the-legal-profession-in-wa/limited-license-legal-technicians"
    ),
    authorizing_rule=(
        "APR 28 (eff. 2012); Rules for Limited License Legal Technicians (eff. 2015);"
        " program sunset eff. July 31, 2021 (no new admissions)"
    ),
    launch_date=datetime.date(2015, 1, 1),
    program_status=ProgramStatus.sunset,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url=(
        "https://www.mywsba.org/PersonifyEbusiness/LegalDirectory.aspx"
        "?ShowSearchResults=TRUE&LicenseType=LLLT"
    ),
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = WashingtonLlltScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_WA_LLLT_PROGRAM)
        print("Program row upserted: prog_wa_lllt")

        print(f"Fetching {scraper.source_url!r} (5 pages via Playwright) ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")
        print(f"  Providers parsed: {len(providers)}")

        store.upsert_snapshot(snap)
        for p in providers:
            store.upsert_provider(p)
        print("Loaded to DuckDB.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    df = pl.read_parquet(_RELEASE / "provider.parquet").filter(
        pl.col("program_id") == "prog_wa_lllt"
    )
    sample = df.select(["provider_id", "legal_name", "current_status"]).head(10)

    print("\n--- 10-row sample (WA LLLT providers) ---")
    for row in sample.to_dicts():
        pid = row["provider_id"]
        name = row["legal_name"]
        status = row["current_status"]
        print(f"  {pid:22s}  {name:<35s}  {status}")

    n_total = len(providers)
    source_total = 95  # WSBA lblRowCount as of 2026-06-29

    by_status = df.group_by("current_status").len().sort("current_status")

    print("\n--- Reconciliation ---")
    print(f"  Source stated total : {source_total}  (WSBA lblRowCount, 2026-06-29)")
    print(f"  Parsed total        : {n_total}")
    print(f"  Coverage            : {n_total}/{source_total} ({n_total / source_total * 100:.1f}%)")
    print("  Status breakdown:")
    for row in by_status.to_dicts():
        print(f"    {row['current_status']:12s}: {row['len']}")


if __name__ == "__main__":
    main()
