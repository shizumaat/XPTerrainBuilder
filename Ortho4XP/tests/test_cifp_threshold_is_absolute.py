"""CIFP THRESHOLD ELEVATIONS ARE ABSOLUTE — the generation-binding twin.

Owner ruling ``docs/RULINGS.md`` 2026-08-05 (commit 739de5c): for v1
thresholds stay AT their published CIFP values.

WHAT THIS REPLACES.  ``runway_segments.generate_patch_osm`` carried a
DEM-CREDIBILITY THRESHOLD LIFT: it sampled the DEM in a 75 m radius
around every CIFP threshold, took the mean ``dem − cifp`` over the ones
whose difference was under 10 m, and — when that mean came out positive —
ADDED it to ``elevation_m`` on EVERY threshold, mutating the dict in
place before a single consumer read it.

WHY IT IS A DEFECT AND NOT A FEATURE.  Every downstream anchor is
derived from ``elevation_m``: the cross-runway anchors, the
centreline-crossing reconciliation, the per-segment elevation seeds, and
— the one that reaches furthest — the reach band's own anchor values,
which is to say the ANCHOR ENVELOPE that now triggers the apron terrace
law (RULINGS 4cbed92).  A lift keyed on DEM warmth therefore moved the
whole airport's datum, and with it the terrace demand, as a function of
which rasters happened to be cached.  Same class as the DEM-steepness
trigger the same campaign deleted: a law keyed on the wrong quantity.

The twin is GENERATION-BINDING, not a source grep: it drives the real
emitter with a DEM sitting far above the published thresholds — the exact
configuration that used to fire the lift — and asserts the published
values come back untouched.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.pavement import runway_segments as RS


class _FlatDEM:
    """A DEM that answers one constant elevation everywhere."""

    def __init__(self, value):
        self.value = value

    def alt(self, _lonlat):
        return self.value


class _Tile:
    def __init__(self, lat, lon, dem):
        self.lat = lat
        self.lon = lon
        self.dem = dem


# One paired runway, thresholds ~1 800 m apart on a common heading, with
# published CIFP elevations well BELOW the DEM the tile answers.
_LAT, _LON = 30.11, 31.40
_CIFP_A_M = 100.0
_CIFP_B_M = 104.0
# +7 m of "credible" DEM rise at both ends: inside the retired law's
# 10 m credibility window and positive, so the mean offset it computed
# was +7.0 and it lifted BOTH thresholds by that much.
_DEM_M = 111.0


def _pair():
    return [(
        "RW05", {"lat": _LAT, "lon": _LON, "elevation_m": _CIFP_A_M,
                 "displaced_m": 0.0},
        "RW23", {"lat": _LAT + 0.0116, "lon": _LON + 0.0116,
                 "elevation_m": _CIFP_B_M, "displaced_m": 0.0},
    )]


def test_a_dem_above_the_field_never_lifts_a_published_threshold():
    """The configuration the retired lift existed for: a field sitting
    7 m below the surrounding terrain.  v1 keeps CIFP."""
    pairs = _pair()
    tile = _Tile(30.0, 31.0, _FlatDEM(_DEM_M))
    RS.generate_patch_osm("TEST", pairs, tile=tile)
    assert pairs[0][1]["elevation_m"] == pytest.approx(_CIFP_A_M)
    assert pairs[0][3]["elevation_m"] == pytest.approx(_CIFP_B_M)


def test_the_inter_threshold_difference_is_the_published_one():
    """The lift preserved differences by construction; what it did NOT
    preserve is the DATUM, and the datum is what every anchor is read
    against.  Both are asserted so a future 'uniform' variant cannot
    slip back in by keeping grades intact."""
    pairs = _pair()
    tile = _Tile(30.0, 31.0, _FlatDEM(_DEM_M))
    RS.generate_patch_osm("TEST", pairs, tile=tile)
    a = pairs[0][1]["elevation_m"]
    b = pairs[0][3]["elevation_m"]
    assert (b - a) == pytest.approx(_CIFP_B_M - _CIFP_A_M)
    assert a == pytest.approx(_CIFP_A_M), (
        "the published datum moved — a threshold lift is back")


def test_a_dem_below_the_field_is_equally_inert():
    """The retired law only lifted on a POSITIVE mean, so a low DEM was
    already inert; asserted so the two directions are one rule."""
    pairs = _pair()
    tile = _Tile(30.0, 31.0, _FlatDEM(_CIFP_A_M - 25.0))
    RS.generate_patch_osm("TEST", pairs, tile=tile)
    assert pairs[0][1]["elevation_m"] == pytest.approx(_CIFP_A_M)
    assert pairs[0][3]["elevation_m"] == pytest.approx(_CIFP_B_M)


def test_the_lift_machinery_is_gone_not_merely_unreached():
    """Dead-but-present code is a trap the next reader walks into: the
    helper and both constants leave with the law."""
    import inspect
    src = inspect.getsource(RS.generate_patch_osm)
    for token in ("_credible_diffs", "_threshold_dem_elev",
                  "THRESHOLD_DEM_MAX_RISE_M", "THRESHOLD_DEM_RADIUS_M"):
        assert f"{token} =" not in src and f"def {token}" not in src, (
            f"{token} survived the deletion")
