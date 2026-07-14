"""Smoke test for the read-only viz data export.

Unlike the rest of the suite (fixtures only, no live sources), this
deliberately runs scripts/export_viz.py against the real, committed
data/release/*.parquet — that IS the fixture here per the viz build's own
contract ("must read from actual project data, never mock"). No network
calls are made; data/release/ is local, committed data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from scripts.export_viz import _EXPECTED_ZERO, _VALIDATION_LOG, main

_ROOT = Path(__file__).parent.parent
_BUNDLE = _ROOT / "viz" / "data" / "bundle.json"


def _release_row_count(table: str) -> int:
    return pq.read_table(_ROOT / "data" / "release" / f"{table}.parquet").num_rows


def test_export_runs_and_matches_release_counts():
    main()
    assert _BUNDLE.exists()

    bundle = json.loads(_BUNDLE.read_text())

    name_map = {
        "programs": "program",
        "providers": "provider",
        "events": "provider_status_event",
        "snapshots": "source_snapshot",
    }
    for bundle_key, release_name in name_map.items():
        got, want = len(bundle[bundle_key]), _release_row_count(release_name)
        assert got == want, f"{bundle_key} count mismatch: {got} != {want}"

    assert bundle["counts"]["programs"] == len(bundle["programs"])
    assert bundle["counts"]["providers"] == len(bundle["providers"])


def test_every_zero_provider_program_has_a_documented_reason():
    main()
    bundle = json.loads(_BUNDLE.read_text())

    zero_programs = {p["program_id"] for p in bundle["programs"] if p["provider_count"] == 0}
    assert zero_programs == set(_EXPECTED_ZERO.keys())

    reasons = {z["program_id"]: z["reason"] for z in bundle["expected_zero"]}
    assert reasons == _EXPECTED_ZERO


def test_every_program_has_a_validation_log_reference():
    main()
    bundle = json.loads(_BUNDLE.read_text())

    for prog in bundle["programs"]:
        pid = prog["program_id"]
        assert pid in _VALIDATION_LOG, f"{pid} missing from _VALIDATION_LOG"
        log_path = _ROOT / _VALIDATION_LOG[pid]
        assert log_path.exists(), f"{log_path} does not exist on disk"


def test_map_covers_every_program_jurisdiction():
    main()
    bundle = json.loads(_BUNDLE.read_text())

    jurisdictions = {p["jurisdiction"] for p in bundle["programs"]}
    assert jurisdictions.issubset(bundle["map"]["states"].keys())


def test_provider_counts_sum_matches_release():
    main()
    bundle = json.loads(_BUNDLE.read_text())

    total = sum(p["provider_count"] for p in bundle["programs"])
    assert total == _release_row_count("provider")
