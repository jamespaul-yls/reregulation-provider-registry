"""Snapshot the WA Entity Regulation Pilot applicants page, load program + providers.

Prints the full applicant-status breakdown (every applicant, whatever its review status)
and reconciles the loaded-provider count against the source's own applicant total.
Applicants not yet authorized are captured in the raw snapshot but are NOT loaded as
providers — see scrapers/washington_entity_pilot.py module docstring and
validation/washington_entity_pilot.md for why (no "pending applicant" status exists in
the current_status enum; extending it is a v2 decision).

Usage:
    uv run python scripts/run_wa_entity_pilot.py
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.db import RegistryStore
from pipeline.export import export
from scrapers.washington_entity_pilot import WashingtonEntityPilotScraper, parse_applicants
from scripts.seed_programs import PROGRAMS

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

_WA_ENTITY_PILOT_PROGRAM = next(p for p in PROGRAMS if p.program_id == "prog_wa_entity_pilot")


def main() -> None:
    _RAW.mkdir(parents=True, exist_ok=True)
    _DB.parent.mkdir(parents=True, exist_ok=True)

    scraper = WashingtonEntityPilotScraper(raw_dir=_RAW)

    with RegistryStore(_DB) as store:
        store.init_schema()
        store.upsert_program(_WA_ENTITY_PILOT_PROGRAM)
        print("Program row upserted: prog_wa_entity_pilot")

        print(f"Fetching {scraper.source_url!r} ...")
        snap, providers = scraper.run()
        print(f"  Snapshot : {snap.snapshot_id}  sha256={snap.content_sha256[:16]}...")

        store.upsert_snapshot(snap)

        raw_bytes = Path(snap.storage_path).read_bytes()
        applicants = parse_applicants(raw_bytes)

        print(f"\n--- Full applicant list ({len(applicants)} total) ---")
        status_counts = collections.Counter(a.status for a in applicants)
        for status, n in sorted(status_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {status:<20} {n}")

        print(f"\n--- Authorized entities loaded as providers: {len(providers)} ---")
        for p in providers:
            store.upsert_provider(p)
            print(f"  {p.legal_name}  (authorization_date={p.authorization_date})")

        if not providers:
            print("  (none — all applicants are pre-authorization review statuses)")

        print("\n--- Sample of full applicant list ---")
        for a in applicants[:10]:
            print(f"  {a.date_received}  {a.entity_name!r}  status={a.status!r}")

    counts = export(db_path=_DB, release_dir=_RELEASE)
    print(f"\nExported row counts: {counts}")

    print("\n--- Reconciliation ---")
    print(f"  Source: {scraper.source_url}")
    print(f"  Source-stated applicant total: {len(applicants)}")
    print(f"  Authorized (loaded as providers): {len(providers)}")
    print(
        f"  Coverage: {len(providers)}/{len(applicants)} applicants authorized "
        "— expected zero until the Board/Court authorizes a participant"
    )


if __name__ == "__main__":
    main()
