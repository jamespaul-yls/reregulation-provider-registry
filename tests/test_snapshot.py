"""Tests for pipeline.snapshot.ingest().

All tests are offline — they read from tests/fixtures/ and write to tmp_path.
The two required assertions (from the task spec) are named explicitly:
  (a) test_snapshot_hash_and_media_type  — correct sha256 and MediaType on the record
  (b) test_dedup_no_second_raw_file      — identical bytes produce no second blob
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from models.enums import MediaType
from models.schema import SourceSnapshot
from pipeline.snapshot import ingest

# ── constants ─────────────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent / "fixtures" / "az_abs_roster.html"
_SOURCE_URL = "https://www.azcourts.gov/abs-roster"
_PROGRAM_ID = "prog_az_abs"
_VERSION = "0.1.0"


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fixture_bytes() -> bytes:
    return _FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def fixture_sha256(fixture_bytes: bytes) -> str:
    return hashlib.sha256(fixture_bytes).hexdigest()


def _call(content: bytes, raw_dir: Path, **kw: object) -> tuple[SourceSnapshot, Path, bool]:
    return ingest(
        content=content,
        source_url=kw.get("source_url", _SOURCE_URL),  # type: ignore[arg-type]
        media_type=kw.get("media_type", MediaType.html),  # type: ignore[arg-type]
        program_id=kw.get("program_id", _PROGRAM_ID),  # type: ignore[arg-type]
        scraper_version=kw.get("scraper_version", _VERSION),  # type: ignore[arg-type]
        raw_dir=raw_dir,
    )


# ── (a) snapshot written with correct hash and media_type ─────────────────────


def test_snapshot_hash_and_media_type(
    fixture_bytes: bytes, fixture_sha256: str, raw_dir: Path
) -> None:
    """(a) A snapshot is written with the correct sha256 and media_type."""
    snap, blob_path, is_new = _call(fixture_bytes, raw_dir)

    # blob exists and round-trips
    assert is_new is True
    assert blob_path.exists()
    assert blob_path.read_bytes() == fixture_bytes

    # SourceSnapshot carries correct hash and media_type
    assert snap.content_sha256 == fixture_sha256
    assert snap.media_type is MediaType.html

    # blob path is keyed by hash with the right extension
    assert blob_path == raw_dir / f"{fixture_sha256}.html"


# ── (b) re-ingesting identical bytes creates no second raw file ───────────────


def test_dedup_no_second_raw_file(fixture_bytes: bytes, raw_dir: Path) -> None:
    """(b) Re-ingesting identical bytes must dedup by sha256, not create a second file."""
    _call(fixture_bytes, raw_dir)
    _, _, is_new_second = _call(fixture_bytes, raw_dir)

    assert is_new_second is False
    assert len(list(raw_dir.iterdir())) == 1


# ── additional snapshot record correctness ────────────────────────────────────


def test_snapshot_is_valid_source_snapshot(fixture_bytes: bytes, raw_dir: Path) -> None:
    snap, _, _ = _call(fixture_bytes, raw_dir)
    assert isinstance(snap, SourceSnapshot)
    assert snap.program_id == _PROGRAM_ID
    assert snap.source_url == _SOURCE_URL
    assert snap.scraper_version == _VERSION


def test_snapshot_id_format(fixture_bytes: bytes, fixture_sha256: str, raw_dir: Path) -> None:
    snap, _, _ = _call(fixture_bytes, raw_dir)
    assert snap.snapshot_id == f"snap_{fixture_sha256[:16]}"


def test_blob_content_round_trips(fixture_bytes: bytes, raw_dir: Path) -> None:
    _, blob_path, _ = _call(fixture_bytes, raw_dir)
    assert blob_path.read_bytes() == fixture_bytes


# ── dedup edge cases ──────────────────────────────────────────────────────────


def test_dedup_different_source_url_same_content(fixture_bytes: bytes, raw_dir: Path) -> None:
    """Dedup is by content hash, not URL — same bytes from a mirror = one blob."""
    _call(fixture_bytes, raw_dir, source_url="https://www.azcourts.gov/abs-roster")
    _, _, is_new = _call(fixture_bytes, raw_dir, source_url="https://mirror.example.com/abs-roster")
    assert is_new is False
    assert len(list(raw_dir.iterdir())) == 1


def test_different_content_produces_separate_blobs(fixture_bytes: bytes, raw_dir: Path) -> None:
    """Mutated bytes have a different sha256 and must land in a separate blob."""
    mutated = fixture_bytes + b"\n<!-- updated -->"
    _call(fixture_bytes, raw_dir)
    _, _, is_new_mutated = _call(mutated, raw_dir)
    assert is_new_mutated is True
    html_blobs = list(raw_dir.glob("*.html"))
    assert len(html_blobs) == 2


# ── infrastructure ────────────────────────────────────────────────────────────


def test_raw_dir_created_if_absent(fixture_bytes: bytes, tmp_path: Path) -> None:
    deep = tmp_path / "nested" / "raw"
    assert not deep.exists()
    _call(fixture_bytes, deep)
    assert deep.exists()


@pytest.mark.parametrize(
    "media_type,ext",
    [
        (MediaType.html, "html"),
        (MediaType.pdf, "pdf"),
        (MediaType.json, "json"),
        (MediaType.xlsx, "xlsx"),
    ],
)
def test_blob_extension_matches_media_type(
    fixture_bytes: bytes, raw_dir: Path, media_type: MediaType, ext: str
) -> None:
    _, blob_path, _ = _call(fixture_bytes, raw_dir, media_type=media_type)
    assert blob_path.suffix == f".{ext}"
