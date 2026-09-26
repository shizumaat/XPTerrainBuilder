"""Lane ``tunnelwitness`` twins — issues #5 [SPJC-3], #12 [OTHH-1],
#16 [OTHH-5].

#5: the SPJC bore (OSM way -5724, ``highway=secondary lanes=3
tunnel=yes``, 35.2 m, inside the airport boundary 728 m from its edge)
passes under NOTHING: no classified cell within 147.8 m, the nearest pack
OBJ footprint (``Costa del sol_001``) 63.2 m away, the only pack DSF
polygons within 40 m are shrub-planter forests covering 0.0 m of it, no
pack road segment within 40 m, and the DEM falls monotonically 21.97 ->
21.44 m along it (rise +0.27 m over its own ends is the chord sag, not a
hill).  §34 (12) (5) (c) refuses it and NO witness is invented — the
question is the owner's (Q-5 on the issue).  These twins pin the refusal
as the law stands, so an answer to Q-5 moves a known number.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.airport import deck_signature as ds
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Boundary, OsmWay, Runway,
                                         RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structures import build_structures


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── deck_signature.way_cover: a plate whose rectangle entered as nothing ──

def _plate(rect):
    return ds.DeckPlate("dsf:obj1", "x.obj", Polygon([(0, 0), (1, 0), (1, 1)]),
                        rect, ((0.0, 0.0), (1.0, 0.0)),
                        (((0.0, 0.0), (0.0, 1.0)), ((10.0, 0.0), (10.0, 1.0))),
                        10.0, 1.0, 10.0, 5.0, 5.0, 5.0, (), ())


def test_way_cover_reads_a_None_rect_as_no_cover():
    """§51 Law A: ``frame_entry.enter`` hands back ``None`` for a plate
    rectangle it could not repair.  MEASURED SPJC 2026-09-21: the dry
    ``--stage structures`` replay died in ``way_cover`` on
    ``None.is_empty``.  A plate with no rectangle runs along no way.
    (Lane ``spjcpads`` guards the same None one step upstream, in
    ``_plate``; both guards stand — this one is the reader's.)"""
    ln = LineString([(-5.0, 0.5), (15.0, 0.5)])
    assert ds.way_cover(_plate(None), ln) == 0.0
    rect = Polygon([(0, 0), (10, 0), (10, 1), (0, 1)])
    assert ds.way_cover(_plate(rect), ln) == pytest.approx(1.0)


# ── #5: an OSM bore inside the fence under nothing at grade ─────────────

class _FallDem:
    """SPJC's DEM along -5724: a plane falling 0.53 m over 35 m."""
    provenance = {"source": "fixture"}

    def z(self, x, y):
        return 21.97 - 0.015 * (x - 300.0)

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _run(law, extra_cells=()):
    frame = Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11)
    ends = (RunwayEnd("16", (0.0, 600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"),
            RunwayEnd("34", (0.0, -600.0), (0, 0), 0.0, 0.0, 22.0, "fixture"))
    rw = Runway("16/34", 45.0, 1, ends, 4, "E")
    bore = OsmWay(-5724, "big_roads", ((300.0, -100.0), (335.0, -100.0)), False,
                  {"highway": "secondary", "lanes": "3", "tunnel": "yes"})
    fence = Boundary("boundary0", _rect(-800, -800, 800, 800), ())
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 22.0, (rw,), (), (), {}, (),
                      (), (fence,), (), (bore,), (), (), pack, _FallDem(),
                      law.ruleset_key)
    cells = [Cell(0, "runway", "16/34", _rect(-22, -600, 22, 600), (), 4, "E",
                  "airside", "runway", {}),
             # the nearest classified cell stands off the bore, as SPJC's
             # building5 does (147.8 m there; the mouth gate still admits)
             Cell(1, "apron", "pav49", _rect(360, -140, 460, -60), (), None, None,
                  "airside", "apron", {})]
    cells += list(extra_cells)
    return build_structures(airport, Classification(tuple(cells), (), {}, ()), law)


def test_SPJC_bore_inside_the_fence_under_nothing_is_REFUSED_pending_Q5(law):
    """#5 as the law stands: the fence is not a witness (§34 (12) (5) (c)
    names cover, a road or railway at grade, the ground, or ``layer``);
    the refusal is named with its evidence.  Q-5 asks the owner whether
    an OSM ``tunnel=yes`` tag alone is trusted inside the fence."""
    _cl, tunnels, st = _run(law)
    assert st.bores == 1
    assert st.tunnels == 0 and not tunnels
    named = [ln for ln in st.mouths_off_field_nearest if "NOT A TERRAIN TUNNEL" in ln]
    assert len(named) == 1, st.mouths_off_field_nearest
    assert "-5724 PASSES UNDER NOTHING AT GRADE" in named[0]


def test_the_same_bore_under_a_pack_PAD_is_built(law):
    """The witness the brief proposed ALREADY EXISTS: a pack object's
    footprint over the bore is classified as a pad / unit footprint and
    the classified cover counts (§34 (12) (5) (c) first witness).  So a
    pack-covered SPJC bore would be built with no code change — the gap
    at SPJC is that nothing covers it."""
    pad = Cell(2, "building", "building_hotel", _rect(310, -115, 328, -85), (), None,
               None, "groundside", "building", {})
    _cl, tunnels, st = _run(law, (pad,))
    assert st.tunnels == 1, st.mouths_off_field_nearest


# ── #16 [OTHH-5]: the walled cap corner is the MITRE ─────────────────────

def test_the_walled_cap_corner_stands_off_BOTH_faces():
    """OTHH ``Terminal_Base_2_1@4`` (25.2639569, 51.6126961): the bay's
    closed-end rim corner stood ``off`` along the DIAGONAL, so the rim
    chord from the side rim's end passed 0.65 m from the floor corner at
    the 0.7071 m lattice floor and the arrangement fused the rim onto
    the floor corner — the pad took the floor's 2.61 m and carried the
    whole rim below the 3.96 m ground.  The corner is the mitre of the
    two outer faces: ``off`` beyond the end edge AND the side stand-off
    beyond the side edge, so every rim chord keeps its stand-off."""
    from shapely.geometry import LineString, Point, Polygon
    from auto_patch_v2.planar.structure_geometry import _geometry_at
    off = 0.7071

    def axis_fn(s):
        return (s, 0.0)
    g = _geometry_at(axis_fn, [0.0, 2.0, 4.0, 6.3], 4.93, off, (-1.0, 0.0), 0.5,
                     True, False, half_fn=lambda s: (4.93, 4.93),
                     rim_fn=lambda s: (off, off), cap_off=off)
    assert g is not None
    floor = g.ramp
    # every rim CHORD round the closed end keeps the stand-off from the
    # floor, the corners included (it read 0.65 m before the mitre)
    h = 4.93 + off
    rim = [(0.0, h), *g.cap_out, (0.0, -h)]
    worst = min(LineString([a, b]).distance(floor) for a, b in zip(rim[:-1], rim[1:]))
    assert worst >= off - 1e-6, (worst, rim)
    # the closed-end corners sit at the mitre (-off, ±(4.93 + off))
    for c in (g.cap_out[0], g.cap_out[2]):
        assert abs(c[0] + off) < 1e-9 and abs(abs(c[1]) - (4.93 + off)) < 1e-9, c
