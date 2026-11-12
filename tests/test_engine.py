"""
The ephemeris engine: kerykeion 6 on the Swiss Ephemeris, with its data files.

kerykeion 6 defaults to libephemeris, and its swisseph backend silently drops
to the Moshier ephemeris without the .se1 files. Either would quietly break
agreement with the immanuel MCP server, which the master-astrologer skill
relies on.
"""

import pytest
import swisseph as swe

import kerykeion.ephemeris_backend.backend as backend
from kerykeion import AstrologicalSubjectFactory

from kerykeion_mcp import engine

ARCSEC = 1 / 3600

# immanuel 1.8.0 (Swiss Ephemeris with its bundled .se1 files), Tromso
# 1988-12-21 09:00 Europe/Oslo 69.65N 18.95E, tropical longitudes.
IMMANUEL_TROMSO = {
    "sun": 269.6833358348879,
    "moon": 65.92002347678114,
    "mercury": 280.80175344813114,
    "venus": 244.47185904470206,
    "mars": 14.976509551893061,
    "jupiter": 57.59184644615487,
    "saturn": 274.33225456930774,
    "chiron": 94.56015014689726,
}


def arc(a, b):
    return abs((a - b + 180) % 360 - 180)


def test_backend_is_swiss_ephemeris_with_data_files():
    assert backend.BACKEND_NAME == "swisseph"
    engine.check()


def test_positions_come_from_the_data_files_not_moshier():
    subject = AstrologicalSubjectFactory.from_birth_data(
        "t", 1990, 6, 15, 12, 0, lat=41.9, lng=12.5, tz_str="UTC", online=False)
    swe.set_ephe_path(backend.EPHE_DATA_PATH)
    moon, flags = swe.calc_ut(subject.julian_day, swe.MOON, swe.FLG_SWIEPH)
    assert not flags & swe.FLG_MOSEPH
    assert arc(subject.moon.abs_pos, moon[0]) < ARCSEC
    # Moshier differs by ~0.4": enough to tell the two apart.
    swe.set_ephe_path("/nonexistent")
    moshier, _ = swe.calc_ut(subject.julian_day, swe.MOON, swe.FLG_SWIEPH)
    swe.set_ephe_path(backend.EPHE_DATA_PATH)
    assert arc(subject.moon.abs_pos, moshier[0]) > 0.1 * ARCSEC


def test_planets_match_immanuel():
    subject = AstrologicalSubjectFactory.from_birth_data(
        "t", 1988, 12, 21, 9, 0, lat=69.65, lng=18.95, tz_str="Europe/Oslo",
        houses_system_identifier="W", online=False)
    for name, longitude in IMMANUEL_TROMSO.items():
        assert arc(getattr(subject, name).abs_pos, longitude) < ARCSEC, name


def test_check_refuses_another_backend(monkeypatch):
    monkeypatch.setattr(backend, "BACKEND_NAME", "libephemeris")
    with pytest.raises(RuntimeError, match="libephemeris"):
        engine.check()


def test_check_refuses_missing_data_files(monkeypatch, tmp_path):
    (tmp_path / "seas_18.se1").write_bytes(b"")
    monkeypatch.setattr(backend, "EPHE_DATA_PATH", str(tmp_path))
    with pytest.raises(RuntimeError, match="sepl_18.se1, semo_18.se1.*swisseph_setup"):
        engine.check()
