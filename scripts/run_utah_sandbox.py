"""Fetch the Utah Sandbox roster, load to DuckDB, export to release/.

Usage:
    uv run python scripts/run_utah_sandbox.py
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
from scrapers.utah_sandbox import UtahSandboxScraper

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_UT_SANDBOX_PROGRAM = Program(
    program_id="prog_ut_sandbox",
    jurisdiction="UT",
    program_name="Utah Legal Services Innovation Sandbox",
    program_type=ProgramType.sandbox,
    regulator="Utah Office of Legal Services Innovation",
    regulator_url="https://utahinnovationoffice.org",
    authorizing_rule="Utah Supreme Court Standing Order 15 (2020); Phase 2 (2024)",
    launch_date=datetime.date(2020, 8, 14),
    program_status=ProgramStatus.active,
    sunset_date=datetime.date(2027, 8, 14),
    allows_nonlawyer_ownership=True,
    allows_upl_waiver=True,
    allows_software_provider=True,
    source_url="https://utahinnovationoffice.org/authorized-entities/",
    retrieved_at=datetime.datetime.now(datetime.UTC),
    scraper_version="0.1.0",
)

# Source-stated totals as of 2026-06-29 scrape (for reconciliation printout).
# Update after each new scrape if the page count changes.
_SOURCE_ACTIVE = 8  # 7 currently authorized + 1 standing order (i4J)
_SOURCE_EXITED = 61  # 7 provisional + 19 rule-5.4 waivers + 35 previously authorized
_SOURCE_TOTAL = _SOURCE_ACTIVE + _SOURCE_EXITED


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = UtahSandboxScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_UT_SANDBOX_PROGRAM)
        print("Program row upserted: prog_ut_sandbox")

        # ── roster ────────────────────────────────────────────────────────────
        print(f"Fetching {scraper.source_url!r} …")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}…")
        print(f"  Providers parsed: {len(providers)}")

        store.upsert_snapshot(snap)
        for p in providers:
            store.upsert_provider(p)
        print("Loaded to DuckDB.")

        # ── activity-report PDFs ──────────────────────────────────────────────
        print("\nSnapshotting activity-report PDFs …")
        pdf_snaps = scraper.snapshot_activity_reports()
        for ps in pdf_snaps:
            store.upsert_snapshot(ps)
        print(f"  PDFs snapshotted: {len(pdf_snaps)}")

    # ── export ────────────────────────────────────────────────────────────────
    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    # ── 10-row sample ─────────────────────────────────────────────────────────
    df = pl.read_parquet(_RELEASE / "provider.parquet").filter(
        pl.col("program_id") == "prog_ut_sandbox"
    )
    _COLS = [
        "legal_name",
        "current_status",
        "practice_areas_raw",
        "uses_technology",
        "uses_ai",
        "website",
    ]
    sample = df.select(_COLS).head(10)

    print("\n--- 10-row sample (UT Sandbox providers) ---")
    for row in sample.to_dicts():
        pa = ", ".join(row["practice_areas_raw"] or [])[:30]
        print(
            f"  [{row['current_status']:8s}] {row['legal_name'][:40]:<40s}"
            f"  tech={str(row['uses_technology']):5s}  ai={str(row['uses_ai']):5s}"
            f"  pa={pa}"
        )

    # ── reconciliation ────────────────────────────────────────────────────────
    n_active = df.filter(pl.col("current_status") == "active").height
    n_exited = df.filter(pl.col("current_status") == "exited").height
    n_total = len(providers)
    coverage_pct = n_total / _SOURCE_TOTAL * 100

    ok_a = "OK" if n_active == _SOURCE_ACTIVE else "MISMATCH"
    ok_e = "OK" if n_exited == _SOURCE_EXITED else "MISMATCH"

    print("\n--- Reconciliation ---")
    print(
        f"  Source stated total : {_SOURCE_TOTAL}  "
        f"({_SOURCE_ACTIVE} active / {_SOURCE_EXITED} exited)"
    )
    print(f"  Parsed total        : {n_total}")
    print(f"  DB active           : {n_active}  (source: {_SOURCE_ACTIVE})  {ok_a}")
    print(f"  DB exited           : {n_exited}  (source: {_SOURCE_EXITED})  {ok_e}")
    print(f"  Coverage            : {n_total}/{_SOURCE_TOTAL} ({coverage_pct:.1f}%)")
    print(f"  Activity PDFs       : {len(pdf_snaps)} / {7} attempted")


if __name__ == "__main__":
    main()
