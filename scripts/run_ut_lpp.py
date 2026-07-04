"""Fetch the Utah LPP directory, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_ut_lpp.py
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
from scrapers.utah_lpp import UtahLppScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_UT_LPP_PROGRAM = Program(
    program_id="prog_ut_lpp",
    jurisdiction="UT",
    program_name="Utah Licensed Paralegal Practitioner Program",
    program_type=ProgramType.alp_license,
    regulator="Utah State Bar",
    regulator_url="https://www.utahbar.org/licensed-paralegal-practitioner/",
    authorizing_rule="Utah Rules Governing Licensed Paralegal Practitioners, Rule 15-703 (2018)",
    launch_date=datetime.date(2019, 1, 1),
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url="https://www.licensedlawyer.org/Find-a-Lawyer/Licensed-Paralegal-Practitioners",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = UtahLppScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_UT_LPP_PROGRAM)
        print("Program row upserted: prog_ut_lpp")

        print(f"Fetching {scraper.source_url!r} …")
        print("  (Playwright + route-interception; expect ~15 s)")
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
        pl.col("program_id") == "prog_ut_lpp"
    )
    sample = df.select(["legal_name", "current_status", "practice_areas_raw"]).head(10)

    print("\n--- 10-row sample (UT LPP providers) ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or []) or "(none)"
        print(f"  [{row['current_status']:8s}] {row['legal_name']:<40s}  pa={pa}")

    n_total = len(providers)
    n_active = df.filter(pl.col("current_status") == "active").height

    print("\n--- Reconciliation ---")
    print(f"  Parsed total   : {n_total}")
    print(f"  DB active      : {n_active}")
    print(
        "  Source total   : 53 (licensedlawyer.org as of 2026-06-29; "
        "opt-in directory — see validation/utah_lpp.md)"
    )
    print("  Test accounts filtered: 1 (Testacct, LPP)")


if __name__ == "__main__":
    main()
