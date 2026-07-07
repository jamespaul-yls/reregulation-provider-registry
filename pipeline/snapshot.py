"""Source-snapshot harness.

Single entry point for converting raw fetched bytes into an immutable blob
on disk plus a validated SourceSnapshot record.

Design constraints:
- Raw blobs are content-addressed by sha256 and never mutated after first write.
- Dedup is by content hash: same bytes from any URL → same blob file, no duplicate.
- Writes are atomic (tmp→rename) so a crash never leaves a partial file at the
  canonical hash path.
- SourceSnapshot always carries full provenance (source_url, retrieved_at,
  scraper_version).
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

from models.enums import MediaType
from models.schema import SourceSnapshot


def ingest(
    content: bytes,
    source_url: str,
    media_type: MediaType,
    program_id: str,
    scraper_version: str,
    raw_dir: Path,
    *,
    retrieved_at: datetime.datetime | None = None,
) -> tuple[SourceSnapshot, Path, bool]:
    """Hash *content*, write it to *raw_dir*, and return a SourceSnapshot record.

    The blob filename is ``{sha256}.{media_type}``, e.g.
    ``a3f1…c9.html``.  If a file with that name already exists the write is
    skipped — the caller gets the same SourceSnapshot shape but ``is_new=False``.

    Args:
        content:        Raw bytes exactly as fetched (HTML, PDF, JSON, …).
        source_url:     Canonical URL the bytes came from.
        media_type:     Declared type; determines the blob's file extension.
        program_id:     FK to program — embedded in the SourceSnapshot.
        scraper_version: Semver string of the scraper that produced the bytes.
        raw_dir:        Directory to write blobs into; created if absent.

    Returns:
        snapshot:   Validated SourceSnapshot (retrieved_at = now UTC).
        blob_path:  Absolute path to the raw file on disk.
        is_new:     True if the blob was written this call; False on dedup hit.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)

    sha = hashlib.sha256(content).hexdigest()
    blob_path = raw_dir / f"{sha}.{media_type.value}"

    is_new = not blob_path.exists()
    if is_new:
        # Atomic write: stage in a .tmp file then rename into place.
        # If I crash mid-write the partial bytes stay in .tmp, not at the
        # canonical hash path.  On POSIX, rename is atomic.
        tmp = blob_path.with_suffix(".tmp")
        try:
            tmp.write_bytes(content)
            tmp.rename(blob_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    snapshot = SourceSnapshot(
        snapshot_id=f"snap_{sha[:16]}",
        program_id=program_id,
        source_url=source_url,
        retrieved_at=(
            retrieved_at if retrieved_at is not None else datetime.datetime.now(datetime.UTC)
        ),
        content_sha256=sha,
        storage_path=str(blob_path),
        media_type=media_type,
        scraper_version=scraper_version,
    )
    return snapshot, blob_path, is_new
