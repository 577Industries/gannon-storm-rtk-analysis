"""High-level orchestrator: pull data, run positioning, aggregate, summarise.

Drives the end-to-end pipeline used by the notebooks and the CLI/Makefile:

    fetch RINEX  +  fetch Kp/Dst  ->  per-station positioning solutions
        ->  regional aggregates  ->  threshold-crossing tallies

The ``run_analysis`` entry-point returns a single dictionary with the four
DataFrames callers typically want. ``HeadlineClaim`` packages the citable
quantitative sentence emitted to ``results/quantitative.md``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import TypedDict

import httpx
import numpy as np
import pandas as pd

from .fetch import (
    DEFAULT_USER_AGENT,
    GANNON_PEAK_DAYS,
    fetch_window,
    gannon_window_dates,
)
from .positioning import (
    PRECISION_AG_PLANTING_THRESHOLD_M,
    PRECISION_AG_SPRAYING_THRESHOLD_M,
    daily_p95_error,
    manifest_for_solution,
    solve_spp,
    threshold_crossings,
)
from .stations import CORRIDOR_STATES, CORS_STATIONS, CorsStation
from .swpc import (
    fetch_dst,
    fetch_kp,
    join_kp_to_minute_grid,
)

logger = logging.getLogger(__name__)


class AnalysisBundle(TypedDict):
    """Combined output of ``run_analysis``."""

    solutions: pd.DataFrame
    daily: pd.DataFrame
    crossings_planting: pd.DataFrame
    crossings_spraying: pd.DataFrame
    kp: pd.DataFrame
    dst: pd.DataFrame
    headline: HeadlineClaim


@dataclass(frozen=True, slots=True)
class HeadlineClaim:
    """A citable summary of the storm-window result."""

    n_stations: int
    states: tuple[str, ...]
    storm_dates: tuple[date, ...]
    threshold_m: float
    aggregate_hours_over_threshold: float
    n_stations_over_threshold: int
    peak_h_error_p95_m: float
    peak_kp: float
    peak_dst_nT: float
    quiet_baseline_mean_m: float

    def sentence(self) -> str:
        """Render the headline as a single-paragraph claim suitable for a blog."""
        return (
            f"Across {self.n_stations_over_threshold} of {self.n_stations} NGS CORS "
            f"stations spanning the {', '.join(self.states)} corridor, the v1 "
            f"climatological model produced 2D horizontal SPP error exceeding the "
            f"agronomic {self.threshold_m * 100:.1f} cm threshold for an aggregate "
            f"of {self.aggregate_hours_over_threshold:.0f} station-hours during "
            f"May {self.storm_dates[0].day}-{self.storm_dates[-1].day}, 2024 "
            f"(peak Kp={self.peak_kp:.1f}, Dst minimum={self.peak_dst_nT:.0f} nT). "
            f"Pre-storm quiet-period mean 2D error was {self.quiet_baseline_mean_m:.2f} m; "
            f"peak storm-window 95th-percentile 2D error was "
            f"{self.peak_h_error_p95_m:.1f} m."
        )


def run_analysis(
    stations: list[CorsStation] | None = None,
    *,
    data_dir: Path,
    rate_limit_sec: float = 0.25,
    skip_missing: bool = True,
    threshold_m: float = PRECISION_AG_PLANTING_THRESHOLD_M,
) -> AnalysisBundle:
    """Run the complete Gannon analysis pipeline.

    Args:
        stations: Subset of CORS catalog; defaults to ``CORS_STATIONS``.
        data_dir: Cache root (RINEX + indices land under ``data_dir``).
        rate_limit_sec: Politeness for NGS.
        skip_missing: If True, log and continue on per-station fetch errors.
        threshold_m: Operator-configurable accuracy threshold; defaults to
            the 2.5 cm planting threshold.

    Returns:
        ``AnalysisBundle`` containing per-epoch solutions, daily aggregates,
        threshold crossings, indices, and the headline claim.
    """
    use_stations = stations if stations is not None else CORS_STATIONS
    logger.info("Analysing %d stations", len(use_stations))

    # --- 1. Indices first (cheap) ---
    swpc_cache = data_dir / "swpc"
    swpc_cache.mkdir(parents=True, exist_ok=True)
    kp_df = fetch_kp(cache_path=swpc_cache / "kp.txt")
    dst_df = fetch_dst(cache_path=swpc_cache)
    kp_minute = join_kp_to_minute_grid(kp_df)

    # --- 2. Per-station RINEX + positioning ---
    cache_root = data_dir
    cache_root.mkdir(parents=True, exist_ok=True)
    rows: list[pd.DataFrame] = []
    manifests: list[dict[str, object]] = []
    with httpx.Client(timeout=60.0, headers={"User-Agent": DEFAULT_USER_AGENT}) as client:
        for station in use_stations:
            try:
                file_map = fetch_window(
                    station,
                    cache_root,
                    client=client,
                    rate_limit_sec=rate_limit_sec,
                    skip_missing=skip_missing,
                )
            except Exception as exc:
                logger.warning("Fetch failed for %s: %s", station.station_id, exc)
                if skip_missing:
                    continue
                raise
            for d, path in file_map.items():
                try:
                    df = solve_spp(
                        path,
                        station,
                        kp_series=kp_minute,
                        dst_series=dst_df,
                    )
                except Exception as exc:
                    logger.warning("Solve failed for %s %s: %s", station.station_id, d, exc)
                    if skip_missing:
                        continue
                    raise
                rows.append(df)
                manifests.append(asdict(manifest_for_solution(path, station, df)))

    if not rows:
        raise RuntimeError("No positioning solutions produced — check fetch logs")
    solutions = pd.concat(rows)
    solutions = solutions.sort_index()

    # --- 3. Aggregates ---
    daily = daily_p95_error(solutions)
    crossings_planting = threshold_crossings(
        solutions, threshold_m=PRECISION_AG_PLANTING_THRESHOLD_M
    )
    crossings_spraying = threshold_crossings(
        solutions, threshold_m=PRECISION_AG_SPRAYING_THRESHOLD_M
    )

    # --- 4. Headline ---
    headline = _compute_headline(
        solutions=solutions,
        daily=daily,
        crossings=crossings_planting
        if threshold_m == PRECISION_AG_PLANTING_THRESHOLD_M
        else crossings_spraying,
        kp=kp_df,
        dst=dst_df,
        states=tuple(s.state for s in use_stations),
        threshold_m=threshold_m,
    )

    return {
        "solutions": solutions,
        "daily": daily,
        "crossings_planting": crossings_planting,
        "crossings_spraying": crossings_spraying,
        "kp": kp_df,
        "dst": dst_df,
        "headline": headline,
    }


def _compute_headline(
    *,
    solutions: pd.DataFrame,  # noqa: ARG001 - reserved for v2 headline detail
    daily: pd.DataFrame,
    crossings: pd.DataFrame,
    kp: pd.DataFrame,
    dst: pd.DataFrame,
    states: tuple[str, ...],
    threshold_m: float,
) -> HeadlineClaim:
    storm_dates = GANNON_PEAK_DAYS
    storm_mask = crossings["time_utc"].dt.date.isin(storm_dates)
    storm_rows = crossings[storm_mask]
    agg_hours = float(storm_rows["hours_over_threshold"].sum())
    n_stations_over = int(
        (storm_rows.groupby("station_id")["hours_over_threshold"].sum() > 0).sum()
    )
    n_stations = int(daily["station_id"].nunique())

    # Quiet baseline: May 8-9 (pre-storm)
    pre_storm_dates = {date(2024, 5, 8), date(2024, 5, 9)}
    pre_mask = daily["time_utc"].dt.date.isin(pre_storm_dates)
    quiet_baseline = float(daily.loc[pre_mask, "h_error_2d_median_m"].mean())

    # Peak storm 95th-percentile across stations
    storm_mask_daily = daily["time_utc"].dt.date.isin(storm_dates)
    peak_p95 = float(daily.loc[storm_mask_daily, "h_error_2d_p95_m"].max())

    states_unique = tuple(sorted({s for s in states if s in CORRIDOR_STATES}))
    return HeadlineClaim(
        n_stations=n_stations,
        states=states_unique,
        storm_dates=storm_dates,
        threshold_m=threshold_m,
        aggregate_hours_over_threshold=agg_hours,
        n_stations_over_threshold=n_stations_over,
        peak_h_error_p95_m=peak_p95,
        peak_kp=float(kp["kp"].max()),
        peak_dst_nT=float(dst["dst"].min()),
        quiet_baseline_mean_m=quiet_baseline,
    )


def write_quantitative_md(
    bundle: AnalysisBundle,
    out_path: Path,
) -> None:
    """Emit ``results/quantitative.md`` — a committed summary table."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headline = bundle["headline"]
    daily = bundle["daily"].copy()
    daily["date"] = daily["time_utc"].dt.date

    storm_dates = set(GANNON_PEAK_DAYS)
    pre_storm_dates = {date(2024, 5, 8), date(2024, 5, 9)}

    def _classify(d: date) -> str:
        if d in storm_dates:
            return "STORM"
        if d in pre_storm_dates:
            return "PRESTORM"
        return "RECOVERY"

    daily["window"] = daily["date"].apply(_classify)

    per_station = (
        daily.groupby(["station_id", "window"])
        .agg(
            p95_2d_error_m=("h_error_2d_p95_m", "max"),
            median_2d_error_m=("h_error_2d_median_m", "median"),
        )
        .reset_index()
        .pivot(index="station_id", columns="window")
    )
    per_station.columns = [f"{a}_{b}" for a, b in per_station.columns]
    per_station = per_station.reset_index()

    lines: list[str] = [
        "# Gannon storm 2D horizontal SPP error — per-station summary",
        "",
        "_Generated by `gannon-storm-rtk-analysis` v0.1.0._",
        "",
        "## Headline",
        "",
        f"> {headline.sentence()}",
        "",
        "## Method",
        "",
        "- Stations: NGS CORS, lat/lon and ITRF2014 truth coordinates from each",
        "  station's day-131 RINEX header.",
        "- Indices: GFZ Potsdam Kp (CC-BY-4.0); Kyoto WDC hourly Dst.",
        "- Positioning: v1 climatological model — see `docs/methodology.md`.",
        "- Threshold for crossings: 2.5 cm planting (operator-configurable).",
        "- Pre-storm window: May 8-9, 2024 (Kp <= 3 baseline).",
        "- Storm window: May 10-12, 2024 (G3-G5 peak).",
        "- Recovery window: May 13-14, 2024 (residual G1-G2 activity).",
        "",
        "## Per-station summary",
        "",
        "| Station | State | Pre-storm p95 (m) | Storm p95 (m) | Ratio |",
        "|---|---|---|---|---|",
    ]
    for _, row in per_station.iterrows():
        pre = row.get("p95_2d_error_m_PRESTORM", float("nan"))
        storm = row.get("p95_2d_error_m_STORM", float("nan"))
        ratio = (storm / pre) if pre and np.isfinite(pre) and pre > 0 else float("nan")
        state = "?"
        for s in CORS_STATIONS:
            if s.station_id == row["station_id"]:
                state = s.state
                break
        lines.append(f"| {row['station_id']} | {state} | {pre:.3f} | {storm:.2f} | {ratio:.0f}x |")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("wrote %s", out_path)


def quick_corridor_run(*, data_dir: Path, n_stations: int | None = None) -> AnalysisBundle:
    """Convenience wrapper for the notebooks: corridor-only, optional limit."""
    from .stations import stations_in_corridor

    stations = stations_in_corridor()
    if n_stations is not None:
        stations = stations[:n_stations]
    return run_analysis(stations, data_dir=data_dir)


def utc_window_summary(bundle: AnalysisBundle) -> pd.DataFrame:
    """Return a tidy table of (date, kp_max, dst_min, regional_p95_2d_m)."""
    daily = bundle["daily"]
    grouped = daily.groupby(daily["time_utc"].dt.date).agg(
        regional_p95_2d_m=("h_error_2d_p95_m", lambda s: float(np.percentile(s, 95))),
        regional_median_2d_m=("h_error_2d_median_m", "median"),
        kp_max=("kp_max", "max"),
        dst_min=("dst_min", "min"),
        n_stations=("station_id", "nunique"),
    )
    grouped.index.name = "date"
    return grouped.reset_index()


def required_data_window() -> tuple[date, date]:
    """Return the (start, end) of the analysis window."""
    dates = gannon_window_dates()
    return dates[0], dates[-1]
