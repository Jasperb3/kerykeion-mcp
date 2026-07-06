"""
Input validation for Kerykeion MCP tools.

Meaning-bearing parameters (house system, zodiac type, sidereal mode, chart
style) are rejected with an educational ChartInputError rather than silently
coerced to a default -- a wrong house system or ayanamsha changes which chart
the caller actually receives. Cosmetic parameters (theme, language) are still
coerced to a sane default since they don't change the astrological content.
"""

from datetime import datetime
from typing import Optional

import pytz

VALID_THEMES = ["classic", "light", "dark", "strawberry", "dark-high-contrast"]
VALID_LANGUAGES = ["EN", "IT", "FR", "ES", "PT", "CN", "RU", "TR", "DE", "HI"]
VALID_HOUSE_SYSTEMS = {
    "P": "Placidus",
    "W": "Whole Sign",
    "K": "Koch",
    "A": "Equal",
    "C": "Campanus",
    "R": "Regiomontanus",
    "M": "Morinus",
    "O": "Porphyry",
    "G": "Gauquelin (Sectors)",
}
VALID_ZODIAC_TYPES = ["Tropical", "Sidereal"]
# Matches kerykeion.AstrologicalSubjectFactory.from_birth_data's sidereal_mode
# Literal exactly (verified against installed kerykeion 5.6.0 via inspect.signature).
VALID_SIDEREAL_MODES = [
    "FAGAN_BRADLEY", "LAHIRI", "DELUCE", "RAMAN", "USHASHASHI",
    "KRISHNAMURTI", "DJWHAL_KHUL", "YUKTESHWAR", "JN_BHASIN",
    "BABYL_KUGLER1", "BABYL_KUGLER2", "BABYL_KUGLER3", "BABYL_HUBER",
    "BABYL_ETPSC", "ALDEBARAN_15TAU", "HIPPARCHOS", "SASSANIAN",
    "J2000", "J1900", "B1950",
]
VALID_CHART_STYLES = ["full", "wheel_only", "aspect_grid"]


class ChartInputError(ValueError):
    """Raised for invalid chart input; carries an educational message and hint."""

    def __init__(self, message: str, hint: str = ""):
        self.message = message
        self.hint = hint
        super().__init__(message)


def validate_theme(theme: str) -> str:
    """Validate and return theme, defaulting to 'classic' (cosmetic, coerced)."""
    if theme.lower() in VALID_THEMES:
        return theme.lower()
    return "classic"


def validate_language(language: str) -> str:
    """Validate and return language, defaulting to 'EN' (cosmetic, coerced)."""
    lang_upper = language.upper()
    if lang_upper in VALID_LANGUAGES:
        return lang_upper
    return "EN"


def validate_house_system(house_system: str) -> str:
    """Validate house system identifier; raises ChartInputError if invalid."""
    hs_upper = house_system.upper()
    if hs_upper in VALID_HOUSE_SYSTEMS:
        return hs_upper
    valid_list = ", ".join(f"{k} ({v})" for k, v in VALID_HOUSE_SYSTEMS.items())
    raise ChartInputError(
        f"Invalid house_system '{house_system}'.",
        hint=f"Valid house systems are: {valid_list}",
    )


def validate_chart_style(chart_style: str) -> str:
    """Validate chart style; raises ChartInputError if invalid."""
    if chart_style.lower() in VALID_CHART_STYLES:
        return chart_style.lower()
    raise ChartInputError(
        f"Invalid chart_style '{chart_style}'.",
        hint=f"Valid chart styles are: {', '.join(VALID_CHART_STYLES)}",
    )


def validate_zodiac_type(zodiac_type: str) -> str:
    """Validate zodiac type; raises ChartInputError if invalid."""
    if zodiac_type in VALID_ZODIAC_TYPES:
        return zodiac_type
    raise ChartInputError(
        f"Invalid zodiac_type '{zodiac_type}'.",
        hint=f"Valid zodiac types are: {', '.join(VALID_ZODIAC_TYPES)}",
    )


def validate_sidereal_mode(zodiac_type: str, sidereal_mode: Optional[str]) -> Optional[str]:
    """
    Validate sidereal_mode given the (already-validated) zodiac_type.

    Requires sidereal_mode when zodiac_type == "Sidereal" -- never silently
    picks an ayanamsha (kerykeion itself defaults to FAGAN_BRADLEY, which is
    not what "Vedic" means to most callers).
    """
    if zodiac_type != "Sidereal":
        return None
    if sidereal_mode is None:
        raise ChartInputError(
            "zodiac_type='Sidereal' requires an explicit sidereal_mode.",
            hint=(
                "Common ayanamshas: LAHIRI (standard for Vedic/Jyotish work), "
                "FAGAN_BRADLEY (Western sidereal), RAMAN, KRISHNAMURTI. "
                f"Full list: {', '.join(VALID_SIDEREAL_MODES)}"
            ),
        )
    mode_upper = sidereal_mode.upper()
    if mode_upper not in VALID_SIDEREAL_MODES:
        raise ChartInputError(
            f"Invalid sidereal_mode '{sidereal_mode}'.",
            hint=f"Valid sidereal modes are: {', '.join(VALID_SIDEREAL_MODES)}",
        )
    return mode_upper


def validate_coordinates(lat: float, lng: float, label: str = "") -> None:
    """Validate latitude/longitude ranges; raises ChartInputError if out of range."""
    prefix = f"{label}: " if label else ""
    if not (-90 <= lat <= 90):
        hint = ""
        if abs(lat) > 90 and abs(lng) <= 90:
            hint = "Did you swap latitude and longitude?"
        raise ChartInputError(
            f"{prefix}Latitude {lat} is outside the valid range -90 to +90 (positive = North).",
            hint=hint,
        )
    if not (-180 <= lng <= 180):
        hint = ""
        if abs(lng) > 180 and abs(lat) <= 180 and abs(lat) > 90:
            hint = "Did you swap latitude and longitude?"
        raise ChartInputError(
            f"{prefix}Longitude {lng} is outside the valid range -180 to +180 (positive = East).",
            hint=hint,
        )


def validate_datetime_fields(
    year: int, month: int, day: int, hour: int, minute: int, label: str = ""
) -> None:
    """Validate a birth/event date and time; raises ChartInputError if invalid."""
    prefix = f"{label}: " if label else ""
    if not (0 <= hour <= 23):
        raise ChartInputError(
            f"{prefix}Hour {hour} is outside the valid range 0-23.",
        )
    if not (0 <= minute <= 59):
        raise ChartInputError(
            f"{prefix}Minute {minute} is outside the valid range 0-59.",
        )
    try:
        datetime(year, month, day)
    except ValueError as e:
        raise ChartInputError(
            f"{prefix}Invalid date year={year}, month={month}, day={day}: {e}",
        ) from e


def validate_timezone(tz_str: str, label: str = "") -> None:
    """Validate an IANA timezone string; raises ChartInputError if invalid."""
    prefix = f"{label}: " if label else ""
    try:
        pytz.timezone(tz_str)
    except pytz.exceptions.UnknownTimeZoneError as e:
        raise ChartInputError(
            f"{prefix}Unknown timezone '{tz_str}'.",
            hint=(
                "Use IANA timezone format, e.g. 'Europe/Rome', "
                "'America/New_York', 'Asia/Tokyo'."
            ),
        ) from e
