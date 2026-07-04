"""Snapshot the D.C. Rule 5.4(b) evidentiary page, load program row to DuckDB.

No provider rows are created — Rule 5.4(b) is a permissive ethics rule with no
registration requirement and no roster maintained by any DC regulator (see
scrapers/dc_rule54.py and validation/dc_rule54.md for the documented reason).
The rule page is snapshotted so the "why it's zero" claim is itself backed by an
immutable, content-hashed capture rather than only a source_url assertion.

Usage:
    uv run python scripts/run_dc_rule54.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.db import RegistryStore
from pipeline.export import export
from scrapers.dc_rule54 import DcRule54Scraper
from scripts.seed_programs import PROGRAMS

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_DC_RULE54_PROGRAM = next(p for p in PROGRAMS if p.program_id == "prog_dc_rule54")


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = DcRule54Scraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_DC_RULE54_PROGRAM)
        print("Program row upserted: prog_dc_rule54")

        print(f"Fetching {scraper.source_url!r} ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")
        print(f"  Providers parsed: {len(providers)}  (expected 0 — no roster exists)")

        store.upsert_snapshot(snap)
        print("Loaded snapshot to DuckDB. No provider rows to load.")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    print("\n--- Reconciliation ---")
    print("  Source: " + scraper.source_url)
    print("  Source-stated total: 0 (permissive ethics rule; no roster maintained)")
    print(f"  Parsed total       : {len(providers)}")
    print("  Coverage           : N/A (0/0) — structural, not a data gap")


if __name__ == "__main__":
    main()
