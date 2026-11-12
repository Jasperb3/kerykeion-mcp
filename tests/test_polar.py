"""
Polar-latitude behaviour.

kerykeion 5.6 silently clamped every latitude beyond +/-66 deg to exactly
+/-66 deg, which moved the Ascendant and every cusp (13 deg at Tromso). From
6.0 kerykeion keeps the true latitude and, where the Swiss Ephemeris refuses
Placidus or Koch inside a polar circle, substitutes Porphyry and records it
(polar_house_fallbacks). The server reports that fallback -- matching the
immanuel MCP server, so both engines' cusps agree.

Reference values for Tromso come from the immanuel server and are pinned
here against the live Swiss Ephemeris.
"""

import re

import pytest
import swisseph as swe

from kerykeion import AstrologicalSubjectFactory

from kerykeion_mcp.server import (
    fell_back,
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
    return AstrologicalSubjectFactory.from_birth_data(
        name="t", **place, houses_system_identifier=house_system, online=False, **kwargs,
    )


def swe_houses(subject, lat, house_system):
    return swe.houses(subject.julian_day, lat, subject.lng, house_system.encode())


def pair(first, second):
    return {
        **{f"{k}1": v for k, v in first.items()}, "name1": "a",
        **{f"{k}2": v for k, v in second.items()}, "name2": "b",
    }


# --- the true latitude and kerykeion's fallback record ----------------------

def test_subject_keeps_its_true_latitude():
    assert build(TROMSO, "W").lat == 69.65
    assert build(dict(TROMSO, lat=-77.85, lng=166.67, tz_str="Antarctica/McMurdo"), "W").lat == -77.85


def test_kerykeion_records_the_polar_fallback():
    # The server's reporting reads these; if kerykeion renames them, it breaks here.
    subject = build(TROMSO)
    assert subject.houses_system_identifier == "P"
    assert subject.effective_houses_system_identifier == "O"
    [record] = subject.polar_house_fallbacks
    assert (record.requested_house_system_identifier, record.used_house_system_identifier) == ("P", "O")
    assert record.used_latitude == 69.65
    assert build(dict(TROMSO, lat=66.4)).polar_house_fallbacks == []


# --- cusps against the Swiss Ephemeris and the immanuel reference ------------

def test_tromso_matches_immanuel_reference_within_one_arcminute():
    subject = build(TROMSO)
    assert subject.effective_houses_system_identifier == "O"
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
    # 66.4 deg is beyond kerykeion 5.6's old 66.0 clamp but outside the polar circle.
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
    assert subject.effective_houses_system_identifier == "O"
    assert fell_back(subject, house_system)
    want, ascmc = swe_houses(subject, place["lat"], "O")
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC


@pytest.mark.parametrize("house_system", ["O", "R", "C", "A", "W", "M"])
@pytest.mark.parametrize("place", POLAR_PLACES.values(), ids=POLAR_PLACES.keys())
def test_non_quadrant_systems_are_cast_as_asked_at_the_true_latitude(place, house_system):
    subject = build(place, house_system)
    assert subject.effective_houses_system_identifier == house_system
    assert not fell_back(subject, house_system)
    want, ascmc = swe_houses(subject, place["lat"], house_system)
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC
    assert arc(subject.ascendant.abs_pos, ascmc[0]) < ARCSEC


@pytest.mark.parametrize("house_system", ["R", "C"])
def test_reversed_cusps_are_cast(house_system):
    # kerykeion 5.6 could not place planets in these backwards-running cusps
    # (Longyearbyen, this moment); 6.x casts them, so the tool does too.
    place = POLAR_PLACES["Longyearbyen"]
    want, _ = swe.houses(swe.julday(1988, 12, 21, 8.0), place["lat"], place["lng"], house_system.encode())
    assert any((want[(i + 1) % 12] - want[i]) % 360 > 180 for i in range(12))
    result = generate_natal_chart(name="t", **place, house_system=house_system, output_format="text")
    assert result["status"] == "success", result
    assert "warnings" not in result


def test_sidereal_polar_chart_falls_back_too():
    subject = build(TROMSO, zodiac_type="Sidereal", sidereal_mode="LAHIRI")
    assert subject.effective_houses_system_identifier == "O"
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    want, _ = swe.houses_ex(subject.julian_day, 69.65, 18.95, b"O", swe.FLG_SIDEREAL)
    for got, expected in zip(cusps(subject), want):
        assert arc(got, expected) < ARCSEC


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
    assert 'house_system="Porphyry"' in result["text"]
    assert '<polar_house_fallback strategy="substitute_system" requested="Placidus" used="Porphyry"' in result["text"]
    assert re.search(r'<point name="Ascendant" [^>]*abs_pos="239.92"', result["text"])


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


def assert_mixed_reported(result, fallen, kept, kept_system="P (Placidus)"):
    """One subject fell back and the other kept the requested system."""
    assert result["status"] == "success", result
    settings = result["applied_settings"]
    assert settings["house_system_by_subject"] == {fallen: PLACIDUS_FALLBACK, kept: kept_system}
    assert settings["house_system"] == "mixed: " + "; ".join(
        f"{label} {system}" for label, system in settings["house_system_by_subject"].items())
    assert PLACIDUS_WARNING in result["warnings"]
    assert any(w.startswith(f"{fallen}'s houses are {PLACIDUS_FALLBACK}") and f"{kept}'s are {kept_system}" in w
               for w in result["warnings"]), result["warnings"]


def test_synastry_with_one_polar_subject_reports_per_subject():
    result = generate_synastry_chart(**pair(TROMSO, LONDON), output_format="text")
    assert_mixed_reported(result, "person1", "person2")
    assert result["applied_settings"]["house_system"] == (
        "mixed: person1 O (Porphyry, polar fallback from P Placidus); person2 P (Placidus)")
    aspects = get_synastry_aspects(**pair(LONDON, TROMSO))
    assert_mixed_reported(aspects, "person2", "person1")


def test_synastry_mixed_warning_leads_the_text():
    result = generate_synastry_chart(**pair(LONDON, POLAR_PLACES["McMurdo"]), output_format="text")
    assert_mixed_reported(result, "person2", "person1")
    for warning in result["warnings"]:
        assert f"Warning: {warning}" in result["text"].split("<", 1)[0]


def test_synastry_with_two_polar_subjects_is_not_mixed():
    result = generate_synastry_chart(**pair(TROMSO, POLAR_PLACES["McMurdo"]), output_format="text")
    assert_fallback_reported(result)
    assert result["warnings"] == [PLACIDUS_WARNING]


def test_composite_with_one_polar_subject_casts_both_with_porphyry():
    result = generate_composite_chart(**pair(TROMSO, LONDON), output_format="text")
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "person1": PLACIDUS_FALLBACK, "person2": "O (Porphyry, to match person1)",
    }
    assert any("person2 was also cast with Porphyry" in w for w in result["warnings"])
    assert 'house_system="Porphyry"' in result["text"]



def test_composite_with_two_polar_subjects():
    result = generate_composite_chart(**pair(TROMSO, POLAR_PLACES["McMurdo"]), output_format="text")
    assert_fallback_reported(result)
    assert result["applied_settings"]["house_system_by_subject"] == {
        "person1": PLACIDUS_FALLBACK, "person2": PLACIDUS_FALLBACK,
    }
    assert result["warnings"] == [PLACIDUS_WARNING]


TRANSIT_TIME = dict(transit_year=2026, transit_month=11, transit_day=12, transit_hour=12, transit_minute=0)


def natal_args(place):
    return {f"natal_{k}": v for k, v in place.items()} | {"natal_name": "t"}


def test_transit_with_polar_natal_place():
    result = generate_transit_chart(
        **natal_args(TROMSO), transit_lat=51.5, transit_lng=0.0, transit_tz_str="Europe/London",
        **TRANSIT_TIME, output_format="text",
    )
    assert_mixed_reported(result, "natal", "transit")


def test_transit_with_polar_transit_place():
    result = generate_transit_chart(
        **natal_args(LONDON), transit_lat=69.65, transit_lng=18.95, transit_tz_str="Europe/Oslo",
        **TRANSIT_TIME, output_format="text",
    )
    assert_mixed_reported(result, "transit", "natal")


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
    assert 'house_system="Porphyry"' in result["text"]


def test_return_moment_does_not_depend_on_the_search_latitude():
    # kerykeion 5.6 needed a polar retry here (it searched from +/-66 deg);
    # kept as a guard that the return moment is independent of latitude.
    at = lambda lat: generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE, return_lat=lat, return_lng=18.95,
        return_tz_str="Europe/Oslo", output_format="text",
    )
    moments = {at(lat)["return_date"] for lat in (1.0, 45.0, 66.0, 66.4, 69.65, -69.65)}
    assert len(moments) == 1


def test_return_moment_does_not_depend_on_the_search_location():
    # The return moment must not depend on where the search runs.
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


# --- exactly at a pole: no horizon, so no Ascendant, MC or houses ------------

POLE = dict(LONDON, lat=-90.0, lng=0.0, tz_str="UTC")


def assert_pole_error(result):
    assert result["status"] == "error", result
    assert result["type"] == "PoleError"
    assert "pole" in result["error"].lower()
    assert "89.99" in result["hint"]
    assert "birth time" in result["hint"]


@pytest.mark.parametrize("lat", [90.0, -90.0])
def test_pole_charts_are_rejected_for_every_subject(lat):
    pole = dict(POLE, lat=lat)
    assert_pole_error(generate_natal_chart(name="t", **pole, output_format="text"))
    assert_pole_error(generate_event_chart(event_name="t", **pole, output_format="text"))
    assert_pole_error(get_aspects(name="t", **pole))
    assert_pole_error(get_chart_patterns(name="t", **pole))
    assert_pole_error(get_current_positions(lat=lat, lng=0.0, tz_str="UTC"))
    assert_pole_error(generate_synastry_chart(**pair(LONDON, pole), output_format="text"))
    assert_pole_error(get_synastry_aspects(**pair(pole, LONDON)))
    assert_pole_error(generate_composite_chart(**pair(LONDON, pole), output_format="text"))
    assert_pole_error(generate_transit_chart(
        **natal_args(pole), transit_lat=51.5, transit_lng=0.0, transit_tz_str="Europe/London",
        **TRANSIT_TIME, output_format="text"))
    assert_pole_error(generate_transit_chart(
        **natal_args(LONDON), transit_lat=lat, transit_lng=0.0, transit_tz_str="UTC",
        **TRANSIT_TIME, output_format="text"))
    assert_pole_error(generate_planetary_return(name="t", **pole, **RETURN_DATE, output_format="text"))
    assert_pole_error(generate_planetary_return(
        name="t", **LONDON, **RETURN_DATE, return_lat=lat, return_lng=0.0, return_tz_str="UTC",
        output_format="text"))


def test_just_off_the_pole_is_cast():
    result = generate_natal_chart(name="t", **dict(POLE, lat=-89.99), output_format="text")
    assert result["status"] == "success", result


def test_other_errors_carry_no_type(birth_rome):
    result = generate_natal_chart(**dict(birth_rome, lng=500.0), output_format="text")
    assert result["status"] == "error"
    assert "type" not in result


# --- the angles' motion --------------------------------------------------------
# The angles turn with the sky (~360 degrees a day), not as planets move, and
# inside the polar circles the Ascendant even runs backwards for part of the
# day. A motion flag or speed on them reads as planetary motion, so no output
# carries either; planets and nodes keep theirs.

SVALBARD_BACKWARD = dict(year=1990, month=6, day=15, hour=2, minute=0, lat=78.22, lng=15.63, tz_str="UTC")
MCMURDO = dict(year=1992, month=12, day=21, hour=3, minute=30, lat=-77.846, lng=166.676, tz_str="Antarctica/McMurdo")
ANGLE_POINT = re.compile(r'<point name="(?:Ascendant|Descendant|Medium_Coeli|Imum_Coeli)" [^>]*>')


def assert_angles_carry_no_motion(text):
    angles = ANGLE_POINT.findall(text)
    assert angles, "no angle points in the text"
    for element in angles:
        assert "motion=" not in element and "speed=" not in element, element
    for name in ("Sun", "True_North_Lunar_Node"):
        assert re.search(rf'<point name="{name}" [^>]*motion="(?:direct|retrograde)" speed="-?[\d.]+"', text), name


def every_text_output(place):
    date = {k: v for k, v in place.items() if k in ("year", "month", "day", "hour", "minute")}
    return {
        "natal": generate_natal_chart(name="t", **place, output_format="text"),
        "synastry": generate_synastry_chart(**pair(LONDON, place), output_format="text"),
        "transit": generate_transit_chart(
            **natal_args(LONDON), transit_lat=place["lat"], transit_lng=place["lng"],
            transit_tz_str=place["tz_str"], **{f"transit_{k}": v for k, v in date.items()},
            output_format="text"),
        "return": generate_planetary_return(name="t", **place, return_year=2026, output_format="text"),
        "event": generate_event_chart(event_name="t", **place, output_format="text"),
        "current": get_current_positions(lat=place["lat"], lng=place["lng"], tz_str=place["tz_str"]),
    }


@pytest.mark.parametrize("place", [LONDON, MCMURDO, SVALBARD_BACKWARD], ids=["london", "mcmurdo", "svalbard"])
def test_no_output_gives_the_angles_a_motion_or_speed(place):
    for kind, result in every_text_output(place).items():
        assert result["status"] == "success", (kind, result)
        assert_angles_carry_no_motion(result["text"])


def test_composite_angles_carry_no_motion():
    text = generate_composite_chart(**pair(LONDON, MCMURDO), output_format="text")["text"]
    for element in ANGLE_POINT.findall(text):
        assert "motion=" not in element and "speed=" not in element, element


def test_a_backward_polar_ascendant_gets_no_retrograde_glyph(tmp_output_dir):
    result = generate_natal_chart(name="t", **SVALBARD_BACKWARD, house_system="W", output_format="images")
    svg = open(result["svg_path"], encoding="utf-8").read()
    for name in ("Ascendant", "Descendant", "Medium_Coeli", "Imum_Coeli"):
        elements = re.findall(rf"<g [^>]*kr:slug='{name}'[^>]*>", svg)
        assert elements, name
        for element in elements:
            assert "kr:retrograde" not in element, element
    assert "kr:slug='Pluto' kr:retrograde" in svg  # planets keep the glyph


def test_angles_keep_their_speed_for_aspect_movement():
    # The speed stays in the model: kerykeion times applying/separating
    # aspects to an angle from it.
    from kerykeion_mcp.server import SubjectFactory
    subject = SubjectFactory.from_birth_data(name="t", **SVALBARD_BACKWARD, houses_system_identifier="W", online=False)
    assert subject.ascendant.speed == pytest.approx(-113.68, abs=0.01)
    assert subject.ascendant.retrograde is None
