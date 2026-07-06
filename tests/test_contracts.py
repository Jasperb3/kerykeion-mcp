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
