"""Writes validation/completeness.md — the human-readable completeness-audit report.

Only rewrites the frame-reconciliation section (between the BEGIN/END
markers); the legislative-scan and within-program sections are left as
placeholders until those modules are built, and any human edits outside the
markers are preserved across re-runs.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from completeness.models import InventoryProgram, ResidualGapRow

_START = "<!-- BEGIN frame_reconcile -->"
_END = "<!-- END frame_reconcile -->"

_HEADER = (
    "# Completeness Audit\n\n"
    "Reproducible adversarial coverage checks for the reregulation provider "
    "registry — turns the manual coverage pass into provenance-backed, "
    "re-runnable code (`make completeness`). See `completeness/`\n\n"
)

_FOOTER = (
    "\n\n## 2. Legislative-scan flags\n\n"
    "_Not yet implemented — see `completeness/legislative_scan.py` (TODO)._\n\n"
    "## 3. Within-program reconciliation\n\n"
    "_Not yet implemented — see `completeness/within_program.py` (TODO)._\n"
)


def _frame_section(
    sources: list[tuple[str, str]],
    gaps: list[ResidualGapRow],
    informational: list[InventoryProgram],
    unmapped: list[str],
) -> str:
    today = datetime.date.today().isoformat()
    lines = [_START, "", "## 1. Frame reconciliation", "", f"_Last run: {today}_", ""]

    lines.append("**Sources checked:**")
    for name, url in sources:
        lines.append(f"- `{name}`: <{url}>")
    lines.append("")

    n_resolved = sum(1 for g in gaps if g.resolved)
    n_unresolved = len(gaps) - n_resolved
    lines.append(
        f"**Ledger state:** {len(gaps)} row(s) in `validation/residual_gaps.csv` "
        f"— {n_resolved} resolved (human-classified), {n_unresolved} still "
        "`unresolved` pending review. This module only ever proposes new "
        "candidates as `unresolved`; classification and `resolved` are set by "
        "a human and are never overwritten by a re-run (see `completeness/ledger.py`)."
    )
    lines.append("")
    if gaps:
        lines.append("| Item | Jurisdiction | Classification | Proposed action / resolution |")
        lines.append("|---|---|---|---|")
        for g in gaps:
            lines.append(
                f"| {g.item} | {g.jurisdiction} | `{g.classification}` | {g.proposed_action} |"
            )
        lines.append("")

    lines.append(
        f"**Informational (non-actionable) IAALS signals:** {len(informational)} "
        "row(s) under status buckets other than Implemented/Being Implemented "
        "(Programs Under Consideration, Not Moving Forward, Litigation, "
        "Resolutions, Data & Evaluation) — recorded for visibility, not "
        "written to the ledger since they are not claims that a program "
        "currently operates."
    )
    lines.append("")
    if informational:
        lines.append("| Model type | Status bucket | Jurisdiction |")
        lines.append("|---|---|---|")
        for r in informational:
            lines.append(f"| {r.model_type_raw} | {r.status_bucket} | {r.jurisdiction_raw} |")
        lines.append("")

    if unmapped:
        names = ", ".join(sorted(set(unmapped)))
        lines.append(f"**Unmapped domestic jurisdiction name(s) ({len(set(unmapped))}):** {names}")
        lines.append("")

    lines.append(_END)
    return "\n".join(lines)


def write_completeness_report(
    path: Path,
    sources: list[tuple[str, str]],
    gaps: list[ResidualGapRow],
    informational: list[InventoryProgram],
    unmapped: list[str],
) -> None:
    section = _frame_section(sources, gaps, informational, unmapped)

    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _START in text and _END in text:
            pre, _, rest = text.partition(_START)
            _, _, post = rest.partition(_END)
            path.write_text(pre + section + post, encoding="utf-8")
            return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HEADER + section + _FOOTER, encoding="utf-8")
