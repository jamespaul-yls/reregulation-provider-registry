"""Minimal US state/territory name -> USPS code lookup.

Scoped to what completeness fetchers need: resolving free-text jurisdiction
names found in prose on external sites (e.g. "Washington, D.C.", "Puerto
Rico", "Utah (through its Sandbox)"). This is NOT the full USPS+FIPS
crosswalk described as a v1 reference vocab in docs/methodology.md — that is
future work. resolve_usps() never raises; callers must surface unmapped
names rather than silently dropping them (see frame_reconcile.py).
"""

from __future__ import annotations

import re

_NAME_TO_USPS: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "washington, d.c.": "DC",
    "washington d.c.": "DC",
    "district of columbia": "DC",
    "puerto rico": "PR",
    "american samoa": "AS",
    "guam": "GU",
    "northern mariana islands": "MP",
    "u.s. virgin islands": "VI",
    "virgin islands": "VI",
}

# Strips a trailing parenthetical, e.g. "Utah (through its Sandbox)" -> "Utah".
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def resolve_usps(name: str) -> str | None:
    """Best-effort map of a free-text US jurisdiction name to a USPS code.

    Returns None (never raises) if the name isn't recognized.
    """
    cleaned = _PAREN_RE.sub("", name).strip().lower()
    return _NAME_TO_USPS.get(cleaned)
