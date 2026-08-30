"""THE WIDTH TEST BESIDE THE AREA TEST — HECA round 6 item 5.

Spec ``docs/specs/heca-round6-groundside-classification-spec.md``
(Family A, item 5) and ``heca-round6b-rework-spec.md`` item 5.  The
owner's law: "a severed groundside piece thinner than a service-road
width along an airside edge is not a groundside surface — it merges into
the adjacent airside grading (the adjacent-ground band), never a
separate shape."

MEASURED SITE (owner patch 1.50.1713).  ShapeID 3151 (way -13146) came
out of the scorer-v2 class-change cut as 108 sliver pieces totalling
1,424 m²; the fixture ribbon at 30.1157630,31.4116825 is 332 m² with
480.9 m of airside frontage — a mean width of 0.69 m, a ribbon between
the taxiway and the gap_interior_ring that can carry nothing and mints
bumps.  The AREA floor alone (``_GROUNDSIDE_MIN_AREA_M2`` = 5 m²) keeps
every one of them.

The twins below are single-variable pairs on ``_is_airside_frontage_
sliver`` — the predicate the drop test in
``_separate_groundside_from_airside`` consults — plus the end-to-end
pin through the separation pass itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ``pipeline`` first: junction_repair <-> elevation is an import cycle.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import config as C  # noqa: E402
from auto_patch.layout import SHARED_VERTEX_TOL_M  # noqa: E402
from auto_patch import groundside as G  # noqa: E402


def _ribbon(width_m: float, length_m: float = 480.9):
    """A ribbon lying along the airside clip, its long side inside the
    frontage tolerance — the shape of the owner's 108 pieces."""
    y0 = 10.0 + SHARED_VERTEX_TOL_M          # just off the clip edge
    return box(0.0, y0, length_m, y0 + width_m)


CLIP = box(0.0, 0.0, 600.0, 10.0)              # the airside pavement


def test_the_threshold_is_half_a_service_road_width_from_config():
    """The law's number has ONE source: a value spelled here instead
    would be a second copy of a standards constant (the config.py
    rule)."""
    assert G._SLIVER_MAX_MEAN_WIDTH_M == 0.5 * C.SERVICE_ROAD_WIDTH_M


def test_the_owner_ribbon_is_a_sliver():
    """The measured fixture, to scale: 0.69 m mean width over its
    airside frontage."""
    part = _ribbon(0.69)
    assert G._is_airside_frontage_sliver(part, CLIP) is True


def test_a_piece_wider_than_the_threshold_survives():
    """The single variable is the WIDTH.  Same frontage, same clip: a
    piece that could carry half a service road is a surface and stays."""
    part = _ribbon(0.5 * C.SERVICE_ROAD_WIDTH_M + 1.0)
    assert G._is_airside_frontage_sliver(part, CLIP) is False


def test_a_piece_with_no_airside_frontage_is_never_a_frontage_sliver():
    """The law is about the ground BESIDE airside pavement.  A thin
    piece far from any airside edge is governed by the area floor
    alone, exactly as before — the test must not become a general
    thinness cull of the airport's groundside."""
    far = box(0.0, 300.0, 480.9, 300.69)       # same ribbon, no frontage
    assert G._is_airside_frontage_sliver(far, CLIP) is False


def test_the_separation_drops_the_sliver_and_keeps_the_lot():
    """END TO END through the pass that owns the drop test: a
    groundside ring overlapping airside is cut back, and of the two
    surviving pieces the RIBBON along the frontage is dropped while the
    body of the lot survives."""
    from auto_patch.layout import (BuiltShape, PavementLayout,
                                   ROLE_APRON, ROLE_GROUNDSIDE_PAVEMENT)

    apron = BuiltShape(polygon=CLIP, role=ROLE_APRON,
                       node_altitudes=[100.0] * 5)
    # A lot spanning the apron edge: what survives the clearance clip is
    # a wide body BELOW the apron plus a hairline ribbon ABOVE it.
    lot_poly = box(0.0, -60.0, 480.9, 10.0 + 1.0 + 0.69)
    lot = BuiltShape(polygon=lot_poly, role=ROLE_GROUNDSIDE_PAVEMENT,
                     ref="groundside", node_altitudes=[97.0] * 5)
    layout = PavementLayout(icao="TEST", anchor=(30.0, 31.0),
                            shapes=[apron, lot])

    from auto_patch.constant_dem import ConstantDEM
    dem = ConstantDEM(97.0, lat=30, lon=31)

    n = G._separate_groundside_from_airside(layout, dem, 30, 31)
    assert n == 1
    lots = [s for s in layout.shapes
            if s.role == ROLE_GROUNDSIDE_PAVEMENT]
    assert lots, "the lot BODY must survive — this is not an area cull"
    for s in lots:
        minx, miny, maxx, maxy = s.polygon.bounds
        assert miny < 0.0, ("the frontage ribbon above the apron was "
                            "kept as its own groundside surface")
