"""
Tests for boundary validation and structured error responses (Phase 1).

Every meaning-bearing parameter (coordinates, datetime, timezone, house
system, chart style, zodiac type/sidereal mode) must be rejected with an
educational {"status": "error", ...} response rather than silently
substituted or left to raise a raw traceback.
"""

import swisseph as swe

from kerykeion_mcp.server import (
    generate_natal_chart,
    get_aspects,
    handle_chart_errors,
)


def test_longitude_out_of_range_rejected_with_hint(birth_rome):
    bad = dict(birth_rome)
    bad["lng"] = 500.0
    result = generate_natal_chart(**bad, output_format="text")
    assert result["status"] == "error"
    assert "500" in result["error"]
    assert "-180" in result["error"] or "180" in result["error"]


def test_swapped_coordinates_hint(birth_rome):
    bad = dict(birth_rome)
    bad["lat"], bad["lng"] = 120.0, 41.9
    result = generate_natal_chart(**bad, output_format="text")
    assert result["status"] == "error"
    assert "swap" in result["hint"].lower()


def test_invalid_calendar_date_rejected(birth_rome):
    bad = dict(birth_rome)
    bad["month"], bad["day"] = 2, 30
    result = generate_natal_chart(**bad, output_format="text")
    assert result["status"] == "error"
    assert "2" in result["error"]


def test_invalid_timezone_rejected_with_iana_hint(birth_rome):
    bad = dict(birth_rome)
    bad["tz_str"] = "Europe/Atlantis"
    result = generate_natal_chart(**bad, output_format="text")
    assert result["status"] == "error"
    assert "Atlantis" in result["error"]
    assert "Europe/Rome" in result["hint"] or "IANA" in result["hint"]


def test_invalid_house_system_rejected_listing_valid_codes(birth_rome):
    result = generate_natal_chart(**birth_rome, house_system="X", output_format="text")
    assert result["status"] == "error"
    assert "Placidus" in result["hint"]


def test_gauquelin_not_offered(birth_rome):
    # kerykeion rejects "G" at every latitude, so it is not advertised.
    result = generate_natal_chart(**birth_rome, house_system="G", output_format="text")
    assert result["status"] == "error"
    assert result["error"] == "Invalid house_system 'G'."
    assert "Gauquelin" not in result["hint"]


def test_invalid_chart_style_rejected(birth_rome):
    result = generate_natal_chart(**birth_rome, chart_style="bogus", output_format="text")
    assert result["status"] == "error"
    assert "wheel_only" in result["hint"]


def test_happy_path_includes_applied_settings_and_status(birth_rome):
    result = generate_natal_chart(**birth_rome, output_format="text")
    assert result["status"] == "success"
    assert result["applied_settings"]["house_system"] == "P (Placidus)"
    assert result["applied_settings"]["zodiac_type"] == "Tropical"


def test_sidereal_without_mode_rejected(birth_rome):
    result = get_aspects(**birth_rome, zodiac_type="Sidereal")
    assert result["status"] == "error"
    assert "LAHIRI" in result["hint"]


def test_sidereal_with_lahiri_applies(birth_rome):
    result = get_aspects(**birth_rome, zodiac_type="Sidereal", sidereal_mode="LAHIRI")
    assert result["status"] == "success"
    assert result["applied_settings"]["sidereal_mode"] == "LAHIRI"


def test_swiss_ephemeris_errors_become_structured_errors():
    @handle_chart_errors
    def tool():
        raise swe.Error("swisseph.calc_ut: ephemeris file not found")
    result = tool()
    assert result["status"] == "error"
    assert "ephemeris file not found" in result["error"]
    assert "Internal error" not in result["error"]
    assert result["hint"]


# ---------------------------------------------------------------------------
# Clock-change times. kerykeion's own message tells the caller to "specify
# is_dst", which no tool accepts, and the hint was empty. The server now says
# what the caller can do: cast the reading meant in UTC.
# ---------------------------------------------------------------------------

LONDON = dict(name="Clock", lat=51.5074, lng=-0.1278, tz_str="Europe/London")


def test_time_that_happened_twice_explains_the_utc_route():
    # 28 October 1990, 01:30 in London: once in BST (00:30 UTC), again in GMT (01:30 UTC).
    result = generate_natal_chart(year=1990, month=10, day=28, hour=1, minute=30, output_format="text", **LONDON)
    assert result["status"] == "error"
    assert result["type"] == "AmbiguousTimeError"
    assert "twice" in result["error"]
    text = result["error"] + result["hint"]
    assert "is_dst" not in text
    assert 'tz_str="UTC"' in result["hint"]
    assert "00:30" in result["hint"] and "01:30" in result["hint"]
    assert "BST" in result["hint"] and "GMT" in result["hint"]


def test_the_utc_route_casts_both_readings():
    first = get_aspects(name="Clock", year=1990, month=10, day=28, hour=0, minute=30,
                        lat=51.5074, lng=-0.1278, tz_str="UTC")
    second = get_aspects(name="Clock", year=1990, month=10, day=28, hour=1, minute=30,
                         lat=51.5074, lng=-0.1278, tz_str="UTC")
    assert first["status"] == second["status"] == "success"
    assert first["aspects"] != second["aspects"]     # an hour apart: the angles' aspects differ


def test_time_that_never_happened_explains_itself():
    # 31 March 1991, 01:30 in London: the clocks went from 01:00 GMT straight to 02:00 BST.
    result = get_aspects(year=1991, month=3, day=31, hour=1, minute=30, **LONDON)
    assert result["status"] == "error"
    assert result["type"] == "NonexistentTimeError"
    assert "never" in result["error"] or "did not" in result["error"]
    assert "is_dst" not in result["error"] + result["hint"]
    assert 'tz_str="UTC"' in result["hint"] and "01:30" in result["hint"]


def test_other_library_errors_keep_their_shape():
    @handle_chart_errors
    def boom():
        from kerykeion import KerykeionException
        raise KerykeionException("something else went wrong")

    result = boom()
    assert result == {"status": "error", "error": "something else went wrong", "hint": ""}
