"""Tests for the CORS RINEX fetcher.

Live-endpoint tests are marked ``integration`` and skipped by default in CI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gannon_analysis.fetch import (
    GANNON_PEAK_DAYS,
    GANNON_WINDOW_END,
    GANNON_WINDOW_START,
    NGS_CORS_BASE,
    fetch_rinex,
    gannon_window_dates,
    local_cache_path,
    rinex_filename,
    rinex_url,
)


def test_window_dates_inclusive() -> None:
    dates = gannon_window_dates()
    assert dates[0] == GANNON_WINDOW_START
    assert dates[-1] == GANNON_WINDOW_END
    assert len(dates) == 7


def test_window_includes_storm_peak_days() -> None:
    dates = gannon_window_dates()
    for d in GANNON_PEAK_DAYS:
        assert d in dates


def test_rinex_filename_pattern() -> None:
    assert rinex_filename("LANS", date(2024, 5, 10)) == "lans1310.24d.gz"
    assert rinex_filename("p041", date(2024, 1, 1)) == "p0410010.24d.gz"


def test_rinex_url_construction() -> None:
    url = rinex_url("iaal", date(2024, 5, 10))
    assert url.startswith(NGS_CORS_BASE)
    assert "/2024/131/iaal/iaal1310.24d.gz" in url


def test_local_cache_path_layout(tmp_path: Path) -> None:
    p = local_cache_path("iaal", date(2024, 5, 10), tmp_path)
    assert p == tmp_path / "cors" / "2024" / "131" / "iaal" / "iaal1310.24d.gz"


def test_fetch_rinex_uses_cache(tmp_path: Path, rinex_fixture: Path) -> None:
    """If the file already exists in cache, fetch_rinex returns it without
    going to the network (we pass no client and assert no exception)."""
    # Prepare cache hit
    target = local_cache_path("iaal", date(2024, 5, 10), tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rinex_fixture.read_bytes())
    out = fetch_rinex("iaal", date(2024, 5, 10), tmp_path)
    assert out == target
    assert out.exists()


@pytest.mark.integration
def test_fetch_rinex_live(tmp_path: Path) -> None:
    """Live-endpoint test against NGS CORS — opt-in only.

    Run via ``pytest -m integration``.
    """
    out = fetch_rinex("iaal", date(2024, 5, 10), tmp_path, rate_limit_sec=0.0)
    assert out.exists()
    assert out.stat().st_size > 10_000  # files are O(100KB-1MB)
