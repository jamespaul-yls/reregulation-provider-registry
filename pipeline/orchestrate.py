"""Orchestrator: seed → scrape → snapshot dedup → diff → export.

Usage:
    uv run python -m pipeline.orchestrate           # full run, writes to DB + disk
    uv run python -m pipeline.orchestrate --dry-run # fetch + diff preview, no writes

Idempotent:
  - A new raw blob is written only when content sha256 changes.
  - A new SourceSnapshot row is written only when sha256 changes.
  - provider_status_event rows grow only when providers actually change.
  - Re-running with identical source content is a documented no-op.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

from pipeline.db import RegistryStore
from pipeline.diff import diff_snapshots
from pipeline.export import export
from scrapers.base import BaseScraper
from scrapers.fetchers import SourceUnreachableError

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"
_RAW = _ROOT / "data" / "raw"
_RELEASE = _ROOT / "data" / "release"

# Canonical order — matches pipeline/scrape.py
_REGISTERED: list[str] = [
    "scrapers.arizona_abs.ArizonaAbsScraper",
    "scrapers.utah_sandbox.UtahSandboxScraper",
    "scrapers.arizona_lp.ArizonaLpScraper",
    "scrapers.utah_lpp.UtahLppScraper",
    "scrapers.colorado_llp.ColoradoLlpScraper",
    "scrapers.minnesota_lp.MinnesotaLpScraper",
    "scrapers.washington_lllt.WashingtonLlltScraper",
    "scrapers.texas_alp.TexasAlpScraper",
    "scrapers.california_lda.CaliforniaLdaScraper",
]


def _load_scraper(dotted: str, raw_dir: Path) -> BaseScraper:
    module_path, cls_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls: type[BaseScraper] = getattr(module, cls_name)
    return cls(raw_dir=raw_dir)


def _seed_programs(store: RegistryStore) -> None:
    """Upsert all program rows (idempotent)."""
    # Import here to avoid making scripts/ a package dependency.
    sys.path.insert(0, str(_ROOT))
    from scripts.seed_programs import PROGRAMS  # type: ignore[import]

    for prog in PROGRAMS:
        store.upsert_program(prog)
    logger.info("seeded %d program rows", len(PROGRAMS))


# ── per-scraper run ───────────────────────────────────────────────────────────


def _run_one(
    dotted: str,
    store: RegistryStore,
    raw_dir: Path,
    *,
    dry_run: bool,
) -> dict:
    scraper = _load_scraper(dotted, raw_dir)
    program_id = scraper.program_id

    try:
        new_snap, new_providers = scraper.run()
    except SourceUnreachableError as exc:
        # Transient network failure after all retries — expected occasionally.
        # Log at WARNING so it doesn't drown out real failures in CI.
        logger.warning("[%s] source unreachable: %s", program_id, exc)
        return {"program_id": program_id, "status": "unreachable", "error": str(exc)}
    except Exception as exc:
        # Scraper bug or parser crash — always investigate.
        logger.error("[%s] scraper error: %s", program_id, exc, exc_info=True)
        return {"program_id": program_id, "status": "error", "error": str(exc)}

    # ── sha256 dedup ──────────────────────────────────────────────────────────
    prev_snap = store.get_latest_snapshot(program_id)
    content_changed = prev_snap is None or prev_snap.content_sha256 != new_snap.content_sha256

    if not content_changed:
        logger.info(
            "[%s] unchanged  sha256=%s…  providers=%d  (skipping diff)",
            program_id,
            new_snap.content_sha256[:16],
            len(new_providers),
        )
        return {
            "program_id": program_id,
            "status": "unchanged",
            "sha256": new_snap.content_sha256[:16],
            "providers": len(new_providers),
            "events": 0,
        }

    # ── diff ──────────────────────────────────────────────────────────────────
    # Capture old providers BEFORE upserting new batch so last_seen_snapshot_id
    # still points to the previous snapshot (correct left-hand side for diff).
    old_providers = store.list_providers_by_snapshot(prev_snap.snapshot_id) if prev_snap else []

    if dry_run:
        # Compute events without touching the store.
        events = diff_snapshots(
            old_snapshot=prev_snap if prev_snap is not None else new_snap,
            old_providers=old_providers,
            new_snapshot=new_snap,
            new_providers=new_providers,
            store=store,
            write=False,
        )
    else:
        # FK order: snapshot → providers → events (diff writes events internally).
        store.upsert_snapshot(new_snap)
        for p in new_providers:
            store.upsert_provider(p)
        events = diff_snapshots(
            old_snapshot=prev_snap if prev_snap is not None else new_snap,
            old_providers=old_providers,
            new_snapshot=new_snap,
            new_providers=new_providers,
            store=store,
            write=True,
        )

    n_auth = sum(1 for e in events if str(e.event_type) == "authorized")
    n_gone = sum(1 for e in events if str(e.event_type) == "disappeared_from_roster")
    n_chng = sum(1 for e in events if str(e.event_type) == "status_change")

    if dry_run:
        action = "would_update (first)" if prev_snap is None else "would_update"
        logger.info(
            "[%s] %s  sha256=%s…  providers=%d  events=%d "
            "(+%d authorized  -%d disappeared  ~%d status_change)",
            program_id,
            action,
            new_snap.content_sha256[:16],
            len(new_providers),
            len(events),
            n_auth,
            n_gone,
            n_chng,
        )
        return {
            "program_id": program_id,
            "status": action,
            "sha256": new_snap.content_sha256[:16],
            "providers": len(new_providers),
            "events": len(events),
            "authorized": n_auth,
            "disappeared": n_gone,
            "status_change": n_chng,
        }

    logger.info(
        "[%s] updated  sha256=%s…  providers=%d  events=%d (+%d  -%d  ~%d)",
        program_id,
        new_snap.content_sha256[:16],
        len(new_providers),
        len(events),
        n_auth,
        n_gone,
        n_chng,
    )
    return {
        "program_id": program_id,
        "status": "updated",
        "sha256": new_snap.content_sha256[:16],
        "providers": len(new_providers),
        "events": len(events),
        "authorized": n_auth,
        "disappeared": n_gone,
        "status_change": n_chng,
    }


# ── public entry point ────────────────────────────────────────────────────────


def run(
    *,
    db_path: Path = _DB,
    raw_dir: Path = _RAW,
    dry_run: bool = False,
) -> list[dict]:
    """Run all registered scrapers and return per-program result dicts."""
    _DB.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    with RegistryStore(db_path) as store:
        store.init_schema()
        _seed_programs(store)

        results = []
        for dotted in _REGISTERED:
            result = _run_one(dotted, store, raw_dir, dry_run=dry_run)
            results.append(result)

        if not dry_run:
            counts = export(db_path=db_path, release_dir=_RELEASE)
            logger.info("exported: %s", counts)

    return results


def _print_summary(results: list[dict], dry_run: bool) -> None:
    label = "DRY-RUN SUMMARY" if dry_run else "RUN SUMMARY"
    print(f"\n{'─' * 70}")
    print(f"  {label}")
    print(f"{'─' * 70}")
    fmt = "  {pid:<22} {status:<20} {providers:>5} providers  {events:>5} events"
    print(fmt.format(pid="program", status="status", providers="N", events="Δevt"))
    print(f"  {'─' * 66}")
    total_events = 0
    for r in results:
        events = r.get("events", 0)
        total_events += events
        status = r["status"]
        # Mark soft and hard failures visually distinct from data outcomes.
        display_status = (
            f"[WARN] {status}"
            if status == "unreachable"
            else f"[ERR]  {status}"
            if status == "error"
            else status
        )
        print(
            fmt.format(
                pid=r["program_id"],
                status=display_status,
                providers=r.get("providers", "—"),
                events=events,
            )
        )
        if status in ("updated", "would_update", "would_update (first)") and events:
            print(
                f"    ↳ +{r.get('authorized', 0)} authorized  "
                f"-{r.get('disappeared', 0)} disappeared  "
                f"~{r.get('status_change', 0)} status_change"
            )
        if status in ("unreachable", "error"):
            print(f"    ↳ {r.get('error', '')[:80]}")
    print(f"{'─' * 70}")
    print(f"  total events {'(preview)' if dry_run else 'written'}: {total_events}")
    if dry_run:
        print("  ── NO WRITES PERFORMED ──")
    print(f"{'─' * 70}\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Reregulation registry orchestrator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Fetch live content and compute diffs but write nothing to the DB "
            "or disk (raw blobs are still written — they are idempotent and "
            "content-addressed)."
        ),
    )
    args = parser.parse_args()

    results = run(dry_run=args.dry_run)
    _print_summary(results, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
