"""
Chart pattern detection for the Kerykeion MCP server.

Pure functions over a pre-computed aspect list and planet positions -- no
ephemeris access, so unit tests can feed synthetic fixtures.

Detection and balance counts operate on the ten classical-to-modern planets
(Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto);
other bodies (nodes, Chiron, angles) are ignored even if present in the input.

Aspect inputs are the aspects kerykeion already found -- its orb policy is
reused, not re-derived -- with one exception: kerykeion's single-chart aspect
set does not include quincunxes, so Yod detection computes quincunxes locally
from absolute longitudes with a 3-degree orb.

Input shapes:
    planets: {"Sun": {"sign": "Gem", "element": "Air", "mode": "Mutable",
                      "abs_pos": 84.15}, ...}
    aspects: [{"p1": "Sun", "p2": "Moon", "type": "opposition"}, ...]
"""

from itertools import combinations
from typing import Iterable

PATTERN_PLANETS = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)

ELEMENTS = ("Fire", "Earth", "Air", "Water")
MODES = ("Cardinal", "Fixed", "Mutable")

STELLIUM_DEGREE_SPAN = 8.0
QUINCUNX_DEGREES = 150.0
QUINCUNX_ORB = 3.0


def _filter_planets(planets: dict) -> dict:
    return {name: p for name, p in planets.items() if name in PATTERN_PLANETS}


def _aspect_pairs(aspects: list[dict], aspect_type: str) -> set[frozenset]:
    return {
        frozenset((a["p1"], a["p2"]))
        for a in aspects
        if a["type"] == aspect_type
        and a["p1"] in PATTERN_PLANETS
        and a["p2"] in PATTERN_PLANETS
    }


def _shared(values: Iterable[str]) -> str:
    unique = set(values)
    return unique.pop() if len(unique) == 1 else "Mixed"


def _angular_distance(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def _stelliums_by_sign(planets: dict) -> list[dict]:
    by_sign: dict[str, list[str]] = {}
    for name, p in planets.items():
        by_sign.setdefault(p["sign"], []).append(name)
    return [
        {
            "type": "stellium_by_sign",
            "planets": sorted(members),
            "sign": sign,
            "note": "a concentration of energy inviting deliberate, conscious channeling of this sign's themes",
        }
        for sign, members in sorted(by_sign.items())
        if len(members) >= 3
    ]


def _stelliums_by_degree(planets: dict) -> list[dict]:
    """Clusters of >=3 planets within STELLIUM_DEGREE_SPAN that straddle a sign
    boundary (same-sign clusters are already covered by the sign variant)."""
    items = sorted((p["abs_pos"] % 360, name) for name, p in planets.items())
    n = len(items)
    if n < 3:
        return []
    # Unwrap the circle so clusters spanning 0 degrees Aries are contiguous.
    extended = items + [(pos + 360, name) for pos, name in items]
    clusters = []
    for i in range(n):
        j = i
        while j + 1 < i + n and extended[j + 1][0] - extended[i][0] <= STELLIUM_DEGREE_SPAN:
            j += 1
        if j - i + 1 >= 3:
            members = [name for _, name in extended[i:j + 1]]
            clusters.append((members, extended[j][0] - extended[i][0]))
    out = []
    seen: set[frozenset] = set()
    member_sets = [frozenset(m) for m, _ in clusters]
    for idx, (members, span) in enumerate(clusters):
        key = member_sets[idx]
        # Keep only maximal, distinct clusters.
        if key in seen or any(key < other for other in member_sets):
            continue
        seen.add(key)
        signs = sorted({planets[name]["sign"] for name in members})
        if len(signs) < 2:
            continue
        out.append({
            "type": "stellium_by_degree",
            "planets": sorted(members),
            "signs": signs,
            "span_degrees": round(span, 2),
            "note": "a tight cluster blending adjacent signs' themes into one concentrated focus",
        })
    return out


def _t_squares(planets: dict, opps: set[frozenset], squares: set[frozenset]) -> list[dict]:
    out = []
    seen = set()
    for pair in opps:
        a, b = sorted(pair)
        for apex in planets:
            if apex in pair:
                continue
            if frozenset((a, apex)) in squares and frozenset((b, apex)) in squares:
                key = (frozenset((a, b, apex)), apex)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "type": "t_square",
                    "planets": sorted((a, b, apex)),
                    "apex": apex,
                    "mode": _shared(planets[p]["mode"] for p in (a, b, apex)),
                    "note": "dynamic tension seeking constructive outlet through the apex planet",
                })
    return out


def _grand_trines(planets: dict, trines: set[frozenset]) -> list[dict]:
    out = []
    for trio in combinations(sorted(planets), 3):
        pairs = {frozenset(p) for p in combinations(trio, 2)}
        if pairs <= trines:
            out.append({
                "type": "grand_trine",
                "planets": list(trio),
                "element": _shared(planets[p]["element"] for p in trio),
                "note": "an easeful circuit of talent that rewards conscious activation rather than passive reliance",
            })
    return out


def _grand_crosses(planets: dict, opps: set[frozenset], squares: set[frozenset]) -> list[dict]:
    out = []
    for quad in combinations(sorted(planets), 4):
        pairs = [frozenset(p) for p in combinations(quad, 2)]
        quad_opps = [p for p in pairs if p in opps]
        if len(quad_opps) != 2 or quad_opps[0] & quad_opps[1]:
            continue
        if all(p in squares for p in pairs if p not in quad_opps):
            out.append({
                "type": "grand_cross",
                "planets": list(quad),
                "mode": _shared(planets[p]["mode"] for p in quad),
                "note": "sustained multidirectional tension that builds resilience and capacity when engaged consciously",
            })
    return out


def _kites(planets: dict, grand_trines: list[dict], opps: set[frozenset]) -> list[dict]:
    out = []
    for gt in grand_trines:
        for vertex in gt["planets"]:
            for tail in planets:
                if tail in gt["planets"]:
                    continue
                if frozenset((vertex, tail)) in opps:
                    out.append({
                        "type": "kite",
                        "planets": sorted(gt["planets"] + [tail]),
                        "trine_planets": gt["planets"],
                        "tail": tail,
                        "note": "a grand trine given direction -- the tail planet offers a concrete outlet for its ease",
                    })
    return out


def _yods(planets: dict, sextiles: set[frozenset]) -> list[dict]:
    out = []
    for pair in sorted(sextiles, key=sorted):
        base1, base2 = sorted(pair)
        if base1 not in planets or base2 not in planets:
            continue
        for apex in planets:
            if apex in pair:
                continue
            to_base1 = _angular_distance(planets[apex]["abs_pos"], planets[base1]["abs_pos"])
            to_base2 = _angular_distance(planets[apex]["abs_pos"], planets[base2]["abs_pos"])
            if (abs(to_base1 - QUINCUNX_DEGREES) <= QUINCUNX_ORB
                    and abs(to_base2 - QUINCUNX_DEGREES) <= QUINCUNX_ORB):
                out.append({
                    "type": "yod",
                    "planets": sorted((apex, base1, base2)),
                    "apex": apex,
                    "note": "an invitation to integrate two disparate talents through the apex planet's domain",
                })
    return out


def detect_patterns(planets: dict, aspects: list[dict]) -> list[dict]:
    """Detect chart patterns from planet positions and a kerykeion aspect list.

    Returns a list of pattern dicts, each with a "type", the "planets"
    involved, pattern-specific fields (apex/mode/element/sign/tail/...), and a
    neutral, growth-oriented "note". T-squares wholly contained in a detected
    grand cross are suppressed (the cross already accounts for them).
    """
    planets = _filter_planets(planets)
    opps = _aspect_pairs(aspects, "opposition")
    squares = _aspect_pairs(aspects, "square")
    trines = _aspect_pairs(aspects, "trine")
    sextiles = _aspect_pairs(aspects, "sextile")

    patterns = []
    patterns += _stelliums_by_sign(planets)
    patterns += _stelliums_by_degree(planets)
    crosses = _grand_crosses(planets, opps, squares)
    patterns += crosses
    cross_sets = [set(c["planets"]) for c in crosses]
    patterns += [
        t for t in _t_squares(planets, opps, squares)
        if not any(set(t["planets"]) <= cross for cross in cross_sets)
    ]
    grand_trines = _grand_trines(planets, trines)
    patterns += grand_trines
    patterns += _kites(planets, grand_trines, opps)
    patterns += _yods(planets, sextiles)
    return patterns


def element_balance(planets: dict) -> dict:
    """Element counts over the supplied planets (intended set: the ten planets
    in PATTERN_PLANETS). Missing elements are flagged explicitly -- an absent
    element is interpretively significant."""
    planets = _filter_planets(planets)
    counts = {element: 0 for element in ELEMENTS}
    for p in planets.values():
        counts[p["element"]] += 1
    return {"counts": counts, "missing": [e for e in ELEMENTS if counts[e] == 0]}


def mode_balance(planets: dict) -> dict:
    """Mode (quadruplicity) counts over the supplied planets (intended set:
    the ten planets in PATTERN_PLANETS). Missing modes are flagged."""
    planets = _filter_planets(planets)
    counts = {mode: 0 for mode in MODES}
    for p in planets.values():
        counts[p["mode"]] += 1
    return {"counts": counts, "missing": [m for m in MODES if counts[m] == 0]}
