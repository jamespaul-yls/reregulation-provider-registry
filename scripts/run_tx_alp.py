"""Snapshot the Texas LLPCA program-status page, load program row to DuckDB.

No provider rows are created — the program is paused and no roster exists as of
June 2026. Run this periodically to detect when the State Bar publishes a roster.

Usage:
    uv run python scripts/run_tx_alp.py
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.enums import ProgramStatus, ProgramType
from models.schema import Program
from pipeline.db import RegistryStore
from pipeline.export import export
from scrapers.texas_alp import TexasAlpScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_TX_ALP_PROGRAM = Program(
    program_id="prog_tx_alp",
    jurisdiction="TX",
    program_name=("Texas Licensed Legal Paraprofessionals and Licensed Court-Access Assistants"),
    program_type=ProgramType.alp_license,
    regulator="State Bar of Texas",
    regulator_url="https://www.texasbar.com/paraprofessionals/",
    authorizing_rule=(
        "Texas Rules Governing Licensed Legal Paraprofessionals and Licensed"
        " Court-Access Assistants, Misc. Docket No. 24-9050 (prelim. approval"
        " 2024-08-06); effective date delayed by Misc. Docket No. 24-9095"
        " (2024-11-04) — effective date TBD pending further Supreme Court order"
    ),
    launch_date=None,  # program never became effective as of June 2026
    program_status=ProgramStatus.paused,
    allows_nonlawyer_ownership=False,
    allows_upl_waiver=True,
    allows_software_provider=False,
    source_url="https://www.texasbar.com/paraprofessionals/",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = TexasAlpScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_TX_ALP_PROGRAM)
        print("Program row upserted: prog_tx_alp")

        print(f"Fetching {scraper.source_url!r} ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")
        print(f"  Providers parsed: {len(providers)}  (expected 0 — program is paused)")

        store.upsert_snapshot(snap)
        print("Loaded snapshot to DuckDB. No provider rows to load.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    print("\n--- Reconciliation ---")
    print("  Source: https://www.texasbar.com/paraprofessionals/")
    print("  Source-stated total: 0 (no roster published)")
    print(f"  Parsed total       : {len(providers)}")
    print("  Coverage           : 0/0 (N/A — program not yet effective)")
    print("  Program status     : paused (Misc. Docket 24-9095, 2024-11-04)")
    print("  Next action        : re-run when Supreme Court sets new effective date")


if __name__ == "__main__":
    main()
