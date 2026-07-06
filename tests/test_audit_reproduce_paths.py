"""Regression tests for repo-relative storage_path resolution.

docs/audit/adversarial_review.md finding B2: pipeline.audit._check_blobs and
pipeline.reproduce._verify_blob used to do `Path(storage_path)` directly,
which only worked because storage_path was (bug) an absolute path baked to
this machine's exact directory. Both now resolve a relative storage_path
against the module's _ROOT constant. These tests prove that resolution works
against a fake repo root (monkeypatched _ROOT), independent of this machine's
actual layout — no network calls, no access to the real data/ directory.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest

import pipeline.audit as audit_mod
import pipeline.reproduce as reproduce_mod


def _write_blob(root: Path, content: bytes) -> tuple[str, str]:
    """Write *content* under <root>/data/raw/<sha>.html; return (relative_path, sha)."""
    sha = hashlib.sha256(content).hexdigest()
    blob_dir = root / "data" / "raw"
    blob_dir.mkdir(parents=True, exist_ok=True)
    (blob_dir / f"{sha}.html").write_bytes(content)
    return f"data/raw/{sha}.html", sha


# ── pipeline.audit._check_blobs ────────────────────────────────────────────────


def test_check_blobs_resolves_relative_path_against_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_mod, "_ROOT", tmp_path)
    rel_path, sha = _write_blob(tmp_path, b"<html>fake roster</html>")

    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE source_snapshot (snapshot_id VARCHAR, storage_path VARCHAR, "
        "content_sha256 VARCHAR)"
    )
    con.execute("INSERT INTO source_snapshot VALUES (?, ?, ?)", ["snap_test", rel_path, sha])

    errors = audit_mod._check_blobs(con)
    assert errors == []


def test_check_blobs_reports_missing_blob_with_resolved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_mod, "_ROOT", tmp_path)

    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE source_snapshot (snapshot_id VARCHAR, storage_path VARCHAR, "
        "content_sha256 VARCHAR)"
    )
    con.execute(
        "INSERT INTO source_snapshot VALUES (?, ?, ?)",
        ["snap_missing", "data/raw/does-not-exist.html", "0" * 64],
    )

    errors = audit_mod._check_blobs(con)
    assert len(errors) == 1
    assert "snap_missing" in errors[0]
    # The resolved (root-joined) path is surfaced, not just the raw relative string,
    # so a human debugging a real failure can see exactly where it looked.
    assert str(tmp_path) in errors[0]


def test_check_blobs_still_accepts_absolute_storage_path(tmp_path: Path) -> None:
    """Backward compatibility: an already-absolute path still works unresolved."""
    content = b"<html>legacy absolute row</html>"
    sha = hashlib.sha256(content).hexdigest()
    blob = tmp_path / f"{sha}.html"
    blob.write_bytes(content)

    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE source_snapshot (snapshot_id VARCHAR, storage_path VARCHAR, "
        "content_sha256 VARCHAR)"
    )
    con.execute("INSERT INTO source_snapshot VALUES (?, ?, ?)", ["snap_abs", str(blob), sha])

    errors = audit_mod._check_blobs(con)
    assert errors == []


# ── pipeline.reproduce._verify_blob ────────────────────────────────────────────


def test_verify_blob_resolves_relative_path_against_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reproduce_mod, "_ROOT", tmp_path)
    rel_path, sha = _write_blob(tmp_path, b"<html>fake roster 2</html>")

    raw = reproduce_mod._verify_blob(rel_path, sha)
    assert raw == b"<html>fake roster 2</html>"


def test_verify_blob_raises_with_resolved_path_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reproduce_mod, "_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match=str(tmp_path)):
        reproduce_mod._verify_blob("data/raw/does-not-exist.html", "0" * 64)


def test_verify_blob_still_accepts_absolute_storage_path(tmp_path: Path) -> None:
    content = b"<html>legacy absolute row 2</html>"
    sha = hashlib.sha256(content).hexdigest()
    blob = tmp_path / f"{sha}.html"
    blob.write_bytes(content)

    raw = reproduce_mod._verify_blob(str(blob), sha)
    assert raw == content
