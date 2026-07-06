"""Pydantic models for the completeness-audit package.

Separate from models/schema.py (the v1 release schema) on purpose: these are
dev-only audit artifacts and must never be mistaken for release tables or
exported by pipeline/export.py.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from models.enums import MediaType, ProgramType
from models.schema import HttpUrlStr, Sha256Str

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class CompletenessSnapshot(BaseModel):
    """Immutable record of an external-inventory fetch.

    Mirrors models.schema.SourceSnapshot but is NOT FK'd to `program` — these
    snapshots capture cross-cutting external sources (e.g. the IAALS
    knowledge-center page), not one program's own roster. Written to the
    `completeness_snapshot` table (completeness/db.py), never to
    `source_snapshot`.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    snapshot_id: NonEmptyStr
    subject: NonEmptyStr  # e.g. "iaals" — the InventoryFetcher.source_name
    source_url: HttpUrlStr
    retrieved_at: datetime.datetime
    content_sha256: Sha256Str
    storage_path: NonEmptyStr
    media_type: MediaType
    fetcher_version: NonEmptyStr


class InventoryProgram(BaseModel):
    """One (jurisdiction, model type, status) row parsed from an external inventory.

    Provenance (source_url/retrieved_at) lives on the CompletenessSnapshot
    returned alongside a batch of these rows, not duplicated per row.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    source_name: NonEmptyStr  # "iaals"
    model_type_raw: NonEmptyStr  # source's own label, e.g. "Regulatory Sandbox"
    model_type: ProgramType | None  # mapped to our enum; None if unmappable
    status_bucket: NonEmptyStr  # e.g. "Implemented Programs", "Programs Under Consideration"
    region: NonEmptyStr  # "Domestic" | "International"
    jurisdiction_raw: NonEmptyStr  # e.g. "Washington, D.C."
    jurisdiction: str | None  # USPS code; None if unmappable (never silently dropped)


class ResidualGapRow(BaseModel):
    """One row of validation/residual_gaps.csv.

    classification is always written as "unresolved" by the auto-detection
    code — frame_reconcile.py proposes, it never decides in_frame_missing /
    out_of_frame / intentionally_excluded. Those calls are the user's.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    item: NonEmptyStr
    jurisdiction: NonEmptyStr
    classification: NonEmptyStr
    source_url: HttpUrlStr
    proposed_action: NonEmptyStr
    resolved: bool
    detected_by: NonEmptyStr  # "frame_reconcile" | "legislative_scan" | "within_program"
    detected_at: datetime.date
