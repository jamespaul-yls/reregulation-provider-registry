"""Legislative status resolver for reregulation programs.

Queries Open States v3 API (primary) with LegiScan free tier as fallback to
surface bills or rules that affect a program's operational status.  Proposes
updates to program.program_status and program.sunset_date with full legislative
provenance; writes them only when --apply is passed.

Environment variables (load via `uv run --env-file .env`):
    OPENSTATES_KEY   — Open States v3 API key
    LEGISCAN_KEY     — LegiScan API key

Usage:
    uv run --env-file .env python -m resolve.program_status --dry-run
    uv run --env-file .env python -m resolve.program_status \
        --programs prog_tx_alp prog_wa_lllt --apply

Design notes
------------
Many reregulation programs are authorised by court/administrative rule, not by
the legislature.  Open States covers only legislative bills; for court-rule
programs the config supplies a ``status_override`` and ``override_source_url``
so the resolver still produces a documented, provenance-stamped output without
relying on the API.

For purely legislative programs (TX ALP, UT Sandbox) the resolver:
  1. Searches Open States by state + query terms.
  2. Falls back to LegiScan if Open States returns nothing or errors.
  3. Scores each returned bill for relevance and classifies it as
     positive (authorises) / negative (sunsets/repeals) / neutral.
  4. Builds a StatusSignal — a proposed update plus confidence score.

Confidence < 0.5 → no change proposed; 0.5–0.8 → flagged for review; ≥ 0.8
→ safe to apply automatically with --apply.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from models.enums import ProgramStatus
from models.schema import Program

if TYPE_CHECKING:
    from pipeline.db import RegistryStore

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"
_OPENSTATES_BASE = "https://v3.openstates.org"
_LEGISCAN_BASE = "https://api.legiscan.com"
_RATE_LIMIT_S = 1.0  # seconds between API requests
_REQUEST_TIMEOUT = 30.0  # seconds

_ROOT = Path(__file__).parent.parent
_DB = _ROOT / "data" / "db" / "registry.duckdb"

# ── direction / enactment keywords ────────────────────────────────────────────

_NEGATIVE_TOKENS = frozenset(
    [
        "sunset",
        "repeal",
        "abolish",
        "abolition",
        "eliminate",
        "elimination",
        "terminate",
        "termination",
        "discontinue",
        "prohibit",
        "ban",
        "void",
        "nullif",
        "rescind",
        "revok",
        "end the",
    ]
)
_POSITIVE_TOKENS = frozenset(
    [
        "creat",
        "establish",
        "authoriz",
        "authoris",
        "licens",
        "pilot",
        "allow",
        "enabl",
        "expand",
        "extend",
        "continu",
        "renew",
        "reauthoriz",
        "regulat",
        "recogniz",
        "recognis",
        "certif",
        "implement",
    ]
)
# Action descriptions that confirm enactment
_ENACTED_PHRASES = frozenset(
    [
        "signed by governor",
        "chaptered",
        "enacted",
        "effective immediately",
        "approved by governor",
        "signed into law",
        "filed with secretary of state",
        "governor approved",
        "became law",
    ]
)
# Action classifications from Open States that confirm enactment
_ENACTED_CLASSIFICATIONS = frozenset(
    [
        "executive-signature",
        "became-law",
        "executive-signed",
    ]
)
_FAILED_PHRASES = frozenset(
    [
        "failed",
        "died",
        "vetoed",
        "indefinitely postponed",
        "withdrawn",
        "tabled",
        "adjourned",
        "recommitted",
    ]
)


# ── data structures ───────────────────────────────────────────────────────────


class BillDirection(StrEnum):
    positive = "positive"  # authorises / extends the program
    negative = "negative"  # sunsets / repeals the program
    neutral = "neutral"  # amends without clear direction
    unknown = "unknown"


@dataclass
class ProgramConfig:
    """Per-program search configuration."""

    jurisdiction: str  # Open States state code, lowercase
    queries: list[str]  # search terms (tried in order)
    known_bills: list[str] = field(default_factory=list)  # e.g. ["SB 1218"]
    # If the program was authorised/sunset by a court/admin rule rather than
    # legislation, supply the known status and its source here.  The API is
    # still queried for context but the override takes precedence.
    status_override: ProgramStatus | None = None
    override_source_url: str = ""
    override_sunset_date: datetime.date | None = None
    # For enacted bills that still have implementation pending (rules not yet
    # adopted), use proposed instead of active.
    enacted_means_proposed: bool = False


@dataclass
class BillMatch:
    """A legislative item returned by Open States or LegiScan."""

    bill_id: str
    identifier: str  # e.g. "SB 1218"
    title: str
    session: str
    jurisdiction: str  # state abbreviation, uppercase
    latest_action: str
    latest_action_date: datetime.date | None
    enacted: bool
    failed: bool
    direction: BillDirection
    source_url: str
    relevance: float = 0.0  # set by _score_relevance; 0.0–1.0
    api_source: str = ""  # "openstates" | "legiscan"
    raw: dict = field(default_factory=dict)


@dataclass
class StatusSignal:
    """Proposed update to a program's status field."""

    program_id: str
    current_status: ProgramStatus
    proposed_status: ProgramStatus | None  # None = no change recommended
    proposed_sunset_date: datetime.date | None
    evidence: list[BillMatch]
    confidence: float  # 0.0–1.0
    reason: str
    source_url: str  # primary evidence URL (for provenance)
    retrieved_at: datetime.datetime

    @property
    def is_change(self) -> bool:
        status_changed = (
            self.proposed_status is not None and self.proposed_status != self.current_status
        )
        sunset_changed = self.proposed_sunset_date is not None
        return status_changed or sunset_changed


# ── per-program config registry ───────────────────────────────────────────────

_PROGRAM_CONFIGS: dict[str, ProgramConfig] = {
    # AZ ABS — authorised by AZ Supreme Court Rule 31 amendment (2020).
    # Not a legislative bill; Open States returns no direct match.
    "prog_az_abs": ProgramConfig(
        jurisdiction="az",
        queries=["alternative business structure", "law firm ownership"],
        known_bills=[],
    ),
    # AZ LP — authorised by AZ Supreme Court Rule 31 amendment.
    "prog_az_lp": ProgramConfig(
        jurisdiction="az",
        queries=["legal paraprofessional"],
        known_bills=[],
    ),
    # TX ALP — Texas SB 1218 (88th Leg., 2023) signed June 2023.
    # TX Supreme Court rules implementing it are still pending → proposed.
    "prog_tx_alp": ProgramConfig(
        jurisdiction="tx",
        queries=[
            "licensed legal paraprofessional",
            "court-access assistant",
            "legal paraprofessional",
        ],
        known_bills=["SB 1218"],
        enacted_means_proposed=True,  # rules not yet adopted by TX SC
    ),
    # WA LLLT — sunset by WA Supreme Court amendment to APR 28 (2020),
    # effective 2021-07-31.  Not a legislative bill.
    "prog_wa_lllt": ProgramConfig(
        jurisdiction="wa",
        queries=["limited license legal technician", "LLLT"],
        known_bills=[],
        status_override=ProgramStatus.sunset,
        override_source_url=(
            "https://www.courts.wa.gov/court_rules/"
            "?fa=court_rules.display&group=ga&set=APR&ruleid=APR28"
        ),
        override_sunset_date=datetime.date(2021, 7, 31),
    ),
    # UT Sandbox — Utah SB 97 (2019) "Legal Services Sandbox Initiative".
    "prog_ut_sandbox": ProgramConfig(
        jurisdiction="ut",
        queries=[
            "legal services sandbox",
            "legal services innovation",
            "regulatory sandbox",
        ],
        known_bills=["SB 97"],
    ),
    # UT LPP — Utah SB 1 (2018) created the Licensed Paralegal Practitioner program.
    "prog_ut_lpp": ProgramConfig(
        jurisdiction="ut",
        queries=["licensed paralegal practitioner", "paralegal practitioner"],
        known_bills=["SB 1"],
    ),
    # CO LLP — CO Supreme Court rule; no direct legislative bill.
    "prog_co_llp": ProgramConfig(
        jurisdiction="co",
        queries=["limited licensed professional", "non-attorney"],
        known_bills=[],
    ),
    # MN LP — MN Supreme Court pilot; no direct legislative bill.
    "prog_mn_lp": ProgramConfig(
        jurisdiction="mn",
        queries=["legal paraprofessional", "paraprofessional pilot"],
        known_bills=[],
    ),
    # CA LDA — California Business and Professions Code §6400 et seq.
    "prog_ca_lda": ProgramConfig(
        jurisdiction="ca",
        queries=["legal document assistant"],
        known_bills=[],
    ),
}


# ── key loading ───────────────────────────────────────────────────────────────


def _load_keys() -> tuple[str, str]:
    """Return (openstates_key, legiscan_key) from env, raising if missing."""
    os_key = os.environ.get("OPENSTATES_KEY", "")
    ls_key = os.environ.get("LEGISCAN_KEY", "")
    missing = [n for n, v in [("OPENSTATES_KEY", os_key), ("LEGISCAN_KEY", ls_key)] if not v]
    if missing:
        raise RuntimeError(
            f"Missing env vars: {', '.join(missing)}\n"
            "Run:  uv run --env-file .env python -m resolve.program_status"
        )
    return os_key, ls_key


# ── classification helpers ─────────────────────────────────────────────────────


def _classify_direction(title: str, abstract: str = "") -> BillDirection:
    """Infer whether a bill authorises or sunsets a program from its text."""
    text = (title + " " + abstract).lower()
    neg = sum(1 for tok in _NEGATIVE_TOKENS if tok in text)
    pos = sum(1 for tok in _POSITIVE_TOKENS if tok in text)
    if neg > 0 and pos == 0:
        return BillDirection.negative
    if pos > 0 and neg == 0:
        return BillDirection.positive
    if pos > 0 and neg > 0:
        return BillDirection.neutral
    return BillDirection.unknown


def _check_enacted(latest_action: str, action_classifications: list[str]) -> bool:
    """Return True if action indicates the bill was signed into law."""
    action_lower = latest_action.lower()
    if any(p in action_lower for p in _ENACTED_PHRASES):
        return True
    return any(c in _ENACTED_CLASSIFICATIONS for c in action_classifications)


def _check_failed(latest_action: str) -> bool:
    action_lower = latest_action.lower()
    return any(p in action_lower for p in _FAILED_PHRASES)


def _score_relevance(bill: BillMatch, config: ProgramConfig) -> float:
    """Score how relevant a bill is to this program (0.0–1.0)."""
    score = 0.0
    title_lower = bill.title.lower()

    # Exact known-bill match (highest signal)
    for kb in config.known_bills:
        if kb.lower().replace(" ", "") in bill.identifier.lower().replace(" ", ""):
            score += 0.50
            break

    # Query term found in title
    for q in config.queries:
        if q.lower() in title_lower:
            score += 0.30 / max(len(config.queries), 1)

    # Enacted bills are more definitive
    if bill.enacted:
        score += 0.20

    return min(score, 1.0)


# ── Open States API ───────────────────────────────────────────────────────────


def _parse_openstates_bill(item: dict) -> BillMatch:
    """Convert one Open States API bill record to a BillMatch."""
    # Collect all action classifications for enactment check
    all_classifications: list[str] = []
    for action in item.get("actions", []):
        all_classifications.extend(action.get("classification", []))

    latest_action = item.get("latest_action_description", "")
    latest_date_str = item.get("latest_action_date")
    latest_date: datetime.date | None = None
    if latest_date_str:
        try:
            latest_date = datetime.date.fromisoformat(latest_date_str)
        except ValueError:
            pass

    # Build a human-readable Open States URL
    jurisdiction = item.get("jurisdiction", {}).get("name", "")
    state_code = item.get("jurisdiction", {}).get("id", "")
    # Extract state abbreviation from OCD-ID: ocd-jurisdiction/country:us/state:tx/...
    if "state:" in state_code:
        state_abbr = state_code.split("state:")[1].split("/")[0].upper()
    else:
        state_abbr = jurisdiction[:2].upper()

    session = item.get("session", "")
    identifier = item.get("identifier", "")
    os_url = (
        f"https://openstates.org/{state_abbr.lower()}/bills/"
        f"{session.replace(' ', '-')}/{identifier.replace(' ', '')}/"
    )

    abstract = ""
    abstracts = item.get("abstracts", [])
    if abstracts:
        abstract = abstracts[0].get("abstract", "")

    enacted = _check_enacted(latest_action, all_classifications)
    failed = _check_failed(latest_action)
    direction = _classify_direction(item.get("title", ""), abstract)

    return BillMatch(
        bill_id=item.get("id", ""),
        identifier=identifier,
        title=item.get("title", ""),
        session=session,
        jurisdiction=state_abbr,
        latest_action=latest_action,
        latest_action_date=latest_date,
        enacted=enacted,
        failed=failed,
        direction=direction,
        source_url=os_url,
        api_source="openstates",
        raw=item,
    )


def search_openstates(
    jurisdiction: str,
    queries: list[str],
    api_key: str,
    *,
    per_page: int = 10,
) -> list[BillMatch]:
    """Search Open States v3 for bills matching any of the given queries.

    Returns deduplicated BillMatch list, ordered by latest_action_date desc.
    """
    matches: list[BillMatch] = []
    seen_ids: set[str] = set()

    for query in queries:
        time.sleep(_RATE_LIMIT_S)
        try:
            resp = httpx.get(
                f"{_OPENSTATES_BASE}/bills",
                headers={"X-API-KEY": api_key},
                params=[
                    ("jurisdiction", jurisdiction),
                    ("q", query),
                    ("sort", "updated_desc"),
                    ("per_page", str(per_page)),
                    ("include", "actions"),
                    ("include", "abstracts"),
                ],
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Open States query %r failed: %s", query, exc)
            continue

        data = resp.json()
        for item in data.get("results", []):
            bid = item.get("id", "")
            if bid in seen_ids:
                continue
            seen_ids.add(bid)
            matches.append(_parse_openstates_bill(item))

    matches.sort(key=lambda b: b.latest_action_date or datetime.date.min, reverse=True)
    return matches


# ── LegiScan API ──────────────────────────────────────────────────────────────


def _parse_legiscan_bill(item: dict) -> BillMatch:
    """Convert one LegiScan search result entry to a BillMatch."""
    last_action = item.get("last_action", "")
    last_action_date_str = item.get("last_action_date", "")
    last_date: datetime.date | None = None
    if last_action_date_str:
        try:
            last_date = datetime.date.fromisoformat(last_action_date_str)
        except ValueError:
            pass

    state = item.get("state", "")
    bill_number = item.get("bill_number", "") or item.get("number", "")
    enacted = _check_enacted(last_action, [])
    failed = _check_failed(last_action)
    direction = _classify_direction(item.get("title", ""))

    return BillMatch(
        bill_id=str(item.get("bill_id", "")),
        identifier=bill_number,
        title=item.get("title", ""),
        session="",
        jurisdiction=state.upper(),
        latest_action=last_action,
        latest_action_date=last_date,
        enacted=enacted,
        failed=failed,
        direction=direction,
        source_url=item.get("url", ""),
        api_source="legiscan",
        raw=item,
    )


def search_legiscan(
    state: str,
    queries: list[str],
    api_key: str,
    *,
    year: int = 2,
) -> list[BillMatch]:
    """Search LegiScan for bills matching any of the given queries.

    state: 2-letter abbreviation, uppercase (e.g. "TX").
    year:  0=all time, 1=current session, 2=recent 2 sessions.
    """
    matches: list[BillMatch] = []
    seen_ids: set[str] = set()

    for query in queries:
        time.sleep(_RATE_LIMIT_S)
        try:
            resp = httpx.get(
                _LEGISCAN_BASE,
                params={
                    "key": api_key,
                    "op": "search",
                    "q": query,
                    "state": state.upper(),
                    "year": year,
                },
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("LegiScan query %r failed: %s", query, exc)
            continue

        data = resp.json()
        if data.get("status") != "OK":
            logger.warning("LegiScan non-OK response for %r: %s", query, data.get("status"))
            continue

        search_result = data.get("searchresult", {})
        for key, item in search_result.items():
            if key == "summary" or not isinstance(item, dict):
                continue
            bid = str(item.get("bill_id", ""))
            if not bid or bid in seen_ids:
                continue
            seen_ids.add(bid)
            matches.append(_parse_legiscan_bill(item))

    matches.sort(key=lambda b: b.latest_action_date or datetime.date.min, reverse=True)
    return matches


# ── resolver ──────────────────────────────────────────────────────────────────


def resolve_one(
    program: Program,
    openstates_key: str,
    legiscan_key: str,
    *,
    config: ProgramConfig | None = None,
) -> StatusSignal:
    """Resolve the legislative status for a single program.

    Returns a StatusSignal describing whether the program's status should
    change and why.  Does NOT write to the database.
    """
    cfg = config or _PROGRAM_CONFIGS.get(program.program_id)
    if cfg is None:
        return StatusSignal(
            program_id=program.program_id,
            current_status=program.program_status,
            proposed_status=None,
            proposed_sunset_date=None,
            evidence=[],
            confidence=0.0,
            reason="No search configuration for this program",
            source_url="",
            retrieved_at=datetime.datetime.now(datetime.UTC),
        )

    now = datetime.datetime.now(datetime.UTC)

    # ── Court/admin-rule override: status is known regardless of API ──────────
    if cfg.status_override is not None:
        # Still search for legislative context (useful for the evidence field)
        bills = _search_with_fallback(cfg, openstates_key, legiscan_key)
        return StatusSignal(
            program_id=program.program_id,
            current_status=program.program_status,
            proposed_status=cfg.status_override,
            proposed_sunset_date=cfg.override_sunset_date,
            evidence=bills[:5],
            confidence=1.0,
            reason=(
                f"Status determined by administrative/court order; "
                f"not a legislative bill.  Source: {cfg.override_source_url}"
            ),
            source_url=cfg.override_source_url,
            retrieved_at=now,
        )

    # ── Legislative lookup ────────────────────────────────────────────────────
    bills = _search_with_fallback(cfg, openstates_key, legiscan_key)

    if not bills:
        return StatusSignal(
            program_id=program.program_id,
            current_status=program.program_status,
            proposed_status=None,
            proposed_sunset_date=None,
            evidence=[],
            confidence=0.0,
            reason="No relevant bills found in Open States or LegiScan",
            source_url="",
            retrieved_at=now,
        )

    # Score and sort by relevance
    for b in bills:
        b.relevance = _score_relevance(b, cfg)
    bills.sort(key=lambda b: b.relevance, reverse=True)

    top = bills[0]
    conf = top.relevance

    if conf < 0.3:
        return StatusSignal(
            program_id=program.program_id,
            current_status=program.program_status,
            proposed_status=None,
            proposed_sunset_date=None,
            evidence=bills[:5],
            confidence=conf,
            reason=f"Low relevance ({conf:.2f}); best match: {top.identifier} — {top.title[:80]}",
            source_url=top.source_url,
            retrieved_at=now,
        )

    # Map bill signal → proposed ProgramStatus
    if top.direction == BillDirection.negative and top.enacted:
        proposed = ProgramStatus.sunset
        reason = f"Sunsetting/repealing bill enacted: {top.identifier} ({top.session})"
    elif top.direction == BillDirection.positive and top.enacted:
        proposed = ProgramStatus.proposed if cfg.enacted_means_proposed else ProgramStatus.active
        label = (
            "proposed (implementing rules still pending)"
            if cfg.enacted_means_proposed
            else "active"
        )
        reason = f"Authorising bill enacted ({label}): {top.identifier} ({top.session})"
    elif top.direction == BillDirection.positive and not top.failed:
        proposed = ProgramStatus.proposed
        reason = f"Authorising bill introduced/pending: {top.identifier} ({top.session})"
    elif top.direction == BillDirection.negative and not top.enacted:
        # Sunsetting bill not yet enacted — flag but don't change status
        proposed = None
        conf = conf * 0.4
        reason = f"Sunsetting bill pending (not enacted): {top.identifier} ({top.session})"
    else:
        proposed = None
        reason = (
            f"Direction unclear for {top.identifier}: "
            f"direction={top.direction}, enacted={top.enacted}"
        )

    return StatusSignal(
        program_id=program.program_id,
        current_status=program.program_status,
        proposed_status=proposed,
        proposed_sunset_date=None,
        evidence=bills[:5],
        confidence=conf,
        reason=reason,
        source_url=top.source_url,
        retrieved_at=now,
    )


def _search_with_fallback(
    cfg: ProgramConfig,
    openstates_key: str,
    legiscan_key: str,
) -> list[BillMatch]:
    """Try Open States; fall back to LegiScan if no results."""
    bills = search_openstates(cfg.jurisdiction, cfg.queries, openstates_key)
    if bills:
        logger.debug("Open States returned %d bills for %s", len(bills), cfg.jurisdiction)
        return bills
    logger.info("Open States returned 0 results for %s; trying LegiScan", cfg.jurisdiction.upper())
    return search_legiscan(cfg.jurisdiction.upper(), cfg.queries, legiscan_key)


# ── DB write ──────────────────────────────────────────────────────────────────


def apply_update(
    signal: StatusSignal,
    program: Program,
    store: RegistryStore,
) -> Program | None:
    """Write a StatusSignal's proposed changes to the program table.

    Returns the updated Program if a change was written, else None.
    """
    if not signal.is_change:
        return None

    updated = Program(
        **{
            k: v
            for k, v in program.model_dump().items()
            if k
            not in {
                "program_status",
                "sunset_date",
                "source_url",
                "retrieved_at",
                "scraper_version",
            }
        },
        program_status=signal.proposed_status or program.program_status,
        sunset_date=signal.proposed_sunset_date or program.sunset_date,
        source_url=signal.source_url or program.source_url,
        retrieved_at=signal.retrieved_at,
        scraper_version=_VERSION,
    )
    store.upsert_program(updated)
    logger.info(
        "[%s] updated: %s → %s  (confidence=%.2f)",
        program.program_id,
        program.program_status,
        updated.program_status,
        signal.confidence,
    )
    return updated


# ── orchestration ─────────────────────────────────────────────────────────────


def run(
    *,
    program_ids: list[str] | None = None,
    db_path: Path = _DB,
    dry_run: bool = True,
    openstates_key: str,
    legiscan_key: str,
) -> list[StatusSignal]:
    """Resolve legislative status for all (or selected) programs.

    Loads programs from the DB, resolves each, and optionally writes changes.
    Returns the list of StatusSignals produced.
    """
    from pipeline.db import RegistryStore

    signals: list[StatusSignal] = []

    with RegistryStore(db_path) as store:
        rows = store.conn.execute(
            "SELECT program_id, jurisdiction, program_name, program_type, "
            "regulator, regulator_url, authorizing_rule, launch_date, "
            "program_status, sunset_date, allows_nonlawyer_ownership, "
            "allows_upl_waiver, allows_software_provider, "
            "source_url, retrieved_at, scraper_version "
            "FROM program ORDER BY program_id"
        ).fetchall()
        _COLS = [
            "program_id",
            "jurisdiction",
            "program_name",
            "program_type",
            "regulator",
            "regulator_url",
            "authorizing_rule",
            "launch_date",
            "program_status",
            "sunset_date",
            "allows_nonlawyer_ownership",
            "allows_upl_waiver",
            "allows_software_provider",
            "source_url",
            "retrieved_at",
            "scraper_version",
        ]

        programs: list[Program] = []
        for row in rows:
            d = dict(zip(_COLS, row, strict=True))
            ts = d["retrieved_at"]
            if isinstance(ts, datetime.datetime) and ts.tzinfo is None:
                d["retrieved_at"] = ts.replace(tzinfo=datetime.UTC)
            programs.append(Program(**d))

        # Filter
        if program_ids:
            programs = [p for p in programs if p.program_id in program_ids]
            if not programs:
                logger.warning("No programs matched %s", program_ids)

        for program in programs:
            cfg = _PROGRAM_CONFIGS.get(program.program_id)
            if cfg is None:
                logger.warning("[%s] no config — skipping", program.program_id)
                continue

            logger.info("=== resolving %s (%s) ===", program.program_id, program.jurisdiction)
            signal = resolve_one(program, openstates_key, legiscan_key, config=cfg)
            signals.append(signal)

            if not dry_run and signal.is_change and signal.confidence >= 0.5:
                apply_update(signal, program, store)

    return signals


# ── report ────────────────────────────────────────────────────────────────────


def _print_signals(signals: list[StatusSignal], *, dry_run: bool) -> None:
    label = "DRY-RUN — " if dry_run else ""
    width = 90
    print(f"\n{'═' * width}")
    print(f"  {label}PROGRAM STATUS RESOLVER  ({_VERSION})")
    print(f"{'═' * width}")

    for s in signals:
        change_str = (
            f"{s.current_status} → {s.proposed_status}"
            if s.proposed_status and s.proposed_status != s.current_status
            else f"{s.current_status} (no change)"
        )
        sunset_str = f"  sunset={s.proposed_sunset_date}" if s.proposed_sunset_date else ""
        applied = "" if dry_run else (" [APPLIED]" if s.is_change and s.confidence >= 0.5 else "")
        print(
            f"  {s.program_id:<22}  {change_str:<30}  conf={s.confidence:.2f}{sunset_str}{applied}"
        )
        print(f"    {s.reason[:80]}")
        for b in s.evidence[:2]:
            enacted_tag = " [enacted]" if b.enacted else (" [failed]" if b.failed else "")
            print(f"    └ {b.identifier:<12} {b.title[:55]:<55}  {b.direction:<10}{enacted_tag}")
    print(f"{'═' * width}")
    if dry_run:
        print("  ── NO WRITES PERFORMED ──")
    print(f"{'═' * width}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Resolve legislative status for reregulation programs"
    )
    parser.add_argument(
        "--programs",
        nargs="+",
        metavar="PROGRAM_ID",
        help="Restrict to specific program IDs",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write high-confidence (≥0.5) changes to the DB (default: dry-run)",
    )
    parser.add_argument("--db", default=str(_DB), help="Path to registry.duckdb")
    args = parser.parse_args()

    try:
        os_key, ls_key = _load_keys()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    signals = run(
        program_ids=args.programs,
        db_path=db_path,
        dry_run=not args.apply,
        openstates_key=os_key,
        legiscan_key=ls_key,
    )
    _print_signals(signals, dry_run=not args.apply)


if __name__ == "__main__":
    main()
