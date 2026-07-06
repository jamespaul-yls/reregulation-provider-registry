"""Assertion tests: every program has providers or a documented zero-reason.

Two layers of verification:

1. Static invariant (no DB required, always runs in CI):
   - Every program_id in seed_programs.PROGRAMS is in exactly one of:
     _ZERO_ROSTER_PROGRAMS (zero by design, reason documented) or
     _ROSTER_PROGRAMS (expected to have >0 provider rows).
   - No stale entries in either set.
   - Each zero-roster program has a validation/*.md file on disk.

2. DB integration (skipped when dev DB is absent):
   - Roster programs have >0 provider rows in the DB.
   - Zero-roster programs have exactly 0 provider rows in the DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── canonical sets ────────────────────────────────────────────────────────────
#
# Edit these when adding a new program. Every program_id must appear in
# exactly one set. Adding a zero-roster program without a validation file will
# cause test_zero_roster_validation_files_exist to fail — write the file first.

_ZERO_ROSTER_PROGRAMS: dict[str, str] = {
    # program_id → validation file path (relative to repo root)
    "prog_tx_alp": "validation/texas_alp.md",
    "prog_ca_lda": "validation/california_lda.md",
    "prog_wa_entity_pilot": "validation/washington_entity_pilot.md",
}

_ROSTER_PROGRAMS: set[str] = {
    "prog_ut_sandbox",
    "prog_az_abs",
    "prog_az_lp",
    "prog_ut_lpp",
    "prog_co_llp",
    "prog_mn_lp",
    "prog_wa_lllt",
}

# Expected minimum provider counts (used in DB integration tests).
# A floor, not an exact match — the live roster can only grow.
_MIN_PROVIDER_COUNTS: dict[str, int] = {
    "prog_ut_sandbox": 69,
    "prog_az_abs": 167,
    "prog_az_lp": 120,
    "prog_ut_lpp": 52,
    "prog_co_llp": 126,
    "prog_mn_lp": 42,
    "prog_wa_lllt": 95,
}

_REPO_ROOT = Path(__file__).parent.parent
_DB_PATH = _REPO_ROOT / "data" / "db" / "registry.duckdb"


# ── helpers ───────────────────────────────────────────────────────────────────


def _all_program_ids() -> set[str]:
    import sys

    sys.path.insert(0, str(_REPO_ROOT))
    from scripts.seed_programs import PROGRAMS

    return {p.program_id for p in PROGRAMS}


# ── static invariant tests (no DB, always runs in CI) ────────────────────────


def test_all_programs_documented():
    """Every program in seed_programs is in exactly one coverage set."""
    all_ids = _all_program_ids()
    documented = set(_ZERO_ROSTER_PROGRAMS) | _ROSTER_PROGRAMS
    missing = all_ids - documented
    assert not missing, (
        f"Programs with no coverage documentation: {sorted(missing)}. "
        "Add each to _ZERO_ROSTER_PROGRAMS (with reason file) or _ROSTER_PROGRAMS."
    )


def test_sets_are_disjoint():
    """A program cannot be both zero-roster and a roster program."""
    overlap = set(_ZERO_ROSTER_PROGRAMS) & _ROSTER_PROGRAMS
    assert not overlap, f"program_ids in both sets: {sorted(overlap)}"


def test_no_stale_zero_roster_entries():
    """Every entry in _ZERO_ROSTER_PROGRAMS must exist in seed_programs.PROGRAMS."""
    all_ids = _all_program_ids()
    stale = set(_ZERO_ROSTER_PROGRAMS) - all_ids
    assert not stale, (
        f"Stale zero-roster entries (program removed from seed but not from this dict): "
        f"{sorted(stale)}"
    )


def test_no_stale_roster_entries():
    """Every entry in _ROSTER_PROGRAMS must exist in seed_programs.PROGRAMS."""
    all_ids = _all_program_ids()
    stale = _ROSTER_PROGRAMS - all_ids
    assert not stale, (
        f"Stale roster entries (program removed from seed but not from this set): {sorted(stale)}"
    )


def test_zero_roster_validation_files_exist():
    """Each zero-roster program must have a validation doc explaining the zero count."""
    missing_files = [
        (pid, path)
        for pid, path in _ZERO_ROSTER_PROGRAMS.items()
        if not (_REPO_ROOT / path).exists()
    ]
    assert not missing_files, "Zero-roster programs missing their validation file:\n" + "\n".join(
        f"  {pid}: {path}" for pid, path in missing_files
    )


def test_min_counts_only_for_roster_programs():
    """_MIN_PROVIDER_COUNTS must not reference zero-roster programs."""
    bad = set(_MIN_PROVIDER_COUNTS) & set(_ZERO_ROSTER_PROGRAMS)
    assert not bad, f"Zero-roster programs in _MIN_PROVIDER_COUNTS: {sorted(bad)}"


def test_all_roster_programs_have_min_counts():
    """Every roster program must have a minimum count entry."""
    missing = _ROSTER_PROGRAMS - set(_MIN_PROVIDER_COUNTS)
    assert not missing, (
        f"Roster programs missing from _MIN_PROVIDER_COUNTS: {sorted(missing)}. "
        "Add the expected minimum provider count."
    )


# ── DB integration tests (skipped when dev DB absent) ────────────────────────

_skip_no_db = pytest.mark.skipif(
    not _DB_PATH.exists(),
    reason=(
        "Dev DB not found. Run `uv run python scripts/seed_programs.py` and "
        "individual scraper scripts to populate it."
    ),
)


@_skip_no_db
def test_db_roster_programs_have_providers():
    """Roster programs must have ≥ _MIN_PROVIDER_COUNTS rows in the DB."""
    import duckdb

    con = duckdb.connect(str(_DB_PATH), read_only=True)
    rows = con.execute(
        "SELECT program_id, COUNT(*) AS n FROM provider GROUP BY program_id"
    ).fetchall()
    con.close()

    counts = {pid: n for pid, n in rows}
    failures: list[str] = []
    for pid in _ROSTER_PROGRAMS:
        actual = counts.get(pid, 0)
        expected_min = _MIN_PROVIDER_COUNTS[pid]
        if actual < expected_min:
            failures.append(
                f"  {pid}: expected ≥{expected_min}, got {actual}"
                + (" (not yet scraped?)" if actual == 0 else "")
            )
    assert not failures, "Roster programs below minimum provider count:\n" + "\n".join(failures)


@_skip_no_db
def test_db_zero_roster_programs_have_no_providers():
    """Zero-roster programs must have 0 provider rows in the DB."""
    import duckdb

    con = duckdb.connect(str(_DB_PATH), read_only=True)
    rows = con.execute(
        "SELECT program_id, COUNT(*) AS n FROM provider GROUP BY program_id"
    ).fetchall()
    con.close()

    counts = {pid: n for pid, n in rows}
    violations: list[str] = []
    for pid in _ZERO_ROSTER_PROGRAMS:
        actual = counts.get(pid, 0)
        if actual > 0:
            violations.append(
                f"  {pid}: expected 0, got {actual} — see {_ZERO_ROSTER_PROGRAMS[pid]}"
            )
    assert not violations, "Zero-roster programs unexpectedly have provider rows:\n" + "\n".join(
        violations
    )


@_skip_no_db
def test_db_no_undocumented_zero_programs():
    """Any program in the DB with 0 providers must be in _ZERO_ROSTER_PROGRAMS."""
    import duckdb

    con = duckdb.connect(str(_DB_PATH), read_only=True)
    all_program_ids = {r[0] for r in con.execute("SELECT program_id FROM program").fetchall()}
    provider_counts = {
        pid: n
        for pid, n in con.execute(
            "SELECT program_id, COUNT(*) FROM provider GROUP BY program_id"
        ).fetchall()
    }
    con.close()

    undocumented_zeros = [
        pid
        for pid in all_program_ids
        if provider_counts.get(pid, 0) == 0 and pid not in _ZERO_ROSTER_PROGRAMS
    ]
    assert not undocumented_zeros, (
        "Programs in DB with 0 providers but no documented zero-reason:\n"
        + "\n".join(f"  {pid}" for pid in sorted(undocumented_zeros))
        + "\nAdd each to _ZERO_ROSTER_PROGRAMS with a reason file, "
        "or run its scraper to populate providers."
    )
