"""Fetch the AZ LP directory, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_az_lp.py
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
from scrapers.arizona_lp import ArizonaLpScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_AZ_LP_PROGRAM = Program(
    program_id="prog_az_lp",
    jurisdiction="AZ",
    program_name="Arizona Legal Paraprofessional Program",
    program_type=ProgramType.alp_license,
    regulator="Arizona Supreme Court",
    regulator_url="https://www.azcourts.gov/cld/Legal-Paraprofessional",
    authorizing_rule="ACJA §7-210; AZ Sup. Ct. Rule 33.1 (2022)",
    launch_date=datetime.date(2022, 1, 1),
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url="https://www.azcourts.gov/cld/Legal-Paraprofessional/Directory",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = ArizonaLpScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_AZ_LP_PROGRAM)
        print("Program row upserted: prog_az_lp")

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

    # ── 10-row sample ─────────────────────────────────────────────────────────
    df = pl.read_parquet(_RELEASE / "provider.parquet").filter(pl.col("program_id") == "prog_az_lp")
    sample = df.select(["legal_name", "current_status", "practice_areas_raw"]).head(10)

    print("\n--- 10-row sample (AZ LP providers) ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or [])
        print(f"  [{row['current_status']:8s}] {row['legal_name']:<35s}  pa={pa}")

    # ── reconciliation ────────────────────────────────────────────────────────
    n_active = df.filter(pl.col("current_status") == "active").height
    n_exited = df.filter(pl.col("current_status") == "exited").height
    n_total = len(providers)

    print("\n--- Reconciliation ---")
    print(f"  Parsed total  : {n_total}")
    print(f"  DB active     : {n_active}")
    print(f"  DB exited     : {n_exited}")
    print(
        "  Note: no explicit total stated on the directory page. "
        "2024 Annual Report (Dec 31 2024) cited 79 licensed LPs in 83 practice areas; "
        f"current directory shows {n_total} rows ({n_active} active)."
    )


if __name__ == "__main__":
    main()
