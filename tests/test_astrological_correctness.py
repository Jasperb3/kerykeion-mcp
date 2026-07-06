"""
Tests for Phase 2 astrological-correctness fixes:
F2 (location labels), F4 (sidereal parity), F7 (transit house system),
F8 (planetary return relocation / lunar-return date semantics).
"""

from datetime import datetime, timedelta

from kerykeion_mcp.server import (
    generate_natal_chart,
    generate_synastry_chart,
    generate_transit_chart,
    generate_planetary_return,
)


def test_natal_chart_no_longer_labeled_greenwich(birth_rome):
    result = generate_natal_chart(**birth_rome, output_format="text")
    assert "Greenwich" not in result["text"]


def test_natal_chart_uses_provided_city(birth_rome):
    result = generate_natal_chart(**birth_rome, city="Rome", output_format="text")
    assert "Rome" in result["text"]


def test_sidereal_lahiri_natal_differs_from_tropical(birth_rome):
    tropical = generate_natal_chart(**birth_rome, output_format="text")
    sidereal = generate_natal_chart(
        **birth_rome, zodiac_type="Sidereal", sidereal_mode="LAHIRI", output_format="text"
    )
    assert tropical["status"] == "success"
    assert sidereal["status"] == "success"
    assert tropical["text"] != sidereal["text"]
    assert sidereal["applied_settings"]["sidereal_mode"] == "LAHIRI"


def test_synastry_accepts_and_applies_zodiac_params(birth_rome, birth_london):
    result = generate_synastry_chart(
        name1=birth_rome["name"], year1=birth_rome["year"], month1=birth_rome["month"],
        day1=birth_rome["day"], hour1=birth_rome["hour"], minute1=birth_rome["minute"],
        lat1=birth_rome["lat"], lng1=birth_rome["lng"], tz_str1=birth_rome["tz_str"],
        name2=birth_london["name"], year2=birth_london["year"], month2=birth_london["month"],
        day2=birth_london["day"], hour2=birth_london["hour"], minute2=birth_london["minute"],
        lat2=birth_london["lat"], lng2=birth_london["lng"], tz_str2=birth_london["tz_str"],
        zodiac_type="Sidereal", sidereal_mode="LAHIRI",
        output_format="text",
    )
    assert result["status"] == "success"
    assert result["applied_settings"]["sidereal_mode"] == "LAHIRI"


def test_transit_whole_sign_house_system_applied_to_both_subjects(birth_rome):
    result = generate_transit_chart(
        natal_name=birth_rome["name"], natal_year=birth_rome["year"],
        natal_month=birth_rome["month"], natal_day=birth_rome["day"],
        natal_hour=birth_rome["hour"], natal_minute=birth_rome["minute"],
        natal_lat=birth_rome["lat"], natal_lng=birth_rome["lng"], natal_tz_str=birth_rome["tz_str"],
        transit_lat=birth_rome["lat"], transit_lng=birth_rome["lng"], transit_tz_str=birth_rome["tz_str"],
        house_system="W",
        output_format="text",
    )
    assert result["status"] == "success"
    assert result["applied_settings"]["house_system"] == "W (Whole Sign)"
    # Both the natal and transit subjects must report the requested house
    # system (F7: the transit subject used to always default to Placidus).
    assert result["text"].count("House system: equal/ whole sign") == 2


def test_lunar_return_without_explicit_date_returns_near_today(birth_rome):
    result = generate_planetary_return(**birth_rome, return_type="Lunar", output_format="text")
    assert result["status"] == "success"
    return_date = datetime.fromisoformat(result["return_date"].replace("Z", "+00:00")).replace(tzinfo=None)
    assert return_date - datetime.now() < timedelta(days=28)


def test_return_chart_honors_whole_sign_house_system(birth_rome):
    # K1: the factory-built return subject always came back Placidus; the
    # rebuilt subject must actually be Whole Sign, not just claim it.
    result = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020,
        house_system="W", output_format="text",
    )
    assert result["status"] == "success"
    assert result["applied_settings"]["house_system"] == "W (Whole Sign)"
    assert "House system: equal/ whole sign" in result["text"]


def test_return_date_unchanged_by_subject_rebuild(birth_rome):
    # K1 regression pin: rebuilding the return subject must not shift the
    # moment of exactitude found by the factory (pre-fix golden value).
    result = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020, output_format="text",
    )
    assert result["status"] == "success"
    assert result["return_date"] == "2020-06-14T20:41:15+02:00"


def test_relocated_lunar_return_carries_return_location_label(birth_rome):
    # K1: a relocated return must be labeled with the return location, not the
    # birth city, and its house cusps must differ from the birth-location cast.
    common = dict(
        **birth_rome, city="Rome", nation="IT", return_type="Lunar",
        return_year=2026, return_month=7, return_day=1, output_format="text",
    )
    birth_location = generate_planetary_return(**common)
    relocated = generate_planetary_return(
        **common,
        return_lat=51.5074, return_lng=-0.1278, return_tz_str="Europe/London",
    )
    assert birth_location["status"] == "success"
    assert relocated["status"] == "success"
    assert relocated["text"] != birth_location["text"]
    assert "51.51N, 0.13W" in relocated["text"]
    assert "51.51N" not in birth_location["text"]


def test_sidereal_return_rejected_with_educational_error(birth_rome):
    # K2: kerykeion's return search matches the natal *sidereal* longitude
    # against transiting *tropical* longitudes (probe: ~25-day error), so
    # sidereal returns are explicitly rejected rather than silently wrong.
    result = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020,
        zodiac_type="Sidereal", sidereal_mode="LAHIRI", output_format="text",
    )
    assert result["status"] == "error"
    assert "not yet supported" in result["error"]
    assert result["hint"]


def test_return_applied_settings_include_zodiac_fields(birth_rome):
    result = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020, output_format="text",
    )
    assert result["applied_settings"]["zodiac_type"] == "Tropical"
    assert result["applied_settings"]["sidereal_mode"] is None


def test_solar_return_with_relocation_differs_from_birth_location(birth_rome):
    birth_location = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020, output_format="text"
    )
    relocated = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020,
        return_lat=birth_rome["lat"] + 10, return_lng=birth_rome["lng"] + 10,
        return_tz_str="UTC",
        output_format="text",
    )
    assert birth_location["status"] == "success"
    assert relocated["status"] == "success"
    assert birth_location["text"] != relocated["text"]
