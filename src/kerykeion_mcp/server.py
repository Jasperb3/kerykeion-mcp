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

Output formats:
- "text": AI-readable text description (always included)
- "svg": SVG chart image as base64 data URI
- "png": PNG chart image as base64 data URI (if cairosvg available)
- "all": All available formats

Common timezones: UTC, Europe/London, Europe/Paris, Europe/Rome, 
America/New_York, America/Los_Angeles, Asia/Tokyo, Australia/Sydney
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
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    zodiac_type: str = "Tropical",
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
        theme: Chart theme - "classic", "light", "dark", "strawberry", "dark-high-contrast"
        language: Chart language - "EN", "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"
        house_system: House system - "P" (Placidus), "W" (Whole Sign), "K" (Koch), etc.
        zodiac_type: "Tropical" (Western) or "Sidereal" (Vedic)
        output_format: "text" (text only), "images" (text + save images), or "all"
        output_dir: Directory to save chart images (optional)
        chart_style: "full" (complete chart), "wheel_only" (just the wheel), "aspect_grid" (just aspects table)

    Returns:
        dict: status, applied_settings (settings actually used), text analysis, and file paths
    """
    logger.info(f"Generating natal chart for {name}")

    # Validate inputs
    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)
    chart_style = validate_chart_style(chart_style)
    zodiac_type = validate_zodiac_type(zodiac_type)

    # Create astrological subject
    subject = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        houses_system_identifier=house_system,
        zodiac_type=zodiac_type,
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
            house_system, zodiac_type, theme=theme, language=language, chart_style=chart_style
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

    logger.info(f"Natal chart generated for {name}")
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
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    include_relationship_score: bool = True,
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a synastry chart comparing two people for compatibility analysis.
    
    EMBEDDING IN CLAUDE ARTIFACTS:
    
    Method 1: SVG Embedded in HTML (Recommended)
      - Response includes 'svg_content' - full SVG markup
      - Create HTML artifact: <html><body>{svg_content}</body></html>
    
    Method 2: PNG with File Path
      - Response includes 'png_path' - local file path
      - Create markdown: ![Chart](file:///{png_path})
    
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
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        include_relationship_score: Include compatibility score calculation
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        
    Returns:
        dict: Synastry analysis with status, summary, and file paths
    """
    logger.info(f"Generating synastry chart for {name1} and {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)

    # Create both subjects
    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        houses_system_identifier=house_system,
        online=False,
    )

    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        houses_system_identifier=house_system,
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
            house_system, theme=theme, language=language, chart_style=chart_style
        ),
        "text": to_context(synastry_data),
    }
    
    # Add relationship score if available
    if include_relationship_score and synastry_data.relationship_score:
        result["relationship_score"] = synastry_data.relationship_score.score_value
    
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
    
    logger.info(f"Synastry chart generated for {name1} and {name2}")
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
    transit_year: Optional[int] = None,
    transit_month: Optional[int] = None,
    transit_day: Optional[int] = None,
    transit_hour: Optional[int] = None,
    transit_minute: Optional[int] = None,
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a transit chart showing current (or specified) planetary transits to a natal chart.
    
    EMBEDDING IN CLAUDE ARTIFACTS:
      - Response includes 'svg_content' for HTML: <html><body>{svg_content}</body></html>
      - Response includes 'png_path' for markdown: ![Chart](file:///{png_path})
    
    If transit date/time is not specified, uses current time.
    
    Args:
        natal_name: Name of the natal chart subject
        natal_year, natal_month, natal_day: Birth date
        natal_hour, natal_minute: Birth time
        natal_lat, natal_lng: Birth coordinates
        natal_tz_str: Birth timezone
        transit_lat, transit_lng: Current/transit location coordinates
        transit_tz_str: Current/transit timezone
        transit_year, transit_month, transit_day: Transit date (optional, defaults to now)
        transit_hour, transit_minute: Transit time (optional, defaults to now)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        
    Returns:
        dict: Transit analysis with status, summary, and file paths
    """
    logger.info(f"Generating transit chart for {natal_name}")

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

    # Create natal subject
    natal = AstrologicalSubjectFactory.from_birth_data(
        name=natal_name,
        year=natal_year, month=natal_month, day=natal_day,
        hour=natal_hour, minute=natal_minute,
        lat=natal_lat, lng=natal_lng, tz_str=natal_tz_str,
        houses_system_identifier=house_system,
        online=False,
    )
    
    # Create transit subject - either current time or specified time
    if all(v is not None for v in [transit_year, transit_month, transit_day, transit_hour, transit_minute]):
        transit = AstrologicalSubjectFactory.from_birth_data(
            name="Transits",
            year=transit_year, month=transit_month, day=transit_day,
            hour=transit_hour, minute=transit_minute,
            lat=transit_lat, lng=transit_lng, tz_str=transit_tz_str,
            online=False,
        )
    else:
        transit = AstrologicalSubjectFactory.from_current_time(
            name="Current Transits",
            lat=transit_lat, lng=transit_lng, tz_str=transit_tz_str,
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
            house_system, theme=theme, language=language, chart_style=chart_style
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
    
    logger.info(f"Transit chart generated for {natal_name}")
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
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a composite chart (midpoint composite) for two people.
    
    EMBEDDING IN CLAUDE ARTIFACTS:
      - Response includes 'svg_content' for HTML: <html><body>{svg_content}</body></html>
      - Response includes 'png_path' for markdown: ![Chart](file:///{png_path})
    
    A composite chart creates a single chart representing the relationship 
    by calculating the midpoints of each planet between two charts.
    
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
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        
    Returns:
        dict: Composite chart with status, summary, and file paths
    """
    logger.info(f"Generating composite chart for {name1} and {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)

    # Create both subjects
    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        houses_system_identifier=house_system,
        online=False,
    )
    
    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        houses_system_identifier=house_system,
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
            house_system, theme=theme, language=language, chart_style=chart_style
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
    
    logger.info(f"Composite chart generated for {name1} and {name2}")
    return result


@mcp.tool()
@handle_chart_errors
def generate_planetary_return(
    name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    lat: float, lng: float, tz_str: str,
    return_type: str = "Solar",
    return_year: Optional[int] = None,
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate a planetary return chart (Solar Return, Lunar Return)
    
    EMBEDDING IN CLAUDE ARTIFACTS:
      - Response includes 'svg_content' for HTML: <html><body>{svg_content}</body></html>
      - Response includes 'png_path' for markdown: ![Chart](file:///{png_path})
    
    A return chart is calculated for when a planet returns to its natal position.
    Solar returns occur yearly, lunar returns monthly.
    
    Args:
        name: Name of the chart subject
        year, month, day: Birth date
        hour, minute: Birth time
        lat, lng: Birth coordinates
        tz_str: Birth timezone
        return_type: "Solar" (yearly) or "Lunar" (monthly)
        return_year: Year for the return (defaults to current year)
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        
    Returns:
        dict: Return chart with status, summary, and file paths
    """
    if return_type not in ("Solar", "Lunar"):
        raise ChartInputError(
            f"Invalid return_type '{return_type}'.",
            hint="Valid return types are: Solar, Lunar",
        )

    logger.info(f"Generating {return_type} return for {name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)

    if return_year is None:
        return_year = datetime.now().year

    # Create natal subject
    natal = AstrologicalSubjectFactory.from_birth_data(
        name=name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        houses_system_identifier=house_system,
        online=False,
    )
    
    # Create return factory and get return subject
    return_factory = PlanetaryReturnFactory(
        subject=natal,
        lat=lat,
        lng=lng,
        tz_str=tz_str,
        online=False,
    )
    # Use next_return_from_date (next_return_from_year is deprecated)
    return_model = return_factory.next_return_from_date(
        year=return_year,
        month=1,
        day=1,
        return_type=return_type,
    )
    
    # PlanetReturnModel IS the subject itself (has all planetary positions)
    return_data = ChartDataFactory.create_natal_chart_data(return_model)
    
    result = {
        "status": "success",
        "chart_type": f"{return_type} Return",
        "subject_name": name,
        "return_year": return_year,
        "return_date": return_model.iso_formatted_local_datetime if hasattr(return_model, 'iso_formatted_local_datetime') else None,
        "applied_settings": build_applied_settings(
            house_system, theme=theme, language=language, chart_style=chart_style
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
    
    logger.info(f"{return_type} return chart generated for {name}")
    return result


@mcp.tool()
@handle_chart_errors
def generate_event_chart(
    event_name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    lat: float, lng: float, tz_str: str,
    theme: str = "classic",
    language: str = "EN",
    house_system: str = "P",
    output_format: OutputFormat = "all",
    output_dir: Optional[str] = None,
    chart_style: ChartStyle = "full",
) -> dict:
    """
    Generate an event chart for a specific moment in time (electional, horary, event).
    
    EMBEDDING IN CLAUDE ARTIFACTS:
      - Response includes 'svg_content' for HTML: <html><body>{svg_content}</body></html>
      - Response includes 'png_path' for markdown: ![Chart](file:///{png_path})
    
    Use this for analyzing the astrological conditions at any specific moment,
    such as the start of a business, a question asked, or an important event.
    
    Args:
        event_name: Name/description of the event
        year, month, day: Event date
        hour, minute: Event time
        lat, lng: Event location coordinates
        tz_str: Event timezone
        theme: Chart theme
        language: Chart language (default: EN)
        house_system: House system identifier
        output_format: "text", "images", or "all"
        output_dir: Directory to save chart images (optional)
        
    Returns:
        dict: Event chart with status, summary, and file paths
    """
    logger.info(f"Generating event chart for {event_name}")

    validate_coordinates(lat, lng)
    validate_datetime_fields(year, month, day, hour, minute)
    validate_timezone(tz_str)
    theme = validate_theme(theme)
    language = validate_language(language)
    house_system = validate_house_system(house_system)

    # Create subject for the event moment
    event_subject = AstrologicalSubjectFactory.from_birth_data(
        name=event_name,
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        houses_system_identifier=house_system,
        online=False,
    )
    
    chart_data = ChartDataFactory.create_natal_chart_data(event_subject)
    
    result = {
        "status": "success",
        "chart_type": "Event",
        "event_name": event_name,
        "applied_settings": build_applied_settings(
            house_system, theme=theme, language=language, chart_style=chart_style
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
    
    logger.info(f"Event chart generated for {event_name}")
    return result


@mcp.tool()
@handle_chart_errors
def get_current_positions(
    lat: float,
    lng: float,
    tz_str: str,
    language: str = "EN",
) -> dict:
    """
    Get current planetary positions for a specific location.
    
    Returns a text description of current planetary positions without generating a chart image.
    Useful for quick lookups of where planets currently are.
    
    Args:
        lat: Latitude of location (positive=North, negative=South)
        lng: Longitude of location (positive=East, negative=West)
        tz_str: IANA timezone (e.g., "America/New_York")
        language: Output language (default: EN)
        
    Returns:
        Dictionary with current planetary positions as text
    """
    logger.info(f"Getting current positions for lat={lat}, lng={lng}")

    validate_coordinates(lat, lng)
    validate_timezone(tz_str)
    language = validate_language(language)

    # Create subject for current time
    now = AstrologicalSubjectFactory.from_current_time(
        name="Current Positions",
        lat=lat, lng=lng, tz_str=tz_str,
        online=False,
    )

    result = {
        "status": "success",
        "chart_type": "Current Positions",
        "timestamp": str(now.utc_time) if hasattr(now, 'utc_time') else "current",
        "applied_settings": build_applied_settings("P", language=language),
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
    logger.info(f"Getting aspects for {name}")

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
    
    logger.info(f"Found {len(aspects_list)} aspects for {name}")
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
        
    Returns:
        dict: Contains:
        - aspects: List of inter-chart aspects
        - aspect_count: Total count of aspects
    """
    logger.info(f"Getting synastry aspects for {name1} and {name2}")

    validate_coordinates(lat1, lng1, label="Person 1")
    validate_datetime_fields(year1, month1, day1, hour1, minute1, label="Person 1")
    validate_timezone(tz_str1, label="Person 1")
    validate_coordinates(lat2, lng2, label="Person 2")
    validate_datetime_fields(year2, month2, day2, hour2, minute2, label="Person 2")
    validate_timezone(tz_str2, label="Person 2")
    house_system = validate_house_system(house_system)

    person1 = AstrologicalSubjectFactory.from_birth_data(
        name=name1, year=year1, month=month1, day=day1,
        hour=hour1, minute=minute1,
        lat=lat1, lng=lng1, tz_str=tz_str1,
        houses_system_identifier=house_system,
        online=False,
    )
    
    person2 = AstrologicalSubjectFactory.from_birth_data(
        name=name2, year=year2, month=month2, day=day2,
        hour=hour2, minute=minute2,
        lat=lat2, lng=lng2, tz_str=tz_str2,
        houses_system_identifier=house_system,
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
        "applied_settings": build_applied_settings(house_system),
        "aspect_count": len(aspects_list),
        "aspects": aspects_list,
    }
    
    logger.info(f"Found {len(aspects_list)} synastry aspects between {name1} and {name2}")
    return result


# =============================================================================
# Server Entry Point
# =============================================================================

def main():
    """Start the MCP server."""
    import sys
    
    logger.info("Starting Kerykeion MCP Server")
    logger.info(f"PNG conversion available: {HAS_CAIROSVG}")
    
    # Check for --sse flag for SSE transport (ChatGPT/remote)
    if "--sse" in sys.argv or "--http" in sys.argv:
        # Use streamable HTTP transport with uvicorn
        import uvicorn
        logger.info("Running with HTTP transport on http://0.0.0.0:8000")
        logger.info("SSE endpoint: http://localhost:8000/sse")
        uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)
    else:
        # Default: stdio transport for Claude Desktop
        logger.info("Running with stdio transport (use --sse for HTTP mode)")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
