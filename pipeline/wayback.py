"""Internet Archive CDX/Wayback backfill — historical roster reconstruction.

For each registered source, queries the CDX API to discover historical captures,
fetches each unique capture (deduplicated by content digest), ingests it as a
dated SourceSnapshot (retrieved_at = Wayback capture timestamp), and runs diff.py
across the full ordered series to reconstruct provider entry/exit/status-change
history predating our own scraping.

Prioritized for sunset programs (WA LLLT) where Wayback is the only source of
pre-sunset history.

Known limitations
-----------------
- JS-rendered / headless sources (WA LLLT, UT LPP): Wayback captures the initial
  page load only. Paginated content is partial. WA LLLT overrides _wayback_parse()
  to handle single-page captures; each such capture is flagged as "partial" in the
  report.  UT LPP uses a custom Playwright fetcher and has no _wayback_parse()
  override — it falls back to parse() which will raise on the Cloudflare iframe.
  Skip UT LPP unless you add a custom override.
- PDF sources (CO LLP, MN LP): Wayback captures the PDF directly; parse() works
  unchanged via PdfFetcher media type.
- Rate limit: 1.5 s between IA requests (per robots.txt guidance).
- CDX collapse=digest deduplicates captures with identical content server-side;
  we still check sha256 locally to guard against any CDX quirks.

Usage
-----
    uv run python -m pipeline.wayback                             # all sources
    uv run python -m pipeline.wayback --programs prog_wa_lllt    # one source
    uv run python -m pipeline.wayback --from 2015-01-01 --to 2022-01-01
    uv run python -m pipeline.wayback --max-captures 100 --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from models.enums import MediaType
from models.schema import ProviderRef
from pipeline import snapshot as _snap_mod
from pipeline.db import RegistryStore
from pipeline.diff import diff_snapshots
from scrapers.base import BaseScraper
from scrapers.fetchers import PdfFetcher

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"

_CDX_API = "http://web.archive.org/cdx/search/cdx"
_WAYBACK_CONTENT = "http://web.archive.org/web/{ts}id_/{url}"
_IA_RATE_LIMIT = 1.5  # seconds between IA requests
_FETCH_TIMEOUT = 60.0  # seconds per content fetch
_GAP_THRESHOLD_DAYS = 90
_WAYBACK_SCRAPER_VERSION = "wayback-0.1.0"
_DEFAULT_MAX_CAPTURES = 200

# Canonical scraper dotted-paths in pipeline order (mirrors orchestrate.py).
# UT LPP excluded: custom _LppFetcher uses Playwright iframe trick that Wayback
# cannot replay — add a _wayback_parse() override to UtahLppScraper to enable.
_REGISTERED: list[str] = [
    "scrapers.arizona_abs.ArizonaAbsScraper",
    "scrapers.utah_sandbox.UtahSandboxScraper",
    "scrapers.arizona_lp.ArizonaLpScraper",
    "scrapers.colorado_llp.ColoradoLlpScraper",
    "scrapers.minnesota_lp.MinnesotaLpScraper",
    "scrapers.washington_lllt.WashingtonLlltScraper",
    "scrapers.texas_alp.TexasAlpScraper",
    "scrapers.california_lda.CaliforniaLdaScraper",
]


# ── data structures ───────────────────────────────────────────────────────────


@dataclass
class CdxCapture:
    """One row from the CDX API response."""

    timestamp: str  # "20231015143022"
    original_url: str
    status_code: int
    digest: str  # Wayback content hash (base32 SHA1)
    retrieved_at: datetime.datetime  # UTC, parsed from timestamp


@dataclass
class BackfillReport:
    """Per-program summary returned by backfill_program()."""

    program_id: str
    captures_found: int = 0
    captures_ingested: int = 0
    captures_skipped_dedup: int = 0
    captures_parse_error: int = 0
    partial_captures: int = 0  # headless sources: only page 1 available
    date_range: tuple[datetime.date, datetime.date] | None = None
    gaps: list[tuple[datetime.date, datetime.date, int]] = field(default_factory=list)
    status: str = "ok"
    error: str | None = None


# ── CDX API ───────────────────────────────────────────────────────────────────


def fetch_cdx(
    url: str,
    *,
    from_dt: datetime.date | None = None,
    to_dt: datetime.date | None = None,
    max_captures: int = _DEFAULT_MAX_CAPTURES,
    rate_limit: float = _IA_RATE_LIMIT,
) -> list[CdxCapture]:
    """Query the CDX API and return unique HTTP-200 captures, oldest first.

    Uses collapse=digest to deduplicate identical content server-side.
    """
    params: dict[str, str | int] = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,statuscode,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": max_captures,
    }
    if from_dt:
        params["from"] = from_dt.strftime("%Y%m%d")
    if to_dt:
        params["to"] = to_dt.strftime("%Y%m%d")

    time.sleep(rate_limit)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(_CDX_API, params=params)
        resp.raise_for_status()

    data: list[list[str]] = resp.json()
    if not data:
        return []

    # First row is always the field-name header when output=json.
    if isinstance(data[0], list) and all(isinstance(x, str) for x in data[0]):
        data = data[1:]

    captures: list[CdxCapture] = []
    for row in data:
        if len(row) < 4:
            continue
        ts, orig, status, digest = row[0], row[1], row[2], row[3]
        try:
            status_int = int(status)
        except (ValueError, TypeError):
            continue
        if status_int != 200:
            continue
        retrieved_at = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=datetime.UTC)
        captures.append(
            CdxCapture(
                timestamp=ts,
                original_url=orig,
                status_code=status_int,
                digest=digest,
                retrieved_at=retrieved_at,
            )
        )

    captures.sort(key=lambda c: c.timestamp)
    return captures


def fetch_wayback_content(
    capture: CdxCapture,
    *,
    rate_limit: float = _IA_RATE_LIMIT,
    timeout: float = _FETCH_TIMEOUT,
) -> bytes | None:
    """Fetch raw bytes from Wayback using the id_ modifier.

    The id_ modifier returns the original content without Wayback's JS toolbar
    injection, giving us the same bytes the original server sent.
    Returns None on any HTTP error (logged as WARNING).
    """
    url = _WAYBACK_CONTENT.format(ts=capture.timestamp, url=capture.original_url)
    time.sleep(rate_limit)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        logger.warning("wayback fetch failed %s: %s", capture.timestamp, exc)
        return None


# ── media type inference ──────────────────────────────────────────────────────


def _scraper_media_type(scraper: BaseScraper) -> MediaType:
    """Infer the expected media type from the scraper's default fetcher class."""
    if scraper.default_fetcher_class is PdfFetcher:
        return MediaType.pdf
    return MediaType.html


# ── loader helper ─────────────────────────────────────────────────────────────


def _load_scraper(dotted: str, raw_dir: Path) -> BaseScraper:
    module_path, cls_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[BaseScraper] = getattr(module, cls_name)
    return cls(raw_dir=raw_dir)


# ── per-program backfill ──────────────────────────────────────────────────────


def backfill_program(
    scraper: BaseScraper,
    store: RegistryStore,
    raw_dir: Path,
    *,
    from_dt: datetime.date | None = None,
    to_dt: datetime.date | None = None,
    max_captures: int = _DEFAULT_MAX_CAPTURES,
    gap_threshold_days: int = _GAP_THRESHOLD_DAYS,
    dry_run: bool = False,
) -> BackfillReport:
    """Reconstruct history for one source from Wayback captures.

    Ordered diff chain:
      CDX captures (oldest→newest) → ingest snapshots → diff pairs → events

    Only processes captures that predate the earliest snapshot already in the DB
    (our own scraping). Any gap between the last Wayback capture and our first
    own snapshot is intentional and reported.
    """
    program_id = scraper.program_id
    report = BackfillReport(program_id=program_id)

    # ── CDX lookup ────────────────────────────────────────────────────────────
    try:
        captures = fetch_cdx(
            scraper.source_url,
            from_dt=from_dt,
            to_dt=to_dt,
            max_captures=max_captures,
        )
    except httpx.HTTPError as exc:
        report.status = "cdx_error"
        report.error = str(exc)
        logger.error("[%s] CDX lookup failed: %s", program_id, exc)
        return report

    report.captures_found = len(captures)
    logger.info("[%s] CDX returned %d captures", program_id, len(captures))

    if not captures:
        report.status = "no_captures"
        return report

    # ── filter to pre-existing-scrape window ──────────────────────────────────
    first_own_snap = store.get_first_snapshot(program_id)
    if first_own_snap is not None:
        cutoff = first_own_snap.retrieved_at
        before = [c for c in captures if c.retrieved_at < cutoff]
        logger.info(
            "[%s] retaining %d/%d captures before own first snap (%s)",
            program_id,
            len(before),
            len(captures),
            cutoff.date(),
        )
        captures = before

    if not captures:
        report.status = "all_covered"
        return report

    media_type = _scraper_media_type(scraper)
    # True only when the scraper class overrides _wayback_parse (e.g. WA LLLT),
    # meaning Wayback captures are single-page partial snapshots.
    is_headless = getattr(type(scraper), "_wayback_parse", None) is not BaseScraper._wayback_parse

    prev_snap = None
    prev_providers: list[ProviderRef] = []
    ingested_dates: list[datetime.date] = []

    for capture in captures:
        # ── fetch ─────────────────────────────────────────────────────────────
        raw = fetch_wayback_content(capture)
        if raw is None:
            report.captures_parse_error += 1
            continue

        # ── ingest with Wayback timestamp ─────────────────────────────────────
        snap, _, _ = _snap_mod.ingest(
            content=raw,
            source_url=capture.original_url,
            media_type=media_type,
            program_id=program_id,
            scraper_version=_WAYBACK_SCRAPER_VERSION,
            raw_dir=raw_dir,
            retrieved_at=capture.retrieved_at,
        )

        # ── content dedup (local sha256 guard) ────────────────────────────────
        if prev_snap is not None and prev_snap.content_sha256 == snap.content_sha256:
            report.captures_skipped_dedup += 1
            logger.debug("[%s] dedup %s (sha256 unchanged)", program_id, capture.timestamp)
            continue

        # ── parse ─────────────────────────────────────────────────────────────
        try:
            providers = scraper._wayback_parse(snap, raw)
        except Exception as exc:
            logger.warning("[%s] parse error at %s: %s", program_id, capture.timestamp, exc)
            report.captures_parse_error += 1
            continue

        if not providers:
            logger.warning(
                "[%s] 0 providers from capture %s — skipping", program_id, capture.timestamp
            )
            report.captures_parse_error += 1
            continue

        # Flag partial captures (headless source → page 1 only).
        if is_headless:
            report.partial_captures += 1

        # Stamp provenance (first_seen / last_seen snapshot IDs).
        providers = [BaseScraper._stamp(p, snap) for p in providers]

        # ── diff + write ──────────────────────────────────────────────────────
        old_snap_for_diff = prev_snap if prev_snap is not None else snap

        if not dry_run:
            store.upsert_snapshot(snap)
            for p in providers:
                # INSERT-only: don't overwrite last_seen_snapshot_id on providers
                # already tracked from our own scraping (Wayback captures are older).
                store.insert_provider_if_new(p)
            diff_snapshots(
                old_snapshot=old_snap_for_diff,
                old_providers=prev_providers,
                new_snapshot=snap,
                new_providers=providers,
                store=store,
                write=True,
            )

        ingested_dates.append(capture.retrieved_at.date())
        report.captures_ingested += 1
        prev_snap = snap
        prev_providers = [
            ProviderRef(provider_id=p.provider_id, current_status=p.current_status)
            for p in providers
        ]

        logger.info(
            "[%s] ingested %s  providers=%d%s",
            program_id,
            capture.retrieved_at.date(),
            len(providers),
            "  [partial]" if is_headless else "",
        )

    # ── date range + gap detection ────────────────────────────────────────────
    if ingested_dates:
        report.date_range = (ingested_dates[0], ingested_dates[-1])
        for i in range(1, len(ingested_dates)):
            gap_days = (ingested_dates[i] - ingested_dates[i - 1]).days
            if gap_days > gap_threshold_days:
                report.gaps.append((ingested_dates[i - 1], ingested_dates[i], gap_days))

    # ── report gap to first own snapshot ─────────────────────────────────────
    if first_own_snap is not None and ingested_dates:
        bridging_gap = (first_own_snap.retrieved_at.date() - ingested_dates[-1]).days
        if bridging_gap > gap_threshold_days:
            report.gaps.append(
                (ingested_dates[-1], first_own_snap.retrieved_at.date(), bridging_gap)
            )

    return report


# ── multi-source orchestration ────────────────────────────────────────────────


def run(
    *,
    program_ids: list[str] | None = None,
    db_path: Path = _DB,
    raw_dir: Path = _RAW,
    from_dt: datetime.date | None = None,
    to_dt: datetime.date | None = None,
    max_captures: int = _DEFAULT_MAX_CAPTURES,
    dry_run: bool = False,
) -> list[BackfillReport]:
    """Run Wayback backfill across registered (or selected) programs."""
    raw_dir.mkdir(parents=True, exist_ok=True)

    registered = _REGISTERED
    if program_ids:

        def _program_id_of(dotted: str) -> str:
            mod, cls_name = dotted.rsplit(".", 1)
            return getattr(importlib.import_module(mod), cls_name).program_id

        registered = [d for d in _REGISTERED if _program_id_of(d) in program_ids]
        if not registered:
            logger.warning("No registered scrapers matched program_ids=%s", program_ids)

    reports: list[BackfillReport] = []
    with RegistryStore(db_path) as store:
        store.init_schema()
        for dotted in registered:
            scraper = _load_scraper(dotted, raw_dir)
            logger.info("=== backfilling %s ===", scraper.program_id)
            report = backfill_program(
                scraper,
                store,
                raw_dir,
                from_dt=from_dt,
                to_dt=to_dt,
                max_captures=max_captures,
                dry_run=dry_run,
            )
            reports.append(report)

    return reports


# ── CLI output ────────────────────────────────────────────────────────────────


def _print_reports(reports: list[BackfillReport], *, dry_run: bool) -> None:
    label = "WAYBACK DRY-RUN SUMMARY" if dry_run else "WAYBACK BACKFILL SUMMARY"
    width = 80
    print(f"\n{'═' * width}")
    print(f"  {label}")
    print(f"{'═' * width}")
    for r in reports:
        date_range = f"{r.date_range[0]} → {r.date_range[1]}" if r.date_range else "—"
        status_tag = f"[{r.status.upper()}]" if r.status not in ("ok", "all_covered") else ""
        print(
            f"  {r.program_id:<22}  CDX:{r.captures_found:>4}  "
            f"ingested:{r.captures_ingested:>4}  "
            f"range: {date_range}  {status_tag}"
        )
        if r.captures_skipped_dedup:
            print(f"    dedup-skipped: {r.captures_skipped_dedup}")
        if r.captures_parse_error:
            print(f"    parse-errors:  {r.captures_parse_error}")
        if r.partial_captures:
            print(f"    partial (page-1 only): {r.partial_captures}")
        if r.gaps:
            for gfrom, gto, gdays in r.gaps:
                print(f"    ⚠ gap {gdays}d: {gfrom} → {gto}")
        if r.error:
            print(f"    error: {r.error[:100]}")
    print(f"{'═' * width}")
    if dry_run:
        print("  ── NO WRITES PERFORMED ──")
    print(f"{'═' * width}\n")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Wayback Machine CDX backfill for the reregulation registry"
    )
    parser.add_argument(
        "--programs",
        nargs="+",
        metavar="PROGRAM_ID",
        help="Restrict to specific program IDs (e.g. prog_wa_lllt)",
    )
    parser.add_argument(
        "--from",
        dest="from_dt",
        metavar="YYYY-MM-DD",
        help="Only captures on or after this date",
    )
    parser.add_argument(
        "--to",
        dest="to_dt",
        metavar="YYYY-MM-DD",
        help="Only captures on or before this date",
    )
    parser.add_argument(
        "--max-captures",
        type=int,
        default=_DEFAULT_MAX_CAPTURES,
        help=f"CDX result limit per source (default {_DEFAULT_MAX_CAPTURES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and diff without writing to the DB",
    )
    parser.add_argument("--db", default=str(_DB), help="Path to DuckDB file")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists() and not args.dry_run:
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    from_dt = datetime.date.fromisoformat(args.from_dt) if args.from_dt else None
    to_dt = datetime.date.fromisoformat(args.to_dt) if args.to_dt else None

    reports = run(
        program_ids=args.programs,
        db_path=db_path,
        from_dt=from_dt,
        to_dt=to_dt,
        max_captures=args.max_captures,
        dry_run=args.dry_run,
    )
    _print_reports(reports, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
