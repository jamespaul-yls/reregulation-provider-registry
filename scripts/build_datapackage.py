"""Generate data/release/datapackage.json with full Frictionless schema.

Run after export_release.py.  Reads actual row counts from the CSV files.

Usage:
    uv run python scripts/build_datapackage.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_RELEASE = _ROOT / "data" / "release"

# ── enum vocabularies (mirrors models/enums.py exactly) ──────────────────────

_PROGRAM_TYPE = [
    "abs",
    "sandbox",
    "alp_license",
    "paraprofessional_pilot",
    "community_justice_worker",
    "document_preparer",
]
_PROGRAM_STATUS = ["active", "sunset", "proposed", "paused"]
_PROVIDER_TYPE = ["entity", "individual"]
_CURRENT_STATUS = ["active", "exited", "suspended", "revoked", "unknown"]
_EVENT_TYPE = [
    "authorized",
    "status_change",
    "disappeared_from_roster",
    "disciplined",
    "reinstated",
]
_ALIAS_SOURCE = ["roster", "website", "litigation", "manual"]
_MEDIA_TYPE = ["html", "pdf", "json", "xlsx"]
_MATCH_METHOD = ["exact", "fuzzy", "manual"]

# ── helpers ───────────────────────────────────────────────────────────────────


def _rowcount(release_dir: Path, name: str) -> int:
    p = release_dir / f"{name}.csv"
    with p.open(newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # subtract header


def _distinct_column(release_dir: Path, name: str, column: str) -> set[str]:
    p = release_dir / f"{name}.csv"
    with p.open(newline="", encoding="utf-8") as f:
        return {row[column] for row in csv.DictReader(f)}


def _field(
    name: str,
    ftype: str,
    description: str,
    required: bool = False,
    enum: list | None = None,
    pattern: str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    fmt: str | None = None,
) -> dict:
    f: dict = {"name": name, "type": ftype, "description": description}
    if fmt:
        f["format"] = fmt
    constraints: dict = {}
    if required:
        constraints["required"] = True
    if enum:
        constraints["enum"] = enum
    if pattern:
        constraints["pattern"] = pattern
    if minimum is not None:
        constraints["minimum"] = minimum
    if maximum is not None:
        constraints["maximum"] = maximum
    if constraints:
        f["constraints"] = constraints
    return f


# ── table schemas ─────────────────────────────────────────────────────────────


def _schema_program() -> dict:
    return {
        "fields": [
            _field(
                "program_id",
                "string",
                "Stable opaque primary key, e.g. prog_az_abs.",
                required=True,
            ),
            _field(
                "jurisdiction",
                "string",
                "USPS two-letter state/territory code, uppercase.",
                required=True,
                pattern=r"^[A-Z]{2}$",
            ),
            _field("program_name", "string", "Full human-readable program name.", required=True),
            _field(
                "program_type",
                "string",
                "Kind of reregulation program.",
                required=True,
                enum=_PROGRAM_TYPE,
            ),
            _field("regulator", "string", "Name of the regulating body.", required=True),
            _field("regulator_url", "string", "Landing page URL of the regulator.", required=True),
            _field(
                "authorizing_rule",
                "string",
                "Canonical citation, e.g. ACJA §7-210 or APR 28.",
                required=True,
            ),
            _field(
                "launch_date",
                "date",
                "Date the program first issued authorizations. NULL if unknown.",
                fmt="any",
            ),
            _field(
                "program_status",
                "string",
                "Operational state of the program itself (not individual providers).",
                required=True,
                enum=_PROGRAM_STATUS,
            ),
            _field(
                "sunset_date",
                "date",
                "Effective end date for sunset programs; anticipated launch for proposed programs.",
                fmt="any",
            ),
            _field(
                "allows_nonlawyer_ownership",
                "boolean",
                "True if non-lawyers may hold equity in a licensed entity (Rule 5.4 relief).",
                required=True,
            ),
            _field(
                "allows_upl_waiver",
                "boolean",
                "True if providers may engage in acts that would otherwise constitute UPL.",
                required=True,
            ),
            _field(
                "allows_software_provider",
                "boolean",
                "True if software platforms may be licensed as providers (AI-relevant).",
                required=True,
            ),
            _field(
                "source_url", "string", "URL of the source document for this row.", required=True
            ),
            _field(
                "retrieved_at",
                "datetime",
                "UTC timestamp of the scrape that produced this row.",
                required=True,
                fmt="any",
            ),
            _field("scraper_version", "string", "Semantic version of the scraper.", required=True),
        ],
        "primaryKey": ["program_id"],
    }


def _schema_source_snapshot() -> dict:
    return {
        "fields": [
            _field(
                "snapshot_id", "string", "Content-addressed PK: snap_<sha256[:16]>.", required=True
            ),
            _field("program_id", "string", "FK → program.", required=True),
            _field("source_url", "string", "Canonical URL that was fetched.", required=True),
            _field(
                "retrieved_at",
                "datetime",
                "UTC fetch time. For Wayback captures, the archive timestamp.",
                required=True,
                fmt="any",
            ),
            _field(
                "content_sha256",
                "string",
                "SHA-256 of raw bytes (lowercase hex). Dedup key.",
                required=True,
                pattern=r"^[0-9a-f]{64}$",
            ),
            _field("storage_path", "string", "Relative path to blob in data/raw/.", required=True),
            _field(
                "media_type",
                "string",
                "Format of the raw capture.",
                required=True,
                enum=_MEDIA_TYPE,
            ),
            _field(
                "scraper_version",
                "string",
                "Scraper version; wayback-* for archive captures.",
                required=True,
            ),
        ],
        "primaryKey": ["snapshot_id"],
        "foreignKeys": [
            {
                "fields": ["program_id"],
                "reference": {"resource": "program", "fields": ["program_id"]},
            },
        ],
    }


def _schema_provider() -> dict:
    return {
        "fields": [
            _field(
                "provider_id",
                "string",
                "Deterministic PK: prov_{program_slug}_{sha256(program_id+legal_name)[:12]}.",
                required=True,
            ),
            _field("program_id", "string", "FK → program.", required=True),
            _field(
                "provider_type",
                "string",
                "Entity (organization) or individual practitioner.",
                required=True,
                enum=_PROVIDER_TYPE,
            ),
            _field(
                "legal_name",
                "string",
                "Legal name exactly as it appears on the regulatory roster.",
                required=True,
            ),
            _field(
                "normalized_name",
                "string",
                "Deterministic normalized form for entity resolution (see methodology.md §3).",
                required=True,
            ),
            _field(
                "jurisdiction",
                "string",
                "USPS two-letter state code where the provider is licensed.",
                required=True,
                pattern=r"^[A-Z]{2}$",
            ),
            _field(
                "authorization_date",
                "date",
                "First authorized date from the roster, if published.",
                fmt="any",
            ),
            _field(
                "current_status",
                "string",
                "COMPUTED from provider_status_event log. Never scraped directly.",
                required=True,
                enum=_CURRENT_STATUS,
            ),
            _field(
                "practice_areas_raw",
                "string",
                "JSON array of practice areas in the source's own terminology, "
                'e.g. ["family law","civil"]. Empty string if none published.',
            ),
            _field(
                "practice_areas_list",
                "string",
                "JSON array of JusticeBench LIST taxonomy codes. "
                "Empty string if mapping not yet applied.",
            ),
            _field(
                "ownership_structure",
                "string",
                "JSON object with lawyer/non-lawyer ownership percentages "
                "and capital source. Entities only; null for individuals.",
            ),
            _field(
                "uses_technology",
                "boolean",
                "True if provider describes technology-assisted service delivery. Null if unknown.",
            ),
            _field(
                "uses_ai",
                "boolean",
                "True if provider describes AI or LLM use. Null if unknown. "
                "The column connecting to the UPL/AI policy question.",
            ),
            _field("website", "string", "Provider public website URL. Null if unknown."),
            _field(
                "first_seen_snapshot_id",
                "string",
                "FK → source_snapshot. Earliest snapshot in which this provider appeared.",
            ),
            _field(
                "last_seen_snapshot_id",
                "string",
                "FK → source_snapshot. Most recent snapshot in which this provider appeared.",
            ),
            _field(
                "source_url",
                "string",
                "URL of the snapshot that last updated this row.",
                required=True,
            ),
            _field(
                "retrieved_at",
                "datetime",
                "retrieved_at of the snapshot that last updated this row.",
                required=True,
                fmt="any",
            ),
            _field(
                "scraper_version",
                "string",
                "Scraper version that last wrote this row.",
                required=True,
            ),
        ],
        "primaryKey": ["provider_id"],
        "foreignKeys": [
            {
                "fields": ["program_id"],
                "reference": {"resource": "program", "fields": ["program_id"]},
            },
            {
                "fields": ["first_seen_snapshot_id"],
                "reference": {"resource": "source_snapshot", "fields": ["snapshot_id"]},
            },
            {
                "fields": ["last_seen_snapshot_id"],
                "reference": {"resource": "source_snapshot", "fields": ["snapshot_id"]},
            },
        ],
    }


def _schema_provider_status_event() -> dict:
    return {
        "fields": [
            _field(
                "event_id",
                "string",
                "Deterministic PK: evt_+sha256(provider_id:snapshot_id:event_type)[:24]. "
                "Idempotent across re-runs.",
                required=True,
            ),
            _field("provider_id", "string", "FK → provider.", required=True),
            _field(
                "event_date",
                "date",
                "Date the change was first OBSERVED (snapshot date), not when it occurred.",
                required=True,
                fmt="any",
            ),
            _field(
                "event_type",
                "string",
                "What kind of change this event documents. "
                "disappeared_from_roster ≠ revoked — see methodology.md §4c.",
                required=True,
                enum=_EVENT_TYPE,
            ),
            _field(
                "new_status",
                "string",
                "Provider current_status after this event.",
                required=True,
                enum=_CURRENT_STATUS,
            ),
            _field(
                "detail",
                "string",
                "Free text. For status_change: 'old → new'. "
                "For disciplined/reinstated: description from discipline source.",
            ),
            _field(
                "source_snapshot_id",
                "string",
                "FK → source_snapshot. The capture that revealed this change.",
                required=True,
            ),
            _field("source_url", "string", "Provenance URL.", required=True),
            _field(
                "retrieved_at", "datetime", "Provenance timestamp (UTC).", required=True, fmt="any"
            ),
            _field("scraper_version", "string", "Scraper version.", required=True),
        ],
        "primaryKey": ["event_id"],
        "foreignKeys": [
            {
                "fields": ["provider_id"],
                "reference": {"resource": "provider", "fields": ["provider_id"]},
            },
            {
                "fields": ["source_snapshot_id"],
                "reference": {"resource": "source_snapshot", "fields": ["snapshot_id"]},
            },
        ],
    }


def _schema_provider_alias() -> dict:
    return {
        "fields": [
            _field("provider_id", "string", "FK → provider.", required=True),
            _field(
                "alias_name", "string", "DBA name, former legal name, or brand name.", required=True
            ),
            _field(
                "alias_source",
                "string",
                "Where the alias was found.",
                required=True,
                enum=_ALIAS_SOURCE,
            ),
            _field("source_url", "string", "Provenance.", required=True),
            _field("retrieved_at", "datetime", "Provenance (UTC).", required=True, fmt="any"),
            _field("scraper_version", "string", "Provenance.", required=True),
        ],
        "primaryKey": ["provider_id", "alias_name"],
        "foreignKeys": [
            {
                "fields": ["provider_id"],
                "reference": {"resource": "provider", "fields": ["provider_id"]},
            },
        ],
    }


def _schema_crosswalk_courtlistener() -> dict:
    return {
        "fields": [
            _field("provider_id", "string", "FK → provider.", required=True),
            _field("cl_docket_id", "integer", "CourtListener docket ID.", required=True),
            _field("cl_party_id", "integer", "CourtListener party ID. Null if not resolved."),
            _field(
                "match_score",
                "number",
                "Composite match confidence 0.0–1.0.",
                required=True,
                minimum=0.0,
                maximum=1.0,
            ),
            _field(
                "match_method",
                "string",
                "How the match was produced.",
                required=True,
                enum=_MATCH_METHOD,
            ),
            _field(
                "verified",
                "boolean",
                "True if a human confirmed the match. Verified rows are never "
                "overwritten by automated pipeline runs.",
                required=True,
            ),
            _field("reviewer", "string", "Identifier of the reviewer. Null if unverified."),
            _field("reviewed_at", "datetime", "When verification was recorded (UTC).", fmt="any"),
        ],
        "primaryKey": ["provider_id", "cl_docket_id"],
        "foreignKeys": [
            {
                "fields": ["provider_id"],
                "reference": {"resource": "provider", "fields": ["provider_id"]},
            },
        ],
    }


_SCHEMAS = {
    "program": _schema_program,
    "source_snapshot": _schema_source_snapshot,
    "provider": _schema_provider,
    "provider_status_event": _schema_provider_status_event,
    "provider_alias": _schema_provider_alias,
    "crosswalk_courtlistener": _schema_crosswalk_courtlistener,
}


def build(release_dir: Path = _RELEASE) -> dict:
    resources = []
    for name, schema_fn in _SCHEMAS.items():
        n = _rowcount(release_dir, name)
        resources.append(
            {
                "name": name,
                "path": f"{name}.csv",
                "mediatype": "text/csv",
                "encoding": "utf-8",
                "rowcount": n,
                "parquet": f"{name}.parquet",  # non-standard; for discovery only
                "schema": schema_fn(),
            }
        )
        print(f"  {name:<30} {n:>6} rows")

    n_programs = _rowcount(release_dir, "program")
    n_providers = _rowcount(release_dir, "provider")
    jurisdictions = _distinct_column(release_dir, "program", "jurisdiction")
    n_states = len(jurisdictions - {"DC"})
    dc_suffix = " + DC" if "DC" in jurisdictions else ""

    pkg = {
        "name": "reregulation-registry",
        "id": "https://github.com/jamespaul-yls/reregulation-provider-registry",
        "title": "U.S. Legal Services Reregulation Provider Registry",
        "version": "1.0.2",
        "created": "2026-06-30T00:00:00Z",
        "licenses": [
            {
                "name": "CC-BY-4.0",
                "title": "Creative Commons Attribution 4.0 International",
                "path": "https://creativecommons.org/licenses/by/4.0/",
            }
        ],
        "contributors": [
            {
                "title": "James Paul",
                "email": "james.paul@yale.edu",
                "role": "author",
            }
        ],
        "keywords": [
            "legal services",
            "reregulation",
            "alternative business structures",
            "legal paraprofessional",
            "regulatory sandbox",
            "access to justice",
            "UPL",
            "legal innovation",
            "longitudinal",
            "open data",
        ],
        "description": (
            "Open, reproducible, longitudinal registry of every authorized provider "
            "operating under a U.S. legal-services reregulation program: Alternative "
            "Business Structures (ABS), regulatory sandboxes, and allied-legal-professional "
            f"/ paraprofessional licenses. v1.0.2 covers {n_programs} programs across "
            f"{n_states} states{dc_suffix} with {n_providers} providers, entry/exit event "
            "tracking, and full provenance. No harm analysis — just the spine."
        ),
        "sources": [
            {
                "title": "Arizona Supreme Court — ABS/LP rosters",
                "path": "https://www.azcourts.gov/cld/Alternative-Business-Structure",
            },
            {
                "title": "Utah Office of Legal Services Innovation — Sandbox roster",
                "path": "https://utahinnovationoffice.org/",
            },
            {
                "title": "WSBA — LLLT directory (sunset program; Wayback archive)",
                "path": "https://www.wsba.org/",
            },
            {
                "title": "Colorado Office of Attorney Regulation Counsel — LLP roster",
                "path": "https://coloradolegalregulation.com/",
            },
            {
                "title": "Minnesota Judicial Branch — LP pilot",
                "path": "https://www.mncourts.gov/",
            },
            {
                "title": "Utah Courts — Licensed Paralegal Practitioner directory",
                "path": "https://www.utcourts.gov/",
            },
        ],
        "resources": resources,
    }

    out = release_dir / "datapackage.json"
    out.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {out}")
    return pkg


if __name__ == "__main__":
    print("Building datapackage.json …")
    build()
