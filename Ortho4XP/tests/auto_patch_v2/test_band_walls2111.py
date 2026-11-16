"""#2111 (KBNA owner sim read 2026-11-16T16:56:54Z): a solid wall standing
in a runway band ends the band — the ground behind it leaves the band
(``planar/band_walls``)."""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.planar.band_walls import wall_cuts  # noqa: E402


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_the_ground_behind_a_wall_leaves_the_band():
    runway = _rect(0.0, -20.0, 1000.0, 20.0)
    band = _rect(-300.0, -150.0, 1300.0, 150.0).difference(runway)
    wall = LineString([(1100.0, -40.0), (1100.0, 40.0)])   # across the end
    (cut,) = wall_cuts([wall], runway, band)
    kept = band.difference(cut)
    # the band keeps the ground between the runway end and the wall ...
    assert kept.contains(_rect(1010.0, -30.0, 1090.0, 30.0))
    # ... and loses what lies behind it, never the runway's side
    assert not kept.intersects(_rect(1110.0, -30.0, 1290.0, 30.0))
    assert kept.contains(_rect(-290.0, -30.0, -10.0, 30.0))


def test_a_wall_outside_the_band_or_on_the_pavement_cuts_nothing():
    runway = _rect(0.0, -20.0, 1000.0, 20.0)
    band = _rect(-300.0, -150.0, 1300.0, 150.0).difference(runway)
    assert wall_cuts([LineString([(2000.0, 0.0), (2000.0, 50.0)])], runway, band) == []
    assert wall_cuts([LineString([(500.0, 20.5), (600.0, 20.5)])], runway, band) == []
