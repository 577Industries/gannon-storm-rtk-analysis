"""Matplotlib plotting helpers for the Gannon analysis.

Every figure has a footer with: data source, computation method, and
generation timestamp. Conventions: figure DPI 150 (publication-grade),
sans-serif font, viridis or storm-severity-ramped colormaps where appropriate.

The headline plot, ``regional_error_with_indices``, is the screen-grabbable
"oh that's bad" image meant for the blog post and LinkedIn thread.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .analysis import AnalysisBundle
from .positioning import (
    PRECISION_AG_PLANTING_THRESHOLD_M,
    PRECISION_AG_SPRAYING_THRESHOLD_M,
)
from .stations import CORS_STATIONS
from .swpc import kp_severity_color

logger = logging.getLogger(__name__)

DATA_FOOTER: str = (
    "Data: NGS CORS RINEX (geodesy.noaa.gov) | GFZ Potsdam Kp | Kyoto WDC Dst\n"
    "Method: gannon_analysis v0.1 climatological positioning model "
    "(see docs/methodology.md)"
)
"""Footer line attached to every emitted figure."""


def _add_footer(fig: Figure) -> None:
    """Attach the standard data/method/timestamp footer to a figure."""
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fig.text(
        0.01,
        0.005,
        f"{DATA_FOOTER}\nGenerated {ts} | 577 Industries Inc. | github.com/577-Industries/gannon-storm-rtk-analysis",
        ha="left",
        va="bottom",
        fontsize=6,
        color="#444",
    )


def _setup_axes(ax: Axes, *, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", alpha=0.4)


def plot_regional_error_vs_time(
    bundle: AnalysisBundle,
    *,
    threshold_m: float = PRECISION_AG_PLANTING_THRESHOLD_M,
    secondary_threshold_m: float = PRECISION_AG_SPRAYING_THRESHOLD_M,
    out_path: Path | None = None,
) -> Figure:
    """The headline plot: regional median + p95 2D error with Kp/Dst overlays.

    Two stacked panels:
      Top:    regional median and 95th-percentile 2D horizontal error vs time
              with operator threshold lines (planting + spraying) and severity
              bars annotating peak G-scale.
      Bottom: Kp (right axis) and Dst (left axis) on the same x-axis.
    """
    solutions = bundle["solutions"]
    kp_df = bundle["kp"]
    dst_df = bundle["dst"]

    # Resample to 1-hour median + p95 for plottability
    hourly = solutions.groupby(pd.Grouper(level="time_utc", freq="1h")).agg(
        median_m=("h_error_2d_m", "median"),
        p95_m=("h_error_2d_m", lambda s: float(np.percentile(s, 95))),
    )

    fig, axes = plt.subplots(
        2, 1, figsize=(14, 8.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )
    ax_err: Axes = axes[0]
    ax_idx: Axes = axes[1]

    # Plot p95 envelope filled
    ax_err.fill_between(
        hourly.index,
        hourly["median_m"],
        hourly["p95_m"],
        color="#d62728",
        alpha=0.25,
        label="Median to 95th-percentile (across corridor)",
    )
    ax_err.plot(hourly.index, hourly["p95_m"], color="#9b1c1c", lw=1.8, label="95th-percentile")
    ax_err.plot(hourly.index, hourly["median_m"], color="#1f77b4", lw=1.4, label="Median")

    # Threshold lines
    ax_err.axhline(
        threshold_m,
        color="#1a9850",
        ls="--",
        lw=1.2,
        label=f"Planting ({threshold_m * 100:.1f} cm)",
    )
    ax_err.axhline(
        secondary_threshold_m,
        color="#f46d43",
        ls="--",
        lw=1.2,
        label=f"Spraying ({secondary_threshold_m * 100:.1f} cm)",
    )

    ax_err.set_yscale("log")
    _setup_axes(
        ax_err,
        title=(
            "May 2024 Gannon Storm — IA/IL/IN/OH corridor 2D horizontal SPP error\n"
            "v1 climatological model | "
            f"peak Kp={kp_df['kp'].max():.1f} | "
            f"Dst min={dst_df['dst'].min():.0f} nT"
        ),
        xlabel="",
        ylabel="2D horizontal error (m, log)",
    )
    ax_err.legend(loc="upper left", fontsize=8)

    # Bottom: Kp + Dst
    ax_idx2 = ax_idx.twinx()
    # Kp as colored stems
    for t, kp_val in kp_df["kp"].items():
        ax_idx2.bar(
            t, kp_val, width=0.115, color=kp_severity_color(float(kp_val)), edgecolor="none"
        )
    ax_idx.plot(dst_df.index, dst_df["dst"], color="#1f1f1f", lw=1.6, label="Dst (nT)")
    ax_idx.axhline(0, color="#888", lw=0.6)

    _setup_axes(ax_idx, title="", xlabel="UTC", ylabel="Dst (nT)")
    ax_idx2.set_ylabel("Kp (G-scale color-coded)")
    ax_idx2.set_ylim(0, 9.5)
    ax_idx.set_ylim(min(dst_df["dst"].min() * 1.1, -50), 50)

    # X-axis formatting
    ax_idx.xaxis.set_major_locator(mdates.DayLocator())  # type: ignore[no-untyped-call]
    ax_idx.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))  # type: ignore[no-untyped-call]
    ax_idx.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))  # type: ignore[no-untyped-call]

    # Mark G5 issuance and Gannon storm window
    storm_start = datetime(2024, 5, 10, 17, 23)  # NOAA G5 issuance ~17:23 UT 2024-05-10
    storm_end = datetime(2024, 5, 12, 12)
    for ax in (ax_err, ax_idx):
        ax.axvspan(storm_start, storm_end, color="#fff0c0", alpha=0.30, zorder=0)  # type: ignore[arg-type]
    ax_err.text(
        storm_start,  # type: ignore[arg-type]
        ax_err.get_ylim()[1] * 0.55,
        "  NOAA G5 watch issued\n  2024-05-10 17:23 UT",
        ha="left",
        va="top",
        fontsize=8,
        color="#7a5800",
    )

    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    _add_footer(fig)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        logger.info("wrote %s", out_path)
    return fig


def plot_per_station_error_grid(
    bundle: AnalysisBundle,
    *,
    out_path: Path | None = None,
    threshold_m: float = PRECISION_AG_PLANTING_THRESHOLD_M,
) -> Figure:
    """Per-station 2D error vs UTC, color-coded by hourly Kp severity.

    One subplot per station; stations grouped by state in row order.
    """
    solutions = bundle["solutions"]
    stations = sorted(solutions["station_id"].unique())
    # Sort by state for readability
    stations_meta = {s.station_id: s for s in CORS_STATIONS}
    stations.sort(key=lambda s: (stations_meta[s].state, s))

    ncols = 4
    nrows = (len(stations) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 2.8 * nrows + 1), sharex=True, sharey=True)
    axes = np.atleast_2d(axes)

    for i, sid in enumerate(stations):
        r, c = divmod(i, ncols)
        ax = axes[r, c]
        sub = solutions[solutions["station_id"] == sid]
        # Down-sample to 5-minute median for tractable plotting
        hourly = (
            sub.groupby(pd.Grouper(level="time_utc", freq="5min"))
            .agg(h_error_2d_m=("h_error_2d_m", "median"), kp=("kp", "max"))
            .dropna()
        )
        colors = [kp_severity_color(float(k)) for k in hourly["kp"]]
        ax.scatter(hourly.index, hourly["h_error_2d_m"], c=colors, s=2.2, alpha=0.85)
        ax.set_yscale("log")
        ax.axhline(threshold_m, color="#1a9850", ls="--", lw=0.8)
        state = stations_meta[sid].state if sid in stations_meta else "?"
        ax.set_title(f"{sid.upper()} ({state})", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.tick_params(labelsize=8)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))  # type: ignore[no-untyped-call]
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))  # type: ignore[no-untyped-call]

    # Hide empty axes
    for j in range(len(stations), nrows * ncols):
        r, c = divmod(j, ncols)
        axes[r, c].set_visible(False)

    fig.suptitle(
        "Per-station 2D horizontal SPP error vs UTC (Gannon storm window)\n"
        "Color: Kp severity (green quiet -> dark-red G5). Green dashed line: 2.5 cm planting threshold.",
        fontsize=11,
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 0.97))
    _add_footer(fig)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        logger.info("wrote %s", out_path)
    return fig


def plot_threshold_crossings_bars(
    bundle: AnalysisBundle,
    *,
    out_path: Path | None = None,
) -> Figure:
    """Stacked bar chart: per-station hours over threshold by UTC day."""
    cr = bundle["crossings_planting"].copy()
    cr["date"] = cr["time_utc"].dt.date

    fig, ax = plt.subplots(figsize=(12, 6))
    pivot = cr.pivot_table(
        index="date",
        columns="station_id",
        values="hours_over_threshold",
        fill_value=0,
    )
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="turbo", legend=False, width=0.85)
    _setup_axes(
        ax,
        title="Stacked station-hours with 2D horizontal error > 2.5 cm (planting threshold)",
        xlabel="UTC date",
        ylabel="Station-hours over threshold",
    )
    ax.tick_params(axis="x", labelrotation=30)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, ncol=5, fontsize=7, loc="upper left")
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    _add_footer(fig)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        logger.info("wrote %s", out_path)
    return fig


def plot_station_map(
    bundle: AnalysisBundle,
    *,
    out_path: Path | None = None,
) -> Figure:
    """Scatter station locations on a state outline (lat/lon scatter, no cartopy).

    A "real" map with state shapes uses cartopy; this version uses lat/lon
    scatter with peak-storm p95 as color and size so it works without cartopy.
    """
    daily = bundle["daily"]
    storm_dates = {
        pd.Timestamp(d).date() for d in [date_2024(5, 10), date_2024(5, 11), date_2024(5, 12)]
    }
    daily_storm = daily[daily["time_utc"].dt.date.isin(storm_dates)]
    peak_per_station = daily_storm.groupby("station_id")["h_error_2d_p95_m"].max()

    stations_meta = {s.station_id: s for s in CORS_STATIONS}
    lats: list[float] = []
    lons: list[float] = []
    vals: list[float] = []
    labels: list[str] = []
    for sid, peak in peak_per_station.items():
        if sid in stations_meta:
            lats.append(stations_meta[sid].latitude_deg)
            lons.append(stations_meta[sid].longitude_deg)
            vals.append(float(peak))
            labels.append(sid.upper())

    fig, ax = plt.subplots(figsize=(10, 7))
    sc = ax.scatter(
        lons,
        lats,
        c=vals,
        s=[80 + min(v * 2, 800) for v in vals],
        cmap="inferno_r",
        edgecolor="black",
        linewidths=0.7,
    )
    for lon, lat, lab in zip(lons, lats, labels, strict=False):
        ax.annotate(lab, (lon, lat), textcoords="offset points", xytext=(6, 4), fontsize=8)

    cb = fig.colorbar(sc, ax=ax, shrink=0.85)
    cb.set_label("Peak storm-window 2D error 95th-percentile (m)")
    _setup_axes(
        ax,
        title="NGS CORS station locations — Gannon storm peak 2D-error severity",
        xlabel="Longitude (degrees east)",
        ylabel="Latitude (degrees north)",
    )
    ax.set_xlim(-97, -80)
    ax.set_ylim(36, 45)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    _add_footer(fig)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        logger.info("wrote %s", out_path)
    return fig


def date_2024(month: int, day: int) -> datetime:
    """Tiny helper used to anchor storm-day comparisons."""
    return datetime(2024, month, day)
