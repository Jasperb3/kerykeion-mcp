"""
Kerykeion MCP Server

A Model Context Protocol server providing astrological chart generation 
capabilities using the Kerykeion library. Works with Claude Desktop and
ChatGPT Desktop via standard MCP transport.
"""

import functools
import logging
from datetime import datetime
from typing import Optional, Literal

import pytz
from mcp.server.fastmcp import FastMCP
from kerykeion import (
    AstrologicalSubjectFactory,
    ChartDataFactory,
    ChartDrawer,
    CompositeSubjectFactory,
    PlanetaryReturnFactory,
    AspectsFactory,
    KerykeionException,
    to_context,
)

from .chart_utils import (
    generate_and_save_images,
    HAS_CAIROSVG,
)
from .patterns import (
    PATTERN_PLANETS,
    detect_patterns,
    element_balance,
    mode_balance,
)
from .validation import (
    ChartInputError,
    validate_theme,
    validate_language,
    validate_house_system,
    validate_sidereal_mode,
    validate_chart_style,
    validate_zodiac_type,
    validate_coordinates,
    validate_datetime_fields,
    validate_timezone,
    VALID_HOUSE_SYSTEMS,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle_chart_errors(func):
    """
    Catch input/library errors and return a structured error response instead
    of letting a raw traceback reach the MCP client. Unknown exceptions are
    still logged with a full traceback server-side.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ChartInputError as e:
            return {"status": "error", "error": e.message, "hint": e.hint}
        except pytz.exceptions.UnknownTimeZoneError as e:
            return {"status": "error", "error": f"Unknown timezone: {e}", "hint": ""}
        except KerykeionException as e:
            return {"status": "error", "error": str(e), "hint": ""}
        except ValueError as e:
            return {"status": "error", "error": str(e), "hint": ""}
        except Exception as e:
            logger.exception(f"Internal error in {func.__name__}")
            return {
                "status": "error",
                "error": f"Internal error generating chart: {type(e).__name__}",
                "hint": "Check server logs.",
            }

    return wrapper


def build_applied_settings(
    house_system: str,
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    theme: Optional[str] = None,
    language: Optional[str] = None,
    chart_style: Optional[str] = None,
) -> dict:
    """Build the applied_settings block echoing exactly what was computed."""
    settings = {
        "house_system": f"{house_system} ({VALID_HOUSE_SYSTEMS[house_system]})",
        "zodiac_type": zodiac_type,
        "sidereal_mode": sidereal_mode,
    }
    if theme is not None:
        settings["theme"] = theme
    if language is not None:
        settings["language"] = language
    if chart_style is not None:
        settings["chart_style"] = chart_style
    return settings


def resolve_location(city: str, nation: str, lat: float, lng: float) -> tuple[str, str]:
    """
    Resolve the city/nation label passed to kerykeion.

    kerykeion defaults blank city/nation to "Greenwich, GB" -- truthful only
    for charts actually cast there. When the caller doesn't supply a city,
    fall back to a coordinate-derived label instead of that default.
    """
    if city:
        return city, nation
    lat_label = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'}"
    lng_label = f"{abs(lng):.2f}{'E' if lng >= 0 else 'W'}"
    return f"{lat_label}, {lng_label}", nation

# Server instructions for AI assistants
SERVER_INSTRUCTIONS = """
Kerykeion MCP Server - Astrological Chart Generation

This server provides tools to generate astrological charts including:
- Natal (birth) charts
- Synastry (relationship compatibility) charts  
- Transit charts (current transits to natal positions)
- Composite charts (relationship charts)
- Planetary return charts (Solar, Lunar returns)
- Current planetary positions

All tools operate in OFFLINE mode - you must provide:
- Latitude (lat): Positive for North, negative for South
- Longitude (lng): Positive for East, negative for West
- Timezone (tz_str): IANA timezone format (e.g., "Europe/Rome", "America/New_York")

Output formats (output_format parameter):
- "text": AI-readable text description only
- "images": text plus SVG/PNG files saved to disk (paths returned as svg_path/png_path)
- "all": text and images

Every response includes a "status" field ("success" or "error") and, on
success, an "applied_settings" block reporting exactly which house system,
zodiac type, and sidereal mode were used -- never assume a requested setting
was honored without checking it there. On error, the response includes an
educational "error" message and "hint" instead of a raw exception.

Common timezones: UTC, Europe/London, Europe/Paris, Europe/Rome,
America/New_York, America/Los_Angeles, Asia/Tokyo, Australia/Sydney

Interpretation framing: present challenging aspects and hard placements as
developmental invitations, not verdicts or predictions of doom. Never offer
medical, legal, or fatalistic ("you will die/divorce/fail") predictions from
a chart. House-dependent claims (Ascendant, house placements, angles) require
a confident birth time -- flag uncertainty when the birth time is approximate
or unknown rather than presenting house-based claims as fact.
"""

# Create MCP server instance
mcp = FastMCP(
    name="Kerykeion Charts",
    instructions=SERVER_INSTRUCTIONS,
)


# =============================================================================
# PROMPTS - Pre-defined conversation starters
# =============================================================================

@mcp.prompt()
def natal_chart_prompt() -> str:
    """Prompt template for creating a natal chart."""
    return """I'd like to generate a natal (birth) chart. Please ask me for:
1. Name (or identifier)
2. Birth date (year, month, day)
3. Birth time (hour, minute) - as accurate as possible
4. Birth location coordinates (latitude, longitude) or city name to look up
5. Timezone (IANA format like "Europe/Rome" or "America/New_York")

Then use the generate_natal_chart tool to create the chart and provide 
an interpretation of the key placements."""


@mcp.prompt()
def synastry_prompt() -> str:
    """Prompt template for creating a synastry/compatibility chart."""
    return """I'd like to analyze relationship compatibility with a synastry chart. 
Please ask me for birth data for both people:
- Name, birth date, birth time, location coordinates, and timezone

Then use the generate_synastry_chart tool to create the chart and analyze 
the key aspects between the two charts."""


@mcp.prompt()
def transit_prompt() -> str:
    """Prompt template for analyzing current transits."""
    return """I'd like to see my current planetary transits. Please ask me for:
1. My birth data (name, date, time, location coordinates, timezone)
2. My current location coordinates and timezone (for transit calculations)

Then use the generate_transit_chart tool to show which transiting planets 
are making aspects to my natal positions."""


# =============================================================================
# TOOLS - Chart Generation
# =============================================================================

OutputFormat = Literal["text", "images", "all"]
ChartStyle = Literal["full", "wheel_only", "aspect_grid"]


def get_svg_by_style(drawer: ChartDrawer, chart_style: str) -> str:
    """Generate SVG string based on chart style."""
    if chart_style == "wheel_only":
        return drawer.generate_wheel_only_svg_string()
    elif chart_style == "aspect_grid":
        return drawer.generate_aspect_grid_only_svg_string()
    else:
        return drawer.generate_svg_string()


@mcp.tool()
@handle_chart_errors
def generate_natal_chart(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    lat: float,
    lng: float,
    tz_str: str,
    city: str = "",
    nation: str = "",
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a natal (birth) chart for an individual.

    Args:
        name: Name or identifier for the chart subject
        year: Birth year (e.g., 1990)
        month: Birth month (1-12)
        day: Birth day (1-31)
        hour: Birth hour (0-23, 24-hour format)
        minute: Birth minute (0-59)
        lat: Latitude of birth location (positive=North, negative=South)
        lng: Longitude of birth location (positive=East, negative=West)
        tz_str: IANA timezone (e.g., "Europe/Rome", "America/New_York")
        city: Birth city name (optional; used only for chart labeling, not calculation)
        nation: Birth country/nation code (optional; used only for chart labeling)
        theme: Chart theme - "classic", "light", "dark", "strawberry", "dark-high-contrast"
        language: Chart language - "EN", "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
        house_system: House system - "P" (Placidus), "W" (Whole Sign), "K" (Koch), etc.
        zodiac_type: "Tropical" (Western) or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal" (e.g. "LAHIRI")
        output_format: "text" (text only), "images" (text + save images), or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full" (complete chart), "wheel_only" (just the wheel), "aspect_grid" (just aspects table)

    Returns:
        dict: status, applied_settings (settings actually used), text analysis, and file paths
    """
    logger.info("Generating natal chart")
    logger.debug(f"Subject: {name}")

    # Validate inputs
    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    city, nation = resolve_location(city, nation, lat, lng)

    # Create astrological subject
    subject = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        city=city, nation=nation,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    # Create chart data
    chart_data = ChartDataFactory.create_natal_chart_data(subject)

    # Build response
    result = {
        "status": "success",
        "chart_type": "Natal",
        "chart_style": chart_style,
        "subject_name": name,
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(chart_data),
    }

    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=chart_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)

        # Save images to files
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"natal_{chart_style}_{name}",
            output_dir=output_dir,
        )
        result.update(image_paths)

    logger.info("Natal chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def generate_synastry_chart(
    name1: str,
    year1: int, month1: int, day1: int,
    hour1: int, minute1: int,
    lat1: float, lng1: float, tz_str1: str,
    name2: str,
    year2: int, month2: int, day2: int,
    hour2: int, minute2: int,
    lat2: float, lng2: float, tz_str2: str,
    city1: str = "", nation1: str = "",
    city2: str = "", nation2: str = "",
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    include_relationship_score: bool = True,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a synastry chart comparing two people for compatibility analysis.

    Response contains 'svg_path'/'png_path' (local file paths) when
    output_format includes images -- read the SVG file directly to embed it.

    Args:
        name1: Name of first person
        year1, month1, day1: Birth date of first person
        hour1, minute1: Birth time of first person
        lat1, lng1: Birth coordinates of first person
        tz_str1: Timezone of first person's birth
        city1, nation1: Birth city/nation of first person (optional, chart labeling only)
        name2: Name of second person
        year2, month2, day2: Birth date of second person
        hour2, minute2: Birth time of second person
        lat2, lng2: Birth coordinates of second person
        tz_str2: Timezone of second person's birth
        city2, nation2: Birth city/nation of second person (optional, chart labeling only)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"
        include_relationship_score: Include compatibility score calculation
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full", "wheel_only", or "aspect_grid"

    Returns:
        dict: Synastry analysis with status, applied_settings, and file paths
    """
    logger.info("Generating synastry chart")
    logger.debug(f"Subjects: {name1}, {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    city1, nation1 = resolve_location(city1, nation1, lat1, lng1)
    city2, nation2 = resolve_location(city2, nation2, lat2, lng2)

    # Create both subjects
    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        city=city1, nation=nation1,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        city=city2, nation=nation2,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    # Create synastry chart data
    synastry_data = ChartDataFactory.create_synastry_chart_data(
        first_subject=person1,
        second_subject=person2,
        include_house_comparison=True,
        include_relationship_score=include_relationship_score,
    )

    result = {
        "status": "success",
        "chart_type": "Synastry",
        "subjects": [name1, name2],
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(synastry_data),
    }
    
    # Add relationship score if available
    if include_relationship_score and synastry_data.relationship_score:
        score = synastry_data.relationship_score
        result["relationship_score"] = {
            "value": score.score_value,
            "description": score.score_description,
            # Sun signs in the same quadruplicity, per Discepolo
            "is_destiny_sign": score.is_destiny_sign,
            "breakdown": [item.model_dump() for item in score.score_breakdown],
            "scale": "0-44+ (Discepolo method)",
            "note": (
                "Counts specific aspect contacts per Ciro Discepolo's method; "
                "one lens among many, not a verdict on relationship viability."
            ),
        }
    
    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=synastry_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)
        
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"synastry_{name1}_{name2}",
            output_dir=output_dir,
        )
        result.update(image_paths)
    
    logger.info("Synastry chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def generate_transit_chart(
    natal_name: str,
    natal_year: int, natal_month: int, natal_day: int,
    natal_hour: int, natal_minute: int,
    natal_lat: float, natal_lng: float, natal_tz_str: str,
    transit_lat: float,
    transit_lng: float,
    transit_tz_str: str,
    natal_city: str = "", natal_nation: str = "",
    transit_year: Optional[int] = None,
    transit_month: Optional[int] = None,
    transit_day: Optional[int] = None,
    transit_hour: Optional[int] = None,
    transit_minute: Optional[int] = None,
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a transit chart showing current (or specified) planetary transits to a natal chart.

    Response contains 'svg_path'/'png_path' (local file paths) when
    output_format includes images -- read the SVG file directly to embed it.

    If transit date/time is not specified, uses current time.

    Args:
        natal_name: Name of the natal chart subject
        natal_year, natal_month, natal_day: Birth date
        natal_hour, natal_minute: Birth time
        natal_lat, natal_lng: Birth coordinates
        natal_tz_str: Birth timezone
        natal_city, natal_nation: Birth city/nation (optional, chart labeling only)
        transit_lat, transit_lng: Current/transit location coordinates
        transit_tz_str: Current/transit timezone
        transit_year, transit_month, transit_day: Transit date (optional, defaults to now)
        transit_hour, transit_minute: Transit time (optional, defaults to now)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier -- applied to both the natal and transit subjects
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full", "wheel_only", or "aspect_grid"

    Returns:
        dict: Transit analysis with status, applied_settings, and file paths
    """
    logger.info("Generating transit chart")
    logger.debug(f"Natal subject: {natal_name}")

    validate_coordinates(natal_lat, natal_lng, label="Natal location")
    validate_datetime_fields(natal_year, natal_month, natal_day, natal_hour, natal_minute, label="Natal date")
    validate_timezone(natal_tz_str, label="Natal timezone")
    validate_coordinates(transit_lat, transit_lng, label="Transit location")
    validate_timezone(transit_tz_str, label="Transit timezone")
    if all(v is not None for v in [transit_year, transit_month, transit_day, transit_hour, transit_minute]):
        validate_datetime_fields(transit_year, transit_month, transit_day, transit_hour, transit_minute, label="Transit date")
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    natal_city, natal_nation = resolve_location(natal_city, natal_nation, natal_lat, natal_lng)

    # Create natal subject
    natal = AstrologicalSubjectFactory.from_birth_data(
        name=natal_name,
        year=natal_year, month=natal_month, day=natal_day,
        hour=natal_hour, minute=natal_minute,
        lat=natal_lat, lng=natal_lng, tz_str=natal_tz_str,
        city=natal_city, nation=natal_nation,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    # Create transit subject - either current time or specified time
    if all(v is not None for v in [transit_year, transit_month, transit_day, transit_hour, transit_minute]):
        transit = AstrologicalSubjectFactory.from_birth_data(
            name="Transits",
            year=transit_year, month=transit_month, day=transit_day,
            hour=transit_hour, minute=transit_minute,
            lat=transit_lat, lng=transit_lng, tz_str=transit_tz_str,
            houses_system_identifier=house_system,
            zodiac_type=zodiac_type,
            sidereal_mode=sidereal_mode,
            online=False,
        )
    else:
        transit = AstrologicalSubjectFactory.from_current_time(
            name="Current Transits",
            lat=transit_lat, lng=transit_lng, tz_str=transit_tz_str,
            houses_system_identifier=house_system,
            zodiac_type=zodiac_type,
            sidereal_mode=sidereal_mode,
            online=False,
        )

    # Create transit chart data
    transit_data = ChartDataFactory.create_transit_chart_data(
        natal_subject=natal,
        transit_subject=transit,
    )

    result = {
        "status": "success",
        "chart_type": "Transit",
        "natal_subject": natal_name,
        "transit_time": str(transit.utc_time) if hasattr(transit, 'utc_time') else "current",
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(transit_data),
    }
    
    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=transit_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)
        
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"transit_{natal_name}",
            output_dir=output_dir,
        )
        result.update(image_paths)
    
    logger.info("Transit chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def generate_composite_chart(
    name1: str,
    year1: int, month1: int, day1: int,
    hour1: int, minute1: int,
    lat1: float, lng1: float, tz_str1: str,
    name2: str,
    year2: int, month2: int, day2: int,
    hour2: int, minute2: int,
    lat2: float, lng2: float, tz_str2: str,
    city1: str = "", nation1: str = "",
    city2: str = "", nation2: str = "",
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a composite chart (midpoint composite) for two people.

    Response contains 'svg_path'/'png_path' (local file paths) when
    output_format includes images -- read the SVG file directly to embed it.

    A composite chart creates a single chart representing the relationship
    by calculating the midpoints of each planet between two charts.

    Args:
        name1: Name of first person
        year1, month1, day1: Birth date of first person
        hour1, minute1: Birth time of first person
        lat1, lng1: Birth coordinates of first person
        tz_str1: Timezone of first person's birth
        city1, nation1: Birth city/nation of first person (optional, chart labeling only)
        name2: Name of second person
        year2, month2, day2: Birth date of second person
        hour2, minute2: Birth time of second person
        lat2, lng2: Birth coordinates of second person
        tz_str2: Timezone of second person's birth
        city2, nation2: Birth city/nation of second person (optional, chart labeling only)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full", "wheel_only", or "aspect_grid"

    Returns:
        dict: Composite chart with status, applied_settings, and file paths
    """
    logger.info("Generating composite chart")
    logger.debug(f"Subjects: {name1}, {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    city1, nation1 = resolve_location(city1, nation1, lat1, lng1)
    city2, nation2 = resolve_location(city2, nation2, lat2, lng2)

    # Create both subjects
    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        city=city1, nation=nation1,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        city=city2, nation=nation2,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )
    
    # Create composite subject
    composite_factory = CompositeSubjectFactory(person1, person2)
    composite_subject = composite_factory.get_midpoint_composite_subject_model()
    
    # Create composite chart data
    composite_data = ChartDataFactory.create_composite_chart_data(composite_subject)
    
    result = {
        "status": "success",
        "chart_type": "Composite",
        "subjects": [name1, name2],
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(composite_data),
    }
    
    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=composite_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)
        
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"composite_{name1}_{name2}",
            output_dir=output_dir,
        )
        result.update(image_paths)
    
    logger.info("Composite chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def generate_planetary_return(
    name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    lat: float, lng: float, tz_str: str,
    city: str = "", nation: str = "",
    return_type: str = "Solar",
    return_year: Optional[int] = None,
    return_month: Optional[int] = None,
    return_day: Optional[int] = None,
    return_lat: Optional[float] = None,
    return_lng: Optional[float] = None,
    return_tz_str: Optional[str] = None,
    return_city: str = "", return_nation: str = "",
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a planetary return chart (Solar Return, Lunar Return)

    Response contains 'svg_path'/'png_path' (local file paths) when
    output_format includes images -- read the SVG file directly to embed it.

    A return chart is calculated for when a planet returns to its natal position.
    Solar returns occur yearly, lunar returns monthly. Standard convention casts
    a return chart for wherever the person actually is at the time of the return
    (relocation) -- pass return_lat/return_lng/return_tz_str to do that; if
    omitted, the return is cast for the birth location.

    Args:
        name: Name of the chart subject
        year, month, day: Birth date
        hour, minute: Birth time
        lat, lng: Birth coordinates
        tz_str: Birth timezone
        city, nation: Birth city/nation (optional, chart labeling only)
        return_type: "Solar" (yearly) or "Lunar" (monthly)
        return_year: Year to start searching for the return from (defaults to today's year)
        return_month, return_day: Month/day to start searching from (defaults to today,
            unless only return_year is given, in which case defaults to Jan 1 for
            backward compatibility)
        return_lat, return_lng, return_tz_str: Location to cast the return chart for
            (defaults to birth location if omitted)
        return_city, return_nation: Label for the return location (optional, chart
            labeling only). If omitted, a relocated return is labeled with its
            coordinates; a non-relocated return keeps the birth location label.
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        zodiac_type: "Tropical" only. Sidereal return charts are rejected with an
            explanatory error -- the underlying return search is not sidereal-aware.
        sidereal_mode: Not supported for returns (see zodiac_type)
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full", "wheel_only", or "aspect_grid"

    Returns:
        dict: Return chart with status, applied_settings, and file paths
    """
    if return_type not in ("Solar", "Lunar"):
        raise ChartInputError(
            f"Invalid return_type '{return_type}'.",
            hint="Valid return types are: Solar, Lunar",
        )
    zodiac_type = validate_zodiac_type(zodiac_type)
    if zodiac_type == "Sidereal":
        # kerykeion's return search compares the natal subject's stored
        # (sidereal) longitude against transiting *tropical* longitudes, so a
        # sidereal return lands ~an ayanamsha of solar motion off (verified
        # by probe: 2030 LAHIRI solar return found 25 days early). Reject
        # rather than ship a silently wrong chart.
        raise ChartInputError(
            "Sidereal return charts are not yet supported by the underlying search.",
            hint=(
                "Generate the return tropically, or use a sidereal transit "
                "chart at the known return moment."
            ),
        )
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)

    logger.info(f"Generating {return_type} return")
    logger.debug(f"Subject: {name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    city, nation = resolve_location(city, nation, lat, lng)

    search_lat = return_lat if return_lat is not None else lat
    search_lng = return_lng if return_lng is not None else lng
    search_tz_str = return_tz_str if return_tz_str is not None else tz_str
    if return_lat is not None or return_lng is not None:
        validate_coordinates(search_lat, search_lng, label="Return location")
    if return_tz_str is not None:
        validate_timezone(search_tz_str, label="Return timezone")

    # Label the return chart with the *return* location: an explicit
    # return_city wins; a relocated return without one gets a coordinate
    # label; a non-relocated return keeps the birth label.
    if not return_city and return_lat is None and return_lng is None:
        return_city_label, return_nation_label = city, nation
    else:
        return_city_label, return_nation_label = resolve_location(
            return_city, return_nation, search_lat, search_lng
        )

    # Default to today's date (needed for lunar returns, which recur every
    # ~27.3 days -- searching from Jan 1 would return January's lunar return
    # for a caller in July). Jan-1 default is preserved when only return_year
    # is given, for backward compatibility.
    if return_year is None and return_month is None and return_day is None:
        today = datetime.now()
        return_year, return_month, return_day = today.year, today.month, today.day
    else:
        if return_year is None:
            return_year = datetime.now().year
        if return_month is None:
            return_month = 1
        if return_day is None:
            return_day = 1

    # Create natal subject
    natal = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        city=city, nation=nation,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    # Create return factory and get return subject
    return_factory = PlanetaryReturnFactory(
        subject=natal,
        lat=search_lat,
        lng=search_lng,
        tz_str=search_tz_str,
        online=False,
    )
    # Use next_return_from_date (next_return_from_year is deprecated)
    return_model = return_factory.next_return_from_date(
        year=return_year,
        month=return_month,
        day=return_day,
        return_type=return_type,
    )

    # The factory only locates the moment of exactitude -- the subject it
    # builds ignores the requested house system (always Placidus). Rebuild
    # the return subject at that moment with the settings actually requested,
    # so applied_settings stays truthful by construction.
    return_subject = AstrologicalSubjectFactory.from_iso_utc_time(
        name=f"{name} {return_type} Return",
        iso_utc_time=return_model.iso_formatted_utc_datetime,
        lat=search_lat, lng=search_lng, tz_str=search_tz_str,
        city=return_city_label, nation=return_nation_label,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )
    return_data = ChartDataFactory.create_natal_chart_data(return_subject)

    result = {
        "status": "success",
        "chart_type": f"{return_type} Return",
        "subject_name": name,
        "return_year": return_year,
        "return_date": return_model.iso_formatted_local_datetime if hasattr(return_model, 'iso_formatted_local_datetime') else None,
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(return_data),
    }
    
    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=return_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)
        
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"{return_type.lower()}_return_{name}",
            output_dir=output_dir,
        )
        result.update(image_paths)
    
    logger.info(f"{return_type} return chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def generate_event_chart(
    event_name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    lat: float, lng: float, tz_str: str,
    city: str = "", nation: str = "",
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate an event chart for a specific moment in time (electional, horary, event).

    Response contains 'svg_path'/'png_path' (local file paths) when
    output_format includes images -- read the SVG file directly to embed it.

    Use this for analyzing the astrological conditions at any specific moment,
    such as the start of a business, a question asked, or an important event.

    Args:
        event_name: Name/description of the event
        year, month, day: Event date
        hour, minute: Event time
        lat, lng: Event location coordinates
        tz_str: Event timezone
        city, nation: Event city/nation (optional, chart labeling only)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full", "wheel_only", or "aspect_grid"

    Returns:
        dict: Event chart with status, applied_settings, and file paths
    """
    logger.info("Generating event chart")
    logger.debug(f"Event: {event_name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    city, nation = resolve_location(city, nation, lat, lng)

    # Create subject for the event moment
    event_subject = AstrologicalSubjectFactory.from_birth_data(
        name=event_name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        city=city, nation=nation,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    chart_data = ChartDataFactory.create_natal_chart_data(event_subject)

    result = {
        "status": "success",
        "chart_type": "Event",
        "event_name": event_name,
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(chart_data),
    }
    
    # Generate and save images if requested
    if output_format in ("images", "all"):
        drawer = ChartDrawer(
            chart_data=chart_data,
            theme=theme,
            chart_language=language,
        )
        svg_string = get_svg_by_style(drawer, chart_style)
        
        image_paths = generate_and_save_images(
            svg_string=svg_string,
            chart_name=f"event_{event_name}",
            output_dir=output_dir,
        )
        result.update(image_paths)
    
    logger.info("Event chart generated")
    return result


@mcp.tool()
@handle_chart_errors
def get_current_positions(
    lat: float,
    lng: float,
    tz_str: str,
    city: str = "",
    nation: str = "",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
) -> dict:
    """
    Get current planetary positions for a specific location.

    Returns a text description of current planetary positions without generating a chart image.
    Useful for quick lookups of where planets currently are.

    Args:
        lat: Latitude of location (positive=North, negative=South)
        lng: Longitude of location (positive=East, negative=West)
        tz_str: IANA timezone (e.g., "America/New_York")
        city, nation: Location city/nation (optional, chart labeling only)
        language: Output language (default: EN)
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"

    Returns:
        Dictionary with current planetary positions as text
    """
    logger.info(f"Getting current positions for lat={lat}, lng={lng}")

    validate_coordinates(lat, lng)
    validate_timezone(tz_str)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)
    city, nation = resolve_location(city, nation, lat, lng)

    # Create subject for current time
    now = AstrologicalSubjectFactory.from_current_time(
        name="Current Positions",
        lat=lat, lng=lng, tz_str=tz_str,
        city=city, nation=nation,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    result = {
        "status": "success",
        "chart_type": "Current Positions",
        "timestamp": str(now.utc_time) if hasattr(now, 'utc_time') else "current",
        "applied_settings": build_applied_settings(
            house_system, zodiac_type, sidereal_mode, language=language
        ),
        "text": to_context(now),
    }
    
    # Add lunar phase if available
    if now.lunar_phase:
        result["lunar_phase"] = {
            "phase_name": now.lunar_phase.moon_phase_name,
            "emoji": now.lunar_phase.moon_emoji,
        }
    
    logger.info("Current positions retrieved")
    return result


@mcp.tool()
@handle_chart_errors
def get_aspects(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    lat: float,
    lng: float,
    tz_str: str,
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
) -> dict:
    """
    Get detailed aspect list for a single chart without generating images.
    
    Returns all planetary aspects (conjunctions, trines, squares, oppositions, sextiles, etc.)
    with exact orb values. Useful for AI analysis of chart patterns.
    
    Args:
        name: Name of the chart subject
        year, month, day: Birth date
        hour, minute: Birth time
        lat, lng: Birth coordinates
        tz_str: IANA timezone
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal"
        sidereal_mode: Required if zodiac_type is "Sidereal" (e.g., "LAHIRI")
        
    Returns:
        dict: Contains:
        - aspects: List of aspects with planet names, type, and orb
        - aspect_count: Total count of aspects
    """
    logger.info("Getting aspects")
    logger.debug(f"Subject: {name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    house_system = validate_house_system(house_system)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)

    subject = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )
    
    aspect_result = AspectsFactory.single_chart_aspects(subject)
    
    # Format aspects for AI consumption
    aspects_list = []
    for aspect in aspect_result.aspects:
        aspects_list.append({
            "planet1": aspect.p1_name,
            "planet2": aspect.p2_name,
            "aspect_type": aspect.aspect,
            "orb": round(aspect.orbit, 2),
            "aspect_degrees": aspect.aspect_degrees,
        })
    
    result = {
        "status": "success",
        "chart_type": "Aspects",
        "subject_name": name,
        "applied_settings": build_applied_settings(house_system, zodiac_type, sidereal_mode),
        "aspect_count": len(aspects_list),
        "aspects": aspects_list,
    }
    
    logger.info(f"Found {len(aspects_list)} aspects")
    return result


@mcp.tool()
@handle_chart_errors
def get_synastry_aspects(
    name1: str,
    year1: int, month1: int, day1: int,
    hour1: int, minute1: int,
    lat1: float, lng1: float, tz_str1: str,
    name2: str,
    year2: int, month2: int, day2: int,
    hour2: int, minute2: int,
    lat2: float, lng2: float, tz_str2: str,
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
) -> dict:
    """
    Get aspects between two charts (synastry aspects) without generating images.

    Returns all inter-chart aspects showing how planets in one chart aspect planets
    in the other. Useful for relationship compatibility analysis.

    Args:
        name1: Name of first person
        year1, month1, day1: Birth date of first person
        hour1, minute1: Birth time of first person
        lat1, lng1: Birth coordinates of first person
        tz_str1: Timezone of first person's birth
        name2: Name of second person
        year2, month2, day2: Birth date of second person
        hour2, minute2: Birth time of second person
        lat2, lng2: Birth coordinates of second person
        tz_str2: Timezone of second person's birth
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"

    Returns:
        dict: Contains:
        - aspects: List of inter-chart aspects
        - aspect_count: Total count of aspects
    """
    logger.info("Getting synastry aspects")
    logger.debug(f"Subjects: {name1}, {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    house_system = validate_house_system(house_system)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)

    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )
    
    aspect_result = AspectsFactory.dual_chart_aspects(person1, person2)
    
    # Format aspects for AI consumption
    aspects_list = []
    for aspect in aspect_result.aspects:
        aspects_list.append({
            "planet1": f"{name1}:{aspect.p1_name}",
            "planet2": f"{name2}:{aspect.p2_name}",
            "aspect_type": aspect.aspect,
            "orb": round(aspect.orbit, 2),
            "aspect_degrees": aspect.aspect_degrees,
        })
    
    result = {
        "status": "success",
        "chart_type": "Synastry Aspects",
        "subjects": [name1, name2],
        "applied_settings": build_applied_settings(house_system, zodiac_type, sidereal_mode),
        "aspect_count": len(aspects_list),
        "aspects": aspects_list,
    }
    
    logger.info(f"Found {len(aspects_list)} synastry aspects")
    return result


@mcp.tool()
@handle_chart_errors
def get_chart_patterns(
    name: str,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    lat: float,
    lng: float,
    tz_str: str,
    house_system: str = "P",
    zodiac_type: str = "Tropical",
    sidereal_mode: Optional[str] = None,
) -> dict:
    """
    Detect chart patterns (stelliums, T-squares, grand trines, grand crosses,
    yods, kites) and element/mode balance for a single chart, without images.

    Detection runs over the ten classical-to-modern planets (Sun through
    Pluto) using the aspects kerykeion found with its own orb policy, except
    quincunxes (for yods), which are computed from longitudes with a 3-degree
    orb because kerykeion's single-chart aspect set omits them. Each pattern
    carries a neutral, growth-oriented one-line note.

    Args:
        name: Name of the chart subject
        year, month, day: Birth date
        hour, minute: Birth time
        lat, lng: Birth coordinates
        tz_str: IANA timezone
        house_system: House system identifier
        zodiac_type: "Tropical" or "Sidereal" (requires sidereal_mode, e.g. 'LAHIRI' for Vedic)
        sidereal_mode: Ayanamsha, required if zodiac_type is "Sidereal"

    Returns:
        dict: Contains:
        - patterns: List of detected patterns with type, planets, and note
        - element_balance / mode_balance: counts with missing categories flagged
    """
    logger.info("Detecting chart patterns")
    logger.debug(f"Subject: {name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    house_system = validate_house_system(house_system)
    zodiac_type = validate_zodiac_type(zodiac_type)
    sidereal_mode = validate_sidereal_mode(zodiac_type, sidereal_mode)

    subject = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
        sidereal_mode=sidereal_mode,
        online=False,
    )

    aspect_result = AspectsFactory.single_chart_aspects(subject)
    aspects = [
        {"p1": a.p1_name, "p2": a.p2_name, "type": a.aspect}
        for a in aspect_result.aspects
    ]
    planets = {}
    for planet_name in PATTERN_PLANETS:
        point = getattr(subject, planet_name.lower())
        planets[planet_name] = {
            "sign": point.sign,
            "element": point.element,
            "mode": point.quality,
            "abs_pos": point.abs_pos,
        }

    patterns = detect_patterns(planets, aspects)

    result = {
        "status": "success",
        "chart_type": "Chart Patterns",
        "subject_name": name,
        "applied_settings": build_applied_settings(house_system, zodiac_type, sidereal_mode),
        "pattern_count": len(patterns),
        "patterns": patterns,
        "element_balance": element_balance(planets),
        "mode_balance": mode_balance(planets),
    }

    logger.info(f"Found {len(patterns)} patterns")
    return result


# =============================================================================
# Server Entry Point
# =============================================================================

def main():
    """Start the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Kerykeion MCP Server")
    parser.add_argument("--sse", action="store_true", help="Serve legacy HTTP+SSE transport (deprecated)")
    parser.add_argument("--http", action="store_true", help="Serve Streamable HTTP transport")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind HTTP transports to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind HTTP transports to (default: 8000)")
    args = parser.parse_args()

    logger.info("Starting Kerykeion MCP Server")
    logger.info(f"PNG conversion available: {HAS_CAIROSVG}")

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            f"Binding to non-loopback host {args.host} exposes this server -- which "
            "accepts birth data (PII) and writes files -- to your network. Only do "
            "this on a trusted network, and prefer a tunnel over a public bind."
        )

    if args.sse:
        # Legacy HTTP+SSE transport, deprecated by the MCP spec (2025-03-26)
        # in favor of Streamable HTTP. Kept for backward compatibility.
        import uvicorn
        logger.warning("--sse uses the deprecated HTTP+SSE transport; prefer --http (Streamable HTTP)")
        logger.info(f"Running with HTTP+SSE transport on http://{args.host}:{args.port}")
        logger.info(f"SSE endpoint: http://{args.host}:{args.port}/sse")
        uvicorn.run(mcp.sse_app(), host=args.host, port=args.port)
    elif args.http:
        import uvicorn
        logger.info(f"Running with Streamable HTTP transport on http://{args.host}:{args.port}")
        uvicorn.run(mcp.streamable_http_app(), host=args.host, port=args.port)
    else:
        # Default: stdio transport for Claude Desktop
        logger.info("Running with stdio transport (use --http for HTTP mode)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
