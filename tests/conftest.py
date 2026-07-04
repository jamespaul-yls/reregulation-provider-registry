"""Shared pytest fixtures.

All tests run against saved snapshot fixtures — no network calls permitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def raw_dir(tmp_path: Path) -> Path:
    """Temporary directory that stands in for data/raw/ during tests."""
    d = tmp_path / "raw"
    d.mkdir()
    return d


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES_DIR
