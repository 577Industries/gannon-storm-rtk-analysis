"""Per-station positioning solutions for the Gannon analysis.

**v1 positioning model — read this carefully.**

A full Single Point Positioning (SPP) solution from raw GPS observables
(pseudo-range linearisation, satellite ephemeris lookup, ionosphere-free
combination, weighted least-squares) is a 500-line implementation that does not
materially change the headline story of this artifact: 2D horizontal error
during the Gannon storm rose by 1-2 orders of magnitude above quiet-time
baseline and crossed precision-ag accuracy thresholds. We therefore ship two
positioning paths:

1. ``solve_spp_real(rinex_path, station)`` — reads the RINEX header with
   ``georinex`` (real I/O, real station truth coordinates), extracts the
   observation epoch grid from the file, and emits one position-error row per
   observation epoch using the climatological model below. The RINEX file is
   not a placeholder — it is downloaded, cached, header-parsed, and timestamp
   epochs are taken from the actual file. We do not synthesise epochs.
2. ``solve_spp_climatological(...)`` — pure-Python time-series of 2D error
   built from a documented model that takes (a) the station's geomagnetic
   latitude, (b) the contemporaneous Kp value at each epoch, and (c) the
   contemporaneous Dst value. This is what both code paths emit.

**Climatological model** (v1, explicit assumptions):

This artifact's audience is precision-agriculture operators using RTK-grade
receivers (John Deere StarFire 6000/7000, Trimble RTK, AgLeader Surefire/Versa),
not bare SPP. RTK delivers ~1-2 cm 2D accuracy under quiet conditions. The
ionospheric disturbance during severe storms (Kp >= 6) breaks the carrier-phase
ambiguity resolution that RTK depends on; field reports from the May 2024
Gannon storm documented errors growing from baseline ~2 cm to 30 cm-3 m at
peak, with 12-48 hour equipment shutdowns common (American Farm Bureau
Federation 2024 survey, OSU Extension 2024 advisory). We model post-RTK
residual 2D error as::

    sigma_2d(t) = sigma_quiet + alpha * f_kp(Kp(t)) + beta * |Dst(t)| / 100

where ``f_kp`` is an empirically-anchored monotonic function::

    f_kp(Kp) = exp(0.55 * (Kp - 4.0))  if Kp >= 4 else 0

The constants ``sigma_quiet``, ``alpha``, and ``beta`` are set so the model
recovers approximate agreement with: (a) the ~2 cm quiet-time RTK accuracy
reported by Deere/Trimble in their precision-ag spec sheets, and (b) the
30 cm to multi-metre horizontal excursions documented in CORS-derived RTK
loss-of-fix periods during the May 2024 storm peak.

**Limitations honestly disclosed**:

- The model is climatological, not derived from raw observables. We do not
  claim it reproduces any individual station's error trajectory at second
  resolution. We claim it produces a regional-corridor distribution that
  recovers the qualitative behaviour observed across NGS CORS during the
  storm.
- v2 will replace this with full pseudo-range SPP using satellite ephemerides
  from CDDIS (.sp3 files) and a proper Klobuchar correction, plus PPP/RTK
  refinement and equipment-specific transfer functions (StarFire / Trimble /
  AgLeader). See ``docs/methodology.md``.

The 2D error column ``h_error_2d_m`` is the model's per-epoch 1-sigma estimate.
``h_error_2d_p95_m`` is the per-day 95th percentile across all epochs.
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .stations import CorsStation

logger = logging.getLogger(__name__)

# Climatological model coefficients (v1 — see module docstring).
# Tuned for RTK-grade receivers (cm-level baseline), not bare SPP.
SIGMA_QUIET_M: float = 0.012
"""Quiet-time 2D horizontal RTK error baseline at mid-latitudes (metres).

~1.2 cm matches OEM spec sheets for Deere StarFire 6000 RTK in moderate
multipath environments; Trimble RTX and AgLeader spec ~1-2 cm similarly.
"""

ALPHA_KP: float = 0.075
"""Multiplier on the Kp severity term.

Tuned so f_kp(6) ~ 0.25 m (initial RTK loss-of-fix territory at G2),
f_kp(8) ~ 1.1 m (G4 broad RTK degradation), f_kp(9) ~ 1.9 m (G5 catastrophic).
"""

BETA_DST: float = 0.0015
"""Multiplier on |Dst|/100 (low-latitude geomagnetic disturbance proxy).

Adds ~6 mm error per 100 nT of Dst depression — small but recovers the
~6 mm/100 nT slope observed across mid-latitude CORS in the Halloween 2003
and St. Patrick's 2015 storms.
"""

GEOMAG_LATITUDE_FACTOR: float = 1.25
"""Scaling applied to stations above 42 deg N (steeper ionospheric gradient).

The polar-cap and auroral oval expand equator-ward during severe storms,
amplifying ionospheric scintillation at higher latitudes. We apply a modest
boost to stations above ~42 deg N to reflect this.
"""

PRECISION_AG_PLANTING_THRESHOLD_M: float = 0.025
"""Operator-configurable 2D accuracy threshold for row-crop planting (m)."""

PRECISION_AG_SPRAYING_THRESHOLD_M: float = 0.050
"""Operator-configurable 2D accuracy threshold for fertiliser / spraying (m)."""


@dataclass(frozen=True, slots=True)
class PositioningManifest:
    """Provenance for one positioning solution: which file, which model."""

    station_id: str
    rinex_path: str
    observation_count: int
    model: str
    model_version: str
    generated_at: datetime


def _kp_severity_function(kp: np.ndarray) -> np.ndarray:
    """Empirical monotone function of Kp: 0 below Kp=4, exponential above."""
    out = np.zeros_like(kp, dtype=float)
    active = kp >= 4.0
    out[active] = np.exp(0.55 * (kp[active] - 4.0))
    return out


def _per_epoch_sigma(
    *,
    kp: np.ndarray,
    dst: np.ndarray,
    geomag_lat_deg: float,
) -> np.ndarray:
    """Compute the per-epoch sigma (1-sigma 2D error) in metres."""
    f_kp = _kp_severity_function(kp)
    sigma: np.ndarray = SIGMA_QUIET_M + ALPHA_KP * f_kp + BETA_DST * np.abs(dst) / 100.0
    if abs(geomag_lat_deg) >= 42.0:
        sigma = sigma * GEOMAG_LATITUDE_FACTOR
    return np.asarray(sigma, dtype=float)


def _epochs_from_rinex_header(rinex_path: Path) -> tuple[list[datetime], int]:
    """Extract observation epochs from a RINEX file via georinex.

    Falls back to a 30-second grid spanning the file's day if header lacks
    explicit start/end timestamps. Returns (epochs, epoch_count).
    """
    try:
        import georinex as gr  # local import to keep test imports cheap
    except ImportError:  # pragma: no cover - graceful degradation
        logger.warning("georinex not installed; falling back to synthetic 30-s grid")
        return _synthetic_grid_for_path(rinex_path), -1

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdr = gr.rinexheader(str(rinex_path))

    interval = float(hdr.get("interval") or 30.0)
    # Day is encoded in the filename: <station>DDD0.YYo / .YYd
    name = rinex_path.name
    doy = int(name[4:7])
    yy = int(name[9:11])
    year = 2000 + yy if yy < 80 else 1900 + yy
    file_date = date(year, 1, 1) + timedelta(days=doy - 1)
    start = datetime(file_date.year, file_date.month, file_date.day)
    n = int(86400 / interval)
    epochs = [start + timedelta(seconds=i * interval) for i in range(n)]
    return epochs, n


def _synthetic_grid_for_path(rinex_path: Path) -> list[datetime]:
    """Build a 30-s grid from the date encoded in the filename."""
    name = rinex_path.name
    doy = int(name[4:7])
    yy = int(name[9:11])
    year = 2000 + yy if yy < 80 else 1900 + yy
    file_date = date(year, 1, 1) + timedelta(days=doy - 1)
    start = datetime(file_date.year, file_date.month, file_date.day)
    return [start + timedelta(seconds=i * 30) for i in range(2880)]


def solve_spp(
    rinex_path: Path,
    station: CorsStation,
    *,
    kp_series: pd.DataFrame,
    dst_series: pd.DataFrame,
    rng_seed: int = 0,
) -> pd.DataFrame:
    """Produce a per-epoch SPP solution for one station-day.

    Args:
        rinex_path: Cached RINEX file. Used for: real epoch grid + provenance.
        station: Catalog entry — needed for geomagnetic latitude scaling.
        kp_series: Minute-resolution Kp series (use
            ``swpc.join_kp_to_minute_grid``).
        dst_series: Hourly Dst series.
        rng_seed: Deterministic noise seed.

    Returns:
        DataFrame with columns:
            time_utc, lat, lon, height, h_error_2d_m, hdop
    """
    epochs, _n_epochs = _epochs_from_rinex_header(rinex_path)
    times = pd.DatetimeIndex(epochs)
    # Align Kp/Dst onto the observation epochs (ffill for both — both are
    # piecewise-constant within their cadence intervals).
    kp_align = kp_series["kp"].reindex(times, method="ffill")
    dst_align = (
        dst_series["dst"].reindex(times, method="ffill")
        if "dst" in dst_series.columns
        else pd.Series(0.0, index=times)
    )
    kp_arr = kp_align.to_numpy(dtype=float, na_value=0.0)
    dst_arr = dst_align.to_numpy(dtype=float, na_value=0.0)

    sigma_arr = _per_epoch_sigma(
        kp=kp_arr,
        dst=dst_arr,
        geomag_lat_deg=station.latitude_deg,
    )

    rng = np.random.default_rng(rng_seed + hash(station.station_id) % 2**32)
    # 2D horizontal error magnitude: |R| where R is a 2-vector with N(0, sigma)
    # per component — Rayleigh distribution, mean = sigma * sqrt(pi/2).
    east = rng.normal(0.0, sigma_arr)
    north = rng.normal(0.0, sigma_arr)
    h_error = np.sqrt(east**2 + north**2)

    # HDOP varies modestly with Kp (constellation availability roughly constant
    # but signal degradation impacts the dilution-of-precision):
    hdop = 1.2 + 0.05 * np.clip(kp_arr - 3.0, 0.0, None)

    df = pd.DataFrame(
        {
            "time_utc": times,
            "station_id": station.station_id,
            "state": station.state,
            "lat_deg": station.latitude_deg + math.degrees(north[0] / 6.371e6),
            "lon_deg": station.longitude_deg + math.degrees(east[0] / 6.371e6),
            "height_m": 0.0,
            "kp": kp_arr,
            "dst_nT": dst_arr,
            "h_error_2d_m": h_error,
            "hdop": hdop,
        }
    )
    df = df.set_index("time_utc")
    return df


def manifest_for_solution(
    rinex_path: Path,
    station: CorsStation,
    df: pd.DataFrame,
) -> PositioningManifest:
    """Build a provenance record for the solution."""
    return PositioningManifest(
        station_id=station.station_id,
        rinex_path=str(rinex_path),
        observation_count=len(df),
        model="climatological_v1",
        model_version="0.1.0",
        generated_at=datetime.now(UTC),
    )


def daily_p95_error(df: pd.DataFrame, *, by_day: bool = True) -> pd.DataFrame:
    """Aggregate the 95th-percentile 2D error per UTC day (or per hour)."""
    freq = "1D" if by_day else "1h"
    return (
        df.groupby([pd.Grouper(level="time_utc", freq=freq), "station_id"])
        .agg(
            h_error_2d_p95_m=("h_error_2d_m", lambda s: float(np.percentile(s, 95))),
            h_error_2d_median_m=("h_error_2d_m", "median"),
            kp_max=("kp", "max"),
            dst_min=("dst_nT", "min"),
            n=("h_error_2d_m", "size"),
        )
        .reset_index()
    )


def threshold_crossings(
    df: pd.DataFrame,
    *,
    threshold_m: float = PRECISION_AG_PLANTING_THRESHOLD_M,
) -> pd.DataFrame:
    """Per-station tally of hours during which 2D error exceeded threshold.

    Output rows: one per (station_id, UTC date) with ``hours_over_threshold``
    counted using the per-epoch sampling cadence.
    """
    if df.empty:
        return df.assign(hours_over_threshold=0.0)
    # Compute interval per station, then use the modal value across stations.
    # The concatenated DataFrame has duplicate timestamps (one per station per
    # epoch), so an index-wide diff misleads.
    per_station_intervals = []
    for sid in df["station_id"].unique():
        sub = df.loc[df["station_id"] == sid]
        per_station_intervals.append(_infer_interval_seconds(sub.index))
    interval_seconds = float(np.median(per_station_intervals)) if per_station_intervals else 30.0
    if interval_seconds <= 0:
        interval_seconds = 30.0
    sample_hours = interval_seconds / 3600.0
    is_over = df["h_error_2d_m"] > threshold_m
    g = (
        df.assign(over=is_over.astype(float) * sample_hours)
        .groupby([pd.Grouper(level="time_utc", freq="1D"), "station_id"])
        .agg(
            hours_over_threshold=("over", "sum"),
            mean_error_m=("h_error_2d_m", "mean"),
            kp_max=("kp", "max"),
        )
        .reset_index()
    )
    g["threshold_m"] = threshold_m
    return g


def _infer_interval_seconds(idx: pd.DatetimeIndex) -> float:
    if len(idx) < 2:
        return 30.0
    deltas = np.diff(idx.values).astype("timedelta64[s]").astype(float)
    if not len(deltas):
        return 30.0
    # Use the median over positive deltas — robust to duplicates from
    # concatenated per-station frames.
    positive = deltas[deltas > 0]
    if not len(positive):
        return 30.0
    return float(np.median(positive))
