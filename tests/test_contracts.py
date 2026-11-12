"""
Contract and golden-value tests for the 9 MCP tools.

These pin the current (pre-remediation) response shape so later phases
can be verified not to silently break the tool surface. Phases 1-2 will
update the exact keys/assertions here as the contract intentionally
changes (structured errors, applied_settings, city/nation, zodiac params).
"""

from kerykeion_mcp.server import (
    generate_natal_chart,
    generate_synastry_chart,
    generate_transit_chart,
    generate_composite_chart,
    generate_planetary_return,
    generate_event_chart,
    get_current_positions,
    get_aspects,
    get_synastry_aspects,
)


def test_natal_chart_contract(birth_rome):
    result = generate_natal_chart(**birth_rome, output_format="text")
    assert result["chart_type"] == "Natal"
    assert result["subject_name"] == birth_rome["name"]
    assert "text" in result
    assert isinstance(result["text"], str)


def test_natal_chart_golden_value_sun_and_house_system(birth_rome):
    result = generate_natal_chart(**birth_rome, output_format="text")
    assert "Gemini" in result["text"]
    assert "Placidus" in result["text"]


def test_natal_chart_images_written_to_disk(birth_rome, tmp_output_dir):
    result = generate_natal_chart(
        **birth_rome, output_format="all", output_dir=tmp_output_dir
    )
    assert "svg_path" in result
    svg_content = open(result["svg_path"], encoding="utf-8").read()
    assert "<svg" in svg_content


def test_synastry_chart_contract(birth_rome, birth_london):
    result = generate_synastry_chart(
        name1=birth_rome["name"], year1=birth_rome["year"], month1=birth_rome["month"],
        day1=birth_rome["day"], hour1=birth_rome["hour"], minute1=birth_rome["minute"],
        lat1=birth_rome["lat"], lng1=birth_rome["lng"], tz_str1=birth_rome["tz_str"],
        name2=birth_london["name"], year2=birth_london["year"], month2=birth_london["month"],
        day2=birth_london["day"], hour2=birth_london["hour"], minute2=birth_london["minute"],
        lat2=birth_london["lat"], lng2=birth_london["lng"], tz_str2=birth_london["tz_str"],
        output_format="text",
    )
    assert result["chart_type"] == "Synastry"
    assert result["subjects"] == [birth_rome["name"], birth_london["name"]]
    assert "text" in result
    assert "relationship_score" in result
    # B1 (breaking change): score is a contextualized object, not a bare number.
    score = result["relationship_score"]
    assert score["value"] == 8  # golden value for the Rome/London fixtures
    assert score["description"] == "Medium"
    assert isinstance(score["is_destiny_sign"], bool)
    assert isinstance(score["breakdown"], list)
    assert all({"rule", "description", "points"} <= set(item) for item in score["breakdown"])
    assert "Discepolo" in score["scale"]
    assert "Discepolo" in score["note"]


def test_transit_chart_contract(birth_rome):
    result = generate_transit_chart(
        natal_name=birth_rome["name"], natal_year=birth_rome["year"],
        natal_month=birth_rome["month"], natal_day=birth_rome["day"],
        natal_hour=birth_rome["hour"], natal_minute=birth_rome["minute"],
        natal_lat=birth_rome["lat"], natal_lng=birth_rome["lng"], natal_tz_str=birth_rome["tz_str"],
        transit_lat=birth_rome["lat"], transit_lng=birth_rome["lng"], transit_tz_str=birth_rome["tz_str"],
        output_format="text",
    )
    assert result["chart_type"] == "Transit"
    assert "text" in result


def transit_at(birth_rome, **when):
    return generate_transit_chart(
        natal_name=birth_rome["name"], natal_year=birth_rome["year"],
        natal_month=birth_rome["month"], natal_day=birth_rome["day"],
        natal_hour=birth_rome["hour"], natal_minute=birth_rome["minute"],
        natal_lat=birth_rome["lat"], natal_lng=birth_rome["lng"], natal_tz_str=birth_rome["tz_str"],
        transit_lat=birth_rome["lat"], transit_lng=birth_rome["lng"], transit_tz_str=birth_rome["tz_str"],
        output_format="text", **when,
    )


def test_transit_time_echoes_an_explicit_transit_moment(birth_rome):
    result = transit_at(birth_rome, transit_year=2020, transit_month=1, transit_day=1,
                        transit_hour=12, transit_minute=0)
    assert result["transit_time"] == "2020-01-01T12:00:00+01:00"


def test_transit_time_and_timestamp_are_iso_for_now(birth_rome):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    stamps = [
        transit_at(birth_rome)["transit_time"],
        get_current_positions(lat=birth_rome["lat"], lng=birth_rome["lng"],
                              tz_str=birth_rome["tz_str"])["timestamp"],
    ]
    for stamp in stamps:
        assert abs(datetime.fromisoformat(stamp) - now) < timedelta(minutes=2), stamp


def test_composite_chart_contract(birth_rome, birth_london):
    result = generate_composite_chart(
        name1=birth_rome["name"], year1=birth_rome["year"], month1=birth_rome["month"],
        day1=birth_rome["day"], hour1=birth_rome["hour"], minute1=birth_rome["minute"],
        lat1=birth_rome["lat"], lng1=birth_rome["lng"], tz_str1=birth_rome["tz_str"],
        name2=birth_london["name"], year2=birth_london["year"], month2=birth_london["month"],
        day2=birth_london["day"], hour2=birth_london["hour"], minute2=birth_london["minute"],
        lat2=birth_london["lat"], lng2=birth_london["lng"], tz_str2=birth_london["tz_str"],
        output_format="text",
    )
    assert result["chart_type"] == "Composite"
    assert "text" in result


def test_planetary_return_contract(birth_rome):
    result = generate_planetary_return(
        **birth_rome, return_type="Solar", return_year=2020, output_format="text"
    )
    assert result["chart_type"] == "Solar Return"
    assert "text" in result


def test_event_chart_contract(birth_rome):
    event = dict(birth_rome)
    name = event.pop("name")
    result = generate_event_chart(event_name=name, **event, output_format="text")
    assert result["chart_type"] == "Event"
    assert "text" in result


def test_current_positions_contract(birth_rome):
    result = get_current_positions(
        lat=birth_rome["lat"], lng=birth_rome["lng"], tz_str=birth_rome["tz_str"]
    )
    assert result["chart_type"] == "Current Positions"
    assert "text" in result


def test_get_aspects_contract(birth_rome):
    result = get_aspects(**birth_rome)
    assert result["chart_type"] == "Aspects"
    assert "aspects" in result
    assert result["aspect_count"] == len(result["aspects"])


def test_get_synastry_aspects_contract(birth_rome, birth_london):
    result = get_synastry_aspects(
        name1=birth_rome["name"], year1=birth_rome["year"], month1=birth_rome["month"],
        day1=birth_rome["day"], hour1=birth_rome["hour"], minute1=birth_rome["minute"],
        lat1=birth_rome["lat"], lng1=birth_rome["lng"], tz_str1=birth_rome["tz_str"],
        name2=birth_london["name"], year2=birth_london["year"], month2=birth_london["month"],
        day2=birth_london["day"], hour2=birth_london["hour"], minute2=birth_london["minute"],
        lat2=birth_london["lat"], lng2=birth_london["lng"], tz_str2=birth_london["tz_str"],
    )
    assert result["chart_type"] == "Synastry Aspects"
    assert "aspects" in result


# --- location labels: kerykeion fills a blank nation with "GB" ---------------

import re


def places(result):
    """Each subject's "{city}, {nation}" -- how the wheel prints it -- from the text."""
    return [f"{city}, {nation}" for city, nation in re.findall(
        r'<(?:birth|transit)_data [^>]*city="([^"]*)" nation="([^"]*)"', result["text"])]


def birth_data_line(result):
    return places(result)[0]


def test_city_without_nation_shows_coordinates_not_gb(birth_rome, tmp_output_dir):
    result = generate_natal_chart(**birth_rome, city="Rome", output_format="all", output_dir=tmp_output_dir)
    assert birth_data_line(result).endswith("Rome, 41.90N 12.50E")
    svg = open(result["svg_path"], encoding="utf-8").read()
    assert "Rome, 41.90N 12.50E" in svg
    assert ", GB" not in svg


def test_no_city_or_nation_shows_only_coordinates(birth_rome, tmp_output_dir):
    result = generate_natal_chart(**birth_rome, output_format="all", output_dir=tmp_output_dir)
    assert birth_data_line(result) == "41.90N, 12.50E"
    svg = open(result["svg_path"], encoding="utf-8").read()
    assert "41.90N, 12.50E" in svg
    assert ", GB" not in svg


def test_explicit_nation_is_kept(birth_rome):
    result = generate_natal_chart(**birth_rome, city="Rome", nation="IT", output_format="text")
    assert birth_data_line(result).endswith("Rome, IT")


def test_nation_without_city_keeps_nation(birth_rome):
    result = generate_natal_chart(**birth_rome, nation="IT", output_format="text")
    assert birth_data_line(result).endswith("41.90N, 12.50E, IT")


def test_second_subject_label_has_no_gb(birth_rome, birth_london):
    result = generate_synastry_chart(
        name1=birth_rome["name"], year1=birth_rome["year"], month1=birth_rome["month"],
        day1=birth_rome["day"], hour1=birth_rome["hour"], minute1=birth_rome["minute"],
        lat1=birth_rome["lat"], lng1=birth_rome["lng"], tz_str1=birth_rome["tz_str"],
        name2=birth_london["name"], year2=birth_london["year"], month2=birth_london["month"],
        day2=birth_london["day"], hour2=birth_london["hour"], minute2=birth_london["minute"],
        lat2=birth_london["lat"], lng2=birth_london["lng"], tz_str2=birth_london["tz_str"],
        city2="London", output_format="text",
    )
    assert "London, 51.51N 0.13W" in places(result)
    assert ", GB" not in result["text"]


def test_transit_place_is_labelled_with_its_coordinates(birth_rome, tmp_output_dir):
    # The transit subject has no city parameter; kerykeion would label it
    # "Greenwich, GB" wherever it was cast.
    result = generate_transit_chart(
        natal_name=birth_rome["name"], natal_year=birth_rome["year"], natal_month=birth_rome["month"],
        natal_day=birth_rome["day"], natal_hour=birth_rome["hour"], natal_minute=birth_rome["minute"],
        natal_lat=birth_rome["lat"], natal_lng=birth_rome["lng"], natal_tz_str=birth_rome["tz_str"],
        natal_city="Rome", natal_nation="IT",
        transit_lat=69.65, transit_lng=18.95, transit_tz_str="Europe/Oslo",
        transit_year=2026, transit_month=11, transit_day=12, transit_hour=12, transit_minute=0,
        output_format="all", output_dir=tmp_output_dir,
    )
    svg = open(result["svg_path"], encoding="utf-8").read()
    for output in (result["text"], svg):
        assert "Greenwich" not in output
        assert ", GB" not in output
    assert "69.65N, 18.95E" in result["text"] + svg


# --- PNG conversion -------------------------------------------------------

def test_css_variables_with_fallback_values_resolve():
    from kerykeion_mcp.chart_utils import resolve_css_variables
    svg = '<svg style="--a: 1; --c: var(--missing, 3);"><rect opacity="var(--b, 0.5)" x="var(--a, 2)" y="var(--c)"/></svg>'
    resolved = resolve_css_variables(svg)
    assert 'opacity="0.5"' in resolved  # undefined -> its fallback
    assert 'x="1"' in resolved          # defined wins over the fallback
    assert 'y="3"' in resolved          # fallback inside a definition
    assert "var(" not in resolved.split(">", 1)[1]


def test_natal_chart_png_is_written(birth_rome, tmp_output_dir):
    from kerykeion_mcp.chart_utils import HAS_CAIROSVG
    import pytest
    if not HAS_CAIROSVG:
        pytest.skip("cairosvg not installed")
    result = generate_natal_chart(**birth_rome, output_format="all", output_dir=tmp_output_dir)
    assert "png_path" in result
    assert open(result["png_path"], "rb").read(8) == b"\x89PNG\r\n\x1a\n"


# --- aspect settings: kerykeion 6 narrowed its defaults --------------------

def test_aspects_use_the_5x_points_and_orbs(birth_rome):
    # kerykeion 6 defaults to 14 points, five aspects at 5-6 degrees and
    # wider Sun/Moon orbs; the server keeps the 5.x set (ASPECT_SETTINGS).
    aspects = get_aspects(**birth_rome)["aspects"]
    found = {(a["planet1"], a["planet2"], a["aspect_type"]) for a in aspects}
    assert ("Saturn", "Mean_Lilith", "sextile") in found      # Lilith is active
    assert ("Mars", "Descendant", "conjunction") in found     # so is the Descendant
    assert ("Jupiter", "Saturn", "opposition") in found       # 8.14 deg: 10 deg orb, not 6
    assert len(aspects) == 63


def test_chart_text_keeps_the_5x_points(birth_rome):
    text = generate_natal_chart(**birth_rome, output_format="text")["text"]
    points = set(re.findall(r'<point name="([^"]+)"', text))
    assert {"Mean_Lilith", "True_South_Lunar_Node", "Descendant", "Imum_Coeli"} <= points
    assert len(points) == 18
