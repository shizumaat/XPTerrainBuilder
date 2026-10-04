"""Round 20 — the tunnel ramp follows the road and reaches grade.

Two laws, both in ``auto_patch.bridges``:

R20-1 CURVATURE SURVIVES THE WALK.  The surface walk's plan filter was a
15 m SPACING merge — it deleted a vertex for being close to its
neighbour, whatever the road did there (measured at KCLT: OSM node
-75937 deleted, 1.86 m off the chord left behind).  It is now a
DEVIATION filter (``bridges._deviation_filter``), so the retained chain
is within ``_TUNNEL_WALK_DEVIATION_TOL_M`` of EVERY input vertex, and the
rounding-safe segment floor the spacing merge was really buying is
DERIVED from the emitted altitude grid instead of guessed.

R20-2 THE RUN REACHES GRADE.  The run was sized on a PORTAL-LOCAL
ambient at ``TUNNEL_APPROACH_GRADE`` (5 %) while the chain is emitted at
``plan_grade`` (3.5 %), so where the road climbed away from the mouth the
ramp stopped buried (KCLT: 4.26 m below the DEM beside it).  The run now
extends while ``dem_along_walk(s) - elev_low > emit_grade * s`` and ends
where the ramp meets the ground — never SHORTER than R14's minimum
lawful run, and never a declared minimum of its own.

Everything here is headless and synthetic: the road-layer loader and the
DEM sampler are monkeypatched (the fixture idiom of
``tests/test_tunnel_dem_cut_portals.py``), nothing is written, no network
and no X-Plane install are touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import config  # noqa: E402


# ══════════════════════════════════════════════════════════════════
# R20-2 — the run reaches grade
# ══════════════════════════════════════════════════════════════════
ANCHOR_LATITUDE = 35.213
ANCHOR_LONGITUDE = -80.942
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
TILE_LATITUDE = 35
TILE_LONGITUDE = -81

# TWO SURFACES, AS IN PRODUCTION.  ``apt_elev`` comes from the boundary
# ribbon (CIFP-anchored, grade-clamped); the deck reference the bore
# floor is measured from comes from the DEM beside the road.  They are
# different quantities and the scene keeps them apart, seated so the
# gatherer's clearance floor (deck − BRIDGE_ROAD_CLEARANCE_M) and the
# cluster's emit floor (apt_elev − tunnel_depth_m) COINCIDE — which is
# what the owner's KCLT portal measures (206.34 vs 206.36) and what the
# round's reach claim rests on.  Where a field's two floors diverge the
# ramp cannot meet ground however the run is sized; that split is a
# separate defect, deliberately not papered over here.
TUNNEL_DEPTH_DEFAULT_M = 8.0
GROUND_M = 211.4
RIBBON_SURFACE_M = GROUND_M + (
    TUNNEL_DEPTH_DEFAULT_M - float(config.BRIDGE_ROAD_CLEARANCE_M))
EMIT_FLOOR_M = RIBBON_SURFACE_M - TUNNEL_DEPTH_DEFAULT_M
BORE_DEPTH_M = GROUND_M - EMIT_FLOOR_M


def test_scene_seats_the_two_floors_on_one_value() -> None:
    """The scene's premise, asserted rather than assumed."""
    assert EMIT_FLOOR_M == pytest.approx(
        GROUND_M - float(config.BRIDGE_ROAD_CLEARANCE_M))
    assert BORE_DEPTH_M == pytest.approx(
        float(config.BRIDGE_ROAD_CLEARANCE_M))


