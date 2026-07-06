"""
Unit tests for the pattern detection module (B2).

All detection tests use synthetic planet/aspect fixtures -- no ephemeris.
Signs/elements/modes use kerykeion's value style ("Ari", "Fire", "Cardinal").
"""

from kerykeion_mcp.patterns import detect_patterns, element_balance, mode_balance


def planet(sign, element, mode, abs_pos):
    return {"sign": sign, "element": element, "mode": mode, "abs_pos": abs_pos}


def aspect(p1, p2, aspect_type):
    return {"p1": p1, "p2": p2, "type": aspect_type}


def of_type(patterns, pattern_type):
    return [p for p in patterns if p["type"] == pattern_type]


# ---------------------------------------------------------------- stelliums

def test_stellium_by_sign_detected():
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 5.0),
        "Mercury": planet("Ari", "Fire", "Cardinal", 15.0),
        "Venus": planet("Ari", "Fire", "Cardinal", 28.0),
        "Moon": planet("Lib", "Air", "Cardinal", 185.0),
    }
    found = of_type(detect_patterns(planets, []), "stellium_by_sign")
    assert len(found) == 1
    assert found[0]["sign"] == "Ari"
    assert sorted(found[0]["planets"]) == ["Mercury", "Sun", "Venus"]
    assert found[0]["note"]


def test_no_stellium_with_only_two_planets_in_sign():
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 5.0),
        "Mercury": planet("Ari", "Fire", "Cardinal", 15.0),
        "Moon": planet("Lib", "Air", "Cardinal", 185.0),
    }
    assert of_type(detect_patterns(planets, []), "stellium_by_sign") == []


def test_stellium_by_degree_across_sign_boundary():
    # 7-degree span straddling Aries/Taurus: no single sign holds 3 planets.
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 28.0),
        "Moon": planet("Tau", "Earth", "Fixed", 32.0),
        "Mars": planet("Tau", "Earth", "Fixed", 35.0),
    }
    found = of_type(detect_patterns(planets, []), "stellium_by_degree")
    assert len(found) == 1
    assert sorted(found[0]["planets"]) == ["Mars", "Moon", "Sun"]
    assert found[0]["span_degrees"] == 7.0
    assert sorted(found[0]["signs"]) == ["Ari", "Tau"]


def test_stellium_by_degree_boundary_orb():
    base = {
        "Sun": planet("Ari", "Fire", "Cardinal", 28.0),
        "Moon": planet("Tau", "Earth", "Fixed", 32.0),
    }
    at_orb = dict(base, Mars=planet("Tau", "Earth", "Fixed", 36.0))  # span exactly 8
    past_orb = dict(base, Mars=planet("Tau", "Earth", "Fixed", 36.1))  # span 8.1
    assert of_type(detect_patterns(at_orb, []), "stellium_by_degree")
    assert not of_type(detect_patterns(past_orb, []), "stellium_by_degree")


def test_stellium_by_degree_wraps_zero_aries_point():
    planets = {
        "Sun": planet("Pis", "Water", "Mutable", 357.0),
        "Moon": planet("Ari", "Fire", "Cardinal", 1.0),
        "Mars": planet("Ari", "Fire", "Cardinal", 3.0),
    }
    found = of_type(detect_patterns(planets, []), "stellium_by_degree")
    assert len(found) == 1
    assert sorted(found[0]["planets"]) == ["Mars", "Moon", "Sun"]


def test_same_sign_cluster_not_reported_as_degree_stellium():
    # Tight cluster inside one sign is a sign stellium, not a degree stellium.
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 10.0),
        "Moon": planet("Ari", "Fire", "Cardinal", 12.0),
        "Mars": planet("Ari", "Fire", "Cardinal", 14.0),
    }
    patterns = detect_patterns(planets, [])
    assert of_type(patterns, "stellium_by_sign")
    assert not of_type(patterns, "stellium_by_degree")


# ---------------------------------------------------------------- t-squares

T_SQUARE_PLANETS = {
    "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
    "Moon": planet("Lib", "Air", "Cardinal", 180.0),
    "Mars": planet("Can", "Water", "Cardinal", 90.0),
    "Jupiter": planet("Sag", "Fire", "Mutable", 250.0),
}

T_SQUARE_ASPECTS = [
    aspect("Sun", "Moon", "opposition"),
    aspect("Sun", "Mars", "square"),
    aspect("Moon", "Mars", "square"),
]


def test_t_square_detected_with_apex_and_mode():
    found = of_type(detect_patterns(T_SQUARE_PLANETS, T_SQUARE_ASPECTS), "t_square")
    assert len(found) == 1
    assert found[0]["apex"] == "Mars"
    assert found[0]["mode"] == "Cardinal"
    assert sorted(found[0]["planets"]) == ["Mars", "Moon", "Sun"]
    assert found[0]["note"]


def test_no_t_square_when_one_square_missing():
    aspects = [a for a in T_SQUARE_ASPECTS if not (a["p1"] == "Moon" and a["p2"] == "Mars")]
    assert of_type(detect_patterns(T_SQUARE_PLANETS, aspects), "t_square") == []


# ------------------------------------------------------------- grand trines

GRAND_TRINE_PLANETS = {
    "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
    "Moon": planet("Leo", "Fire", "Fixed", 120.0),
    "Jupiter": planet("Sag", "Fire", "Mutable", 240.0),
    "Saturn": planet("Lib", "Air", "Cardinal", 180.0),
}

GRAND_TRINE_ASPECTS = [
    aspect("Sun", "Moon", "trine"),
    aspect("Moon", "Jupiter", "trine"),
    aspect("Sun", "Jupiter", "trine"),
]


def test_grand_trine_detected_with_element():
    found = of_type(detect_patterns(GRAND_TRINE_PLANETS, GRAND_TRINE_ASPECTS), "grand_trine")
    assert len(found) == 1
    assert found[0]["element"] == "Fire"
    assert sorted(found[0]["planets"]) == ["Jupiter", "Moon", "Sun"]


def test_no_grand_trine_without_third_trine():
    aspects = GRAND_TRINE_ASPECTS[:2]
    assert of_type(detect_patterns(GRAND_TRINE_PLANETS, aspects), "grand_trine") == []


# ------------------------------------------------------------ grand crosses

GRAND_CROSS_PLANETS = {
    "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
    "Moon": planet("Can", "Water", "Cardinal", 90.0),
    "Mars": planet("Lib", "Air", "Cardinal", 180.0),
    "Saturn": planet("Cap", "Earth", "Cardinal", 270.0),
}

GRAND_CROSS_ASPECTS = [
    aspect("Sun", "Mars", "opposition"),
    aspect("Moon", "Saturn", "opposition"),
    aspect("Sun", "Moon", "square"),
    aspect("Moon", "Mars", "square"),
    aspect("Mars", "Saturn", "square"),
    aspect("Saturn", "Sun", "square"),
]


def test_grand_cross_detected_with_mode():
    patterns = detect_patterns(GRAND_CROSS_PLANETS, GRAND_CROSS_ASPECTS)
    found = of_type(patterns, "grand_cross")
    assert len(found) == 1
    assert found[0]["mode"] == "Cardinal"
    assert sorted(found[0]["planets"]) == ["Mars", "Moon", "Saturn", "Sun"]
    # The four T-squares embedded in a grand cross are not reported separately.
    assert of_type(patterns, "t_square") == []


def test_no_grand_cross_when_square_missing():
    aspects = GRAND_CROSS_ASPECTS[:-1]
    patterns = detect_patterns(GRAND_CROSS_PLANETS, aspects)
    assert of_type(patterns, "grand_cross") == []
    # With the cross broken, its component T-squares surface normally.
    assert of_type(patterns, "t_square")


# --------------------------------------------------------------------- yods

def test_yod_detected_from_local_quincunxes():
    # Quincunxes are not in kerykeion's single-chart aspects; the module
    # computes them from longitudes (3-degree orb). Sextile comes from aspects.
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
        "Moon": planet("Vir", "Earth", "Mutable", 150.0),
        "Mars": planet("Sco", "Water", "Fixed", 210.0),
    }
    found = of_type(detect_patterns(planets, [aspect("Moon", "Mars", "sextile")]), "yod")
    assert len(found) == 1
    assert found[0]["apex"] == "Sun"
    assert sorted(found[0]["planets"]) == ["Mars", "Moon", "Sun"]


def test_yod_quincunx_boundary_orb():
    def build(moon_pos):
        return {
            "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
            "Moon": planet("Vir", "Earth", "Mutable", moon_pos),
            "Mars": planet("Sco", "Water", "Fixed", 210.0),
        }
    sextile = [aspect("Moon", "Mars", "sextile")]
    assert of_type(detect_patterns(build(153.0), sextile), "yod")  # orb exactly 3
    assert not of_type(detect_patterns(build(153.1), sextile), "yod")


def test_no_yod_without_sextile_between_base_planets():
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
        "Moon": planet("Vir", "Earth", "Mutable", 150.0),
        "Mars": planet("Sco", "Water", "Fixed", 210.0),
    }
    assert of_type(detect_patterns(planets, []), "yod") == []


# -------------------------------------------------------------------- kites

def test_kite_detected_with_tail():
    planets = dict(GRAND_TRINE_PLANETS)
    aspects = GRAND_TRINE_ASPECTS + [aspect("Sun", "Saturn", "opposition")]
    found = of_type(detect_patterns(planets, aspects), "kite")
    assert len(found) == 1
    assert found[0]["tail"] == "Saturn"
    assert sorted(found[0]["planets"]) == ["Jupiter", "Moon", "Saturn", "Sun"]


def test_no_kite_without_opposition_to_trine_vertex():
    assert of_type(detect_patterns(GRAND_TRINE_PLANETS, GRAND_TRINE_ASPECTS), "kite") == []


# ---------------------------------------------------------- element / mode

def test_element_balance_counts_and_missing():
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
        "Moon": planet("Leo", "Fire", "Fixed", 120.0),
        "Mars": planet("Tau", "Earth", "Fixed", 35.0),
    }
    balance = element_balance(planets)
    assert balance["counts"] == {"Fire": 2, "Earth": 1, "Air": 0, "Water": 0}
    assert sorted(balance["missing"]) == ["Air", "Water"]


def test_mode_balance_counts_and_missing():
    planets = {
        "Sun": planet("Ari", "Fire", "Cardinal", 0.0),
        "Moon": planet("Leo", "Fire", "Fixed", 120.0),
        "Mars": planet("Tau", "Earth", "Fixed", 35.0),
    }
    balance = mode_balance(planets)
    assert balance["counts"] == {"Cardinal": 1, "Fixed": 2, "Mutable": 0}
    assert balance["missing"] == ["Mutable"]
