"""Merge newly-detected candidate rows into validation/residual_gaps.csv.

Never overwrites a row a human has already touched — mirrors the
crosswalk_courtlistener rule "verified rows are immutable"
(pipeline/db.py::upsert_crosswalk). Each row's full identity for storage/export
is (item, jurisdiction, detected_by) — that triple is preserved verbatim and is
what `read_ledger()` returns.

But whether a *candidate* is genuinely new is judged on (item, jurisdiction)
alone, ignoring detected_by. detected_by is provenance (who/what found this
row), not part of what makes two rows "the same real-world gap": if a human
already resolved "Alternative Business Structures — Washington, D.C." via
manual research (detected_by=manual-dc-rule54-removal), a later live run of
the automated detector proposing the identical item/jurisdiction under
detected_by=frame_reconcile is the same gap, not a new one, and must not be
appended as a second `unresolved` row. This is a real bug that recurred twice
in practice before being fixed here — see docs/audit/coverage_confidence.md §1
and docs/sampling_frame.md §6 for the incident history.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path

from completeness.models import ResidualGapRow

FIELDNAMES = [
    "item",
    "jurisdiction",
    "classification",
    "source_url",
    "proposed_action",
    "resolved",
    "detected_by",
    "detected_at",
]


def _read_existing(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {(r["item"], r["jurisdiction"], r["detected_by"]): r for r in rows}


def read_ledger(path: Path) -> list[ResidualGapRow]:
    """Read the current ledger state — reflects any human classification edits."""
    rows = []
    for r in sorted(_read_existing(path).values(), key=lambda r: (r["jurisdiction"], r["item"])):
        rows.append(
            ResidualGapRow(
                item=r["item"],
                jurisdiction=r["jurisdiction"],
                classification=r["classification"],
                source_url=r["source_url"],
                proposed_action=r["proposed_action"],
                resolved=r["resolved"] == "True",
                detected_by=r["detected_by"],
                detected_at=datetime.date.fromisoformat(r["detected_at"]),
            )
        )
    return rows


def merge_ledger(path: Path, candidates: list[ResidualGapRow]) -> int:
    """Merge *candidates* into the CSV ledger at *path*.

    Returns the total row count in the ledger after the merge.
    """
    existing = _read_existing(path)
    # Tracks which (item, jurisdiction) pairs are already covered by *any* row,
    # regardless of detected_by — this is the check that stops a different
    # detection method from re-proposing a gap someone already resolved.
    covered_gaps = {(item, jurisdiction) for item, jurisdiction, _detected_by in existing}

    for c in candidates:
        key = (c.item, c.jurisdiction, c.detected_by)
        if key in existing:
            continue  # human may have edited this row — never clobber it
        if (c.item, c.jurisdiction) in covered_gaps:
            continue  # same real-world gap already has a row under a different
            # detected_by — do not append a duplicate unresolved row for it
        existing[key] = {
            "item": c.item,
            "jurisdiction": c.jurisdiction,
            "classification": c.classification,
            "source_url": c.source_url,
            "proposed_action": c.proposed_action,
            "resolved": str(c.resolved),
            "detected_by": c.detected_by,
            "detected_at": c.detected_at.isoformat(),
        }
        covered_gaps.add((c.item, c.jurisdiction))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in sorted(existing.values(), key=lambda r: (r["jurisdiction"], r["item"])):
            writer.writerow(row)

    return len(existing)
