"""Scraper for the Washington Entity Regulation Pilot Project.

Source: https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants
Fetch strategy: StaticFetcher — static HTML, single table, no JS rendering needed.

Authorizing rule: Washington Supreme Court Order No. 25700-B-721 (Dec. 5, 2024) — a
Framework-driven, time-boxed pilot allowing entities to provide legal and law-related
services under limited exemptions from RCW 2.48.180 / RPC 5.4 / LLLT RPC 5.4, with
individual per-entity court orders and ongoing WSBA/Board monitoring. Structurally this
mirrors Utah's sandbox (time-boxed Framework test, per-entity authorization) rather than
an open-ended ABS certification program.

This ONE program resolves BOTH the IAALS "WA ABS" and "WA sandbox" completeness-audit
listings (docs/sampling_frame.md §6) — the same reason prog_ut_sandbox absorbs Utah's ABS
listing. Do not create a second WA program row for either model type.

Applicant list vs. provider table:
  The WSBA page publishes the FULL applicant list — every entity that has applied,
  whatever its review status — with an explicit disclaimer: "Inclusion on this list does
  NOT mean the entity is authorized to practice law in Washington." Our `current_status`
  enum (models/enums.py::CurrentStatus) has no "pending applicant" state, and extending it
  is a v2 decision, not made here (see validation/washington_entity_pilot.md). So:

    1. parse_applicants() parses the FULL table (date received, entity name, status) —
       this is what gets captured in the raw snapshot, regardless of review status.
    2. parse() loads AS PROVIDERS only the subset whose status indicates the entity has
       actually been authorized to participate (_is_authorized_status(), token-based on
       _AUTHORIZED_TOKENS). As of this scraper's first run, zero applicants meet that
       bar — all four listed applicants are "Under Review". This is a documented zero
       (see validation doc), not a gap. Any status that's neither a recognized
       authorized-token match nor the one known pre-authorization label ("Under Review")
       is logged as a warning rather than silently treated as not-authorized — see
       _is_unrecognized_status().
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

from models.enums import ProviderType
from models.schema import Provider, SourceSnapshot
from resolve.normalize import normalize_name
from scrapers.base import BaseScraper
from scrapers.fetchers import StaticFetcher

logger = logging.getLogger(__name__)

_URL = "https://www.wsba.org/about-wsba/entity-regulation-pilot/applicants"

# Token-based (not exact-string) classification of whether a WSBA applicant status
# indicates the Board/Court has actually authorized the entity to participate. None of
# _AUTHORIZED_TOKENS have been observed on the live page yet — the only status seen so far
# is "Under Review" (_KNOWN_PRE_AUTHORIZATION_STATUSES). This is necessarily an educated
# guess (see docs/methodology.md "Known source limitations by program" -> WA Entity
# Pilot); confirm the exact wording against the live page once WSBA actually authorizes
# an entity. Token-based rather than exact-match so a plausible real label like "Board
# Approved" or "Authorized — Active" still matches without needing to predict the exact
# string. _NEGATIVE_OVERRIDE_TOKENS exists specifically so a status containing a
# substring/token of _AUTHORIZED_TOKENS but meaning the opposite (e.g. "Not Authorized",
# "Inactive") is never misclassified as authorized.
_AUTHORIZED_TOKENS = {"authorized", "approved", "participating", "active"}
_NEGATIVE_OVERRIDE_TOKENS = {
    "not",
    "under",
    "pending",
    "review",
    "denied",
    "rejected",
    "revoked",
    "withdrawn",
    "declined",
    "closed",
    "inactive",
    "suspended",
}
_KNOWN_PRE_AUTHORIZATION_STATUSES = {"under review"}

_DATE_FORMATS = ("%b. %d, %Y", "%B %d, %Y", "%b %d, %Y")


def _status_tokens(status: str) -> set[str]:
    return set(re.findall(r"[a-z]+", status.lower()))


def _is_authorized_status(status: str) -> bool:
    """Best-effort: does *status* indicate the entity is authorized to participate?"""
    tokens = _status_tokens(status)
    if tokens & _NEGATIVE_OVERRIDE_TOKENS:
        return False
    return bool(tokens & _AUTHORIZED_TOKENS)


def _is_unrecognized_status(status: str) -> bool:
    """True if *status* is neither the one known pre-authorization label nor authorized.

    This is the safety net for the fact that _AUTHORIZED_TOKENS is a guess (see comment
    above): a genuinely new status label — whatever it turns out to mean — should produce
    a loud log line, not a silent classification either way. See
    docs/audit/adversarial_review.md S4.
    """
    normalized = status.strip().lower()
    if normalized in _KNOWN_PRE_AUTHORIZATION_STATUSES:
        return False
    return not _is_authorized_status(status)


@dataclass(frozen=True)
class ApplicantRow:
    """One row of the full WSBA applicant list — includes not-yet-authorized entities."""

    date_received: datetime.date | None
    entity_name: str
    status: str


def _parse_date(raw: str) -> datetime.date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _provider_id(legal_name: str) -> str:
    digest = hashlib.sha256(f"prog_wa_entity_pilot\x00{legal_name}".encode()).hexdigest()
    return f"prov_wa_entity_pilot_{digest[:12]}"


def parse_applicants(raw: bytes) -> list[ApplicantRow]:
    """Parse the FULL applicant table (every status) from the raw HTML page.

    Raises ValueError if the table structure doesn't match what the live page has shown
    (three columns: Date Received, Entity Name, Status — a fourth "Application" column
    with a PDF link is dropped, not part of the registry schema).
    """
    tree = HTMLParser(raw.decode("utf-8", errors="replace"))
    table = tree.css_first("table")
    if table is None:
        raise ValueError(
            "WA Entity Regulation Pilot applicants page: no <table> found — "
            "page structure may have changed."
        )

    rows = table.css("tr")
    if not rows:
        raise ValueError("WA Entity Regulation Pilot applicants table has no rows.")

    header_cells = [c.text(strip=True).lower() for c in rows[0].css("td, th")]
    if not any("entity" in h for h in header_cells) or not any("status" in h for h in header_cells):
        raise ValueError(
            f"WA Entity Regulation Pilot: unexpected table header {header_cells!r} — "
            "page structure may have changed."
        )

    applicants: list[ApplicantRow] = []
    for tr in rows[1:]:
        cells = tr.css("td")
        if len(cells) < 3:
            continue
        date_text = cells[0].text(strip=True)
        entity_name = cells[1].text(strip=True).replace("\xa0", " ").strip()
        status = cells[2].text(strip=True)
        if not entity_name:
            continue
        applicants.append(
            ApplicantRow(
                date_received=_parse_date(date_text),
                entity_name=entity_name,
                status=status,
            )
        )
    return applicants


class WashingtonEntityPilotScraper(BaseScraper):
    version = "0.1.0"
    program_id = "prog_wa_entity_pilot"
    source_url = _URL
    default_fetcher_class = StaticFetcher

    def parse(self, snapshot: SourceSnapshot, raw: bytes) -> list[Provider]:
        applicants = parse_applicants(raw)

        providers: list[Provider] = []
        for a in applicants:
            if _is_unrecognized_status(a.status):
                logger.warning(
                    "WA Entity Pilot: unrecognized applicant status %r for %r — not the "
                    "known pre-authorization label %r and not matched by "
                    "_AUTHORIZED_TOKENS %r. This may be a new status WSBA started "
                    "publishing; verify by hand whether it means the entity is now "
                    "authorized (scrapers/washington_entity_pilot.py).",
                    a.status,
                    a.entity_name,
                    next(iter(_KNOWN_PRE_AUTHORIZATION_STATUSES)),
                    sorted(_AUTHORIZED_TOKENS),
                )
            if not _is_authorized_status(a.status):
                continue
            providers.append(
                Provider(
                    provider_id=_provider_id(a.entity_name),
                    program_id=self.program_id,
                    provider_type=ProviderType.entity,
                    legal_name=a.entity_name,
                    normalized_name=normalize_name(a.entity_name),
                    jurisdiction="WA",
                    authorization_date=a.date_received,
                    # provenance — overwritten by _stamp() in run()
                    source_url=snapshot.source_url,
                    retrieved_at=snapshot.retrieved_at,
                    scraper_version=snapshot.scraper_version,
                )
            )
        return providers
