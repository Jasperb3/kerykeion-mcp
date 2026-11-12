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
    """Each subject's structured (city, nation) fields from the text."""
    return re.findall(r'<(?:birth|transit)_data [^>]*city="([^"]*)" nation="([^"]*)"', result["text"])


def birth_data_place(result):
    return places(result)[0]


def test_city_without_nation_leaves_nation_empty_but_labels_the_wheel(birth_rome, tmp_output_dir):
    result = generate_natal_chart(**birth_rome, city="Rome", output_format="all", output_dir=tmp_output_dir)
    assert birth_data_place(result) == ("Rome", "")
    assert 'lat="41.90" lng="12.50"' in result["text"]
    svg = open(result["svg_path"], encoding="utf-8").read()
    assert "Rome, 41.90N 12.50E" in svg
    assert ", GB" not in svg


def test_no_city_or_nation_leaves_both_empty_but_labels_the_wheel(birth_rome, tmp_output_dir):
    result = generate_natal_chart(**birth_rome, output_format="all", output_dir=tmp_output_dir)
    assert birth_data_place(result) == ("", "")
    assert "41.90N" not in result["text"]
    svg = open(result["svg_path"], encoding="utf-8").read()
    assert "41.90N, 12.50E" in svg
    assert ", GB" not in svg


def test_explicit_nation_is_kept(birth_rome):
    result = generate_natal_chart(**birth_rome, city="Rome", nation="IT", output_format="text")
    assert birth_data_place(result) == ("Rome", "IT")


def test_nation_without_city_keeps_nation(birth_rome):
    result = generate_natal_chart(**birth_rome, nation="IT", output_format="text")
    assert birth_data_place(result) == ("", "IT")


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
    assert places(result) == [("", ""), ("London", "")]
    assert ", GB" not in result["text"]


def test_svalbard_current_positions_leave_the_place_fields_empty():
    result = get_current_positions(lat=78.22, lng=15.63, tz_str="UTC")
    assert re.search(r'city="" nation="" lat="78.22" lng="15.63"', result["text"])


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
    assert places(result) == [("Rome", "IT"), ("", "")]
    assert "69.65N, 18.95E" in svg


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


# --- chart labels in the text ------------------------------------------------

def test_current_positions_text_calls_its_block_moment(birth_rome):
    text = get_current_positions(lat=birth_rome["lat"], lng=birth_rome["lng"], tz_str=birth_rome["tz_str"])["text"]
    assert re.search(r'<moment date="[^"]+" city="" nation="" lat="41.90"', text)
    assert "<birth_data" not in text


def test_return_and_event_text_carry_their_own_chart_type(birth_rome):
    solar = generate_planetary_return(**birth_rome, return_type="Solar", return_year=2020, output_format="text")
    lunar = generate_planetary_return(**birth_rome, return_type="Lunar", return_year=2020, output_format="text")
    event = dict(birth_rome)
    event = generate_event_chart(event_name=event.pop("name"), **event, output_format="text")
    for result, chart_type in ((solar, "Solar Return"), (lunar, "Lunar Return"), (event, "Event")):
        assert f'<chart_analysis type="{chart_type}">' in result["text"]
        assert 'type="Natal"' not in result["text"]
    natal = generate_natal_chart(**birth_rome, output_format="text")
    assert '<chart_analysis type="Natal">' in natal["text"]


def test_synastry_and_composite_text_is_kerykeions_own(birth_rome, birth_london):
    from kerykeion import AstrologicalSubjectFactory, ChartDataFactory, CompositeSubjectFactory, to_context
    from kerykeion_mcp.server import ACTIVE_POINTS, ASPECT_SETTINGS, context_text

    def subject(birth, city, nation):
        return AstrologicalSubjectFactory.from_birth_data(
            **birth, city=city, nation=nation, online=False, active_points=ACTIVE_POINTS)

    first, second = subject(birth_rome, "Rome", "IT"), subject(birth_london, "London", "GB")
    synastry = ChartDataFactory.create_synastry_chart_data(first, second, **ASPECT_SETTINGS)
    composite = ChartDataFactory.create_composite_chart_data(
        CompositeSubjectFactory(first, second).get_midpoint_composite_subject_model(), **ASPECT_SETTINGS)
    for data, chart_type in ((synastry, "Synastry"), (composite, "Composite")):
        # Only the angles' motion and speed differ (see test_polar).
        motionless = re.sub(r'(<point name="(?:Ascendant|Descendant|Medium_Coeli|Imum_Coeli)" [^>]*?)'
                            r' motion="[^"]*" speed="[^"]*"', r"\1", to_context(data))
        assert context_text(data) == motionless
        assert f'<chart_analysis type="{chart_type}">' in context_text(data)


# exclude_derived_points: an aspect to the Descendant, IC or South Node mirrors
# one to the Ascendant, MC or North Node, and an aspect between two angles is
# fixed by the house frame, so the option drops both kinds.
LONDON_1985 = dict(year=1985, month=6, day=21, hour=12, minute=0, lat=51.5074, lng=-0.1278, tz_str="Europe/London")
MCMURDO_1992 = dict(year=1992, month=12, day=21, hour=3, minute=30, lat=-77.846, lng=166.676,
                    tz_str="Antarctica/McMurdo")
DERIVED = {"Descendant", "Imum_Coeli", "True_South_Lunar_Node", "Mean_South_Lunar_Node"}
AXES = {"Ascendant", "Descendant", "Medium_Coeli", "Imum_Coeli"}


def london_mcmurdo():
    return {**{f"{k}1": v for k, v in dict(name="London", **LONDON_1985).items()},
            **{f"{k}2": v for k, v in dict(name="McMurdo", **MCMURDO_1992).items()}}


def assert_no_derived(pairs):
    for first, second in pairs:
        assert first not in DERIVED and second not in DERIVED, (first, second)
        assert not (first in AXES and second in AXES), (first, second)


def aspect_names(result):
    return [(a["planet1"].split(":")[-1], a["planet2"].split(":")[-1]) for a in result["aspects"]]


def text_aspect_names(text):
    return re.findall(r'<aspect [^>]*?p1(?:_name)?="(\w+)"[^>]*? p2(?:_name)?="(\w+)"', text)


def test_get_synastry_aspects_can_exclude_derived_points():
    full = get_synastry_aspects(**london_mcmurdo())
    lean = get_synastry_aspects(**london_mcmurdo(), exclude_derived_points=True)
    assert (full["aspect_count"], lean["aspect_count"]) == (116, 76)
    assert_no_derived(aspect_names(lean))
    sun = {"planet1": "London:Sun", "planet2": "McMurdo:Sun", "aspect_type": "opposition"}
    assert any(sun.items() <= a.items() for a in lean["aspects"])
    assert lean["applied_settings"]["exclude_derived_points"] is True
    assert "exclude_derived_points" not in full["applied_settings"]


def test_get_aspects_can_exclude_derived_points():
    full = get_aspects(name="London", **LONDON_1985)
    lean = get_aspects(name="London", **LONDON_1985, exclude_derived_points=True)
    assert (full["aspect_count"], lean["aspect_count"]) == (52, 34)
    assert_no_derived(aspect_names(lean))
    sun = lambda result: [a for a in result["aspects"] if "Sun" in (a["planet1"], a["planet2"])
                          and not {a["planet1"], a["planet2"]} & DERIVED]
    assert sun(lean) == sun(full) and sun(lean)


def test_chart_texts_and_wheels_can_exclude_derived_points(tmp_output_dir):
    from kerykeion_mcp.server import get_chart_patterns
    date = {k: v for k, v in MCMURDO_1992.items() if k in ("year", "month", "day", "hour", "minute")}
    natal = dict(name="London", **LONDON_1985)
    calls = {
        "natal": lambda **o: generate_natal_chart(**natal, **o),
        "synastry": lambda **o: generate_synastry_chart(**london_mcmurdo(), **o),
        "transit": lambda **o: generate_transit_chart(
            **{f"natal_{k}": v for k, v in natal.items()}, transit_lat=MCMURDO_1992["lat"],
            transit_lng=MCMURDO_1992["lng"], transit_tz_str=MCMURDO_1992["tz_str"],
            **{f"transit_{k}": v for k, v in date.items()}, **o),
        "composite": lambda **o: generate_composite_chart(**london_mcmurdo(), **o),
        "return": lambda **o: generate_planetary_return(**natal, return_year=2026, **o),
        "event": lambda **o: generate_event_chart(event_name="E", **LONDON_1985, **o),
    }
    for kind, call in calls.items():
        full = call(output_format="text")
        lean = call(output_format="images", exclude_derived_points=True)
        assert lean["status"] == "success", (kind, lean)
        full_pairs, lean_pairs = text_aspect_names(full["text"]), text_aspect_names(lean["text"])
        assert full_pairs and 0 < len(lean_pairs) < len(full_pairs), kind
        assert_no_derived(lean_pairs)
        svg = open(lean["svg_path"], encoding="utf-8").read()
        assert svg.count("kr:node='Aspect'") == len(lean_pairs), kind
        assert lean["applied_settings"]["exclude_derived_points"] is True, kind
        assert "exclude_derived_points" not in full["applied_settings"], kind
    patterns = get_chart_patterns(name="London", **LONDON_1985, exclude_derived_points=True)
    assert patterns["status"] == "success"
    assert patterns["applied_settings"]["exclude_derived_points"] is True
