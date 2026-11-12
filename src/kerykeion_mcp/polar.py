"""
Cast charts inside the polar circles at their true latitude.

kerykeion 5.6 clamps every latitude beyond +/-66 deg to exactly +/-66 deg
before calculating anything (LocationData.prepare_for_calculation calls
utilities.check_and_adjust_polar_latitude) and logs it only at INFO. The
chart is then cast for the wrong place: at Tromso (69.65N) the Ascendant is
13 deg out, at Longyearbyen 138 deg, whatever house system was asked for.
The clamp exists because the Swiss Ephemeris refuses Placidus and Koch at
|lat| >= 90 deg - obliquity (about 66.56 deg): pyswisseph raises
"swisseph.houses_ex2: within polar circle, switched to Porphyry".

install() patches two names in kerykeion.astrological_subject_factory, and
only there (the utilities function and the swisseph module are untouched):

- check_and_adjust_polar_latitude (a from-import there) becomes a
  pass-through, so charts use their real latitude and Placidus/Koch inside
  the circles raise instead of being silently moved.
- swe becomes a proxy whose houses() and houses_ex() -- the calls kerykeion
  makes -- re-ask houses_ex2() when they fail. pyswisseph's houses() and
  houses_ex() raise a bare "swisseph.houses: error"; only houses_ex2()
  carries the Swiss Ephemeris's reason ("within polar circle, switched to
  Porphyry"). Successful calls never reach houses_ex2, so every other chart
  is computed exactly as before.

build_subject() catches that polar error and rebuilds the subject with
Porphyry -- what the Swiss Ephemeris C library had already switched to, and
what the immanuel MCP server does -- so both engines' cusps agree. The
fallback is visible on the subject (houses_system_identifier "O"), and the
server reports it in applied_settings and warnings.

Far inside the circles, Regiomontanus and Campanus cusps can run backwards
through the zodiac (Longyearbyen, 78N). The Swiss Ephemeris casts them, but
kerykeion's house placement (utilities.is_point_between) cannot use them and
raises; build_subject() turns that into an educational ChartInputError
rather than substituting a system.
"""

import logging
from importlib import metadata

import swisseph as swe
import kerykeion.astrological_subject_factory as _subject_factory
from kerykeion import KerykeionException

from .validation import ChartInputError, VALID_HOUSE_SYSTEMS

logger = logging.getLogger(__name__)

# The kerykeion releases whose astrological_subject_factory.py this was checked
# against. Widen only after re-reading LocationData.prepare_for_calculation and
# AstrologicalSubjectFactory._calculate_houses.
SUPPORTED = ("5.6.",)
POLAR_MESSAGE = "polar circle"
SPAN_MESSAGE = "The angle between start and end point is not allowed to exceed 180°"
PORPHYRY = "O"


def _true_latitude(latitude: float) -> float:
    return latitude


def _with_reason(function):
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except swe.Error:
            # Same arguments, positionally and by keyword: houses_ex2 raises
            # the descriptive error; if it somehow succeeds, keep the original.
            swe.houses_ex2(*args, **kwargs)
            raise
    call.__name__ = function.__name__
    return call


class _SwissEphemerisWithReasons:
    """swisseph, with the two house functions kerykeion calls explaining failures."""

    houses = staticmethod(_with_reason(swe.houses))
    houses_ex = staticmethod(_with_reason(swe.houses_ex))

    def __getattr__(self, name):
        return getattr(swe, name)


PROXY = _SwissEphemerisWithReasons()


def installed() -> bool:
    return (_subject_factory.check_and_adjust_polar_latitude is _true_latitude
            and _subject_factory.swe is PROXY)


def install() -> None:
    version = metadata.version("kerykeion")
    if not version.startswith(SUPPORTED):
        raise RuntimeError(
            f"kerykeion {version} is not one the polar-latitude shim was checked "
            f"against ({', '.join(SUPPORTED)}x). Re-check "
            f"kerykeion.astrological_subject_factory for the latitude clamp and "
            f"update kerykeion_mcp/polar.py.")
    if not hasattr(_subject_factory, "check_and_adjust_polar_latitude"):
        raise RuntimeError(
            "kerykeion.astrological_subject_factory no longer imports "
            "check_and_adjust_polar_latitude; update kerykeion_mcp/polar.py.")
    if _subject_factory.swe is not swe and _subject_factory.swe is not PROXY:
        raise RuntimeError("kerykeion.astrological_subject_factory.swe is not the swisseph module")
    _subject_factory.check_and_adjust_polar_latitude = _true_latitude
    _subject_factory.swe = PROXY


def is_polar_error(error: Exception) -> bool:
    return isinstance(error, swe.Error) and POLAR_MESSAGE in str(error)


def build_subject(factory, **kwargs):
    """
    Call an AstrologicalSubjectFactory constructor; if the Swiss Ephemeris
    refuses the house system inside a polar circle, rebuild with Porphyry.
    The Swiss Ephemeris decides -- there is no latitude test here.
    """
    house_system = kwargs["houses_system_identifier"]
    try:
        return factory(**kwargs)
    except swe.Error as error:
        if not is_polar_error(error):
            raise
        logger.info("Polar circle: %s houses fell back to Porphyry", house_system)
        return factory(**{**kwargs, "houses_system_identifier": PORPHYRY})
    except KerykeionException as error:
        if not str(error).startswith(SPAN_MESSAGE):
            raise
        name = VALID_HOUSE_SYSTEMS.get(house_system, house_system)
        raise ChartInputError(
            f"At this time and latitude ({kwargs.get('lat')}) the {name} house cusps "
            f"run out of zodiacal order, which happens far inside the polar circles; "
            f"kerykeion cannot place planets in those houses.",
            hint=(
                "Use a system whose cusps always run forward: Porphyry (\"O\"), "
                "Equal (\"A\"), Whole Sign (\"W\") or Morinus (\"M\")."
            ),
        ) from error


def fell_back(subject, requested: str) -> bool:
    """True if this subject's houses are Porphyry because of the polar fallback."""
    return requested != PORPHYRY and subject.houses_system_identifier == PORPHYRY
