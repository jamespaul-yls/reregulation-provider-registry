"""Snapshot the California LDA statute page, load program row to DuckDB.

No provider rows are created — California LDA registration is county-level
(B&P Code § 6400 et seq.) with no statewide registry. Run this to document
the program's existence and detect changes to the statute or any future
centralized registry.

Usage:
    uv run python scripts/run_ca_lda.py
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
from scrapers.california_lda import CaliforniaLdaScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_CA_LDA_PROGRAM = Program(
    program_id="prog_ca_lda",
    jurisdiction="CA",
    program_name="California Legal Document Assistant Program",
    program_type=ProgramType.document_preparer,
    regulator="California County Clerks (county-level registration)",
    regulator_url=(
        "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
        "?sectionNum=6400.&lawCode=BPC"
    ),
    authorizing_rule=(
        "California Business & Professions Code § 6400 et seq. (enacted 1999);"
        " requires registration with county clerk and $25,000 bond in each county"
        " where services are provided"
    ),
    launch_date=datetime.date(1999, 1, 1),  # B&P Code § 6400 enacted 1999
    program_status=ProgramStatus.active,
    allows_nonlawyer_ownership=False,  # sole proprietor or entity; no attorney ownership required
    allows_upl_waiver=False,  # document prep only; no legal advice
    allows_software_provider=False,
    source_url=(
        "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
        "?sectionNum=6400.&lawCode=BPC"
    ),
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = CaliforniaLdaScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_CA_LDA_PROGRAM)
        print("Program row upserted: prog_ca_lda")

        print(f"Fetching {scraper.source_url!r} ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")
        print(
            f"  Providers parsed: {len(providers)}"
            "  (expected 0 — county-level registry, not scraped in v1)"
        )

        store.upsert_snapshot(snap)
        print("Loaded snapshot to DuckDB. No provider rows to load.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    print("\n--- Reconciliation ---")
    print("  Source: B&P Code § 6400 statute page (leginfo.legislature.ca.gov)")
    print("  Source-stated total: unknown (no statewide count published)")
    print(f"  Parsed total       : {len(providers)}")
    print("  Coverage           : 0/unknown — county-level scraping deferred to v2")
    print("  Next action        : implement per-county scrapes for top counties (v2)")


if __name__ == "__main__":
    main()
