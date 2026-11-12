"""
Polar-latitude behaviour.

kerykeion 5.6 silently clamps every latitude beyond +/-66 deg to exactly
+/-66 deg, which moves the Ascendant and every cusp (13 deg at Tromso). The
server removes that clamp (kerykeion_mcp.polar) and, where the Swiss Ephemeris
refuses Placidus or Koch inside a polar circle, falls back to Porphyry and
says so -- matching the immanuel MCP server, so both engines' cusps agree.

Reference values for Tromso come from the immanuel server and are pinned
here against the live Swiss Ephemeris.
"""

import inspect

import pytest
import swisseph as swe

import kerykeion.astrological_subject_factory as asf
from kerykeion import AstrologicalSubjectFactory, utilities

from kerykeion_mcp import polar
from kerykeion_mcp.server import (
    generate_natal_chart,
    generate_event_chart,
    generate_synastry_chart,
    generate_transit_chart,
    generate_composite_chart,
    generate_planetary_return,
    get_current_positions,
    get_aspects,
    get_synastry_aspects,
    get_chart_patterns,
)

ARCMIN = 1 / 60
ARCSEC = 1 / 3600
HOUSES = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
          "eighth", "ninth", "tenth", "eleventh", "twelfth"]

TROMSO = dict(year=1988, month=12, day=21, hour=9, minute=0,
              lat=69.65, lng=18.95, tz_str="Europe/Oslo")
LONDON = dict(year=1990, month=6, day=1, hour=12, minute=0,
              lat=51.5074, lng=-0.1278, tz_str="Europe/London")

# From the immanuel MCP server: Tromso, default Placidus -> Porphyry.
TROMSO_ASC = 239.9184
TROMSO_MC = 231.4858
TROMSO_CUSPS = [239.9184, 297.1075, 354.2967, 51.4858, 54.2967, 57.1075,
                59.9184, 117.1075, 174.2967, 231.4858, 234.2967, 237.1075]

PLACIDUS_WARNING = (
    "A chart in this response lies inside a polar circle, where Placidus houses "
    "are undefined, so the Swiss Ephemeris used Porphyry cusps instead. The "
    "Ascendant and MC are unaffected. Pass house_system=\"W\" (or another "
    "non-polar system) to avoid the fallback."
)
PLACIDUS_FALLBACK = "O (Porphyry, polar fallback from P Placidus)"


def arc(a, b):
    return abs((a - b + 180) % 360 - 180)


def cusps(subject):
    return [getattr(subject, f"{name}_house").abs_pos for name in HOUSES]


def build(place, house_system="P", **kwargs):
    return polar.build_subject(
        AstrologicalSubjectFactory.from_birth_data,
        name="t", **place, houses_system_identifier=house_system, online=False, **kwargs,
    )


def swe_houses(subject, lat, house_system):
    return swe.houses(subject.julian_day, lat, subject.lng, house_system.encode())


def pair(first, second):
    return {
        **{f"{k}1": v for k, v in first.items()}, "name1": "a",
        **{f"{k}2": v for k, v in second.items()}, "name2": "b",
    }


# --- the clamp shim -----------------------------------------------------------

def test_shim_is_installed_by_importing_the_server():
    assert polar.installed()


def test_subject_keeps_its_true_latitude():
    assert build(TROMSO, "W").lat == 69.65
    assert build(dict(TROMSO, lat=-77.85, lng=166.67, tz_str="Antarctica/McMurdo"), "W").lat == -77.85


def test_kerykeion_still_clamps_without_the_shim():
    # If this fails, kerykeion changed its clamp; re-check polar.py.
    assert utilities.check_and_adjust_polar_latitude(69.65) == 66.0
    assert utilities.check_and_adjust_polar_latitude(-69.65) == -66.0


def test_kerykeion_still_calls_the_clamp_by_this_name():
    # The shim replaces this module-level name; if kerykeion renames or moves
    # the function, or stops calling it here, the shim silently does nothing.
    assert hasattr(asf, "check_and_adjust_polar_latitude")
    source = inspect.getsource(asf.LocationData.prepare_for_calculation)
    assert "check_and_adjust_polar_latitude(self.lat)" in source


def test_shim_refuses_an_unchecked_kerykeion_version(monkeypatch):
    monkeypatch.setattr(polar.metadata, "version", lambda name: "5.7.0")
    with pytest.raises(RuntimeError, match="5.7.0"):
        polar.install()


# --- cusps against the Swiss Ephemeris and the immanuel reference ------------

def test_tromso_matches_immanuel_reference_within_one_arcminute():
    subject = build(TROMSO)
    assert subject.houses_system_identifier == "O"
    assert arc(subject.ascendant.abs_pos, TROMSO_ASC) < ARCMIN
    assert arc(subject.medium_coeli.abs_pos, TROMSO_MC) < ARCMIN
    for got, want in zip(cusps(subject), TROMSO_CUSPS):
        assert arc(got, want) < ARCMIN


def test_tromso_matches_swiss_ephemeris_porphyry_to_the_arcsecond():
    subject = build(TROMSO)
    want, ascmc = swe_houses(subject, 69.65, "O")
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC
    assert arc(subject.medium_coeli.abs_pos, ascmc[1]) < ARCSEC


@pytest.mark.parametrize("house_system", ["P", "K"])
def test_just_outside_the_circle_is_real_quadrant_houses_at_the_true_latitude(house_system):
    # 66.4 deg is beyond kerykeion's 66.0 clamp but outside the polar circle.
    subject = build(dict(TROMSO, lat=66.4), house_system)
    assert subject.houses_system_identifier == house_system
    assert subject.lat == 66.4
    want, ascmc = swe_houses(subject, 66.4, house_system)
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC


POLAR_PLACES = {
    "66.7N": dict(TROMSO, lat=66.7),
    "Tromso": TROMSO,
    "Longyearbyen": dict(TROMSO, lat=78.22, lng=15.65, tz_str="Arctic/Longyearbyen"),
    "McMurdo": dict(TROMSO, lat=-77.85, lng=166.67, tz_str="Antarctica/McMurdo"),
}


@pytest.mark.parametrize("house_system", ["P", "K"])
@pytest.mark.parametrize("place", POLAR_PLACES.values(), ids=POLAR_PLACES.keys())
def test_inside_the_circle_quadrant_houses_fall_back_to_porphyry(place, house_system):
    with pytest.raises(swe.Error, match="polar circle"):
        swe.houses_ex2(swe.julday(1988, 12, 21, 8.0), place["lat"], place["lng"], house_system.encode())
    subject = build(place, house_system)
    assert subject.houses_system_identifier == "O"
    assert polar.fell_back(subject, house_system)
    want, ascmc = swe_houses(subject, place["lat"], "O")
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC


CAST_AS_ASKED = [
    (place_id, house_system)
    for place_id in POLAR_PLACES
    for house_system in ["O", "R", "C", "A", "W", "M"]
    # At this moment Longyearbyen's Regiomontanus/Campanus cusps run
    # backwards; see test_reversed_cusps_are_an_educational_error.
    if not (place_id == "Longyearbyen" and house_system in "RC")
]


@pytest.mark.parametrize("place_id, house_system", CAST_AS_ASKED)
def test_non_quadrant_systems_are_cast_as_asked_at_the_true_latitude(place_id, house_system):
    place = POLAR_PLACES[place_id]
    subject = build(place, house_system)
    assert subject.houses_system_identifier == house_system
    assert not polar.fell_back(subject, house_system)
    want, ascmc = swe_houses(subject, place["lat"], house_system)
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC


@pytest.mark.parametrize("house_system", ["R", "C"])
def test_reversed_cusps_are_an_educational_error(house_system):
    place = POLAR_PLACES["Longyearbyen"]
    want, _ = swe.houses(swe.julday(1988, 12, 21, 8.0), place["lat"], place["lng"], house_system.encode())
    # The Swiss Ephemeris casts them, but some consecutive cusps step backwards.
    assert any((want[(i + 1) % 12] - want[i]) % 360 > 180 for i in range(12))
    result = generate_natal_chart(name="t", **place, house_system=house_system, output_format="text")
    assert result["status"] == "error"
    assert "out of zodiacal order" in result["error"]
    assert "Porphyry" in result["hint"] and "Whole Sign" in result["hint"]


def test_sidereal_polar_chart_falls_back_too():
    subject = build(TROMSO, zodiac_type="Sidereal", sidereal_mode="LAHIRI")
    assert subject.houses_system_identifier == "O"
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    want, _ = swe.houses_ex(subject.julian_day, 69.65, 18.95, b"O", swe.FLG_SIDEREAL)
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC


def test_non_polar_swiss_ephemeris_errors_are_not_retried():
    def broken(**kwargs):
        raise swe.Error("some other failure")
    with pytest.raises(swe.Error, match="some other failure"):
        polar.build_subject(broken, houses_system_identifier="P")


# --- reporting through the tools ----------------------------------------------

def assert_fallback_reported(result, warning=PLACIDUS_WARNING):
    assert result["status"] == "success", result
    assert result["applied_settings"]["house_system"] == PLACIDUS_FALLBACK
    assert warning in result["warnings"]


def assert_not_reported(result, house_system="P (Placidus)"):
    assert result["status"] == "success", result
    assert result["applied_settings"]["house_system"] == house_system
    assert "warnings" not in result
    assert "house_system_by_subject" not in result["applied_settings"]


def test_natal_reports_the_fallback_everywhere():
    result = generate_natal_chart(name="t", **TROMSO, output_format="text")
    assert_fallback_reported(result)
    assert result["warnings"] == [PLACIDUS_WARNING]
    assert result["text"].startswith(f"Warning: {PLACIDUS_WARNING}\n\n")
    assert "House system: Porphyry" in result["text"]
    assert "absolute position 239.92" in result["text"]  # Ascendant


def test_koch_fallback_names_koch():
    result = generate_natal_chart(name="t", **TROMSO, house_system="K", output_format="text")
    assert result["applied_settings"]["house_system"] == "O (Porphyry, polar fallback from K Koch)"
    assert result["warnings"] == [PLACIDUS_WARNING.replace("Placidus", "Koch")]


def test_non_quadrant_polar_chart_has_no_warning():
    assert_not_reported(
        generate_natal_chart(name="t", **TROMSO, house_system="W", output_format="text"),
        "W (Whole Sign)",
    )


def test_just_outside_the_circle_has_no_warning():
    assert_not_reported(generate_natal_chart(name="t", **dict(TROMSO, lat=66.4), output_format="text"))


def test_wheel_shows_true_latitude_and_porphyry(tmp_output_dir):
    result = generate_natal_chart(name="t", **TROMSO, output_format="all", output_dir=tmp_output_dir)
    svg = open(result["svg_path"], encoding="utf-8").read()
    assert "Latitude: 69°39" in svg
    assert "66°0'0" not in svg
    assert "Porphyry" in svg
    assert "Placidus" not in svg


def test_event_chart_reports_the_fallback():
    assert_fallback_reported(generate_event_chart(event_name="t", **TROMSO, output_format="text"))


def test_get_aspects_and_patterns_report_the_fallback():
    assert_fallback_reported(get_aspects(name="t", **TROMSO))
    assert_fallback_reported(get_chart_patterns(name="t", **TROMSO))


def test_planet_only_outputs_do_not_depend_on_the_house_system():
    def planet_aspects(result):
        angles = ("Ascendant", "Descendant", "Medium_Coeli", "Imum_Coeli")
        return [a for a in result["aspects"] if a["planet1"] not in angles and a["planet2"] not in angles]
    placidus = get_aspects(name="t", **TROMSO)
    whole = get_aspects(name="t", **TROMSO, house_system="W")
    assert planet_aspects(placidus) == planet_aspects(whole)
    # Angles do not depend on the house system either.
    assert placidus["aspects"] == whole["aspects"]
    patterns_p = get_chart_patterns(name="t", **TROMSO)
    patterns_w = get_chart_patterns(name="t", **TROMSO, house_system="W")
    assert patterns_p["patterns"] == patterns_w["patterns"]


def test_current_positions_report_the_fallback():
    assert_fallback_reported(get_current_positions(lat=69.65, lng=18.95, tz_str="Europe/Oslo"))


def test_synastry_with_one_polar_subject_reports_per_subject():
    result = generate_synastry_chart(**pair(TROMSO, LONDON), output_format="text")
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "person1": PLACIDUS_FALLBACK, "person2": "P (Placidus)",
    }
    aspects = get_synastry_aspects(**pair(LONDON, TROMSO))
    assert_fallback_reported(aspects)
    assert aspects["applied_settings"]["house_system_by_subject"] == {
        "person1": "P (Placidus)", "person2": PLACIDUS_FALLBACK,
    }


def test_composite_with_one_polar_subject_casts_both_with_porphyry():
    result = generate_composite_chart(**pair(TROMSO, LONDON), output_format="text")
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "person1": PLACIDUS_FALLBACK, "person2": "O (Porphyry, to match person1)",
    }
    assert any("person2 was also cast with Porphyry" in w for w in result["warnings"])
    assert "House system: Porphyry" in result["text"]


TRANSIT_TIME = dict(transit_year=2026, transit_month=11, transit_day=12, transit_hour=12, transit_minute=0)


def natal_args(place):
    return {f"natal_{k}": v for k, v in place.items()} | {"natal_name": "t"}


def test_transit_with_polar_natal_place():
    result = generate_transit_chart(
        **natal_args(TROMSO), transit_lat=51.5, transit_lng=0.0, transit_tz_str="Europe/London",
        **TRANSIT_TIME, output_format="text",
    )
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "natal": PLACIDUS_FALLBACK, "transit": "P (Placidus)",
    }


def test_transit_with_polar_transit_place():
    result = generate_transit_chart(
        **natal_args(LONDON), transit_lat=69.65, transit_lng=18.95, transit_tz_str="Europe/Oslo",
        **TRANSIT_TIME, output_format="text",
    )
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "natal": "P (Placidus)", "transit": PLACIDUS_FALLBACK,
    }


RETURN_DATE = dict(return_year=2026, return_month=1, return_day=1)


def test_solar_return_for_a_polar_natal():
    result = generate_planetary_return(name="t", **TROMSO, **RETURN_DATE, output_format="text")
    assert_fallback_reported(result)


def test_solar_return_relocated_into_the_circle():
    result = generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE,
        return_lat=69.65, return_lng=18.95, return_tz_str="Europe/Oslo", output_format="text",
    )
    assert_fallback_reported(result)
    assert "House system: Porphyry" in result["text"]


def test_return_moment_does_not_depend_on_the_search_latitude():
    # The polar retry in generate_planetary_return searches from +/-66 deg;
    # that is only sound while the return moment is independent of latitude.
    at = lambda lat: generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE, return_lat=lat, return_lng=18.95,
        return_tz_str="Europe/Oslo", output_format="text",
    )
    moments = {at(lat)["return_date"] for lat in (1.0, 45.0, 66.0, 66.4, 69.65, -69.65)}
    assert len(moments) == 1


def test_return_moment_does_not_depend_on_the_search_location():
    # generate_planetary_return also substitutes a placeholder for a 0.0
    # coordinate (kerykeion treats it as missing); sound only while the
    # moment is independent of where the search runs.
    at = lambda lat, lng: generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE, return_lat=lat, return_lng=lng,
        return_tz_str="Europe/London", output_format="text",
    )["return_date"]
    assert len({at(51.48, lng) for lng in (-120.0, -0.01, 0.01, 30.0, 150.0)}) == 1


@pytest.mark.parametrize("lat, lng", [(51.4779, 0.0), (0.0, 30.0), (0.0, 0.0)])
def test_return_at_zero_coordinates(lat, lng):
    result = generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE, return_lat=lat, return_lng=lng,
        return_tz_str="Europe/London", output_format="text",
    )
    assert result["status"] == "success", result
    home = generate_planetary_return(name="t", **LONDON, **RETURN_DATE, output_format="text")
    assert result["return_date"] == home["return_date"]


def test_lunar_return_relocated_out_of_the_circle():
    result = generate_planetary_return(
        name="t", **TROMSO, return_type="Lunar", return_year=2026, return_month=11, return_day=1,
        return_lat=51.5, return_lng=-0.12, return_tz_str="Europe/London", output_format="text",
    )
    assert_not_reported(result)
