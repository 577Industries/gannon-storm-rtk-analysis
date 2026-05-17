"""Tests for the SWPC/GFZ/Kyoto-WDC index fetchers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from gannon_analysis.swpc import (
    _kp_from_index,
    _parse_dst_text,
    fetch_dst,
    fetch_kp,
    join_kp_to_minute_grid,
    kp_severity_color,
)


def test_kp_g_scale_mapping() -> None:
    assert _kp_from_index(0.0) == "G0"
    assert _kp_from_index(3.0) == "G0"
    assert _kp_from_index(5.0) == "G1"
    assert _kp_from_index(6.0) == "G2"
    assert _kp_from_index(7.0) == "G3"
    assert _kp_from_index(8.0) == "G4"
    assert _kp_from_index(9.0) == "G5"


def test_fetch_kp_from_fixture(kp_fixture: Path, tmp_path: Path) -> None:
    cache = tmp_path / "kp.txt"
    cache.write_text(kp_fixture.read_text())
    df = fetch_kp(cache_path=cache)
    assert not df.empty
    assert df["kp"].max() == pytest.approx(9.0, abs=0.01)
    assert df["g_scale"].max() == "G5"
    # The G5 watch was issued around 17:23 UT 2024-05-10, but Kp values
    # of 8.667+ start with the 15:00-18:00 UT interval that day.
    storm_window = df.loc[
        (df.index >= pd.Timestamp("2024-05-10 15:00"))
        & (df.index <= pd.Timestamp("2024-05-11 18:00"))
    ]
    assert storm_window["kp"].max() >= 8.0


def test_fetch_dst_from_fixture(dst_fixture: Path, tmp_path: Path) -> None:
    cache_dir = tmp_path / "swpc"
    cache_dir.mkdir()
    cache_dir.joinpath("dst-202405.txt").write_text(dst_fixture.read_text())
    df = fetch_dst(start=date(2024, 5, 10), end=date(2024, 5, 11), cache_path=cache_dir)
    assert not df.empty
    # Catastrophic Dst depression on 2024-05-11 -- WDC reported -406 nT.
    assert df["dst"].min() <= -200
    assert df["dst"].max() < 200


def test_parse_dst_text_handles_typical_format() -> None:
    sample = "DST2405*10PPX120   0  12  10  12  21  16   7   9  16  13  15  13   3  -1   1  10  23  25  66 -33-131-157-277-339-308 -41"
    df = _parse_dst_text(sample, year=2024, month=5)
    assert len(df) == 24
    assert df["dst"].iloc[0] == 12
    # The 339 column is at hour 23 in this sample
    assert df["dst"].min() == -339


def test_join_kp_to_minute_grid_forward_fills(kp_fixture: Path, tmp_path: Path) -> None:
    cache = tmp_path / "kp.txt"
    cache.write_text(kp_fixture.read_text())
    df = fetch_kp(cache_path=cache)
    minute = join_kp_to_minute_grid(df)
    # 7 days * 24 hours * 60 minutes = 10080, give or take.
    assert 5000 < len(minute) < 20000
    assert minute["kp"].notna().sum() / len(minute) > 0.95


def test_kp_severity_colors_distinct() -> None:
    colors = {
        kp_severity_color(0.0),
        kp_severity_color(5.5),
        kp_severity_color(7.5),
        kp_severity_color(9.0),
    }
    assert len(colors) == 4  # all distinct


@pytest.mark.integration
def test_fetch_kp_live(tmp_path: Path) -> None:
    """Live GFZ Kp archive fetch — opt-in."""
    df = fetch_kp(cache_path=tmp_path / "kp.txt")
    assert df["kp"].max() == pytest.approx(9.0, abs=0.01)
