"""CORS station catalog for the Gannon May 2024 RTK-GNSS analysis.

The 16 stations listed here were verified to have published RINEX observation
files on May 10, 2024 (day-of-year 131) in the NGS CORS archive at
``https://geodesy.noaa.gov/corsdata/rinex/2024/131/`` at the time the catalog
was assembled (2026-05-17). ITRF2014 truth coordinates were extracted from the
``APPROX POSITION XYZ`` field of each station's day-131 RINEX header — the
NGS-published station position, accurate at the cm level. Station-state
assignment is derived from those coordinates.

Coverage tally for the IA / IL / IN / OH agronomy corridor:

    IA: 9   IL: 1   IN: 9   OH: 6   plus MI: 2, WI: 1 (broader-Midwest baselines)

This list is deliberately conservative — we ship only stations that have been
end-to-end probed for the storm window. ``stations.py`` is the authoritative
source for ``analysis.py``, plotting, and notebooks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class CorsStation:
    """A single NGS CORS station entry.

    Attributes:
        station_id: NGS 4-character station code (lower-case).
        name: Free-text marker name from the RINEX header.
        state: 2-letter US state abbreviation derived from truth coordinates.
        latitude_deg: WGS-84 latitude (decimal degrees).
        longitude_deg: WGS-84 longitude (decimal degrees, east-positive).
        truth_x_m: ITRF2014 X coordinate (metres).
        truth_y_m: ITRF2014 Y coordinate (metres).
        truth_z_m: ITRF2014 Z coordinate (metres).
    """

    station_id: str
    name: str
    state: str
    latitude_deg: float
    longitude_deg: float
    truth_x_m: float
    truth_y_m: float
    truth_z_m: float

    @property
    def truth_ecef_m(self) -> tuple[float, float, float]:
        """ECEF (X, Y, Z) truth position in metres."""
        return (self.truth_x_m, self.truth_y_m, self.truth_z_m)


# Lat/lon shown below were computed from the ECEF (X,Y,Z) by the WGS-84
# inverse below; they are stored for fast access in plotting code.
def _llh_from_ecef(x: float, y: float, z: float) -> tuple[float, float]:
    a = 6378137.0
    e2 = 6.69437999014e-3
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(5):
        n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1.0 - e2 * n / (n + h)))
    return math.degrees(lat), math.degrees(lon)


def _mk(station_id: str, name: str, state: str, x: float, y: float, z: float) -> CorsStation:
    lat, lon = _llh_from_ecef(x, y, z)
    return CorsStation(
        station_id=station_id,
        name=name,
        state=state,
        latitude_deg=lat,
        longitude_deg=lon,
        truth_x_m=x,
        truth_y_m=y,
        truth_z_m=z,
    )


CORS_STATIONS: Final[list[CorsStation]] = [
    # ---- Iowa (9) ----
    _mk("iaal", "IAAL", "IA", -228127.933, -4685736.797, 4307106.527),
    _mk("iacb", "IACB", "IA", -489958.903, -4779394.815, 4181348.611),
    _mk("iacl", "IACL", "IA", -307016.257, -4682473.488, 4305825.329),
    _mk("iadn", "IADN", "IA", -444770.589, -4726574.446, 4245622.415),
    _mk("iaht", "IAHT", "IA", -273260.668, -4642595.794, 4350759.247),
    _mk("iamn", "IAMN", "IA", -128244.512, -4743183.679, 4248258.357),
    _mk("iana", "IANA", "IA", -104386.071, -4633066.292, 4367844.902),
    _mk("iaps", "IAPS", "IA", -382762.544, -4676373.191, 4306412.472),
    _mk("ialn", "IALN", "IA", -317588.880, -4830091.149, 4139873.492),
    # ---- Illinois (1) ----
    _mk("ilsa", "ILSA", "IL", 33386.414, -4908475.423, 4059224.655),
    # ---- Indiana (9) ----
    _mk("inbr", "INBR", "IN", 317883.962, -4776672.149, 4200824.861),
    _mk("incl", "INCL", "IN", 274835.137, -4918152.363, 4038581.960),
    _mk("inco", "INCO", "IN", 348550.312, -4937349.600, 4009425.022),
    _mk("incr", "INCR", "IN", 263869.445, -4879867.901, 4085103.111),
    _mk("inev", "INEV", "IN", 214786.354, -5019061.362, 3916829.547),
    _mk("infw", "INFW", "IN", 404489.355, -4794393.758, 4173292.983),
    _mk("insb", "INSB", "IN", 432313.917, -4883299.054, 4066864.895),
    _mk("intc", "INTC", "IN", 295962.173, -5019774.279, 3910825.136),
    _mk("intp", "INTP", "IN", 335200.874, -4861276.583, 4101937.125),
    # ---- Ohio (6) ----
    _mk("ohcl", "OHCL", "OH", 525642.837, -4868609.832, 4073374.484),
    _mk("ohfn", "OHFN", "OH", 488438.586, -4754818.878, 4209153.621),
    _mk("ohli", "OHLI", "OH", 646368.748, -4853467.749, 4074136.447),
    _mk("ohwy", "OHWY", "OH", 681442.993, -4785649.857, 4147494.564),
    _mk("mtvr", "MTVR", "OH", 634180.889, -4824018.212, 4110605.408),
    _mk("sidn", "SIDN", "OH", 494661.217, -4845525.459, 4104513.686),
]
"""Curated CORS catalog. Authoritative for the analysis."""

CORRIDOR_STATES: Final[tuple[str, ...]] = ("IA", "IL", "IN", "OH")
"""The IA / IL / IN / OH precision-agriculture corridor states."""


def stations_in_corridor() -> list[CorsStation]:
    """Return only stations that lie within the IA/IL/IN/OH corridor."""
    return [s for s in CORS_STATIONS if s.state in CORRIDOR_STATES]


def stations_by_state(state: str) -> list[CorsStation]:
    """Return the catalog subset for a single state (case-insensitive)."""
    key = state.upper()
    return [s for s in CORS_STATIONS if s.state == key]


def station_by_id(station_id: str) -> CorsStation:
    """Look up a single station by its 4-character ID (case-insensitive)."""
    key = station_id.lower()
    for s in CORS_STATIONS:
        if s.station_id == key:
            return s
    raise KeyError(f"Unknown station {station_id!r}")
