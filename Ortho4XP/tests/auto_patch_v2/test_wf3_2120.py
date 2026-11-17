"""Twin of 2120-WF3 (``sim-review/2120-WF3.md`` §4): a plate-capped sunk
block's plan read part by part (W-A), a mapped way split at the retaining
pieces (W-B), a road leaving a seeded frame's level running out from it
(F6), a portal in a cut seated by its cover slab on the pavement it carries
(P1).  Synthetic: no airport, no pack."""
from __future__ import annotations

import types
from types import SimpleNamespace as NS

import numpy as np
import pytest
from shapely.geometry import LineString, box

from tests.auto_patch_v2.test_sunk_frame2120 import CFG, _airport, _retaining
from tests.auto_patch_v2.test_wall_class_thick import FRAME, _StepDem

_M_LAT = 1.0 / 111_320.0
LAT0 = 33.64


def _half_low(low_m: float = 15.0):
    """A 40 x 100 m block sunk 19.81 m (R2), capped by its road plate at
    y 20, the ground LOW (290) under its southern ``low_m`` and HIGH (300)
    under the rest and north of it."""
    ap = _airport(-19.81, 20.0, 10.0, width=40.0, plate=True, road={"highway": "service"})
    _x, y_step = FRAME.entry()(-84.42, LAT0 + low_m * _M_LAT)
    ap.dem = _StepDem(y_step, 300.0, 290.0)
    return ap, y_step


def test_wa_a_plate_capped_block_over_half_low_ground_is_piece_and_cover():
    """W-A: the part of the plan on the upper level (and the strip along the
    upper face) is the retaining piece; the part over the low ground is its
    cover -- in the shade, no fill; its fill rides its plate's face (F1)"""
    from auto_patch_v2.airport.wall_shade import wall_shade
    ap, y_step = _half_low()
    (c,) = _retaining(ap)
    assert c.sunk_rule == "upper" and c.fill_drop_m == pytest.approx(1.0)
    (piece,), (cover,) = c.pieces, c.cover
    assert piece.area == pytest.approx(25.0 * 100.0, abs=210.0)     # one 2 m station
    assert cover.area == pytest.approx(15.0 * 100.0, abs=210.0)
    assert cover.bounds[3] == pytest.approx(y_step, abs=2.1)      # the low part, south
    assert wall_shade(ap, CFG).covers(cover.buffer(-0.01))


def test_wa_a_road_under_the_cover_is_not_cut():
    from auto_patch_v2.airport.wall_sides import far_side_cut, wall_sides
    ap, y_step = _half_low()
    (c,) = _retaining(ap)
    (w,) = wall_sides(ap, CFG, [c])
    x0, y0, x1, _y1 = c.cover[0].bounds
    road = box(x0 + 20.0, y0 - 10.0, x1 - 20.0, y0 + 8.0)          # into the cover only
    assert far_side_cut(road, [w]).area == pytest.approx(road.area)


def test_wa_a_low_strip_narrower_than_the_smear_stays_fill():
    """the survey's bank along the low face (narrower than the smear) joins
    the piece: no cover, the whole plan retains as before"""
    ap, _y = _half_low(low_m=4.0)
    (c,) = _retaining(ap)
    assert not c.cover and c.fill_drop_m == pytest.approx(1.0)


def test_wb_a_way_mapped_into_a_piece_is_two_parts_ending_on_its_faces():
    """W-B: the way loses its run inside the piece (one helper for the cut
    lines and the mapped ways), and a station on the piece's face reads the
    ground a smear out on that face's side"""
    from auto_patch_v2.airport.wall_sides import smear_sampler, split_at_walls, wall_sides
    ap = _airport(-19.81, 20.0, 10.0)
    (c,) = _retaining(ap)
    (w,) = wall_sides(ap, CFG, [c])
    x0, y0, x1, y1 = w.poly.bounds
    xm = 0.5 * (x0 + x1)
    parts, dropped = split_at_walls([(xm, y0 - 30.0), (xm, y1 + 30.0)], [w.poly])
    assert len(parts) == 2 and dropped == pytest.approx(y1 - y0, abs=0.01)
    assert parts[0][-1][1] == pytest.approx(y0, abs=0.01)
    assert parts[1][0][1] == pytest.approx(y1, abs=0.01)
    assert split_at_walls([(x0 - 50.0, y0 - 30.0), (x1 + 50.0, y0 - 30.0)], [w.poly]) is None
    # a station ON the low face reads the low ground smear out, never the bank
    ap.dem = _StepDem(y0 + 0.5, 300.0, 290.0)                     # the bank right at the face
    sample = smear_sampler(ap.dem.z_many, [w])
    lo = w.lower_face.interpolate(0.5 * w.lower_face.length)
    up = w.upper_face.interpolate(0.5 * w.upper_face.length)
    assert float(sample([lo.x], [lo.y])[0]) == pytest.approx(290.0)
    assert float(sample([up.x], [up.y])[0]) == pytest.approx(300.0)


def test_wb_the_cut_lines_keep_their_split():
    import dataclasses as dc

    from auto_patch_v2.airport.wall_sides import wall_sides
    from auto_patch_v2.classify.wall_cutback import cut_lines_at_walls

    @dc.dataclass(frozen=True)
    class Cut:
        kind: str
        points: tuple
    ap = _airport(-19.81, 20.0, 10.0)
    (c,) = _retaining(ap)
    (w,) = wall_sides(ap, CFG, [c])
    x0, y0, x1, y1 = w.poly.bounds
    xm = 0.5 * (x0 + x1)
    got, st = cut_lines_at_walls([Cut("road_centerline", ((xm, y0 - 30.0), (xm, y1 + 30.0))),
                                  Cut("taxi_centerline", ((xm, y0 - 30.0), (xm, y1 + 30.0)))],
                                 [w])
    assert len(got) == 3 and st["wall_cut_lines"] == 1
    assert st["wall_cut_line_m"] == pytest.approx(y1 - y0, abs=0.1)


# ── F6: a road leaving a seeded frame's level runs out from it ────────────

def test_f6_a_road_leaving_a_frame_level_runs_out_from_its_edge(tmp_path):
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar.low_extent import _frame_runouts
    from auto_patch_v2.planar.overlay import Region
    from test_two_pads1214 import _airport as _pads_airport
    law = Law.for_airport("ZZZZ")
    L = box(500.0, 10.0, 540.0, 60.0)               # the level at 26 (D 30, y -4)

    def ground(x, y):
        return 26.0 if x < 545.0 else 26.0 + min(3.0, 0.1 * (x - 545.0))
    A = _pads_airport([], tmp_path, ground=ground)
    A.osm_ways = [types.SimpleNamespace(id=-1, points=[(505.0, 35.0), (640.0, 35.0)],
                                        tags={"highway": "service"})]
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    reg = Registries()
    reg.held["blk"] = {"unit": "blk", "datum_pred": 30.0}

    def region(ref, g):
        return Region(role="building", ref=ref, polygon=g, code_number=None,
                      code_letter=None, side="airside", source="cell")
    riser = box(500.0, 60.0, 540.0, 63.0)            # the riser along its north edge
    regs = [region("blk/p2", L), region("blk/p2#strip", riser)]
    counts: dict = {}
    _frame_runouts(regs, reg, {"blk/p2": (L, "blk", -4.0)}, box(400.0, 100.0, 500.0, 130.0),
                   [], A, law, 0.5, counts)
    (rec,) = [v for v in reg.landing_runouts.values() if v.get("kind") == "level_end"]
    assert rec["from_level"] and rec["sign"] < 0 and rec["landing"] == "blk/p2"
    assert rec["lip"][0] == pytest.approx(540.0, abs=0.01)        # it leaves the level's edge
    assert min(q.bounds[0] for q in rec["polys"]) == pytest.approx(540.0, abs=0.51)
    assert counts["frame_level_runouts"] == 1
    # a road leaving across the riser asks nothing
    reg2 = Registries()
    reg2.held["blk"] = {"unit": "blk", "datum_pred": 30.0}
    A.osm_ways = [types.SimpleNamespace(id=-2, points=[(520.0, 35.0), (520.0, 140.0)],
                                        tags={"highway": "service"})]
    _frame_runouts(regs, reg2, {"blk/p2": (L, "blk", -4.0)}, box(400.0, 300.0, 500.0, 330.0),
                   [], A, law, 0.5, {})
    assert not reg2.landing_runouts


# ── P1: the portal's datum is its cover slab on the pavement ──────────────

def test_p1_the_portal_seats_its_slab_on_the_pavement_stations():
    from auto_patch_v2.airport import cut_portal_seat as CPS
    plan = box(0.0, 0.0, 40.0, 30.0)
    st = tuple((float(x), 31.0) for x in range(0, 40, 2)) + \
        tuple((float(x), -1.0) for x in range(0, 40, 2))
    paved = [box(-5.0, 30.5, 45.0, 60.0)]                     # the taxiway over the north side
    got = CPS._on_pavement(st, paved)
    assert len(got) == 20 and all(y == 31.0 for _x, y in got)
    assert CPS._on_pavement(st, [box(0.0, 30.5, 1.0, 60.0)]) == st   # too few: today's set
    assert len(CPS._on_pavement(st, [box(-1.0, 30.5, 7.0, 60.0)])) == 4  # a tenth of them
    assert CPS._on_pavement(st, None) == st

    class _Cache:
        pass
    portal = NS(plan=plan, top_y=20.0)
    import auto_patch_v2.airport.deck_signature as DS
    orig = DS.dominant_plate
    try:
        DS.dominant_plate = lambda cache, path, law, hard_only=True: (19.5, 900.0)
        assert CPS._slab_y(portal, "x.obj", _Cache(), object()) == 19.5
        DS.dominant_plate = lambda cache, path, law, hard_only=True: (19.5, 500.0)
        assert CPS._slab_y(portal, "x.obj", _Cache(), object()) is None   # under half the plan
        DS.dominant_plate = lambda cache, path, law, hard_only=True: (20.5, 1200.0)
        assert CPS._slab_y(portal, "x.obj", _Cache(), object()) is None   # over its top
    finally:
        DS.dominant_plate = orig
    assert CPS._slab_y(portal, None, None, None) is None


# ── S1: a lead plate leads its own frame, riders too, never another ───────

def test_s1_every_member_of_a_cut_bridge_frame_rides_its_plate_out_of_every_unit(monkeypatch):
    from auto_patch_v2.airport import cut_bridge as CB
    from auto_patch_v2.airport.cut_portal_seat import CUT_BRIDGE_PLATE
    from auto_patch_v2.airport.open_frame_seat import UNIT_FREE_PLATES, plate_led
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline import rebake_inputs as RI
    rec = NS(plated=("dsf:obj1",), members=("dsf:obj1", "dsf:obj2"), top_y=19.32,
             stations=((0.0, 0.0),), portal="dsf:obj9", resource="objects/deck.obj")
    monkeypatch.setattr(CB, "cut_bridges", lambda *a, **k: (rec,))
    got = RI._cut_bridge_plates(Law.for_airport("ZZZZ"), NS(icao="ZZZZ"), (), (), set())
    assert set(got) == {"dsf:obj1", "dsf:obj2"}                  # the rider too
    assert all(v[3] == CUT_BRIDGE_PLATE for v in got.values())
    assert CUT_BRIDGE_PLATE in UNIT_FREE_PLATES                  # out of every §16g unit
    assert plate_led(NS(plate_kind=CUT_BRIDGE_PLATE))
