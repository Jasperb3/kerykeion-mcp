"""
Tests for boundary validation and structured error responses (Phase 1).

Every meaning-bearing parameter (coordinates, datetime, timezone, house
system, chart style, zodiac type/sidereal mode) must be rejected with an
educational {"status": "error", ...} response rather than silently
substituted or left to raise a raw traceback.
"""

from kerykeion_mcp.server import (
    generate_natal_chart,
    get_aspects,
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
