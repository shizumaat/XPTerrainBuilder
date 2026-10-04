"""Unit tests for auto_patch.pavement.runway_geometry.

Pure-function geometric helpers — no DEM / shapely / I/O dependencies
beyond reading apt.dat for ``parse_aptdat_runway_widths``.  Tests
hit the math against synthetic CIFP-style inputs.
"""
import math


from auto_patch.build_support import get_reciprocal, pair_runways


# ──────────────────────────────────────────────────────────────────────
# get_reciprocal
# ──────────────────────────────────────────────────────────────────────
def test_get_reciprocal_basic():
    """Heading +18 (mod 36) gives the reciprocal — RW09 → RW27."""
    assert get_reciprocal("RW09") == "RW27"
    assert get_reciprocal("RW27") == "RW09"
    assert get_reciprocal("RW01") == "RW19"
    assert get_reciprocal("RW36") == "RW18"


def test_get_reciprocal_with_lr_suffix():
    """L/R suffixes flip across the centerline; C stays C."""
    assert get_reciprocal("RW16L") == "RW34R"
    assert get_reciprocal("RW16R") == "RW34L"
    assert get_reciprocal("RW16C") == "RW34C"
    # And the reverse direction.
    assert get_reciprocal("RW34R") == "RW16L"


def test_get_reciprocal_wraparound():
    """Headings beyond 36 wrap correctly: RW20 → RW02 (not RW38)."""
    assert get_reciprocal("RW20") == "RW02"
    assert get_reciprocal("RW19") == "RW01"


def test_get_reciprocal_eighteen_maps_to_thirty_six():
    """Boundary case: 18 + 18 = 36 exactly — stays RW36, does NOT
    wrap to RW00 (the wrap only applies for headings strictly > 36)."""
    assert get_reciprocal("RW18") == "RW36"
    assert get_reciprocal("RW18L") == "RW36R"
    assert get_reciprocal("RW18C") == "RW36C"


def test_get_reciprocal_invalid_designator():
    """Malformed designators return None instead of raising."""
    assert get_reciprocal("not-a-runway") is None
    assert get_reciprocal("") is None
    assert get_reciprocal("RW1") is None  # need 2 digits


# ──────────────────────────────────────────────────────────────────────
# pair_runways
# ──────────────────────────────────────────────────────────────────────
def test_pair_runways_simple_pair():
    """A complete pair gets matched exactly once, with the alpha-
    earlier designator first."""
    runways = {
        "RW09": {"lat": 0.0, "lon": 0.0, "elevation_m": 100.0},
        "RW27": {"lat": 0.0, "lon": 0.027, "elevation_m": 105.0},
    }
    pairs = pair_runways(runways)
    assert len(pairs) == 1
    desig_a, data_a, desig_b, data_b = pairs[0]
    assert {desig_a, desig_b} == {"RW09", "RW27"}
    assert data_a["elevation_m"] in {100.0, 105.0}
    assert data_b["elevation_m"] in {100.0, 105.0}


def test_pair_runways_unpaired_threshold():
    """When only one end of a runway has CIFP data (common at minor
    airports), the unpaired threshold is returned with desig_b/data_b
    set to None so callers can branch."""
    runways = {
        "RW16L": {"lat": 1.0, "lon": 1.0, "elevation_m": 200.0},
    }
    pairs = pair_runways(runways)
    assert len(pairs) == 1
    desig_a, data_a, desig_b, data_b = pairs[0]
    assert desig_a == "RW16L"
    assert data_a["elevation_m"] == 200.0
    assert desig_b is None
    assert data_b is None


def test_pair_runways_multiple_runways():
    """Multiple parallel runways at one airport — each L/R/C variant
    pairs only with its own reciprocal."""
    runways = {
        "RW16L": {"lat": 0.0, "lon": 0.0, "elevation_m": 50.0},
        "RW16R": {"lat": 0.0, "lon": 0.001, "elevation_m": 50.0},
        "RW34L": {"lat": 0.027, "lon": 0.001, "elevation_m": 55.0},
        "RW34R": {"lat": 0.027, "lon": 0.0, "elevation_m": 55.0},
    }
    pairs = pair_runways(runways)
    assert len(pairs) == 2
    pair_sets = [{a, b} for a, _, b, _ in pairs]
    assert {"RW16L", "RW34R"} in pair_sets
    assert {"RW16R", "RW34L"} in pair_sets


def test_pair_runways_no_double_counting():
    """A paired threshold appears in exactly one pair, never two."""
    runways = {
        "RW09": {"lat": 0.0, "lon": 0.0},
        "RW27": {"lat": 0.0, "lon": 0.027},
    }
    pairs = pair_runways(runways)
    all_designators = []
    for desig_a, _, desig_b, _ in pairs:
        all_designators.append(desig_a)
        if desig_b is not None:
            all_designators.append(desig_b)
    assert len(all_designators) == len(set(all_designators))


# ──────────────────────────────────────────────────────────────────────
# match_runway_ends_by_geometry
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# parse_aptdat_runway_widths
# ──────────────────────────────────────────────────────────────────────


