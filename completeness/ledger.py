"""Merge newly-detected candidate rows into validation/residual_gaps.csv.

Never overwrites a row a human has already touched — mirrors the
crosswalk_courtlistener rule "verified rows are immutable"
(pipeline/db.py::upsert_crosswalk). Keyed by (item, jurisdiction,
detected_by): if that key already exists in the ledger, the existing row
wins untouched, whatever its current classification/proposed_action/resolved
values are — only a brand-new key gets appended, as "unresolved".
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

    for c in candidates:
        key = (c.item, c.jurisdiction, c.detected_by)
        if key in existing:
            continue  # human may have edited this row — never clobber it
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

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in sorted(existing.values(), key=lambda r: (r["jurisdiction"], r["item"])):
            writer.writerow(row)

    return len(existing)
