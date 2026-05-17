"""gannon-storm-rtk-analysis — see README.md.

Retrospective analysis of RTK-GNSS positioning error during the May 10-12, 2024
Gannon G5 superstorm. Pulls NGS CORS RINEX for Iowa / Illinois / Indiana / Ohio,
computes per-station 2D horizontal positioning error envelopes, and correlates
with NOAA SWPC indices (Kp, Dst, proton flux).
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
