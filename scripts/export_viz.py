"""Read-only visualization data export.

Reads ONLY from data/release/*.parquet — the published, three-layer-final
tables — plus a vendored US state-boundary file. Writes viz/data/bundle.json,
a single static JSON bundle consumed entirely by the viz/ frontend.

This never touches data/db/ or data/release/: it is a read-only view layered
on top of the published dataset, generated fresh from committed data every
time `make viz` runs.

Usage:
    uv run python scripts/export_viz.py
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import pyarrow.parquet as pq

_ROOT = Path(__file__).parent.parent
_RELEASE = _ROOT / "data" / "release"
_VENDOR = _ROOT / "viz" / "vendor"
_OUT_DIR = _ROOT / "viz" / "data"
_OUT_FILE = _OUT_DIR / "bundle.json"

# Programs documented as correctly zero-provider in v1, with the reason and
# citation (docs/sampling_frame.md §3). If a new zero-provider program shows
# up in the release data without an entry here, export fails loudly rather
# than the frontend silently rendering an unexplained blank.
_EXPECTED_ZERO: dict[str, str] = {
    "prog_ca_lda": (
        "County-fragmented registration — 58 independent county clerks, no "
        "statewide roster exists to scrape. See docs/sampling_frame.md §3."
    ),
    "prog_tx_alp": (
        "Licensing category paused by Misc. Docket No. 24-9095 (2024-11-04); "
        "no effective launch date, no licenses issued yet. See "
        "docs/sampling_frame.md §3."
    ),
    "prog_wa_entity_pilot": (
        "4 applicants under review as of 2026-07-04; none authorized yet. "
        "Appearing on the applicant list does not mean authorization. See "
        "docs/sampling_frame.md §3."
    ),
}

# Per-program validation log, for the "full reconciliation lives here" citation
# in the program detail panel. Not parsed for numbers — those stay hand-verified
# prose in validation/; the viz only computes what's true of the data itself.
_VALIDATION_LOG: dict[str, str] = {
    "prog_az_abs": "validation/arizona_abs.md",
    "prog_az_lp": "validation/arizona_lp.md",
    "prog_ca_lda": "validation/california_lda.md",
    "prog_co_llp": "validation/colorado_llp.md",
    "prog_mn_lp": "validation/minnesota_lp.md",
    "prog_tx_alp": "validation/texas_alp.md",
    "prog_ut_lpp": "validation/utah_lpp.md",
    "prog_ut_sandbox": "validation/utah_sandbox.md",
    "prog_wa_entity_pilot": "validation/washington_entity_pilot.md",
    "prog_wa_lllt": "validation/washington_lllt.md",
}

_STATE_NAME_TO_USPS: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Puerto Rico": "PR",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

# Not projected: no in-scope v1 program touches Alaska, Hawaii, or Puerto Rico.
_SKIP_STATES = {"Alaska", "Hawaii", "Puerto Rico"}


def _json_safe(v: object) -> object:
    if isinstance(v, datetime.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(datetime.UTC)
        return v.isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    return v


def _load_table(name: str) -> list[dict]:
    tbl = pq.read_table(_RELEASE / f"{name}.parquet")
    return [{k: _json_safe(v) for k, v in row.items()} for row in tbl.to_pylist()]


# ── Albers Conic Equal-Area projection, continental US ──────────────────────
# Standard parallels 29.5N/45.5N, central meridian 96W, reference latitude 38N.
# No in-scope program touches AK/HI/PR, so no AlbersUSA-style inset repositioning
# is needed — a single true conic projection over the lower 48 + DC is accurate.

_LAMBDA0 = math.radians(-96.0)
_PHI0 = math.radians(38.0)
_PHI1 = math.radians(29.5)
_PHI2 = math.radians(45.5)
_N = (math.sin(_PHI1) + math.sin(_PHI2)) / 2
_C = math.cos(_PHI1) ** 2 + 2 * _N * math.sin(_PHI1)
_RHO0 = math.sqrt(_C - 2 * _N * math.sin(_PHI0)) / _N


def _project(lon: float, lat: float) -> tuple[float, float]:
    lam = math.radians(lon)
    phi = math.radians(lat)
    theta = _N * (lam - _LAMBDA0)
    rho = math.sqrt(_C - 2 * _N * math.sin(phi)) / _N
    x = rho * math.sin(theta)
    y = -(_RHO0 - rho * math.cos(theta))  # negate: north up in screen coords
    return x, y


def _build_map() -> dict:
    geo = json.loads((_VENDOR / "us-states.geojson").read_text())

    per_state_rings: dict[str, list[list[tuple[float, float]]]] = {}
    for feat in geo["features"]:
        name = feat["properties"]["name"]
        if name in _SKIP_STATES:
            continue
        usps = _STATE_NAME_TO_USPS[name]
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings = per_state_rings.setdefault(usps, [])
        for poly in polys:
            for ring in poly:
                rings.append([_project(lon, lat) for lon, lat in ring])

    all_xy = [pt for rings in per_state_rings.values() for ring in rings for pt in ring]
    xs, ys = [p[0] for p in all_xy], [p[1] for p in all_xy]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    width, height, pad = 960.0, 600.0, 20.0
    scale = min((width - 2 * pad) / (maxx - minx), (height - 2 * pad) / (maxy - miny))
    tx, ty = pad - minx * scale, pad - miny * scale

    state_paths: dict[str, str] = {}
    for usps, rings in per_state_rings.items():
        parts = []
        for ring in rings:
            pts = [(x * scale + tx, y * scale + ty) for x, y in ring]
            d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}" + "".join(
                f"L{x:.1f},{y:.1f}" for x, y in pts[1:]
            )
            parts.append(d + "Z")
        state_paths[usps] = " ".join(parts)

    return {"viewBox": f"0 0 {width:.0f} {height:.0f}", "states": state_paths}


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    programs = _load_table("program")
    providers = _load_table("provider")
    events = _load_table("provider_status_event")
    snapshots = _load_table("source_snapshot")

    provider_counts: dict[str, int] = {}
    for p in providers:
        provider_counts[p["program_id"]] = provider_counts.get(p["program_id"], 0) + 1
    for prog in programs:
        prog["provider_count"] = provider_counts.get(prog["program_id"], 0)
        prog["validation_log"] = _VALIDATION_LOG.get(prog["program_id"])

    expected_zero = []
    for prog in programs:
        if prog["provider_count"] == 0:
            pid = prog["program_id"]
            if pid not in _EXPECTED_ZERO:
                raise SystemExit(
                    f"export_viz: program {pid!r} has 0 providers but no documented "
                    f"reason in _EXPECTED_ZERO — add one (see docs/sampling_frame.md) "
                    f"before exporting. Refusing to render an unexplained zero."
                )
            expected_zero.append({"program_id": pid, "reason": _EXPECTED_ZERO[pid]})

    bundle = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "counts": {
            "programs": len(programs),
            "states": len({p["jurisdiction"] for p in programs}),
            "providers": len(providers),
            "events": len(events),
            "snapshots": len(snapshots),
        },
        "programs": programs,
        "providers": providers,
        "events": events,
        "snapshots": snapshots,
        "expected_zero": expected_zero,
        "map": _build_map(),
    }

    _OUT_FILE.write_text(json.dumps(bundle, separators=(",", ":")))
    c = bundle["counts"]
    print(
        f"Wrote {_OUT_FILE.relative_to(_ROOT)} — {c['programs']} programs, "
        f"{c['providers']} providers, {c['events']} events, {c['snapshots']} snapshots, "
        f"{len(expected_zero)} documented zero-provider programs"
    )


if __name__ == "__main__":
    main()
