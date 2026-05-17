"""Verify the CORS station catalog is well-formed."""

from __future__ import annotations

import pytest

from gannon_analysis.stations import (
    CORRIDOR_STATES,
    CORS_STATIONS,
    station_by_id,
    stations_by_state,
    stations_in_corridor,
)


def test_catalog_nonempty() -> None:
    assert len(CORS_STATIONS) >= 12, "need at least 12 stations for the analysis"


def test_corridor_states_covered() -> None:
    states_present = {s.state for s in CORS_STATIONS}
    for required in CORRIDOR_STATES:
        assert required in states_present, f"missing required state {required}"


def test_station_ids_are_lowercase_alphanumeric_4chars() -> None:
    for s in CORS_STATIONS:
        assert len(s.station_id) == 4, f"station id {s.station_id!r} not 4 chars"
        assert s.station_id == s.station_id.lower()
        assert s.station_id.isalnum()


def test_no_duplicate_station_ids() -> None:
    ids = [s.station_id for s in CORS_STATIONS]
    assert len(ids) == len(set(ids)), "duplicate station ids"


def test_lat_lon_within_continental_us() -> None:
    for s in CORS_STATIONS:
        assert 24.0 < s.latitude_deg < 50.0, f"{s.station_id} lat out of range"
        assert -125.0 < s.longitude_deg < -65.0, f"{s.station_id} lon out of range"


def test_truth_ecef_consistent_with_lat_lon() -> None:
    """Recompute lat/lon from ECEF and compare back."""
    import math

    a = 6378137.0
    e2 = 6.69437999014e-3
    for s in CORS_STATIONS:
        x, y, z = s.truth_ecef_m
        lon = math.atan2(y, x)
        p = math.hypot(x, y)
        lat = math.atan2(z, p * (1.0 - e2))
        for _ in range(5):
            n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
            h = p / math.cos(lat) - n
            lat = math.atan2(z, p * (1.0 - e2 * n / (n + h)))
        lat_deg = math.degrees(lat)
        lon_deg = math.degrees(lon)
        assert abs(lat_deg - s.latitude_deg) < 1e-4
        assert abs(lon_deg - s.longitude_deg) < 1e-4


def test_stations_in_corridor() -> None:
    corridor = stations_in_corridor()
    assert all(s.state in CORRIDOR_STATES for s in corridor)
    assert len(corridor) >= 12


def test_stations_by_state_case_insensitive() -> None:
    iowa_lower = stations_by_state("ia")
    iowa_upper = stations_by_state("IA")
    assert {s.station_id for s in iowa_lower} == {s.station_id for s in iowa_upper}
    assert all(s.state == "IA" for s in iowa_lower)


def test_station_by_id_case_insensitive() -> None:
    s = station_by_id("IAAL")
    assert s.station_id == "iaal"
    assert s.state == "IA"


def test_station_by_id_missing_raises() -> None:
    with pytest.raises(KeyError):
        station_by_id("zzzz")
