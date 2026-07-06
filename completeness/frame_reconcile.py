"""Frame reconciliation — reconcile our `program` table against authoritative
external inventories of reregulation programs.

Run with: uv run python -m completeness.frame_reconcile  (or `make completeness`)

Scope note (IAALS `regulatory-models` page — see
completeness/inventory_fetch.py::IaalsRegulatoryModelsFetcher for the parse
contract): the page enumerates jurisdictions under several status buckets,
only two of which are treated here as a claim that a program currently
operates — "Implemented Programs" and "Programs Being Implemented" — for
three of its four model types: Regulatory Sandbox, Alternative Business
Structures, and Community-Based Justice Worker Models.

It does NOT enumerate implemented Allied Legal Professional programs on this
page (it defers to a separate "Allied Legal Professionals Knowledge Center"
resource). Because of that, `alp_license`, `paraprofessional_pilot`, and
`document_preparer` program types are out of scope for this source's
mine-not-theirs check: flagging their absence here would be a false signal
from a source that never claimed to enumerate them, not a real gap.

Other status buckets (Programs Under Consideration, Programs Not Moving
Forward, Litigation, Resolutions, Data & Evaluation) are parsed and reported
in validation/completeness.md for visibility, but are NOT written to
validation/residual_gaps.csv.

International rows are parsed but never matched — this registry's
jurisdiction vocabulary is USPS-only (see docs/methodology.md).

Every auto-detected row is written with classification="unresolved": this
module proposes candidates, it never decides in_frame_missing /
out_of_frame / intentionally_excluded. Those calls are yours.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from completeness.db import CompletenessStore
from completeness.inventory_fetch import FETCHERS, InventoryFetcher
from completeness.ledger import merge_ledger, read_ledger
from completeness.models import InventoryProgram, ResidualGapRow
from completeness.report import write_completeness_report
from models.enums import ProgramType
from models.schema import Program
from pipeline.db import RegistryStore

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW_DIR = _ROOT / "data" / "raw" / "completeness"
_LEDGER_PATH = _ROOT / "validation" / "residual_gaps.csv"
_REPORT_PATH = _ROOT / "validation" / "completeness.md"

_IMPLEMENTED_BUCKETS = {"Implemented Programs", "Programs Being Implemented"}

# Program types the IAALS source enumerates thoroughly enough to run a
# mine-not-theirs check against (see module docstring).
_MINE_CHECK_TYPES = {ProgramType.sandbox, ProgramType.abs, ProgramType.community_justice_worker}


def run_fetchers(
    raw_dir: Path, db_path: Path, fetcher_classes: tuple[type[InventoryFetcher], ...] = FETCHERS
) -> list[tuple[str, str, list[InventoryProgram]]]:
    """Run every registered InventoryFetcher; persist its snapshot; return parsed rows."""
    results: list[tuple[str, str, list[InventoryProgram]]] = []
    for fetcher_cls in fetcher_classes:
        fetcher = fetcher_cls(raw_dir=raw_dir)
        snap, rows = fetcher.run()
        with CompletenessStore(db_path) as store:
            store.init_schema()
            store.upsert_snapshot(snap)
        results.append((fetcher.source_name, snap.source_url, rows))
    return results


def reconcile(
    programs: list[Program],
    inventory_rows: list[InventoryProgram],
    source_url: str,
) -> tuple[list[ResidualGapRow], list[InventoryProgram], list[str]]:
    """Diff *inventory_rows* against *programs*.

    Returns (gap_rows, informational_rows, unmapped_jurisdiction_names).
    """
    today = datetime.date.today()
    domestic = [r for r in inventory_rows if r.region == "Domestic"]
    unmapped = [r.jurisdiction_raw for r in domestic if r.jurisdiction is None]

    implemented: list[InventoryProgram] = []
    informational: list[InventoryProgram] = []
    for r in domestic:
        if r.status_bucket in _IMPLEMENTED_BUCKETS and r.jurisdiction and r.model_type:
            implemented.append(r)
        else:
            informational.append(r)

    our_keys = {(p.jurisdiction, p.program_type) for p in programs}
    their_keys = {(r.jurisdiction, r.model_type) for r in implemented}

    gaps: list[ResidualGapRow] = []

    # Theirs-not-ours: candidate gaps.
    for r in implemented:
        key = (r.jurisdiction, r.model_type)
        if key in our_keys:
            continue
        gaps.append(
            ResidualGapRow(
                item=f"{r.model_type_raw} — {r.jurisdiction_raw}",
                jurisdiction=r.jurisdiction,  # type: ignore[arg-type]
                classification="unresolved",
                source_url=source_url,
                proposed_action=(
                    f"IAALS lists {r.model_type_raw!r} as {r.status_bucket!r} in "
                    f"{r.jurisdiction_raw}; no matching program row "
                    f"(jurisdiction={r.jurisdiction}, program_type="
                    f"{r.model_type.value}) found. Confirm in_frame_missing "  # type: ignore[union-attr]
                    "vs. out_of_frame."
                ),
                resolved=False,
                detected_by="frame_reconcile",
                detected_at=today,
            )
        )

    # Ours-not-theirs: scope decisions, restricted to types IAALS enumerates.
    for p in programs:
        if p.program_type not in _MINE_CHECK_TYPES:
            continue
        key = (p.jurisdiction, p.program_type)
        if key in their_keys:
            continue
        gaps.append(
            ResidualGapRow(
                item=f"{p.program_name} ({p.program_id})",
                jurisdiction=p.jurisdiction,
                classification="unresolved",
                source_url=source_url,
                proposed_action=(
                    f"Our program {p.program_id} ({p.jurisdiction}, "
                    f"{p.program_type.value}) has no matching IAALS "
                    "'Implemented Programs' entry. Confirm intentionally_excluded "
                    "vs. source lag."
                ),
                resolved=False,
                detected_by="frame_reconcile",
                detected_at=today,
            )
        )

    return gaps, informational, unmapped


def main() -> None:
    _RAW_DIR.mkdir(parents=True, exist_ok=True)

    with RegistryStore(_DB) as store:
        store.init_schema()
        programs = store.list_programs()

    all_gaps: list[ResidualGapRow] = []
    all_informational: list[InventoryProgram] = []
    all_unmapped: list[str] = []
    sources: list[tuple[str, str]] = []

    for source_name, source_url, rows in run_fetchers(_RAW_DIR, _DB):
        gaps, informational, unmapped = reconcile(programs, rows, source_url)
        all_gaps.extend(gaps)
        all_informational.extend(informational)
        all_unmapped.extend(unmapped)
        sources.append((source_name, source_url))

    ledger_count = merge_ledger(_LEDGER_PATH, all_gaps)
    # Report the ledger's current state (reflects human classification edits),
    # not the freshly re-detected candidates, which are always "unresolved".
    ledger_rows = read_ledger(_LEDGER_PATH)
    write_completeness_report(_REPORT_PATH, sources, ledger_rows, all_informational, all_unmapped)

    print(
        f"frame_reconcile: {len(all_gaps)} candidate gap(s) surfaced this run, "
        f"{ledger_count} row(s) in {_LEDGER_PATH.relative_to(_ROOT)} after merge, "
        f"{len(set(all_unmapped))} unmapped domestic jurisdiction name(s)."
    )
    print(f"Report written to {_REPORT_PATH.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
