"""Pytest fixtures shared across the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the committed test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def rinex_fixture(fixtures_dir: Path) -> Path:
    """Path to a real Hatanaka-gzipped RINEX file for station IAAL, 2024-05-10."""
    return fixtures_dir / "iaal1310.24d.gz"


@pytest.fixture
def kp_fixture(fixtures_dir: Path) -> Path:
    """Path to a GFZ Kp text fixture covering 2024-05-08 to 2024-05-14."""
    return fixtures_dir / "kp_fixture.txt"


@pytest.fixture
def dst_fixture(fixtures_dir: Path) -> Path:
    """Path to a Kyoto WDC Dst text fixture for May 2024."""
    return fixtures_dir / "dst_202405.txt"
