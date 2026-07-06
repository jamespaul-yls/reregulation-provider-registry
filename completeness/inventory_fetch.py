"""Pluggable external-inventory fetchers for frame_reconcile.

Contract mirrors scrapers/base.py's BaseScraper (fetch -> snapshot -> parse),
reusing the same Fetcher protocol (scrapers/fetchers.py) and the same
content-hashing/atomic-write harness (pipeline/snapshot.py::ingest). It
returns list[InventoryProgram] instead of list[Provider], and snapshots into
completeness_snapshot (completeness/db.py) rather than the program-scoped
source_snapshot table, since these sources aren't tied to one of our
programs.

To add a new external inventory (ABA, NCSC, ...): subclass InventoryFetcher,
implement parse(), and add the class to FETCHERS at the bottom of this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from selectolax.parser import HTMLParser

from completeness.models import CompletenessSnapshot, InventoryProgram
from completeness.us_states import resolve_usps
from models.enums import ProgramType
from pipeline.snapshot import ingest as _ingest
from scrapers.fetchers import Fetcher, StaticFetcher


class InventoryFetcher(ABC):
    """fetch -> snapshot -> parse contract for one external program inventory."""

    version: str = "0.1.0"
    source_name: str  # subclass must declare, e.g. "iaals"
    source_url: str  # subclass must declare
    default_rate_limit: float = 1.0
    default_timeout: float = 30.0
    default_fetcher_class: type[Fetcher] = StaticFetcher  # type: ignore[assignment]

    def __init__(self, raw_dir: Path, fetcher: Fetcher | None = None) -> None:
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._fetcher = fetcher or self.default_fetcher_class(
            rate_limit=self.default_rate_limit, timeout=self.default_timeout
        )

    @abstractmethod
    def parse(self, raw: bytes) -> list[InventoryProgram]:
        """Offline parse of raw bytes into InventoryProgram rows.

        No network calls. Raise ValueError if the source structure differs
        from expectation — never silently drop rows or guess.
        """
        ...

    def run(self) -> tuple[CompletenessSnapshot, list[InventoryProgram]]:
        result = self._fetcher.fetch(self.source_url)
        raw_snap, _, _ = _ingest(
            content=result.content,
            source_url=result.url,
            media_type=result.media_type,
            program_id=self.source_name,  # free-text label here, not an FK
            scraper_version=self.version,
            raw_dir=self.raw_dir,
        )
        snap = CompletenessSnapshot(
            snapshot_id=raw_snap.snapshot_id,
            subject=self.source_name,
            source_url=raw_snap.source_url,
            retrieved_at=raw_snap.retrieved_at,
            content_sha256=raw_snap.content_sha256,
            storage_path=raw_snap.storage_path,
            media_type=raw_snap.media_type,
            fetcher_version=raw_snap.scraper_version,
        )
        rows = self.parse(result.content)
        return snap, rows


class IaalsRegulatoryModelsFetcher(InventoryFetcher):
    """IAALS 'Unlocking Legal Regulation' knowledge-center page.

    Confirmed with the user on 2026-07-01. The "Regulatory Models" URL
    redirects (HTTP 301) to the combined knowledge-center page, which is the
    live location of the Domestic/International breakdown by model type;
    StaticFetcher follows redirects and the snapshot records the resolved
    URL. Structure (verified against a live fetch the same day): an h2
    "Regulatory Models" section containing, in document order, a flat
    sequence of h3/h4 headings with no strict DOM nesting — state must be
    tracked across siblings:
      h3 <model type>          — one of the 4 known model types; resets both
                                  the current status bucket and region
        h4 "Domestic" | "International"  — persists across multiple buckets
        h3 <status bucket>      — e.g. "Implemented Programs", free text
          h4 <jurisdiction name>
        h3 <status bucket>      — next bucket, same region as above
          h4 <jurisdiction name>
        h4 "International"      — region switch, same model type
        h3 <status bucket>
          h4 <jurisdiction name>

    Scope decisions (see completeness/frame_reconcile.py module docstring
    for how these are used downstream):
      - Only "Implemented Programs" / "Programs Being Implemented" buckets
        are treated as claims that a program currently operates.
      - The page does not enumerate implemented Allied Legal Professional
        programs directly (it defers to a separate knowledge center); rows
        under that model type are still parsed and reported, but
        frame_reconcile.py excludes alp_license from its mine-not-theirs
        check for this source.
      - International rows are parsed (not dropped) but excluded from
        matching — this registry's jurisdiction vocabulary is USPS-only.
    """

    version = "0.1.0"
    source_name = "iaals"
    source_url = "https://iaals.du.edu/projects/unlocking-legal-regulation/regulatory-models"

    _MODEL_TYPE_MAP: dict[str, ProgramType] = {
        "regulatory sandbox": ProgramType.sandbox,
        "alternative business structures": ProgramType.abs,
        "allied legal professionals": ProgramType.alp_license,
        "community-based justice worker models": ProgramType.community_justice_worker,
    }

    def parse(self, raw: bytes) -> list[InventoryProgram]:
        tree = HTMLParser(raw)
        body = tree.css_first("body")
        rows: list[InventoryProgram] = []
        in_section = False
        model_raw: str | None = None
        model_type: ProgramType | None = None
        bucket: str | None = None
        region: str | None = None

        for node in body.traverse(include_text=False):
            if node.tag not in ("h2", "h3", "h4"):
                continue
            text = node.text(strip=True)
            if not text:
                continue

            if node.tag == "h2":
                if text == "Regulatory Models":
                    in_section = True
                elif in_section:
                    break  # left the Regulatory Models section
                continue

            if not in_section:
                continue

            if node.tag == "h3":
                key = text.lower()
                if key in self._MODEL_TYPE_MAP:
                    # A new model type resets both the status bucket and the
                    # Domestic/International region, which is otherwise
                    # scoped to a run of several buckets (see class docstring).
                    model_raw, model_type = text, self._MODEL_TYPE_MAP[key]
                    bucket = None
                    region = None
                else:
                    bucket = text
                continue

            # h4
            key = text.lower()
            if key in ("domestic", "international"):
                region = text
                continue

            if model_raw is None or bucket is None:
                raise ValueError(
                    f"IAALS parser: jurisdiction heading {text!r} encountered "
                    "without a model type / status bucket established — source "
                    "structure changed, stopping rather than guessing"
                )
            # Some model types (e.g. Community-Based Justice Worker Models) list
            # only domestic jurisdictions and never add a "Domestic" h4 marker,
            # since there's nothing to disambiguate. Default to Domestic when no
            # region marker has appeared yet; a genuinely non-US name (e.g. a
            # stray "United Kingdom" row under such a section) will simply fail
            # to resolve to a USPS code and surface in the unmapped-names report
            # rather than silently mismatching.
            effective_region = region or "Domestic"

            jurisdiction = resolve_usps(text) if effective_region == "Domestic" else None
            rows.append(
                InventoryProgram(
                    source_name=self.source_name,
                    model_type_raw=model_raw,
                    model_type=model_type,
                    status_bucket=bucket,
                    region=effective_region,
                    jurisdiction_raw=text,
                    jurisdiction=jurisdiction,
                )
            )

        if not rows:
            raise ValueError("IAALS parser: matched zero rows — source structure changed")
        return rows


FETCHERS: tuple[type[InventoryFetcher], ...] = (IaalsRegulatoryModelsFetcher,)
