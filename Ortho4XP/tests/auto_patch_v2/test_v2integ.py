"""Post-merge integration twins (lane v2integ, 2026-09-05; report
``docs/specs/auto-patch-v2/m5g-report.md``).

* the verify reader's stretch join covers HOLE-RING vertices — LEMD face
  145 / taxi660: a taxi centreline entering a cross_connector's gap
  interior ring put a stretch endpoint on a vertex no outer ring holds,
  and ``within_shape`` raised ``KeyError`` (the seven-airport re-census of
  2026-09-04, main ``7ddf3f5b``).
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.emit.surface import GradedSurface, SurfaceBreakline, SurfaceFace, SurfaceVertex
from auto_patch_v2.law import Law
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import within_shape

LAT0, LON0 = 40.47, -3.57
R = 6378137.0


def _ll(x: float, y: float) -> tuple[float, float]:
    return (round(LAT0 + math.degrees(y / R), 11),
            round(LON0 + math.degrees(x / (R * math.cos(math.radians(LAT0)))), 11))


@pytest.fixture(scope="module")
def law() -> Law:
    return Law.for_airport("LEMD")


def _holed_connector(z_hole: float) -> tuple[GradedSurface, dict]:
    """A 200 m x 40 m cross_connector (letter F, 1.5 %) with a 10 m gap
    interior ring; a published stretch (letter B, 3 %) runs along the
    connector from the west ring edge to the HOLE's west vertex —
    LEMD's taxi660 entering face 145's gap."""
    pts = {
        0: (0.0, 0.0), 1: (200.0, 0.0), 2: (200.0, 40.0), 3: (0.0, 40.0),
        # the hole (a gap interior ring), ids 10..13
        10: (95.0, 15.0), 11: (105.0, 15.0), 12: (105.0, 25.0), 13: (95.0, 25.0),
        # the stretch's ring endpoint on the west edge
        20: (0.0, 20.0),
    }
    z = {0: 600.0, 1: 600.0, 2: 600.0, 3: 600.0, 20: 600.0,
         10: z_hole, 11: z_hole, 12: z_hole, 13: z_hole}
    verts = tuple(SurfaceVertex(i, _ll(*pts[i]), z[i]) for i in sorted(pts))
    face = SurfaceFace(145, "cross_connector", "pav84", (0, 1, 2, 3, 20),
                       ((10, 11, 12, 13),), "airside", 4, "F")
    bl = SurfaceBreakline(0, "taxi_centerline", "taxi660", (20, 10))
    surf = GradedSurface("LEMD", "icao", (LAT0, LON0), "local", 7, verts, (face,), (bl,), {})
    stretch_ll = [list(_ll(*pts[20])), list(_ll(*pts[10]))]
    pub = {"stretches": [[stretch_ll, 0.03, "B", "taxi660"]], "axes": [], "crown_drops": []}
    return surf, pub


def test_a_stretch_ending_on_a_hole_ring_vertex_prices_without_a_key_error(law):
    """The reader joins stretch vertices through the FRAME's whole vertex
    map (``Patch.xy``), exactly as the generator prices through
    ``pm.vertices`` — a hole-ring vertex on a stretch is a vertex, not a
    ``KeyError`` (LEMD 8521, 2026-09-04)."""
    surf, pub = _holed_connector(z_hole=600.0)
    within, xsec = within_shape(Patch.of(surf, law, pub, {}))
    assert within == [] and xsec == []


def test_the_outer_ring_pairs_are_still_priced_at_the_face_cap_with_the_hole_present(law):
    """A 2 % step across the ring (over F's 1.5 %) still reads as a row
    when the stretch reaches the hole: the join change adds vertices to
    the stretch map, never removes pairs from the ring's population."""
    surf, pub = _holed_connector(z_hole=600.0)
    # lift the north-east ring vertex 2 % over the 200 m length
    verts = tuple(SurfaceVertex(v.id, v.ll, 604.0 if v.id == 2 else v.z) for v in surf.vertices)
    surf2 = GradedSurface(surf.icao, surf.ruleset, surf.origin, surf.crs, surf.identity_dp,
                          verts, surf.faces, surf.breaklines, surf.provenance)
    within, _x = within_shape(Patch.of(surf2, law, pub, {}))
    assert within and all(abs(r["cap_pct"] - 1.5) < 1e-9 for r in within), within[:2]
