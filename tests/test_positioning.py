"""Tests for the climatological positioning model."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gannon_analysis.positioning import (
    ALPHA_KP,
    BETA_DST,
    GEOMAG_LATITUDE_FACTOR,
    PRECISION_AG_PLANTING_THRESHOLD_M,
    SIGMA_QUIET_M,
    _kp_severity_function,
    _per_epoch_sigma,
    daily_p95_error,
    manifest_for_solution,
    solve_spp,
    threshold_crossings,
)
from gannon_analysis.stations import station_by_id
from gannon_analysis.swpc import fetch_dst, fetch_kp, join_kp_to_minute_grid


def test_kp_severity_function_zero_below_4() -> None:
    out = _kp_severity_function(np.array([0.0, 2.0, 3.9]))
    assert np.all(out == 0.0)


def test_kp_severity_function_monotonic_above_4() -> None:
    grid = np.linspace(4.0, 9.0, 50)
    out = _kp_severity_function(grid)
    assert np.all(np.diff(out) >= 0)
    assert out[0] == pytest.approx(1.0)


def test_per_epoch_sigma_baseline_quiet() -> None:
    sigma = _per_epoch_sigma(
        kp=np.array([0.0, 1.0, 2.0]),
        dst=np.array([0.0, 0.0, 0.0]),
        geomag_lat_deg=39.0,
    )
    assert np.allclose(sigma, SIGMA_QUIET_M)


def test_per_epoch_sigma_storm_amplification() -> None:
    quiet = _per_epoch_sigma(kp=np.array([1.0]), dst=np.array([0.0]), geomag_lat_deg=39.0)
    storm = _per_epoch_sigma(kp=np.array([9.0]), dst=np.array([-400.0]), geomag_lat_deg=39.0)
    assert storm[0] > 50 * quiet[0]


def test_per_epoch_sigma_high_latitude_boost() -> None:
    low = _per_epoch_sigma(kp=np.array([8.0]), dst=np.array([-200.0]), geomag_lat_deg=39.0)
    high = _per_epoch_sigma(kp=np.array([8.0]), dst=np.array([-200.0]), geomag_lat_deg=44.0)
    assert high[0] == pytest.approx(low[0] * GEOMAG_LATITUDE_FACTOR, rel=1e-3)


def test_solve_spp_returns_expected_columns(
    rinex_fixture: Path,
    kp_fixture: Path,
    dst_fixture: Path,
    tmp_path: Path,
) -> None:
    cache_kp = tmp_path / "kp.txt"
    cache_kp.write_text(kp_fixture.read_text())
    kp = fetch_kp(cache_path=cache_kp)
    kp_minute = join_kp_to_minute_grid(kp)
    swpc_dir = tmp_path / "swpc"
    swpc_dir.mkdir()
    swpc_dir.joinpath("dst-202405.txt").write_text(dst_fixture.read_text())
    dst = fetch_dst(start=date(2024, 5, 10), end=date(2024, 5, 10), cache_path=swpc_dir)

    station = station_by_id("iaal")
    df = solve_spp(rinex_fixture, station, kp_series=kp_minute, dst_series=dst)
    assert set(df.columns) >= {"station_id", "h_error_2d_m", "hdop", "kp", "dst_nT"}
    assert df["station_id"].nunique() == 1
    assert (df["h_error_2d_m"] >= 0).all()


def test_solve_spp_storm_window_exceeds_quiet(
    rinex_fixture: Path,
    kp_fixture: Path,
    dst_fixture: Path,
    tmp_path: Path,
) -> None:
    cache_kp = tmp_path / "kp.txt"
    cache_kp.write_text(kp_fixture.read_text())
    kp = fetch_kp(cache_path=cache_kp)
    kp_minute = join_kp_to_minute_grid(kp)
    swpc_dir = tmp_path / "swpc"
    swpc_dir.mkdir()
    swpc_dir.joinpath("dst-202405.txt").write_text(dst_fixture.read_text())
    dst = fetch_dst(start=date(2024, 5, 8), end=date(2024, 5, 14), cache_path=swpc_dir)

    station = station_by_id("iaal")
    df = solve_spp(rinex_fixture, station, kp_series=kp_minute, dst_series=dst)
    # Storm peak is May 11; pre-storm baseline May 10 early-UTC.
    storm = df.loc[
        (df.index >= pd.Timestamp("2024-05-10 18:00"))
        & (df.index <= pd.Timestamp("2024-05-10 23:59"))
    ]
    # Compare against the early-UTC of May 10 (Kp still low).
    quiet = df.loc[
        (df.index >= pd.Timestamp("2024-05-10 00:00"))
        & (df.index <= pd.Timestamp("2024-05-10 05:59"))
    ]
    assert storm["h_error_2d_m"].mean() > 10 * quiet["h_error_2d_m"].mean()


def test_daily_p95_error_one_row_per_day_per_station() -> None:
    times = pd.date_range("2024-05-10", periods=2880, freq="30s")
    df = pd.DataFrame(
        {
            "h_error_2d_m": np.linspace(0.005, 2.5, 2880),
            "station_id": "iaal",
            "kp": np.linspace(2, 9, 2880),
            "dst_nT": np.linspace(0, -400, 2880),
        },
        index=times,
    )
    df.index.name = "time_utc"
    out = daily_p95_error(df)
    assert len(out) == 1
    assert out["h_error_2d_p95_m"].iloc[0] > 1.5


def test_threshold_crossings_sums_correctly() -> None:
    # 2880 epochs at 30 s each = 24 hours. Half over threshold.
    times = pd.date_range("2024-05-11", periods=2880, freq="30s")
    err = np.concatenate(
        [np.full(1440, 0.10), np.full(1440, 0.01)]
    )  # first half over, second under
    df = pd.DataFrame(
        {
            "h_error_2d_m": err,
            "station_id": "iaal",
            "kp": np.full(2880, 6.0),
            "dst_nT": np.full(2880, -100.0),
        },
        index=times,
    )
    df.index.name = "time_utc"
    cr = threshold_crossings(df, threshold_m=PRECISION_AG_PLANTING_THRESHOLD_M)
    assert len(cr) == 1
    # 1440 epochs * 30 s = 43200 s = 12 hours
    assert cr["hours_over_threshold"].iloc[0] == pytest.approx(12.0, abs=0.1)


def test_manifest_for_solution_round_trip() -> None:
    station = station_by_id("iaal")
    df = pd.DataFrame({"h_error_2d_m": [0.0]})
    m = manifest_for_solution(Path("/tmp/x.gz"), station, df)
    assert m.station_id == "iaal"
    assert m.observation_count == 1
    assert m.model == "climatological_v1"


def test_threshold_crossings_empty_df() -> None:
    empty = pd.DataFrame(columns=["h_error_2d_m", "station_id", "kp", "dst_nT"])
    empty.index.name = "time_utc"
    cr = threshold_crossings(empty)
    assert "hours_over_threshold" in cr.columns


def test_alpha_beta_constants_positive() -> None:
    assert ALPHA_KP > 0
    assert BETA_DST > 0
    assert SIGMA_QUIET_M > 0
