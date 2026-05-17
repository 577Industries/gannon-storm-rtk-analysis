"""NGS CORS RINEX fetcher.

Downloads daily-observation RINEX files from the NGS public CORS archive at
``https://geodesy.noaa.gov/corsdata/rinex/<YYYY>/<DOY>/<station>/<station><DOY>0.<YY>d.gz``.

May 2024 files are Hatanaka-compressed (.24d) and gzipped. ``georinex`` (which
in turn uses ``hatanaka``) reads these directly without a separate decompression
step. The fetcher caches every file under ``data/cors/<year>/<doy>/<station>/``
and is polite by default (250 ms between station hits, single-threaded).

The data window for the Gannon storm is May 8-14, 2024 (DOY 129-135 inclusive):
three days of pre-storm baseline (May 8-9), the three-day G5 peak (May 10-12),
and two days of recovery (May 13-14).
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from .stations import CorsStation

logger = logging.getLogger(__name__)

NGS_CORS_BASE: str = "https://geodesy.noaa.gov/corsdata/rinex"
"""Public NGS CORS archive URL prefix."""

GANNON_WINDOW_START: date = date(2024, 5, 8)
"""First UTC day of the analysis window (pre-storm baseline)."""

GANNON_WINDOW_END: date = date(2024, 5, 14)
"""Last UTC day of the analysis window (post-storm recovery)."""

GANNON_PEAK_DAYS: tuple[date, date, date] = (
    date(2024, 5, 10),
    date(2024, 5, 11),
    date(2024, 5, 12),
)
"""The three days of peak G5 conditions during the Gannon superstorm."""

DEFAULT_USER_AGENT: str = (
    "gannon-storm-rtk-analysis/0.1 (HELIOS Artifact D; engineering@577industries.com)"
)
"""HTTP User-Agent identifying this client to NGS for support/audit purposes."""


def gannon_window_dates() -> list[date]:
    """Return every UTC date in the Gannon analysis window, inclusive."""
    n = (GANNON_WINDOW_END - GANNON_WINDOW_START).days + 1
    return [GANNON_WINDOW_START + timedelta(days=i) for i in range(n)]


def rinex_filename(station_id: str, the_date: date) -> str:
    """Return the canonical NGS CORS RINEX filename for a station-day.

    Example: ``("lans", 2024-05-10) -> "lans1310.24d.gz"``.
    """
    doy = the_date.timetuple().tm_yday
    yy = the_date.year % 100
    return f"{station_id.lower()}{doy:03d}0.{yy:02d}d.gz"


def rinex_url(station_id: str, the_date: date) -> str:
    """Construct the NGS CORS archive URL for a station-day."""
    doy = the_date.timetuple().tm_yday
    return f"{NGS_CORS_BASE}/{the_date.year}/{doy:03d}/{station_id.lower()}/{rinex_filename(station_id, the_date)}"


def local_cache_path(station_id: str, the_date: date, dest_dir: Path) -> Path:
    """Return the local cache path under ``dest_dir`` for a station-day."""
    doy = the_date.timetuple().tm_yday
    return (
        dest_dir
        / "cors"
        / f"{the_date.year}"
        / f"{doy:03d}"
        / station_id.lower()
        / rinex_filename(station_id, the_date)
    )


def fetch_rinex(
    station_id: str,
    the_date: date,
    dest_dir: Path,
    *,
    client: httpx.Client | None = None,
    rate_limit_sec: float = 0.25,
    timeout_sec: float = 60.0,
    force: bool = False,
) -> Path:
    """Fetch one CORS RINEX observation file. Caches on disk.

    Args:
        station_id: 4-char NGS CORS station ID.
        the_date: UTC observation date.
        dest_dir: Local root directory; files are cached under
            ``<dest_dir>/cors/<YYYY>/<DOY>/<station>/<filename>``.
        client: Optional pre-built httpx client (reuse for batch downloads).
        rate_limit_sec: Delay before each HTTP call when no cache hit.
        timeout_sec: HTTP timeout.
        force: If True, re-download even if a cached copy exists.

    Returns:
        Path to the cached file on disk.

    Raises:
        httpx.HTTPStatusError: on non-2xx response from NGS.
    """
    target = local_cache_path(station_id, the_date, dest_dir)
    if target.exists() and not force:
        logger.debug("cache hit %s", target)
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    url = rinex_url(station_id, the_date)

    own_client = client is None
    cli = client or httpx.Client(timeout=timeout_sec, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        if rate_limit_sec > 0:
            time.sleep(rate_limit_sec)
        logger.info("fetching %s", url)
        resp = cli.get(url)
        resp.raise_for_status()
        # Write atomically: temp file then rename.
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(resp.content)
        tmp.replace(target)
    finally:
        if own_client:
            cli.close()
    return target


def fetch_window(
    station: CorsStation,
    dest_dir: Path,
    *,
    dates: list[date] | None = None,
    client: httpx.Client | None = None,
    rate_limit_sec: float = 0.25,
    skip_missing: bool = True,
) -> dict[date, Path]:
    """Fetch every RINEX file in the Gannon window for one station.

    Args:
        station: Catalog entry.
        dest_dir: Cache root.
        dates: Optional explicit date list. Defaults to ``gannon_window_dates()``.
        client: Reusable httpx client.
        rate_limit_sec: Politeness delay.
        skip_missing: If True, log and continue on per-day fetch errors.

    Returns:
        Mapping of date -> cached file path. Days that failed are omitted.
    """
    out: dict[date, Path] = {}
    use_dates = dates if dates is not None else gannon_window_dates()
    own_client = client is None
    cli = client or httpx.Client(timeout=60.0, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        for d in use_dates:
            try:
                out[d] = fetch_rinex(
                    station.station_id,
                    d,
                    dest_dir,
                    client=cli,
                    rate_limit_sec=rate_limit_sec,
                )
            except httpx.HTTPStatusError as e:
                if skip_missing:
                    logger.warning(
                        "skipping %s %s: HTTP %s",
                        station.station_id,
                        d.isoformat(),
                        e.response.status_code,
                    )
                else:
                    raise
    finally:
        if own_client:
            cli.close()
    return out


def file_was_modified(path: Path, before: datetime) -> bool:
    """Return True if a cached file was modified before ``before`` (UTC).

    Used by sanity checks: NGS files for May 2024 should have an mtime in
    May 2024 (or later, if re-uploaded by NGS). Files modified before that
    indicate a partial or corrupt download.
    """
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return mtime < before
