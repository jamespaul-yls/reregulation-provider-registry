"""BaseScraper — enforces the contract: fetch → snapshot → parse → list[Provider].

Contract:
1. fetcher.fetch(url)  — live network call via pluggable Fetcher strategy.
                         Returns FetchResult(raw_bytes, canonical_url, media_type).
                         Must never parse; must rate-limit; must honor robots.txt/ToS.
2. snapshot()          — content-hashes bytes, writes immutable blob, returns SourceSnapshot.
3. parse()             — offline; takes (SourceSnapshot, raw bytes); returns list[Provider].
                         Must never make network calls.
4. run()               — orchestrates 1-3; stamps provenance from the snapshot onto every
                         returned Provider so subclasses never have to copy it manually.

Subclasses must declare:
  program_id: str   — FK to program table
  source_url: str   — canonical URL passed to the fetcher
  default_fetcher_class — override to choose HeadlessFetcher or PdfFetcher (default: StaticFetcher)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from models.schema import Provider, SourceSnapshot
from pipeline.snapshot import ingest as _ingest
from scrapers.fetchers import (  # noqa: F401 (re-export)
    Fetcher,
    FetchResult,
    RetryingFetcher,
    StaticFetcher,
)


class BaseScraper(ABC):
    version: str = "0.1.0"
    program_id: str  # subclass must declare
    source_url: str  # subclass must declare
    default_rate_limit: float = 1.0
    default_timeout: float = 30.0  # per-request timeout passed to the fetcher
    default_retries: int = 0  # 0 = no retry wrapper; >0 wraps in RetryingFetcher
    default_backoff_base: float = 2.0  # exponential-backoff base (seconds)
    default_fetcher_class: type[Fetcher] = StaticFetcher  # type: ignore[assignment]

    def __init__(self, raw_dir: Path, fetcher: Fetcher | None = None) -> None:
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if fetcher is not None:
            self._fetcher: Fetcher = fetcher
        else:
            inner = self.default_fetcher_class(
                rate_limit=self.default_rate_limit,
                timeout=self.default_timeout,
            )
            self._fetcher = (
                RetryingFetcher(inner, self.default_retries, self.default_backoff_base)
                if self.default_retries > 0
                else inner
            )

    # ── abstract interface ────────────────────────────────────────────────────

    def _wayback_parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        """Parse raw bytes sourced from the Wayback Machine.

        Default: delegates to parse(). Override in scrapers that need preprocessing
        (e.g. JS-rendered sources where Wayback captures a single page and the parser
        expects a pre-assembled combined document).
        """
        return self.parse(snapshot, raw)

    @abstractmethod
    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        """Parse *raw* into validated Provider rows.

        Rules:
        - No network calls.
        - Work entirely from *raw* bytes and *snapshot* metadata.
        - Do not manually copy snapshot.source_url / retrieved_at /
          scraper_version — run() stamps those after parse() returns.
        - Raise ValueError with a descriptive message if the source structure
          differs from expectation; do not silently drop rows.
        """
        ...

    # ── orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[SourceSnapshot, list[Provider]]:
        """Full fetch → snapshot → parse pipeline.

        Returns the SourceSnapshot (persist it first) and the stamped providers.
        Callers should upsert snapshot before providers to satisfy FK constraints.
        """
        result: FetchResult = self._fetcher.fetch(self.source_url)
        snap, _ = self.snapshot(result.content, result.url, result.media_type)
        rows = self.parse(snap, result.content)
        return snap, [self._stamp(row, snap) for row in rows]

    @staticmethod
    def _stamp(provider: Provider, snap: SourceSnapshot) -> Provider:
        """Override provenance fields on *provider* from *snap*."""
        data = provider.model_dump()
        data["source_url"] = snap.source_url
        data["retrieved_at"] = snap.retrieved_at
        data["scraper_version"] = snap.scraper_version
        data["last_seen_snapshot_id"] = snap.snapshot_id
        if data["first_seen_snapshot_id"] is None:
            data["first_seen_snapshot_id"] = snap.snapshot_id
        return Provider.model_validate(data)

    # ── shared helpers ────────────────────────────────────────────────────────

    def snapshot(
        self,
        content: bytes,
        source_url: str,
        media_type,
    ) -> tuple[SourceSnapshot, Path]:
        """Delegate to pipeline.snapshot.ingest(); return (SourceSnapshot, blob_path)."""
        snap, path, _ = _ingest(
            content=content,
            source_url=source_url,
            media_type=media_type,
            program_id=self.program_id,
            scraper_version=self.version,
            raw_dir=self.raw_dir,
        )
        return snap, path
