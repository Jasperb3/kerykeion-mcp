"""
Composite houses: each cusp is the midpoint of the two charts' cusps of the
same number, hung from the Ascendant -- the same construction as the
immanuel MCP server (0.12.2): cusp n = Asc midpoint + the mean of each
chart's (cusp n - Asc) mod 360, which equals the plain midpoint whenever
nothing wraps. kerykeion's default anchor ("auto") holds the Midheaven for
some pairs instead, turning the whole ring (Ascendant included) half a
circle from immanuel's: 40 of 576 London/Svalbard pairs.
"""

import math

import pytest

from kerykeion_mcp.server import ACTIVE_POINTS, SubjectFactory, composite_subject

HOUSES = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
          "eighth", "ninth", "tenth", "eleventh", "twelfth"]
PLANETS = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
           "uranus", "neptune", "pluto"]


def arc(a, b):
    return abs((a - b + 180) % 360 - 180)


def mean(a, b):
    """Shorter-arc midpoint of two longitudes."""
    return math.degrees(math.atan2(math.sin(math.radians(a)) + math.sin(math.radians(b)),
                                   math.cos(math.radians(a)) + math.cos(math.radians(b)))) % 360


def cusps(subject):
    return [getattr(subject, f"{name}_house").abs_pos for name in HOUSES]


def expected_cusps(first, second):
    asc1, asc2 = first.ascendant.abs_pos, second.ascendant.abs_pos
    origin = mean(asc1, asc2)
    return [(origin + (((c1 - asc1) % 360) + ((c2 - asc2) % 360)) / 2) % 360
            for c1, c2 in zip(cusps(first), cusps(second))]


def house_of(longitude, ring):
    for number in range(12):
        start, end = ring[number], ring[(number + 1) % 12]
        if (longitude - start) % 360 < (end - start) % 360:
            return number + 1


def pair_at(hour1, hour2, house_system="O"):
    kwargs = dict(online=False, active_points=ACTIVE_POINTS, houses_system_identifier=house_system)
    london = SubjectFactory.from_birth_data(
        name="London", year=1985, month=6, day=21, hour=hour1, minute=0,
        lat=51.5074, lng=-0.1278, tz_str="Europe/London", **kwargs)
    svalbard = SubjectFactory.from_birth_data(
        name="Svalbard", year=1990, month=1, day=15, hour=hour2, minute=0,
        lat=78.22, lng=15.63, tz_str="UTC", **kwargs)
    return london, svalbard


# Includes London 18:00 / Svalbard 0:00 and 8:00, two pairs where kerykeion's
# "auto" anchor turned the ring half a circle.
GRID = [(h1, h2) for h1 in range(0, 24, 2) for h2 in range(0, 24, 2)]


@pytest.mark.parametrize("hour1,hour2", GRID)
def test_composite_houses_hang_from_the_ascendant(hour1, hour2):
    first, second = pair_at(hour1, hour2)
    composite = composite_subject(first, second)
    ring = cusps(composite)

    for got, want in zip(ring, expected_cusps(first, second)):
        assert arc(got, want) < 0.01
    # Each cusp is a midpoint (near or far) of the two cusps of its number.
    for got, c1, c2 in zip(ring, cusps(first), cusps(second)):
        assert min(arc(got, mean(c1, c2)), arc(got, mean(c1, c2) + 180)) < 0.01
    assert arc(composite.ascendant.abs_pos, ring[0]) < 0.01
    assert arc(composite.medium_coeli.abs_pos, ring[9]) < 0.01
    for name in PLANETS:
        planet = getattr(composite, name)
        assert planet.house == f"{HOUSES[house_of(planet.abs_pos, ring) - 1].title()}_House", name


def test_the_auto_anchor_would_have_turned_these_pairs():
    """Guards that the grid really contains pairs the anchor decides."""
    from kerykeion import CompositeSubjectFactory
    turned = 0
    for hour1, hour2 in GRID:
        first, second = pair_at(hour1, hour2)
        auto = CompositeSubjectFactory(first, second).get_midpoint_composite_subject_model()
        if arc(auto.ascendant.abs_pos, composite_subject(first, second).ascendant.abs_pos) > 90:
            turned += 1
    assert turned > 0
